"""Mobile-friendly TUI for LumifyDev. Single-keypress navigation, no typing required."""

import os
import sys
import tty
import termios

from .api import api, APIError
from .config import require_config
from .display import C_BOLD, C_DIM, C_RED, C_GREEN, C_YELLOW, C_CYAN, C_RESET
from .remote import (
    build_prompt,
    get_session_info_from_card,
    launch_remote_session,
    ssh_run,
)

# Mobile-friendly colors (matching mobile-dev patterns)
C_MAGENTA = "\033[35m"


def read_char():
    """Read a single keypress without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def clear_screen():
    """Clear terminal and show header."""
    os.system("clear")
    print(f"{C_BOLD}LumifyDev{C_RESET}  {C_DIM}kanban → claude code{C_RESET}")
    print(f"{C_DIM}{'─' * 40}{C_RESET}")
    print()


def wait_for_key():
    """Show 'press any key' and wait."""
    print()
    print(f"{C_DIM}Press any key...{C_RESET}")
    read_char()


def run_tui(_args=None):
    """Main TUI entry point — interactive menu loop."""
    config = require_config()

    while True:
        try:
            result = main_menu(config)
            if result is None:
                return
        except KeyboardInterrupt:
            return


def main_menu(config):
    """Top-level menu: Boards, Latest Cards, Oldest Cards."""
    clear_screen()
    print(f"{C_BOLD}{C_YELLOW}Main Menu{C_RESET}")
    print()
    print(f"  {C_BOLD}{C_CYAN}1{C_RESET}) Boards")
    print(f"  {C_BOLD}{C_CYAN}2{C_RESET}) Latest Cards")
    print(f"  {C_BOLD}{C_CYAN}3{C_RESET}) Oldest Cards")
    print()
    print(f"  {C_DIM}q) Quit{C_RESET}")
    print()
    print(f"{C_BOLD}Select: {C_RESET}", end="", flush=True)

    ch = read_char()
    print(ch)

    if ch in ("q", "Q", "\x03"):
        return None

    if ch == "1":
        board = boards_menu(config)
        if board is None:
            return "continue"
        while True:
            card = cards_menu(config, board)
            if card is None:
                break
            action_result = card_action_menu(config, card)
            if action_result == "back_to_boards":
                break
        return "continue"

    if ch == "2":
        card = cross_board_cards_menu(config, sort="newest")
        if card is not None:
            card_action_menu(config, card)
        return "continue"

    if ch == "3":
        card = cross_board_cards_menu(config, sort="oldest")
        if card is not None:
            card_action_menu(config, card)
        return "continue"

    return "continue"  # Invalid key, redraw


def boards_menu(config):
    """Show boards and let user pick one. Returns board dict or None to quit."""
    clear_screen()
    print(f"{C_DIM}Loading boards...{C_RESET}")

    try:
        data = api(config, "/api/v1/integrations/boards")
    except APIError as e:
        clear_screen()
        print(f"{C_RED}Failed to load boards: {e}{C_RESET}")
        wait_for_key()
        return None

    boards = data.get("boards", [])

    if not boards:
        clear_screen()
        print(f"{C_DIM}No boards found.{C_RESET}")
        wait_for_key()
        return None

    clear_screen()
    print(f"{C_BOLD}{C_YELLOW}Boards{C_RESET}")
    print()

    # Show up to 9 boards (single-keypress selection)
    for i, board in enumerate(boards[:9]):
        key = i + 1
        icon = board.get("icon", "")
        title = board.get("title", "Untitled")
        prefix = f"{icon} " if icon else ""
        print(f"  {C_BOLD}{C_CYAN}{key}{C_RESET}) {prefix}{title}")

    print()
    print(f"  {C_DIM}q) Quit{C_RESET}")
    print()
    print(f"{C_BOLD}Select: {C_RESET}", end="", flush=True)

    ch = read_char()
    print(ch)

    if ch in ("q", "Q", "\x03"):  # q or Ctrl+C
        return None

    if ch.isdigit() and 1 <= int(ch) <= min(9, len(boards)):
        return boards[int(ch) - 1]

    return boards_menu(config)  # Invalid input, redraw


def cards_menu(config, board):
    """Show cards for a board grouped by list. Returns card dict or None to go back."""
    board_id = board["id"]
    board_title = board.get("title", "Untitled")
    board_icon = board.get("icon", "")

    clear_screen()
    print(f"{C_DIM}Loading cards...{C_RESET}")

    try:
        lists_data = api(config, f"/api/v1/integrations/boards/{board_id}/lists")
        cards_data = api(config, f"/api/v1/integrations/boards/{board_id}/cards")
    except APIError as e:
        clear_screen()
        print(f"{C_RED}Failed to load cards: {e}{C_RESET}")
        wait_for_key()
        return None

    cards = cards_data.get("cards", [])
    lists = lists_data.get("lists", [])

    if not cards:
        clear_screen()
        prefix = f"{board_icon} " if board_icon else ""
        print(f"{C_BOLD}{prefix}{board_title}{C_RESET}")
        print()
        print(f"{C_DIM}No cards found.{C_RESET}")
        wait_for_key()
        return None

    # Group by list, sort by list position
    by_list = {}
    for card in cards:
        list_name = card.get("list_name", "Unknown")
        by_list.setdefault(list_name, []).append(card)

    list_order = {l["name"]: l["position"] for l in lists}
    sorted_lists = sorted(by_list.keys(), key=lambda n: list_order.get(n, 999))

    # Flatten into numbered list
    numbered_cards = []
    for list_name in sorted_lists:
        for card in by_list[list_name]:
            numbered_cards.append((card, list_name))

    # Paginate — show 9 at a time
    page = 0
    page_size = 9

    while True:
        clear_screen()
        prefix = f"{board_icon} " if board_icon else ""
        print(f"{C_BOLD}{prefix}{board_title}{C_RESET} {C_DIM}({len(cards)} cards){C_RESET}")
        print()

        start = page * page_size
        end = min(start + page_size, len(numbered_cards))
        page_cards = numbered_cards[start:end]

        current_list = None
        for i, (card, list_name) in enumerate(page_cards):
            if list_name != current_list:
                current_list = list_name
                print(f"  {C_BOLD}{C_YELLOW}{list_name}{C_RESET}")

            key = i + 1
            title = card.get("title", "Untitled")
            completed = card.get("completed", False)
            marker = f"{C_GREEN}✓{C_RESET}" if completed else " "
            print(f"  {C_BOLD}{C_CYAN}{key}{C_RESET}) {marker} {title}")

        print()

        # Navigation hints
        nav_parts = []
        if page > 0:
            nav_parts.append(f"{C_MAGENTA}p{C_RESET}) prev")
        if end < len(numbered_cards):
            nav_parts.append(f"{C_MAGENTA}n{C_RESET}) next")
        nav_parts.append(f"{C_DIM}0) back{C_RESET}")

        if len(numbered_cards) > page_size:
            page_num = page + 1
            total_pages = (len(numbered_cards) + page_size - 1) // page_size
            print(f"  {C_DIM}Page {page_num}/{total_pages}{C_RESET}  {' | '.join(nav_parts)}")
        else:
            print(f"  {' | '.join(nav_parts)}")

        print()
        print(f"{C_BOLD}Select: {C_RESET}", end="", flush=True)

        ch = read_char()
        print(ch)

        if ch in ("0", "q", "Q", "\x03"):
            return None

        if ch in ("n", "N") and end < len(numbered_cards):
            page += 1
            continue

        if ch in ("p", "P") and page > 0:
            page -= 1
            continue

        if ch.isdigit() and 1 <= int(ch) <= len(page_cards):
            selected_card, _ = page_cards[int(ch) - 1]
            return selected_card

        # Invalid input, redraw same page


def cross_board_cards_menu(config, sort="newest"):
    """Show cards from all boards sorted by date. Returns card dict or None."""
    clear_screen()
    label = "Latest" if sort == "newest" else "Oldest"
    print(f"{C_DIM}Loading {label.lower()} cards across all boards...{C_RESET}")

    try:
        boards_data = api(config, "/api/v1/integrations/boards")
    except APIError as e:
        clear_screen()
        print(f"{C_RED}Failed to load boards: {e}{C_RESET}")
        wait_for_key()
        return None

    boards = boards_data.get("boards", [])
    if not boards:
        clear_screen()
        print(f"{C_DIM}No boards found.{C_RESET}")
        wait_for_key()
        return None

    # Fetch cards from all boards
    all_cards = []
    board_names = {}
    for board in boards:
        board_id = board["id"]
        board_title = board.get("title", "Untitled")
        board_icon = board.get("icon", "")
        board_label = f"{board_icon} {board_title}".strip() if board_icon else board_title
        board_names[board_id] = board_label

        try:
            data = api(config, f"/api/v1/integrations/boards/{board_id}/cards")
            for card in data.get("cards", []):
                card["_board_label"] = board_label
                card["_board_id"] = board_id
                all_cards.append(card)
        except APIError:
            continue

    if not all_cards:
        clear_screen()
        print(f"{C_DIM}No cards found across any board.{C_RESET}")
        wait_for_key()
        return None

    # Sort by created_at
    reverse = sort == "newest"
    all_cards.sort(key=lambda c: c.get("updated_at", ""), reverse=reverse)

    # Paginate
    page = 0
    page_size = 9

    while True:
        clear_screen()
        print(f"{C_BOLD}{C_YELLOW}{label} Cards{C_RESET} {C_DIM}({len(all_cards)} total){C_RESET}")
        print()

        start = page * page_size
        end = min(start + page_size, len(all_cards))
        page_cards = all_cards[start:end]

        for i, card in enumerate(page_cards):
            key = i + 1
            title = card.get("title", "Untitled")
            board_label = card.get("_board_label", "")
            list_name = card.get("list_name", "")
            completed = card.get("completed", False)
            marker = f"{C_GREEN}✓{C_RESET}" if completed else " "
            print(f"  {C_BOLD}{C_CYAN}{key}{C_RESET}) {marker} {title}")
            print(f"     {C_DIM}{board_label} → {list_name}{C_RESET}")

        print()

        nav_parts = []
        if page > 0:
            nav_parts.append(f"{C_MAGENTA}p{C_RESET}) prev")
        if end < len(all_cards):
            nav_parts.append(f"{C_MAGENTA}n{C_RESET}) next")
        nav_parts.append(f"{C_DIM}0) back{C_RESET}")

        if len(all_cards) > page_size:
            page_num = page + 1
            total_pages = (len(all_cards) + page_size - 1) // page_size
            print(f"  {C_DIM}Page {page_num}/{total_pages}{C_RESET}  {' | '.join(nav_parts)}")
        else:
            print(f"  {' | '.join(nav_parts)}")

        print()
        print(f"{C_BOLD}Select: {C_RESET}", end="", flush=True)

        ch = read_char()
        print(ch)

        if ch in ("0", "q", "Q", "\x03"):
            return None

        if ch in ("n", "N") and end < len(all_cards):
            page += 1
            continue

        if ch in ("p", "P") and page > 0:
            page -= 1
            continue

        if ch.isdigit() and 1 <= int(ch) <= len(page_cards):
            return page_cards[int(ch) - 1]


def card_action_menu(config, card):
    """Show actions for a selected card. Returns None to go back, 'back_to_boards' to jump."""
    card_id = card["id"]
    title = card.get("title", "Untitled")

    while True:
        clear_screen()
        print(f"{C_BOLD}{title}{C_RESET}")
        if card.get("description"):
            desc = card["description"]
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"{C_DIM}{desc}{C_RESET}")
        print()

        print(f"  {C_BOLD}{C_MAGENTA}r{C_RESET}) Run — kick off Claude session")
        print(f"  {C_BOLD}{C_CYAN}s{C_RESET}) Status — peek at session output")
        print(f"  {C_BOLD}{C_CYAN}c{C_RESET}) Checkout — pull branch locally")
        print(f"  {C_BOLD}{C_CYAN}d{C_RESET}) Details — view full card info")
        print()
        print(f"  {C_DIM}0) Back to cards{C_RESET}")
        print(f"  {C_DIM}b) Back to boards{C_RESET}")
        print()
        print(f"{C_BOLD}Select: {C_RESET}", end="", flush=True)

        ch = read_char()
        print(ch)

        if ch in ("0", "q", "Q", "\x03"):
            return None

        if ch in ("b", "B"):
            return "back_to_boards"

        if ch in ("r", "R"):
            do_run(config, card)

        elif ch in ("s", "S"):
            do_status(config, card_id)

        elif ch in ("c", "C"):
            do_checkout(config, card_id)

        elif ch in ("d", "D"):
            do_details(config, card_id)


def do_run(config, card):
    """Run a Claude Code session for a card."""
    card_id = card["id"]
    title = card.get("title", "Untitled")
    description = card.get("description", "")
    list_name = card.get("list_name", "")

    vm_host = config.get("vm_host")
    project_dir = config.get("project_dir")

    if not vm_host or not project_dir:
        clear_screen()
        print(f"{C_RED}VM host or project dir not configured.{C_RESET}")
        print("Run: lumifydev config")
        wait_for_key()
        return

    clear_screen()
    print(f"{C_BOLD}Run: {title}{C_RESET}")
    print()

    # Fetch full card with comments
    try:
        data = api(config, f"/api/v1/integrations/boards/cards/{card_id}")
        full_card = data.get("card", {})
        comments = full_card.get("comments", [])
    except APIError:
        comments = []

    # Optional custom prompt
    print(f"Custom prompt {C_DIM}(Enter to skip):{C_RESET} ", end="", flush=True)

    # Switch back to line mode for typing
    user_prompt = input().strip() or None

    full_prompt = build_prompt(title, list_name, description, comments, user_prompt)

    session_name = f"card-{card_id[:8]}"
    expanded_dir = os.path.expanduser(project_dir)
    project_name = config.get("project_name", os.path.basename(expanded_dir))
    worktree_name = f"{project_name}--{session_name}"

    vm_project_dir = config.get("vm_project_dir", "")
    if not vm_project_dir:
        home = os.path.expanduser("~")
        if expanded_dir.startswith(os.path.join(home, "dev")):
            rel = os.path.relpath(expanded_dir, os.path.join(home, "dev"))
            vm_project_dir = f"/root/dev/{rel}"

    print()
    print(f"{C_DIM}Launching session: {session_name}...{C_RESET}")
    print()

    launch_remote_session(
        vm_host=vm_host,
        vm_project_dir=vm_project_dir,
        session_name=session_name,
        worktree_name=worktree_name,
        prompt=full_prompt,
    )

    # Post comment
    comment_content = (
        f"[LumifyDev] Session started\n"
        f"Session: {session_name}\n"
        f"Worktree: {worktree_name}\n"
        f"VM: {vm_host}"
    )
    try:
        api(
            config,
            f"/api/v1/integrations/boards/cards/{card_id}/comments",
            method="POST",
            body={"content": comment_content},
        )
        print(f"{C_GREEN}Card updated with session info.{C_RESET}")
    except APIError:
        print(f"{C_YELLOW}Could not update card.{C_RESET}")

    print()
    print(f"{C_GREEN}Session is running.{C_RESET}")
    print(f"  {C_DIM}Attach: ssh {vm_host} -t 'tmux attach -t {session_name}'{C_RESET}")
    wait_for_key()


def do_status(config, card_id):
    """Peek at session output."""
    vm_host = config.get("vm_host")
    if not vm_host:
        clear_screen()
        print(f"{C_RED}VM host not configured.{C_RESET}")
        wait_for_key()
        return

    clear_screen()
    print(f"{C_DIM}Loading session info...{C_RESET}")

    info = get_session_info_from_card(config, card_id)
    if not info:
        clear_screen()
        print(f"{C_YELLOW}No LumifyDev session found on this card.{C_RESET}")
        wait_for_key()
        return

    clear_screen()
    session_name = info["session"]
    print(f"{C_BOLD}Session: {session_name}{C_RESET}")
    print(f"{C_DIM}{'─' * 40}{C_RESET}")

    result = ssh_run(vm_host, f"tmux capture-pane -t '{session_name}' -p | tail -25")
    if result.returncode != 0:
        print(f"{C_YELLOW}Session may have ended.{C_RESET}")
    else:
        print(result.stdout)

    wait_for_key()


def do_checkout(config, card_id):
    """Checkout the worktree branch locally."""
    import subprocess

    clear_screen()
    print(f"{C_DIM}Loading session info...{C_RESET}")

    info = get_session_info_from_card(config, card_id)
    if not info:
        clear_screen()
        print(f"{C_YELLOW}No LumifyDev session found on this card.{C_RESET}")
        wait_for_key()
        return

    worktree = info["worktree"]
    project_dir = os.path.expanduser(config.get("project_dir", "."))

    clear_screen()
    print(f"{C_DIM}Checking out: {worktree}{C_RESET}")
    print()

    try:
        subprocess.run(["git", "fetch", "origin"], cwd=project_dir, check=True, capture_output=True)
        result = subprocess.run(["git", "checkout", worktree], cwd=project_dir, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{C_RED}Checkout failed:{C_RESET} {result.stderr.strip()}")
        else:
            print(f"{C_GREEN}Checked out: {worktree}{C_RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{C_RED}Git error:{C_RESET} {e}")

    wait_for_key()


def do_details(config, card_id):
    """Show full card details with comments."""
    clear_screen()
    print(f"{C_DIM}Loading card...{C_RESET}")

    try:
        data = api(config, f"/api/v1/integrations/boards/cards/{card_id}")
    except APIError as e:
        clear_screen()
        print(f"{C_RED}Failed to load card: {e}{C_RESET}")
        wait_for_key()
        return

    card = data.get("card", {})

    clear_screen()
    print(f"{C_BOLD}{card.get('title', 'Untitled')}{C_RESET}")
    if card.get("list_name"):
        print(f"{C_DIM}List: {card['list_name']}{C_RESET}")
    print()

    if card.get("description"):
        print(f"{C_YELLOW}Description:{C_RESET}")
        print(card["description"])
        print()

    comments = card.get("comments", [])
    if comments:
        print(f"{C_YELLOW}Comments ({len(comments)}):{C_RESET}")
        for c in comments:
            user = c.get("user_name", "Unknown")
            content = c.get("content", "")
            print(f"  {C_CYAN}{user}:{C_RESET} {content}")
        print()

    print(f"{C_DIM}ID: {card.get('id', '')}{C_RESET}")
    wait_for_key()

"""CLI command implementations."""

import os
import subprocess
import sys
import urllib.parse

from .api import api, api_request, APIError
from .config import (
    load_config, save_config, require_config, DEFAULT_API_URL,
    is_multi_workspace, get_current_workspace_id, get_workspace_name,
    get_board_config, save_board_config, get_effective_config,
)
from .display import C_BOLD, C_DIM, C_RED, C_GREEN, C_YELLOW, C_CYAN, C_RESET
from .remote import (
    build_prompt,
    get_session_info_from_card,
    launch_remote_session,
    ssh_run,
)


def cmd_config(_args):
    """Interactive config setup — just token + VM host."""
    print(f"{C_BOLD}LumifyDev Setup{C_RESET}")
    print(f"{C_DIM}Configure your LumifyHub connection and VM.{C_RESET}")
    print()

    existing = load_config() or {}

    # API URL
    default_url = existing.get("api_url", DEFAULT_API_URL)
    api_url = input(f"LumifyHub API URL [{default_url}]: ").strip() or default_url

    # API Key
    existing_key = existing.get("api_key", "")
    key_hint = f" [{existing_key[:12]}...]" if existing_key else ""
    print(f"{C_DIM}Use a CLI token (lhcli_*) for multi-workspace access,{C_RESET}")
    print(f"{C_DIM}or a workspace API key (lumify_*) for single workspace.{C_RESET}")
    api_key = input(f"API key / CLI token{key_hint}: ").strip()
    if not api_key and existing_key:
        api_key = existing_key

    if not api_key:
        print(f"{C_RED}API key is required.{C_RESET}")
        print(f"Get a CLI token from: Account Settings → CLI")
        print(f"Or a workspace key from: Workspace Settings → API Keys")
        sys.exit(1)

    # Verify the key
    print(f"{C_DIM}Verifying credentials...{C_RESET}")
    try:
        data = api_request(api_url, api_key, "/api/v1/integrations/auth/verify")
    except APIError as e:
        print(f"{C_RED}Verification failed: {e}{C_RESET}")
        sys.exit(1)

    # VM Host
    default_host = existing.get("vm_host", "")
    host_hint = f" [{default_host}]" if default_host else " (e.g. root@your-vm-ip)"
    vm_host = input(f"VM SSH host{host_hint}: ").strip() or default_host

    # Build config
    config = dict(existing)  # Preserve boards, workspaces, etc.
    config["api_url"] = api_url
    config["api_key"] = api_key
    config["vm_host"] = vm_host

    if api_key.startswith("lhcli_"):
        # Multi-workspace mode
        user = data.get("user", {})
        workspaces = data.get("workspaces", [])
        print(f"{C_GREEN}Authenticated as: {user.get('email', 'Unknown')}{C_RESET}")
        print(f"{C_DIM}Found {len(workspaces)} workspace(s){C_RESET}")

        # Store workspace names
        if "workspaces" not in config:
            config["workspaces"] = {}
        for ws in workspaces:
            if ws["id"] not in config["workspaces"]:
                config["workspaces"][ws["id"]] = {}
            config["workspaces"][ws["id"]]["name"] = ws["name"]

        # Set default workspace
        if not config.get("default_workspace") and workspaces:
            config["default_workspace"] = workspaces[0]["id"]

        # Pick default if multiple
        if len(workspaces) > 1:
            print()
            print(f"{C_BOLD}Default workspace:{C_RESET}")
            current_default = config.get("default_workspace", "")
            for i, ws in enumerate(workspaces):
                marker = " (current)" if ws["id"] == current_default else ""
                print(f"  {i + 1}) {ws['name']}{marker}")
            choice = input(f"Select [{1}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(workspaces):
                config["default_workspace"] = workspaces[int(choice) - 1]["id"]
    else:
        # Single workspace mode
        workspace = data.get("workspace", {})
        config["workspace_id"] = workspace.get("id", "")
        print(f"{C_GREEN}Connected to workspace: {workspace.get('name', 'Unknown')}{C_RESET}")

    save_config(config)
    print()
    print(f"{C_GREEN}Config saved!{C_RESET}")
    print(f"{C_DIM}Link projects to boards with: lumifydev link <board-id>{C_RESET}")
    print(f"{C_DIM}Or just pick a board — you'll be prompted on first use.{C_RESET}")


def _detect_setup_commands(project_dir):
    """Auto-detect setup commands based on project files."""
    expanded = os.path.expanduser(project_dir)
    commands = []

    if os.path.exists(os.path.join(expanded, "bun.lockb")) or os.path.exists(os.path.join(expanded, "bunfig.toml")):
        commands.append("bun install")
    elif os.path.exists(os.path.join(expanded, "package-lock.json")):
        commands.append("npm install")
    elif os.path.exists(os.path.join(expanded, "yarn.lock")):
        commands.append("yarn install")
    elif os.path.exists(os.path.join(expanded, "pnpm-lock.yaml")):
        commands.append("pnpm install")
    elif os.path.exists(os.path.join(expanded, "package.json")):
        commands.append("npm install")

    if os.path.exists(os.path.join(expanded, "requirements.txt")):
        commands.append("pip install -r requirements.txt")
    elif os.path.exists(os.path.join(expanded, "pyproject.toml")):
        commands.append("pip install -e .")

    return commands


def _collect_board_config(default_project_dir="", existing_board_cfg=None):
    """Collect project config for a board interactively. Returns board config dict or None."""
    existing = existing_board_cfg or {}

    # Local project dir
    default_dir = existing.get("project_dir", default_project_dir)
    dir_hint = f" [{default_dir}]" if default_dir else ""
    project_dir = input(f"Local project dir{dir_hint}: ").strip() or default_dir
    if not project_dir:
        print(f"{C_DIM}Skipped. You can link later: lumifydev link <board-id>{C_RESET}")
        return None

    project_dir = os.path.expanduser(project_dir)
    project_name = os.path.basename(project_dir)

    # VM project dir — auto-derive from local path
    home = os.path.expanduser("~")
    default_vm_dir = existing.get("vm_project_dir", "")
    if not default_vm_dir and project_dir.startswith(os.path.join(home, "dev")):
        rel = os.path.relpath(project_dir, os.path.join(home, "dev"))
        default_vm_dir = f"/root/dev/{rel}"

    vm_hint = f" [{default_vm_dir}]" if default_vm_dir else " (e.g. /root/dev/my-project)"
    vm_project_dir = input(f"VM project dir{vm_hint}: ").strip() or default_vm_dir

    # Setup commands — auto-detect, let user override
    detected = _detect_setup_commands(project_dir)
    default_setup = existing.get("setup_commands", detected)
    default_setup_str = ", ".join(default_setup) if default_setup else ""

    if default_setup_str:
        print(f"{C_DIM}Detected setup: {default_setup_str}{C_RESET}")
        setup_input = input(f"Setup commands [{default_setup_str}]: ").strip()
    else:
        setup_input = input(f"Setup commands {C_DIM}(comma-separated, Enter to skip){C_RESET}: ").strip()

    if setup_input:
        setup_commands = [cmd.strip() for cmd in setup_input.split(",") if cmd.strip()]
    else:
        setup_commands = default_setup

    board_cfg = {
        "project_dir": project_dir,
        "project_name": project_name,
        "vm_project_dir": vm_project_dir,
    }
    if setup_commands:
        board_cfg["setup_commands"] = setup_commands

    return board_cfg


def cmd_link(args):
    """Link current directory (or specified path) to a board."""
    config = require_config()
    board_id = args.board_id

    existing_board_cfg = get_board_config(config, board_id)
    default_dir = os.getcwd()

    board_cfg = _collect_board_config(default_project_dir=default_dir, existing_board_cfg=existing_board_cfg)
    if not board_cfg:
        return

    save_board_config(config, board_id, board_cfg)
    print(f"{C_GREEN}Linked!{C_RESET} Board {C_DIM}{board_id[:8]}...{C_RESET} → {board_cfg['project_dir']}")


def prompt_board_setup(config, board_id, board_title=""):
    """Prompt user to configure project for a board (lazy setup). Returns board config or None."""
    label = f" ({board_title})" if board_title else ""
    print(f"{C_YELLOW}No project linked to this board{label}.{C_RESET}")
    print(f"{C_DIM}Set up now to run sessions.{C_RESET}")
    print()

    board_cfg = _collect_board_config()
    if not board_cfg:
        return None

    save_board_config(config, board_id, board_cfg)
    print(f"{C_GREEN}Linked!{C_RESET}")
    print()
    return board_cfg


def cmd_workspaces(_args):
    """List workspaces available to the current CLI token."""
    config = require_config()

    if not is_multi_workspace(config):
        print(f"{C_DIM}Single-workspace mode (workspace API key).{C_RESET}")
        print(f"Switch to a CLI token (lhcli_*) for multi-workspace support.")
        return

    data = api_request(
        config["api_url"], config["api_key"],
        "/api/v1/integrations/auth/verify"
    )
    workspaces = data.get("workspaces", [])
    current_ws = get_current_workspace_id(config)

    print(f"{C_BOLD}Workspaces{C_RESET} ({len(workspaces)})")
    print(f"{C_DIM}{'─' * 50}{C_RESET}")

    for ws in workspaces:
        marker = f" {C_GREEN}← current{C_RESET}" if ws["id"] == current_ws else ""
        print(f"  {ws['name']}{marker}")
        print(f"    {C_DIM}ID: {ws['id']}{C_RESET}")

    print()


def cmd_boards(_args):
    """List boards in the workspace."""
    config = require_config()
    data = api(config, "/api/v1/integrations/boards")
    boards = data.get("boards", [])

    if not boards:
        print(f"{C_DIM}No boards found in this workspace.{C_RESET}")
        return

    ws_name = get_workspace_name(config) if is_multi_workspace(config) else None
    header = f"{C_BOLD}Boards{C_RESET} ({len(boards)})"
    if ws_name:
        header += f" {C_DIM}— {ws_name}{C_RESET}"
    print(header)
    print(f"{C_DIM}{'─' * 60}{C_RESET}")

    for board in boards:
        page_id = board["id"]
        title = board.get("title", "Untitled")
        icon = board.get("icon", "")
        prefix = f"{icon} " if icon else ""
        linked = get_board_config(config, page_id)
        link_marker = f" {C_GREEN}✓{C_RESET}" if linked else ""
        print(f"  {prefix}{title}{link_marker}")
        print(f"    {C_DIM}ID: {page_id}{C_RESET}")
        if linked:
            print(f"    {C_DIM}→ {linked.get('project_dir', '')}{C_RESET}")

    print()
    print(f"{C_DIM}Usage: lumifydev cards <id>{C_RESET}")


def cmd_cards(args):
    """List cards for a board."""
    config = require_config()
    board_id = args.board_id

    # Fetch lists first so we can show grouping
    lists_data = api(config, f"/api/v1/integrations/boards/{board_id}/lists")
    lists = lists_data.get("lists", [])

    # Fetch cards with optional list filter
    path = f"/api/v1/integrations/boards/{board_id}/cards"
    if args.list:
        path += f"?list_name={urllib.parse.quote(args.list)}"

    data = api(config, path)
    cards = data.get("cards", [])

    if not cards:
        filter_msg = f' in list "{args.list}"' if args.list else ""
        print(f"{C_DIM}No cards found{filter_msg}.{C_RESET}")
        return

    # Group cards by list name
    by_list = {}
    for card in cards:
        list_name = card.get("list_name", "Unknown")
        by_list.setdefault(list_name, []).append(card)

    # Sort lists by position from lists_data
    list_order = {l["name"]: l["position"] for l in lists}

    total = len(cards)
    print(f"{C_BOLD}Cards{C_RESET} ({total})")
    print(f"{C_DIM}{'─' * 60}{C_RESET}")

    for list_name in sorted(by_list.keys(), key=lambda n: list_order.get(n, 999)):
        list_cards = by_list[list_name]
        print(f"\n  {C_BOLD}{list_name}{C_RESET} ({len(list_cards)})")

        for card in list_cards:
            card_id = card["id"]
            title = card.get("title", "Untitled")
            completed = card.get("completed", False)
            marker = f"{C_GREEN}✓{C_RESET}" if completed else f"{C_DIM}○{C_RESET}"
            print(f"    {marker} {title}")
            print(f"      {C_DIM}ID: {card_id}{C_RESET}")

    print()
    print(f"{C_DIM}Usage: lumifydev run <id>{C_RESET}")


def _require_board_config(config, board_id, board_title=""):
    """Get board config, prompting for setup if not linked. Returns config or exits."""
    board_cfg = get_board_config(config, board_id)
    if board_cfg:
        return board_cfg

    board_cfg = prompt_board_setup(config, board_id, board_title)
    if not board_cfg:
        print(f"{C_RED}Cannot run without a linked project.{C_RESET}")
        sys.exit(1)
    return board_cfg


def cmd_run(args):
    """Fetch card details and kick off a Claude Code session on the VM."""
    config = require_config()
    card_id = args.card_id
    user_prompt = args.prompt

    vm_host = config.get("vm_host")
    if not vm_host:
        print(f"{C_RED}VM host not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)

    # Fetch card details (includes board_id)
    print(f"{C_DIM}Fetching card details...{C_RESET}")
    data = api(config, f"/api/v1/integrations/boards/cards/{card_id}")
    card = data.get("card", {})

    title = card.get("title", "Untitled")
    description = card.get("description", "")
    list_name = card.get("list_name", "")
    comments = card.get("comments", [])
    board_id = card.get("board_page_id", "")

    # Get board-specific project config
    if board_id:
        effective = get_effective_config(config, board_id)
    else:
        effective = get_effective_config(config)

    project_dir = effective.get("project_dir")
    if not project_dir and board_id:
        board_cfg = prompt_board_setup(config, board_id)
        if not board_cfg:
            print(f"{C_RED}Cannot run without a linked project.{C_RESET}")
            sys.exit(1)
        effective = get_effective_config(config, board_id)
        project_dir = effective.get("project_dir")

    if not project_dir:
        print(f"{C_RED}Project directory not configured.{C_RESET}")
        print("Link a project: lumifydev link <board-id>")
        sys.exit(1)

    print(f"{C_BOLD}{title}{C_RESET}")
    if list_name:
        print(f"{C_DIM}List: {list_name}{C_RESET}")
    print()

    full_prompt = build_prompt(title, list_name, description, comments, user_prompt)

    # Generate session name from card ID
    session_name = f"card-{card_id}"
    expanded_dir = os.path.expanduser(project_dir)
    project_name = effective.get("project_name", os.path.basename(expanded_dir))
    worktree_name = f"{project_name}--{session_name}"

    print(f"{C_DIM}Launching Claude Code session: {session_name}{C_RESET}")
    print(f"{C_DIM}Project: {project_dir}{C_RESET}")
    print()

    # Resolve VM project dir
    vm_project_dir = effective.get("vm_project_dir", "")
    if not vm_project_dir:
        home = os.path.expanduser("~")
        if expanded_dir.startswith(os.path.join(home, "dev")):
            rel = os.path.relpath(expanded_dir, os.path.join(home, "dev"))
            vm_project_dir = f"/root/dev/{rel}"
        else:
            print(f"{C_RED}Cannot determine VM project path.{C_RESET}")
            print("Set vm_project_dir via: lumifydev link <board-id>")
            sys.exit(1)

    launch_remote_session(
        vm_host=vm_host,
        vm_project_dir=vm_project_dir,
        session_name=session_name,
        worktree_name=worktree_name,
        prompt=full_prompt,
        setup_commands=effective.get("setup_commands"),
    )

    # Post comment back to the card
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
    except APIError as e:
        print(f"{C_YELLOW}Warning: Could not post comment to card: {e}{C_RESET}")

    print()
    print(f"{C_BOLD}Session is running.{C_RESET}")
    print(f"  Attach:   ssh {vm_host} -t 'tmux attach -t {session_name}'")
    print(f"  Status:   lumifydev status {card_id}")
    print(f"  Checkout: lumifydev checkout {card_id}")


def cmd_checkout(args):
    """Checkout the worktree branch from a card's LumifyDev session."""
    config = require_config()
    card_id = args.card_id

    session_info = get_session_info_from_card(config, card_id)
    if not session_info:
        print(f"{C_RED}No LumifyDev session found on this card.{C_RESET}")
        sys.exit(1)

    worktree_name = session_info["worktree"]
    print(f"{C_DIM}Fetching and checking out branch: {worktree_name}{C_RESET}")

    # Try to find project_dir from board config or fallback to cwd
    project_dir = config.get("project_dir", ".")
    # Check board configs for a matching project_name
    for board_cfg in config.get("boards", {}).values():
        pname = board_cfg.get("project_name", "")
        if pname and worktree_name.startswith(pname):
            project_dir = board_cfg.get("project_dir", project_dir)
            break

    project_dir = os.path.expanduser(project_dir)
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "checkout", worktree_name],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"{C_RED}Checkout failed:{C_RESET} {result.stderr.strip()}")
            sys.exit(1)

        print(f"{C_GREEN}Checked out: {worktree_name}{C_RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{C_RED}Git error:{C_RESET} {e}")
        sys.exit(1)


def cmd_status(args):
    """Peek at the tmux session output on the VM."""
    config = require_config()
    card_id = args.card_id

    vm_host = config.get("vm_host")
    if not vm_host:
        print(f"{C_RED}VM host not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)

    session_info = get_session_info_from_card(config, card_id)
    if not session_info:
        print(f"{C_RED}No LumifyDev session found on this card.{C_RESET}")
        sys.exit(1)

    session_name = session_info["session"]
    print(f"{C_DIM}Peeking at session: {session_name}{C_RESET}")
    print(f"{C_DIM}{'─' * 60}{C_RESET}")

    result = ssh_run(vm_host, f"tmux capture-pane -t '{session_name}' -p | tail -30")
    if result.returncode != 0:
        print(f"{C_YELLOW}Session may have ended.{C_RESET}")
        if result.stderr:
            print(f"{C_DIM}{result.stderr.strip()}{C_RESET}")
    else:
        print(result.stdout)

"""CLI command implementations."""

import os
import subprocess
import sys
import urllib.parse

from .api import api, api_request, APIError
from .config import (
    load_config, save_config, require_config, DEFAULT_API_URL,
    is_multi_workspace, get_workspace_config, get_current_workspace_id, get_workspace_name,
)
from .display import C_BOLD, C_DIM, C_RED, C_GREEN, C_YELLOW, C_CYAN, C_RESET
from .remote import (
    build_prompt,
    get_session_info_from_card,
    launch_remote_session,
    ssh_run,
)


def cmd_config(_args):
    """Interactive config setup. Supports both workspace API keys and CLI tokens."""
    print(f"{C_BOLD}LumifyDev Setup{C_RESET}")
    print(f"{C_DIM}Configure your LumifyHub workspace and VM connection.{C_RESET}")
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

    # Route based on key type
    if api_key.startswith("lhcli_"):
        _config_multi_workspace(existing, api_url, api_key, data)
    else:
        _config_single_workspace(existing, api_url, api_key, data)


def _config_multi_workspace(existing, api_url, api_key, verify_data):
    """Configure multi-workspace mode using CLI token."""
    user = verify_data.get("user", {})
    workspaces = verify_data.get("workspaces", [])

    print(f"{C_GREEN}Authenticated as: {user.get('email', 'Unknown')}{C_RESET}")
    print(f"{C_DIM}Found {len(workspaces)} workspace(s){C_RESET}")
    print()

    if not workspaces:
        print(f"{C_YELLOW}No workspaces found. Create one at lumifyhub.io first.{C_RESET}")
        sys.exit(1)

    # Show workspaces
    for i, ws in enumerate(workspaces):
        print(f"  {C_BOLD}{C_CYAN}{i + 1}{C_RESET}) {ws['name']} {C_DIM}({ws['id'][:8]}...){C_RESET}")
    print()

    # Configure each workspace
    existing_workspaces = existing.get("workspaces", {})
    new_workspaces = {}

    for ws in workspaces:
        ws_id = ws["id"]
        ws_name = ws["name"]
        ws_existing = existing_workspaces.get(ws_id, {})

        print(f"{C_BOLD}Configure: {ws_name}{C_RESET}")

        # VM Host
        default_host = ws_existing.get("vm_host", existing.get("vm_host", ""))
        host_hint = f" [{default_host}]" if default_host else " (e.g. root@your-vm-ip)"
        vm_host = input(f"  VM SSH host{host_hint}: ").strip() or default_host

        # Project directory
        default_project_dir = ws_existing.get("project_dir", "")
        dir_hint = f" [{default_project_dir}]" if default_project_dir else " (e.g. ~/dev/my-project)"
        project_dir = input(f"  Local project dir{dir_hint}: ").strip() or default_project_dir

        # Project name
        default_project_name = ws_existing.get("project_name", "")
        if not default_project_name and project_dir:
            default_project_name = os.path.basename(os.path.expanduser(project_dir))
        name_hint = f" [{default_project_name}]" if default_project_name else ""
        project_name = input(f"  Project name{name_hint}: ").strip() or default_project_name

        # VM project dir
        default_vm_dir = ws_existing.get("vm_project_dir", "")
        if not default_vm_dir and project_dir:
            expanded = os.path.expanduser(project_dir)
            home = os.path.expanduser("~")
            if expanded.startswith(os.path.join(home, "dev")):
                rel = os.path.relpath(expanded, os.path.join(home, "dev"))
                default_vm_dir = f"/root/dev/{rel}"
        vm_dir_hint = f" [{default_vm_dir}]" if default_vm_dir else ""
        vm_project_dir = input(f"  VM project dir{vm_dir_hint}: ").strip() or default_vm_dir

        new_workspaces[ws_id] = {
            "name": ws_name,
            "vm_host": vm_host,
            "project_dir": project_dir,
            "project_name": project_name,
            "vm_project_dir": vm_project_dir,
        }

        # Preserve setup_commands if they existed
        if "setup_commands" in ws_existing:
            new_workspaces[ws_id]["setup_commands"] = ws_existing["setup_commands"]

        print()

    # Pick default workspace
    default_ws = existing.get("default_workspace", workspaces[0]["id"])
    if len(workspaces) == 1:
        default_ws = workspaces[0]["id"]
    else:
        print(f"{C_BOLD}Default workspace:{C_RESET}")
        for i, ws in enumerate(workspaces):
            marker = " (current)" if ws["id"] == default_ws else ""
            print(f"  {i + 1}) {ws['name']}{marker}")
        choice = input(f"Select [1]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(workspaces):
            default_ws = workspaces[int(choice) - 1]["id"]
        elif not choice:
            default_ws = workspaces[0]["id"]

    config = {
        "api_url": api_url,
        "api_key": api_key,
        "default_workspace": default_ws,
        "workspaces": new_workspaces,
    }

    save_config(config)
    ws_name = new_workspaces.get(default_ws, {}).get("name", "Unknown")
    print(f"{C_GREEN}Config saved!{C_RESET} Default workspace: {ws_name}")
    print(f"{C_DIM}~/.config/lumifydev/config.json{C_RESET}")


def _config_single_workspace(existing, api_url, api_key, verify_data):
    """Configure single-workspace mode using workspace API key."""
    workspace_id = verify_data.get("workspace", {}).get("id", "")
    workspace_name = verify_data.get("workspace", {}).get("name", "Unknown")
    print(f"{C_GREEN}Connected to workspace: {workspace_name}{C_RESET}")

    # VM Host
    default_host = existing.get("vm_host", "")
    host_hint = f" [{default_host}]" if default_host else " (e.g. root@your-vm-ip)"
    vm_host = input(f"VM SSH host{host_hint}: ").strip() or default_host

    # Project directory
    default_project_dir = existing.get("project_dir", "")
    dir_hint = f" [{default_project_dir}]" if default_project_dir else " (e.g. ~/dev/my-project)"
    project_dir = input(f"Local project directory{dir_hint}: ").strip() or default_project_dir

    # Project name
    default_project_name = existing.get("project_name", "")
    if not default_project_name and project_dir:
        default_project_name = os.path.basename(os.path.expanduser(project_dir))
    name_hint = f" [{default_project_name}]" if default_project_name else ""
    project_name = input(f"Project name{name_hint}: ").strip() or default_project_name

    # VM project dir
    default_vm_dir = existing.get("vm_project_dir", "")
    if not default_vm_dir and project_dir:
        expanded = os.path.expanduser(project_dir)
        home = os.path.expanduser("~")
        if expanded.startswith(os.path.join(home, "dev")):
            rel = os.path.relpath(expanded, os.path.join(home, "dev"))
            default_vm_dir = f"/root/dev/{rel}"
    vm_dir_hint = f" [{default_vm_dir}]" if default_vm_dir else " (e.g. /root/dev/my-project)"
    vm_project_dir = input(f"VM project directory{vm_dir_hint}: ").strip() or default_vm_dir

    config = {
        "api_url": api_url,
        "api_key": api_key,
        "workspace_id": workspace_id,
        "vm_host": vm_host,
        "project_dir": project_dir,
        "project_name": project_name,
        "vm_project_dir": vm_project_dir,
    }

    save_config(config)
    print()
    print(f"{C_GREEN}Config saved to {C_RESET}{C_DIM}~/.config/lumifydev/config.json{C_RESET}")


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
    ws_config = get_workspace_config(config)
    data = api(ws_config, "/api/v1/integrations/boards")
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
        print(f"  {prefix}{title}")
        print(f"    {C_DIM}ID: {page_id}{C_RESET}")

    print()
    print(f"{C_DIM}Usage: lumifydev cards <id>{C_RESET}")


def cmd_cards(args):
    """List cards for a board."""
    config = require_config()
    ws_config = get_workspace_config(config)
    board_id = args.board_id

    # Fetch lists first so we can show grouping
    lists_data = api(ws_config, f"/api/v1/integrations/boards/{board_id}/lists")
    lists = lists_data.get("lists", [])

    # Fetch cards with optional list filter
    path = f"/api/v1/integrations/boards/{board_id}/cards"
    if args.list:
        path += f"?list_name={urllib.parse.quote(args.list)}"

    data = api(ws_config, path)
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


def cmd_run(args):
    """Fetch card details and kick off a Claude Code session on the VM."""
    config = require_config()
    ws_config = get_workspace_config(config)
    card_id = args.card_id
    user_prompt = args.prompt

    vm_host = ws_config.get("vm_host")
    if not vm_host:
        print(f"{C_RED}VM host not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)

    project_dir = ws_config.get("project_dir")
    if not project_dir:
        print(f"{C_RED}Project directory not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)

    # Fetch card details
    print(f"{C_DIM}Fetching card details...{C_RESET}")
    data = api(ws_config, f"/api/v1/integrations/boards/cards/{card_id}")
    card = data.get("card", {})

    title = card.get("title", "Untitled")
    description = card.get("description", "")
    list_name = card.get("list_name", "")
    comments = card.get("comments", [])

    print(f"{C_BOLD}{title}{C_RESET}")
    if list_name:
        print(f"{C_DIM}List: {list_name}{C_RESET}")
    print()

    full_prompt = build_prompt(title, list_name, description, comments, user_prompt)

    # Generate session name from card ID
    session_name = f"card-{card_id}"
    expanded_dir = os.path.expanduser(project_dir)
    project_name = ws_config.get("project_name", os.path.basename(expanded_dir))
    worktree_name = f"{project_name}--{session_name}"

    print(f"{C_DIM}Launching Claude Code session: {session_name}{C_RESET}")
    print(f"{C_DIM}Project: {project_dir}{C_RESET}")
    print()

    # Resolve VM project dir
    vm_project_dir = ws_config.get("vm_project_dir", "")
    if not vm_project_dir:
        home = os.path.expanduser("~")
        if expanded_dir.startswith(os.path.join(home, "dev")):
            rel = os.path.relpath(expanded_dir, os.path.join(home, "dev"))
            vm_project_dir = f"/root/dev/{rel}"
        else:
            print(f"{C_RED}Cannot determine VM project path.{C_RESET}")
            print("Set 'vm_project_dir' in your config: lumifydev config")
            sys.exit(1)

    launch_remote_session(
        vm_host=vm_host,
        vm_project_dir=vm_project_dir,
        session_name=session_name,
        worktree_name=worktree_name,
        prompt=full_prompt,
        setup_commands=ws_config.get("setup_commands"),
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
            ws_config,
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
    ws_config = get_workspace_config(config)
    card_id = args.card_id

    session_info = get_session_info_from_card(ws_config, card_id)
    if not session_info:
        print(f"{C_RED}No LumifyDev session found on this card.{C_RESET}")
        sys.exit(1)

    worktree_name = session_info["worktree"]
    print(f"{C_DIM}Fetching and checking out branch: {worktree_name}{C_RESET}")

    project_dir = os.path.expanduser(ws_config.get("project_dir", "."))
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
    ws_config = get_workspace_config(config)
    card_id = args.card_id

    vm_host = ws_config.get("vm_host")
    if not vm_host:
        print(f"{C_RED}VM host not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)

    session_info = get_session_info_from_card(ws_config, card_id)
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

"""Config management for LumifyDev."""

import json
import os
import sys

DEFAULT_API_URL = "https://lumifyhub.io"
CONFIG_DIR = os.path.expanduser("~/.config/lumifydev")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    """Load config from ~/.config/lumifydev/config.json"""
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    """Save config to ~/.config/lumifydev/config.json"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def require_config():
    """Load config or exit with setup instructions."""
    from .display import C_RED, C_RESET

    config = load_config()
    if not config or not config.get("api_key"):
        print(f"{C_RED}Not configured.{C_RESET} Run: lumifydev config")
        sys.exit(1)
    return config


def is_multi_workspace(config):
    """Check if config uses CLI token (multi-workspace mode)."""
    api_key = config.get("api_key", "")
    return api_key.startswith("lhcli_")


def get_current_workspace_id(config):
    """Get the current workspace ID from config."""
    return config.get("current_workspace") or config.get("default_workspace")


def get_workspace_name(config, workspace_id=None):
    """Get the display name for a workspace."""
    ws_id = workspace_id or get_current_workspace_id(config)
    workspaces = config.get("workspaces", {})
    if ws_id and ws_id in workspaces:
        return workspaces[ws_id].get("name", ws_id[:8])
    return config.get("workspace_name", "Default")


def get_board_config(config, board_id):
    """Get project config for a specific board. Returns None if not linked."""
    boards = config.get("boards", {})
    return boards.get(board_id)


def save_board_config(config, board_id, board_config):
    """Save project config for a board."""
    if "boards" not in config:
        config["boards"] = {}
    config["boards"][board_id] = board_config
    save_config(config)


def get_effective_config(config, board_id=None):
    """Get config with board-specific overrides applied.

    Merges: global config < board config.
    Board config provides: project_dir, project_name, vm_project_dir, setup_commands.
    Global config provides: api_url, api_key, vm_host, workspace IDs.
    """
    effective = dict(config)

    # Apply workspace context
    if is_multi_workspace(config):
        ws_id = get_current_workspace_id(config)
        if ws_id:
            effective["current_workspace"] = ws_id

    # Apply board-specific project config
    if board_id:
        board_cfg = get_board_config(config, board_id)
        if board_cfg:
            for key in ("project_dir", "project_name", "vm_project_dir", "setup_commands"):
                if key in board_cfg:
                    effective[key] = board_cfg[key]

    return effective

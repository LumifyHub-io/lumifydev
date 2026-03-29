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


def get_workspace_config(config, workspace_id=None):
    """Get workspace-specific config (vm_host, project_dir, etc.).

    In multi-workspace mode, returns config from workspaces[workspace_id].
    In single-workspace mode, returns top-level config.
    """
    if not is_multi_workspace(config):
        # Legacy single-workspace mode — settings are at top level
        return config

    ws_id = workspace_id or get_current_workspace_id(config)
    workspaces = config.get("workspaces", {})

    if ws_id and ws_id in workspaces:
        # Merge workspace-specific config with top-level (api_url, api_key)
        ws_config = dict(config)
        ws_config.update(workspaces[ws_id])
        ws_config["current_workspace"] = ws_id
        return ws_config

    # No workspace config yet — return top-level
    return config


def get_workspace_name(config, workspace_id=None):
    """Get the display name for a workspace."""
    ws_id = workspace_id or get_current_workspace_id(config)
    workspaces = config.get("workspaces", {})
    if ws_id and ws_id in workspaces:
        return workspaces[ws_id].get("name", ws_id[:8])
    return config.get("workspace_name", "Default")

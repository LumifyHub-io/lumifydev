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

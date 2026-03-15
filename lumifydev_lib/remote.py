"""Remote VM session management via SSH + tmux."""

import base64
import shutil
import subprocess
import sys

from .display import C_RED, C_DIM, C_RESET


def launch_remote_session(vm_host, vm_project_dir, session_name, worktree_name, prompt):
    """
    Launch a Claude Code session on a remote VM via SSH + tmux.

    Flow: SSH → create git worktree → start tmux session → launch Claude → send prompt.
    """
    if not shutil.which("ssh"):
        print(f"{C_RED}ssh not found on PATH.{C_RESET}")
        sys.exit(1)

    prompt_b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    worktree_dir = f"$HOME/dev/worktrees/{worktree_name}"

    remote_script = f"""
# Verify repo exists
if [ ! -d '{vm_project_dir}' ]; then
    echo 'Error: Repository not found at {vm_project_dir}'
    exit 1
fi

# Try to create worktree, fall back to main repo
WORKTREE_DIR="{worktree_dir}"
WORK_DIR='{vm_project_dir}'

if [ -d "$WORKTREE_DIR" ]; then
    echo "Using existing worktree: $WORKTREE_DIR"
    WORK_DIR="$WORKTREE_DIR"
elif git -C '{vm_project_dir}' rev-parse --git-dir >/dev/null 2>&1; then
    cd '{vm_project_dir}'
    # Determine base branch
    BASE_BRANCH="main"
    if ! git rev-parse --verify main >/dev/null 2>&1; then
        BASE_BRANCH="master"
    fi
    # Create worktree
    mkdir -p "$HOME/dev/worktrees"
    if git worktree add -b '{worktree_name}' "$WORKTREE_DIR" "$BASE_BRANCH" 2>/dev/null; then
        WORK_DIR="$WORKTREE_DIR"
        echo "Created worktree: $WORKTREE_DIR"
        # Copy env files to worktree
        for envfile in .env .env.local .env.development .env.development.local; do
            if [ -f '{vm_project_dir}/'$envfile ]; then
                cp '{vm_project_dir}/'$envfile "$WORKTREE_DIR/$envfile"
            fi
        done
    else
        echo "Worktree creation failed, using main repo"
    fi
    cd - > /dev/null
else
    echo "Not a git repo, using directory directly"
fi

# Create tmux session
if tmux has-session -t '{session_name}' 2>/dev/null; then
    echo 'Session already exists'
else
    tmux new-session -d -s '{session_name}' -c "$WORK_DIR"

    # Start Claude Code
    tmux send-keys -t '{session_name}' 'claude --dangerously-skip-permissions' Enter

    # Wait for Claude to initialize, then send prompt
    sleep 4

    # Decode and send prompt
    PROMPT=$(echo '{prompt_b64}' | base64 -d)
    tmux send-keys -t '{session_name}' "$PROMPT"
    sleep 0.2
    tmux send-keys -t '{session_name}' Enter

    echo 'Session created and Claude started with prompt'
fi
"""

    print(f"{C_DIM}Connecting to {vm_host}...{C_RESET}")
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", vm_host, remote_script],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"{C_RED}Failed to launch remote session:{C_RESET}")
        print(result.stderr or result.stdout)
        sys.exit(1)

    if result.stdout.strip():
        print(result.stdout.strip())


def ssh_run(vm_host, command):
    """Run a command on the VM via SSH and return the CompletedProcess."""
    return subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", vm_host, command],
        capture_output=True,
        text=True,
    )


def build_prompt(title, list_name, description, comments, user_prompt):
    """Compose a Claude Code prompt from card details."""
    prompt_parts = [
        f"# Card: {title}",
        f"Status: {list_name}" if list_name else "",
    ]

    if description:
        prompt_parts.append(f"\n## Description\n{description}")

    if comments:
        prompt_parts.append("\n## Comments")
        for comment in comments:
            user_name = comment.get("user_name", "Unknown")
            content = comment.get("content", "")
            prompt_parts.append(f"- {user_name}: {content}")

    if user_prompt:
        prompt_parts.append(f"\n## Task\n{user_prompt}")
    else:
        prompt_parts.append("\n## Task\nImplement this card. Read the CLAUDE.md for project conventions.")

    return "\n".join(p for p in prompt_parts if p)


def parse_session_comment(content):
    """Parse a LumifyDev comment to extract session info.

    Returns dict with 'session', 'worktree', 'vm' keys, or None if not a LumifyDev comment.
    """
    if "[LumifyDev]" not in content:
        return None

    info = {}
    for line in content.split("\n"):
        if line.startswith("Session: "):
            info["session"] = line.split("Session: ", 1)[1].strip()
        elif line.startswith("Worktree: "):
            info["worktree"] = line.split("Worktree: ", 1)[1].strip()
        elif line.startswith("VM: "):
            info["vm"] = line.split("VM: ", 1)[1].strip()

    if "session" in info and "worktree" in info:
        return info

    return None


def get_session_info_from_card(config, card_id):
    """Fetch card comments and find the most recent LumifyDev session info."""
    from .api import api

    data = api(config, f"/api/v1/integrations/boards/cards/{card_id}")
    card = data.get("card", {})
    comments = card.get("comments", [])

    for comment in reversed(comments):
        info = parse_session_comment(comment.get("content", ""))
        if info:
            return info

    return None

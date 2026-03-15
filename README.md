# LumifyDev

Turn [LumifyHub](https://lumifyhub.io) kanban cards into async Claude Code sessions on your VM.

Point at a board card, kick off a remote Claude Code session in an isolated git worktree, and get status updates posted back to the card automatically.

## Setup

1. **Get a LumifyHub API key** — Go to your workspace Settings → API Keys
2. **Have a VM with Claude Code + tmux installed** — Any Linux server accessible via SSH
3. **Configure LumifyDev:**

```bash
lumifydev config
```

This walks you through connecting your LumifyHub workspace and VM.

## Usage

```bash
# List your boards
lumifydev boards

# List cards on a board (optionally filter by list)
lumifydev cards <board-id>
lumifydev cards <board-id> --list "In Progress"

# Kick off a Claude Code session for a card
lumifydev run <card-id>
lumifydev run <card-id> --prompt "implement this feature"

# Check session output on the VM
lumifydev status <card-id>

# Checkout the worktree branch locally
lumifydev checkout <card-id>
```

## How It Works

1. `lumifydev run` fetches the card's title, description, and comments from LumifyHub
2. Composes a prompt with all the card context + your instructions
3. SSHs into your VM, creates an isolated git worktree, starts a tmux session, and launches Claude Code with the prompt
4. Posts a comment back to the card with the session name and worktree info
5. You can check progress with `lumifydev status` or checkout the branch with `lumifydev checkout`

## Config

Stored at `~/.config/lumifydev/config.json`:

```json
{
  "api_url": "https://lumifyhub.io",
  "api_key": "lumify_...",
  "workspace_id": "...",
  "vm_host": "root@your-vm-ip",
  "project_dir": "~/dev/your-project",
  "project_name": "your-project",
  "vm_project_dir": "/root/dev/your-project"
}
```

## Requirements

- Python 3.7+ (no external dependencies)
- SSH access to your VM
- Your VM needs: `git`, `tmux`, and `claude` (Claude Code CLI)
- A [LumifyHub](https://lumifyhub.io) workspace with boards

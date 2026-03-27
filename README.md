# LumifyDev

Turn [LumifyHub](https://lumifyhub.io) kanban cards into async Claude Code sessions on your VM.

Point at a board card, kick off a remote Claude Code session in an isolated git worktree, and get status updates posted back to the card automatically.

## Install

```bash
git clone https://github.com/LumifyHub-io/lumifydev.git
sudo ln -sf $(pwd)/lumifydev/lumifydev /usr/local/bin/lumifydev
```

No dependencies — just Python 3.7+. If you don't have Python installed:

```bash
# macOS
brew install python

# Ubuntu/Debian
sudo apt install python3

# Fedora
sudo dnf install python3
```

## Setup

1. **Get a LumifyHub API key** — Go to your workspace Settings → API Keys
2. **Have a VM with Claude Code + tmux installed** — Any Linux server accessible via SSH
3. **Configure LumifyDev:**

```bash
lumifydev config
```

This walks you through connecting your LumifyHub workspace and VM.

## Interactive Mode (Mobile Friendly)

Just run `lumifydev` with no arguments to launch the interactive TUI — designed for SSH from your phone:

```bash
lumifydev
```

Single-keypress navigation, no typing required:

```
Main Menu
─────────────────────────────────────

  1) Boards          — browse by board
  2) Latest Cards    — newest cards across all boards
  3) Oldest Cards    — oldest cards across all boards

  q) Quit
```

- Pick a board → pick a card → **r**un / **s**tatus / **c**heckout / **d**etails
- Cards are paginated (9 per page) with **n**ext/**p**rev
- **0** to go back, **q** to quit

## CLI Commands

For scripting or desktop use, all commands are also available directly:

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
  "api_url": "https://www.lumifyhub.io",
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

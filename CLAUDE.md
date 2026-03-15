# LumifyDev

Single-file Python CLI (no external deps) that connects LumifyHub kanban boards to async Claude Code sessions.

## Architecture

- `lumifydev` — single executable Python file, all logic in one place
- Config stored at `~/.config/lumifydev/config.json`
- Uses LumifyHub v1/integrations API (API key auth via `x-api-key` header)
- Self-contained VM session management via SSH + tmux (no cc-remote dependency)
- Posts structured comments to cards with `[LumifyDev]` prefix for parsing

## Key Patterns

- **No external dependencies** — stdlib only (argparse, urllib, json, subprocess, base64, shutil)
- **Self-contained remote execution** — SSH into VM, create git worktree, start tmux, launch Claude, send base64-encoded prompt
- **Structured comments** — LumifyDev posts comments in a parseable format so `checkout`/`status` can extract session info
- **Config-driven** — all settings (API URL, key, VM host, project dirs) are user-configurable
- **Designed for public use** — no hardcoded hosts or paths, everything configurable

## Comment Format

```
[LumifyDev] Session started
Session: card-abc12345
Worktree: project-name--card-abc12345
VM: root@vm-ip
```

## Remote Session Flow

1. Base64 encode prompt (avoids shell escaping issues)
2. SSH to VM with a shell script that:
   - Verifies repo exists at `vm_project_dir`
   - Creates git worktree at `~/dev/worktrees/<project>--<session>`
   - Copies `.env*` files to worktree
   - Creates tmux session in worktree directory
   - Launches `claude --dangerously-skip-permissions`
   - Waits 4s for init, then sends decoded prompt

## API Endpoints Used

- `GET /api/v1/integrations/auth/verify` — verify API key
- `GET /api/v1/integrations/boards` — list boards
- `GET /api/v1/integrations/boards/:id/lists` — list board lists
- `GET /api/v1/integrations/boards/:id/cards` — list cards (with ?list_name filter)
- `GET /api/v1/integrations/boards/cards/:id` — get card with comments
- `POST /api/v1/integrations/boards/cards/:id/comments` — add comment

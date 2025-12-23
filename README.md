 # tg-ops

Secure-ish Telegram bot for remote system operations and monitoring on Linux hosts.

This project runs a small HTTP server (webhook endpoint) and uses `python-telegram-bot` in webhook mode.

## Features

- **Bot commands**
  - `/ping` (health check)
  - `/uptime` (runs `uptime`)
  - `/status` (CPU/RAM + configured disks + configured systemd services)
  - `/exec [command]` (execute a shell command; if no args, prompts for a command)
  - `/docker` (inline menu to start/stop/restart configured containers via `docker compose`)
  - `/reboot` (placeholder, currently not implemented)

## Requirements

- **Python**: `>= 3.12`
- **OS**: Linux (uses `systemctl` for services)
- **Docker**: optional (only needed if you use `/docker`)
- **Public HTTPS URL** reachable by Telegram (or a tunnel/reverse proxy). Telegram requires HTTPS for webhooks.

## Installation

### From source (recommended)

```bash
pip install poetry
poetry install
```

Run via Poetry:

```bash
poetry run tg-ops --help
```

### Editable install (pip)

```bash
pip install -e .
tg-ops --help
```

## Configuration

The CLI reads a TOML config file.

- **Default path**: `~/.tg-ops.toml`
- If the file does not exist, the app creates a sample file and exits with an error.

Minimal example (`~/.tg-ops.toml`):

```toml
# Telegram bot token from @BotFather
bot_token = "YOUR_BOT_TOKEN"

# Base public URL for your webhook server (the app uses the /webhook path)
webhook_url = "https://your-domain.example"

# HTTP port to listen on
port = 5000

# Optional, recommended: Telegram webhook secret token
secret_token = ""

# Optional
log_level = "INFO"

# Optional monitoring lists
monitored_services = ["docker", "caddy"]
monitored_disks = ["/", "/data"]

# Optional docker container mapping:
# keys are container names shown in the menu,
# values are docker-compose file paths used for actions.
[monitored_containers]
myapp = "/opt/myapp/docker-compose.yml"
```

## Usage

### Start the server (webhook mode)

```bash
tg-ops run
```

Use a custom config path:

```bash
tg-ops -f /path/to/config.toml run
```

The server listens on `0.0.0.0:<port>` and serves Telegram updates at:

`<webhook_url>/webhook`

### Manage Telegram webhooks

```bash
tg-ops webhook set
tg-ops webhook get
tg-ops webhook unset
```

Notes:

- `webhook set` registers `<webhook_url>/webhook`.
- If you set `secret_token`, Telegram will include it and the server will validate it.

## Security notes

This bot can execute shell commands and trigger Docker actions.

- **Do not expose it without access control.**
- The codebase currently has a hardcoded `ADMIN_ID` in `src/bot/handlers.py`, and the `@restricted` decorator is present but not enabled on most commands.
- Treat this as **trusted-admin-only** tooling.

## Troubleshooting

- **Config file created but app exits**
  - On first run, if `~/.tg-ops.toml` does not exist, a sample is created and the process exits.
  - Fill in at least `bot_token` and `webhook_url`, then re-run.

- **No updates received**
  - Check current webhook state: `tg-ops webhook get`
  - Ensure your public URL is reachable from the internet and terminates TLS.
  - Ensure your reverse proxy forwards `POST /webhook` to `localhost:<port>`.

## License

MIT

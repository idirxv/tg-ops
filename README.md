 # tg-ops

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/09a0312da9ea4ff2a2e9b48a8592a517)](https://app.codacy.com/gh/idirxv/tg-ops/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)

Remote system operations and monitoring on Linux hosts via Telegram.

tg-ops is a lightweight bot that runs a small HTTP webhook server to let you monitor health, check status, and execute commands on your Linux servers directly from a Telegram chat.

## Features

**Bot commands**

- `/ping` Check bot responsiveness.
- `/uptime` Returns the server's uptime.
- `/status` "detailed dashboard: CPU/RAM usage, monitored disks space, and systemd service status."
- `/exec` "Shell Execution: Run arbitrary commands (e.g., /exec ls -la)."
- `/docker` Container Management via Interactive menu.
- `/reboot` Coming Soon.

## Requirements

- **Python**: `>= 3.11`
- **OS**: Linux
- **Docker**: optional (only needed if you use `/docker`)
- **Network**: A public HTTPS URL (e.g. Cloudflare Tunnel, or ngrok) reachable by Telegram's webhook servers.

## Installation

You can install tg-ops via Poetry or standard pip.

### From source (Poetry)

```bash
# 1. Install Poetry if you haven't already
pip install poetry

# 2. Install dependencies
poetry install

# 3. Run the app
poetry run tg-ops --help
```

### With pip

```bash
pip install tg-ops

# Run the app
tg-ops --help
```

## Configuration

`tg-ops` relies on a TOML configuration file.

* Run the app once to generate a default config file at `~/.tg-ops.toml` (or specify a custom path with `-f`):
```bash
tg-ops run
```

* Edit ~/.tg-ops.toml with your details.

Minimal example (`~/.tg-ops.toml`):

```toml
# Telegram bot token from @BotFather
bot_token = "YOUR_BOT_TOKEN"

# Base public URL for your webhook server (the app uses the /webhook path)
webhook_url = "https://your-domain.example"

# HTTP port to listen on
port = 5000

# Optional, recommended: Telegram webhook secret token
secret_token = "super-secret-random-string"

# Optional
log_level = "INFO"

# Optional monitoring lists
monitored_services = ["docker", "nginx", "ssh"]
monitored_disks = ["/", "/mnt/data"]

# Optional docker container mapping:
# keys are container names shown in the menu,
# values are docker-compose file paths used for actions.
[monitored_containers]
myapp = "/opt/myapp/docker-compose.yml"
webapp = "/opt/web/docker-compose.yml"
db = "/opt/db/docker-compose.yml"
```

## Usage

### Start the server and bot

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
# Register the webhook with Telegram (uses settings from config)
tg-ops webhook set

# Check current webhook status
tg-ops webhook get

# Remove the webhook integration
tg-ops webhook unset
```

Notes:

- `webhook set` registers `<webhook_url>/webhook`.
- If you configured a `secret_token` in your TOML file, webhook set will automatically register it with Telegram, ensuring the server rejects any requests without the correct header.

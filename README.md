# tg-ops-bot

Telegram bot controlling Docker Compose stacks of home lab through
[Dockhand](https://github.com/Finsys/dockhand) REST API, via inline
buttons. Runs as own container, published to GHCR by CI, deployed by
Dockhand like any other stack — no extra orchestrator.

Status legend:

| Dot | Meaning |
|-----|---------|
| 🟢 | all containers of stack running |
| 🟡 | some containers running, some not (degraded) |
| 🔴 | no container running |

## How it works

- Two delivery modes, selected with `BOT_MODE`:
  - **`polling`** (default): bot pulls updates from Telegram API.
    No inbound ports, works behind NAT, zero extra setup.
  - **`webhook`**: Telegram pushes updates through Cloudflare Tunnel to
    bot's built-in HTTP server. Lower latency; see
    [Webhook mode](#webhook-mode-cloudflare-tunnel).
- Every Docker operation goes through **Dockhand REST API**
  (`GET /api/stacks`, `POST /api/stacks/{name}/start|stop|restart`) with a
  `Bearer dh_…` API token. Bot **never touches Docker socket**.
- `/ping` replies `Pong` — liveness check.
- `/docker` shows one button per allowlisted stack with status dot.
  Tapping stack opens detail view (per-container states) with actions
  valid for its state: **Start** when stopped, **Stop / Restart** when
  running, all three when partially running, plus Refresh and Back.
- **Stop asks for confirmation** (`Yes, stop` / `Cancel`); Start and Restart
  run immediately. While action runs message shows `⏳` with no
  buttons, then re-renders with fresh status.

## Setup

### 1. Create Telegram bot

1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, follow
   prompts, copy token.
2. Optional: `/setcommands` with `start - list stacks` for nicer menu.

### 2. Find chat ID

Send any message to new bot, then:

```bash
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates" | grep -o '"chat":{"id":[0-9-]*'
```

Number after `"id":` is chat ID.

### 3. Create Dockhand API token

In Dockhand: **Settings → API tokens → create token**. Use **dedicated
token for this bot** so it can be revoked independently. Copy `dh_…`
value.

### 4. Deploy with Dockhand

1. Add this repo as stack in Dockhand (Git source). Compose file pulls
   prebuilt image `ghcr.io/idirxv/tg-ops:latest`, published for amd64 and
   arm64 by `Publish Docker image` workflow on every push to `main`.
2. Set environment variables from `.env.example` in stack's
   environment settings in Dockhand.
3. Deploy. Log should show
   `Bot starting: 1 allowed chat(s), stacks: ...`.

Compose file attaches container to external Docker network
`dockhand`, so `DOCKHAND_URL` can use container name
(e.g. `http://dockhand:3000`). If network doesn't exist, remove
`networks:` blocks from `docker-compose.yml` and point `DOCKHAND_URL` at
host IP and Dockhand's published port instead.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | Bot token from @BotFather |
| `DOCKHAND_URL` | yes | Base URL of Dockhand, e.g. `http://dockhand:3000` |
| `DOCKHAND_API_TOKEN` | yes | Dockhand API token (`dh_…`) |
| `ALLOWED_CHAT_IDS` | yes | Comma-separated Telegram chat IDs (integers) |
| `ALLOWED_STACKS` | yes | Comma-separated stack names bot may control |
| `DOCKHAND_ENV` | yes | Numeric Dockhand environment id — `GET /api/environments` returns it as `id`. Dockhand scopes `/api/stacks` by this; missing or non-numeric value returns empty list |
| `LOG_LEVEL` | no | `DEBUG`, `INFO` (default), `WARNING`, `ERROR` |
| `BOT_MODE` | no | `polling` (default) or `webhook` |
| `WEBHOOK_URL` | webhook mode | Full public URL incl. path, `https://` only, e.g. `https://tgbot.example.com/telegram` |
| `WEBHOOK_SECRET` | webhook mode | 1–256 chars of `A-Za-z0-9_-`; generate with `openssl rand -hex 32` |
| `WEBHOOK_PORT` | no | Listen port, default `5555`; compose publishes on `127.0.0.1:5555`. Override only together with compose port mapping and tunnel's service URL |

Bad or missing config makes container exit immediately with clear error message.

## Webhook mode (Cloudflare Tunnel)

Prerequisite: `cloudflared` tunnel already running on host
(dashboard-managed, `network_mode: host`).

1. Generate secret: `openssl rand -hex 32`.
2. In **Cloudflare Zero Trust → Networks → Tunnels → your tunnel →
   Public hostname**, add: hostname `tgbot.<your-domain>`, service
   `http://localhost:5555`.
3. Set in bot stack's environment:

   ```bash
   BOT_MODE=webhook
   WEBHOOK_URL=https://tgbot.<your-domain>/telegram
   WEBHOOK_SECRET=<generated secret>
   ```

4. Redeploy. On startup bot registers webhook with Telegram itself
   (`setWebhook`), passing secret token.

Why requests stay safe:

- Telegram sends secret in `X-Telegram-Bot-Api-Secret-Token`
  header on every delivery; bot answers **403** to anything without it,
  so random scans of public hostname never reach handler code.
- Container port published on **127.0.0.1 only** — reachable by
  host-network `cloudflared`, not LAN or internet.
- Chat-ID and stack allowlists apply unchanged on top.

**Rollback:** set `BOT_MODE=polling` and redeploy — bot removes
webhook automatically when polling starts.

## Security

- **Chat allowlist**: only chat IDs in `ALLOWED_CHAT_IDS` get any response.
  Everyone else ignored silently, logged at WARNING.
- **Stack allowlist**: bot can only see and act on `ALLOWED_STACKS`.
  Check runs server-side on every button press — inline button data is
  client-forgeable, never trusted.
- **No Docker socket**: bot only talks to Dockhand API; compromise
  of bot doesn't grant host-level Docker access.
- **Container hardening**: non-root user, read-only filesystem, `cap_drop:
  ALL`, `no-new-privileges`, no published ports, memory/CPU limits.
- **Never add bot's own stack to `ALLOWED_STACKS`** — stopping it would
  leave nothing to restart it.
- Use **dedicated Dockhand API token**, revoke if bot's
  environment ever leaks. Keep real values out of git; only `.env.example`
  is committed.

## Local development

Dependencies managed with [uv](https://docs.astral.sh/uv/). `uv sync`
creates `.venv`, installs locked dependency tree (including `dev`
group).

```bash
uv sync
uv run pytest
```

Run bot locally (against reachable Dockhand):

```bash
export TELEGRAM_BOT_TOKEN=... DOCKHAND_URL=... DOCKHAND_API_TOKEN=... \
       ALLOWED_CHAT_IDS=... ALLOWED_STACKS=...
uv run python -m bot.main
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Bot never answers | Chat ID not in `ALLOWED_CHAT_IDS` — check container logs for `Denied update from chat_id=…`, add that ID. |
| `Dockhand rejected the API token (401)` | Token revoked or mistyped — create new one in Dockhand, update `DOCKHAND_API_TOKEN`. |
| `No controllable stacks found in Dockhand.` | Wrong `DOCKHAND_ENV`: Dockhand answers `GET /api/stacks` with `[]` for unknown environment id instead of erroring. Get right id from `GET /api/environments` (numeric `id`, not environment name). |
| Stack missing from list | Name in `ALLOWED_STACKS` doesn't exactly match stack name in Dockhand, or stack isn't registered in Dockhand yet. |
| Buttons answer "Expired or invalid" | Message predates bot restart or config change — send `/docker` for fresh list. |
| `Dockhand unreachable (…)` | Wrong `DOCKHAND_URL` or no network path — verify with `curl` from inside container's network. |

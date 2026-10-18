# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with `uv` (lockfile is committed; `.venv` is created by `uv sync`).

```bash
uv sync                                   # install deps incl. dev group
uv run pytest                             # full test suite
uv run pytest tests/test_config.py -k webhook   # single file / single test
uv run ruff check .                       # lint (E,F,I,UP,B,SIM,RUF)
uv run ruff format .                      # format
uv run mypy                               # type-check (configured to bot/ only)
uv run python -m bot.main                 # run locally; needs the env vars below
```

`pytest` runs with `asyncio_mode = "auto"` — async tests need no decorator.

## Architecture

A Telegram bot that starts/stops/restarts home-lab Docker Compose stacks through the
[Dockhand](https://github.com/Finsys/dockhand) REST API. It never touches the Docker socket.

Layering, inner to outer — each module depends only on the ones above it:

| Module | Role |
|---|---|
| `bot/config.py` | Parses + validates all env vars into a frozen `Config` at startup; raises `ConfigError` |
| `bot/stacks.py` | Pure domain model: parses Dockhand's `/api/stacks` payload into `Stack`/`Container`, derives `StackStatus` |
| `bot/dockhand.py` | Blocking `requests` client for Dockhand (`DockhandClient`), raises `DockhandError` |
| `bot/keyboards.py` | Inline keyboards + the `<action>\|<stack>` callback-data codec (`encode`/`decode`) |
| `bot/auth.py` | Chat-ID allowlist gate |
| `bot/handlers.py` | `/ping`, `/docker`, callback dispatch, HTML rendering |
| `bot/main.py` | `build_application()` wiring + polling/webhook run modes |

Key structural facts that span files:

- **`DockhandClient` is blocking on purpose.** Every call from async handler code must go
  through `asyncio.to_thread` (see `handlers._fetch_stacks`, `_run_action`). Don't make the
  client async; don't call it directly from a coroutine.
- **The auth gate is a `TypeHandler` in group `-1`**, registered before the default-group
  handlers in `build_application`. That's what makes it cover both messages and callback
  queries. Unauthorized updates raise `ApplicationHandlerStop` — silent drop, WARNING log.
- **`keyboards.decode()` is the security boundary.** Callback data comes from the client and
  is forgeable, so every button press re-validates the action and re-checks the stack against
  `config.allowed_stacks` server-side. Never trust a stack name that didn't pass `decode`.
- **State lives in `bot_data`, not module globals.** Handlers pull `config` and `client` via
  the `_config()` / `_client()` helpers; there is no per-user conversation state, so any
  message can be acted on at any time and stale messages just fail `decode`.
- **Status is computed, not read.** `stacks.compute_status` derives 🟢/🟡/🔴 from
  `containerDetails[].state` counts; Dockhand's own `status` field is only a fallback when the
  container list is empty. Note the payload quirk: `containers` holds bare ids,
  `containerDetails` holds the objects.
- **Rendering is HTML parse mode**, so every interpolated name/state goes through
  `html.escape`. `_safe_edit` swallows Telegram's "message is not modified" `BadRequest`
  (hit constantly by Refresh).
- **Stop is the only confirmed action**: `Action.STOP` renders a confirm keyboard,
  `Action.CONFIRM_STOP` ("cstop") performs it. `_ACTIONS` maps the three executing actions to
  Dockhand verbs + progress wording; while an action runs the message shows `⏳` with no
  buttons to block double-taps.
- **Callback data is capped at 64 bytes by Telegram**, which is why `config._MAX_STACK_NAME_BYTES
  = 55` and stack names may not contain `|`. Changing the codec means revisiting both.

## Configuration

Required: `TELEGRAM_BOT_TOKEN`, `DOCKHAND_URL`, `DOCKHAND_API_TOKEN`, `ALLOWED_CHAT_IDS`,
`ALLOWED_STACKS`, `DOCKHAND_ENV`. Optional: `LOG_LEVEL`, `BOT_MODE`, and in webhook mode
`WEBHOOK_URL` (https only), `WEBHOOK_SECRET`, `WEBHOOK_PORT`. See `.env.example` and the
README table. Invalid config exits the process with code 1 before any network call.

`DOCKHAND_ENV` must be the **numeric** environment id from `GET /api/environments` — Dockhand
answers `/api/stacks` with `200 []` for an unknown id instead of an error, so a wrong value
looks like "no stacks found". `config._parse_dockhand_env` rejects non-digits for this reason.

`BOT_MODE=webhook` is expressed in the model as `Config.webhook is not None`; polling is
`None`. The webhook path is derived from `WEBHOOK_URL` (`Webhook.path`), and PTB registers the
webhook with Telegram itself on startup, passing `secret_token` — deliveries without the
`X-Telegram-Bot-Api-Secret-Token` header get 403 before reaching handler code.

## Deployment

`docker-compose.yml` pulls `ghcr.io/idirxv/tg-ops:latest`, built for amd64+arm64 by
`.github/workflows/docker-publish.yml` on pushes to `main` and `v*` tags. Deployed by Dockhand
as a stack. Hardening in compose is intentional and should be preserved when editing it:
non-root user (set in the Dockerfile), `read_only: true` with a tmpfs `/tmp`, `cap_drop: ALL`,
`no-new-privileges`, mem/cpu limits, and the webhook port published on `127.0.0.1` only so
only host-network `cloudflared` can reach it.

Never add the bot's own stack to `ALLOWED_STACKS` — stopping it would leave nothing to
restart it.

`WEBHOOK_PORT` is `5555` on both sides of the compose mapping (`127.0.0.1:5555:5555`) and
defaults to `5555` in three places that must stay in sync: `config._parse_port`,
`Webhook.port`, and compose's `WEBHOOK_PORT: ${WEBHOOK_PORT:-5555}`. A fourth copy lives
outside the repo — the tunnel's public-hostname service URL in the Cloudflare dashboard
(`http://localhost:5555`) — so changing the port needs a dashboard edit too or webhook
delivery silently 502s.

## Testing

`tests/conftest.py` provides `base_env`, `webhook_env`, and a ready `config` fixture built
from a deliberately messy env (stray whitespace, negative chat id) to exercise the parsers.
Dockhand HTTP is stubbed with `responses`; Telegram objects are `MagicMock`/`AsyncMock` — the
suite never touches the network. Tests mirror modules one-to-one (`tests/test_<module>.py`).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `idirxv/tg-ops` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

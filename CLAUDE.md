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
| `bot/sessions.py` | Pure domain model: parses the control service's `/sessions` payload into `Session` |
| `bot/claude_version.py` | Pure domain model: parses `/version` and `/update` into `VersionCheck`/`UpdateResult`, compares versions numerically |
| `bot/claude_host.py` | Blocking `requests` client for the Claude Host control service (`ClaudeHostClient`), raises `ClaudeHostError` |
| `bot/auth.py` | Chat-ID allowlist gate |
| `bot/handlers.py` | `/ping`, `/docker`, callback dispatch, HTML rendering |
| `bot/claude_keyboards.py`, `bot/claude_handlers.py` | The optional `/claude` panel: `claude.<action>\|<arg>` codec + keyboards, and its handlers |
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
- **`/claude` is optional and separate.** It exists only when `Config.claude_host` is set
  (`CLAUDE_CONTROL_URL` + `CLAUDE_CONTROL_TOKEN`, both or neither); `build_application` takes
  the client as an optional third argument and registers the command and its
  `^claude\.`-pattern `CallbackQueryHandler` only then. That handler must be added **before**
  the catch-all stack `on_callback` (first match in a group wins). The client lives in
  `bot_data["claude_host"]`, and like `DockhandClient` it is blocking, so use `asyncio.to_thread`.
  The control service itself is in the home-services repo (`claude-code/control.py`); see
  `docs/adr/0001-claude-host-control-service.md`. Its folder check is the real boundary for
  "open a session in folder X": `claude_keyboards.decode` only checks the shape.
  A session's `Activity` comes from the payload's `status`: `claude agents --json` gives one
  only to sessions with a live process, so a missing `status` means **Retired** (its process
  is gone without it being Closed, whatever the cause; Closed sessions drop out of the
  payload). The main screen lists running sessions only; Retired ones sit behind a
  "⏸️ Sessions Retired (N)" button (`claude.retired`, shown only when N ≥ 1) on a screen of
  their own, where each gets a Resume button instead of Close (`claude stop` fails on
  them): `POST /sessions/<id>/resume` runs `claude respawn`, and the service refuses it for
  a session with a live process, which it would restart mid-turn. The bot re-reads the
  sessions before resuming, so a stale Retired-screen button just refreshes the main
  screen. A resumed session is live again, so Close works on it.
  **Check update** (`GET /version`) reports the Installed version and the newest release on
  the host's channel (`latest: null` when that lookup fails); **Update** (`POST /update`)
  runs `claude update` and carries no version in its callback data, so it can only ever go
  to the newest. Running Sessions keep their version until Closed.
- **Callback data is capped at 64 bytes by Telegram**, which is why `config._MAX_STACK_NAME_BYTES
  = 55` and stack names may not contain `|`. Changing the codec means revisiting both.

## Configuration

Required: `TELEGRAM_BOT_TOKEN`, `DOCKHAND_URL`, `DOCKHAND_API_TOKEN`, `ALLOWED_CHAT_IDS`,
`ALLOWED_STACKS`, `DOCKHAND_ENV`. Optional: `LOG_LEVEL`, `BOT_MODE`, and in webhook mode
`WEBHOOK_URL` (https only), `WEBHOOK_SECRET`, `WEBHOOK_PORT`; `CLAUDE_CONTROL_URL` and
`CLAUDE_CONTROL_TOKEN` to enable `/claude`. See `.env.example` and the
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

### Triage labels

Default vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

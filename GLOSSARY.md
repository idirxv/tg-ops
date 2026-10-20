# tg-ops

A Telegram control panel for the home lab: start, stop and restart Docker Compose stacks, and list, open and close Claude Code sessions, from an authorized chat.

## Language

**Stack**:
A Docker Compose project deployed by Dockhand. Only stacks on the allowlist can be acted on.
_Avoid_: Service, project, container

**Claude Host**:
The home-lab container where Claude Code runs and where sessions live. There is only one.
_Avoid_: Claude bot, Claude Code bot

**Session**:
A Claude Code conversation running on the Claude Host, reachable from the Claude app. Telegram lists, opens and closes sessions but never takes part in the conversation.
_Avoid_: Agent, chat, job

**Open (a Session)**:
Start a new Session, in a chosen Session folder.
_Avoid_: Create, spawn, launch

**Close (a Session)**:
Stop a running Session's process while keeping its conversation, so it can be resumed later. It never deletes the conversation.
_Avoid_: Delete, kill, remove

**Retired (Session)**:
A Session whose process the Claude Host stopped on its own: Claude Code retires a background Session that waits on its user while memory runs low. It stays listed and its conversation is kept, but it can no longer be Closed, only resumed on the host (`claude attach <id>`).
_Avoid_: Dead, ghost, zombie

**Installed version**:
The Claude Code version the Claude Host starts new Sessions with. Running Sessions keep the version they started with until they are Closed and resumed.
_Avoid_: Current version, running version

**Update (Claude Code)**:
Install the newest Claude Code release on the Claude Host. It changes the Installed version, never the running Sessions. Claude Code also updates itself in the background; an Update just does it now.
_Avoid_: Upgrade, restart

**Session folder**:
The directory, inside the Claude Host's workspace, that a Session works in. Defaults to the workspace root.
_Avoid_: Project, repo, cwd

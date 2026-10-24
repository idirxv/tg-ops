# tg-ops

A Telegram control panel for the home lab: start, stop and restart Docker Compose stacks, and list, open, close and resume Claude Code sessions, from an authorized chat.

## Language

**Stack**:
A Docker Compose project deployed by Dockhand. Only stacks on the allowlist can be acted on.
_Avoid_: Service, project, container

**Claude Host**:
The home-lab container where Claude Code runs and where sessions live. There is only one.
_Avoid_: Claude bot, Claude Code bot

**Session**:
A Claude Code conversation running on the Claude Host, reachable from the Claude app. Telegram lists, opens, closes and resumes sessions but never takes part in the conversation.
_Avoid_: Agent, chat, job

**Open (a Session)**:
Start a new Session, in a chosen Session folder.
_Avoid_: Create, spawn, launch

**Close (a Session)**:
Stop a running Session's process while keeping its conversation, so it can be resumed later. It never deletes the conversation.
_Avoid_: Delete, kill, remove

**Retired (Session)**:
A Session whose process is gone without it being Closed, whatever the cause: Claude Code retiring it while memory runs low, the Claude Host stopping or restarting, or the server rebooting. It stays listed and its conversation is kept, but it can no longer be Closed, only Resumed or Discarded.
_Avoid_: Dead, ghost, zombie

**Resume (a Session)**:
Restart the process of a Retired Session, on the Installed version, so its conversation can go on from the Claude app. Only a Retired Session can be Resumed; once it is, it can be Closed again.
_Avoid_: Respawn, restart, reopen, attach

**Discard (a Session)**:
Delete a Retired Session for good, conversation included. Only a Retired Session can be Discarded; a running one can only be Closed.
_Avoid_: Delete, remove, purge

**Installed version**:
The Claude Code version the Claude Host starts new Sessions with. Running Sessions keep the version they started with until they are Closed and resumed.
_Avoid_: Current version, running version

**Update (Claude Code)**:
Install the newest Claude Code release on the Claude Host. It changes the Installed version, never the running Sessions. Claude Code also updates itself in the background; an Update just does it now.
_Avoid_: Upgrade, restart

**Session folder**:
The directory, inside the Claude Host's workspace, that a Session works in. Defaults to the workspace root.
_Avoid_: Project, repo, cwd

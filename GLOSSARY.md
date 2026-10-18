# tg-ops

A Telegram control panel for the home lab: start, stop and restart Docker Compose stacks, and list, open and close Claude Code sessions, from an authorized chat.

## Language

**Stack**:
A Docker Compose project deployed by Dockhand. Only stacks on the allowlist can be acted on.
_Avoid_: Service, project, container

**Claude Host**:
The home-lab container where Claude Code runs and where sessions live. It is the only one; it is not a Stack the bot may stop.
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

**Session folder**:
The directory, inside the Claude Host's workspace, that a Session works in. Defaults to the workspace root.
_Avoid_: Project, repo, cwd

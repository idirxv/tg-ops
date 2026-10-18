# Control the Claude Host through an in-image HTTP service

tg-ops manages Sessions on the Claude Host via a small authenticated HTTP service baked into the Claude Host image (home-services repo), reached over a shared internal Docker network with a bearer token. We rejected Docker exec and the Docker socket because tg-ops deliberately never touches the socket, and `claude remote-control` itself exposes no API. The service wraps Claude Code's own background-session commands (`claude --bg`, `agents --json`, `stop`) and replaces the container's automatic `claude remote-control`.

Sessions stay reachable from the Claude app because the container sets `remoteControlAtStartup: true`: verified on the Claude Host that a `--bg` session then registers with Remote Control, and that it starts in a workspace subfolder without a trust prompt.

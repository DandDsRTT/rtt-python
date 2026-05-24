# RTT — Project Instructions

The RTT monolith is a microtonal/RTT engine with a NiceGUI web front end
(`rtt/web/app.py`). Launch it with `python app.py` (optionally `python app.py <port>`).

## Web app port: 8137 — never 8188

On this machine the RTT web app **must** serve on port **8137**.

- The canonical launch (`python app.py` → `rtt.web.app.main()`) already defaults to
  **8137**. Prefer it, or pass an explicit port — but see the prohibition below.
- **Never bind port 8188.** It is reserved for **ComfyUI** (used by the sibling
  Origenerator project). If RTT squats 8188, ComfyUI cannot start and its clients fail
  with HTTP 404 + websocket "Disconnected" — it breaks the ComfyUI/Origenerator
  integration.
- This applies to **every** launch, including ad-hoc preview/run harness commands that
  call `ui.run(port=...)` directly and bypass `main()`. If a per-worktree preview needs
  its own port (to avoid colliding with another worktree's instance), pick any free port
  **except 8188** — and steer clear of 8189, which is one fat-finger away. When in doubt,
  defer to `main()` / 8137.

`tests/test_web_app_smoke.py` locks the 8137 default; keep it green.

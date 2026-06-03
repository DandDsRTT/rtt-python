# RTT — Project Instructions

The RTT monolith is a microtonal/RTT engine with a NiceGUI web front end
(`rtt/web/app.py`). Launch it with `python app.py` (optionally `python app.py <port>`).

## Web app port: 8137 is the user's — agents launch on their own port

Port **8137** belongs to the **human user**: they keep `python app.py` running there to
actually use the app. It is also the app's canonical default (`rtt.web.app.main()`), which
`tests/test_web_app_smoke.py` locks — keep that green. Do **not** change the default.

**Never launch a server on 8137 yourself.** When any agent starts the app to verify a
change — `python app.py`, an ad-hoc `ui.run(port=...)`, a preview/run harness, or an
integration test — a second instance on 8137 collides with the user's running session and
refreshes their browser constantly, making the app unusable for them. This is the single
biggest way agents disrupt the user. So, for **every** agent-initiated launch:

- **Use a separate free port** — default to the **8200+** range, one per worktree so
  parallel sessions don't fight. **Never 8137** (the user's), **never 8188** (reserved for
  **ComfyUI** in the sibling Origenerator project — squatting it 404s ComfyUI's clients and
  breaks its websocket), and **avoid 8189** (one fat-finger from 8188).
- **Pass `reload=False`.** Hot-reload watches the whole repo tree — worktrees included — so
  a `reload=True` agent instance churns on every edit (yours and other agents') and orphans
  workers that keep the port bound. Agents relaunch deliberately; they don't need reload.

## Integration tests run in-process — run them, don't ask

This project's only "integration" suite, `tests/test_web_integration.py`, drives the
`Editor` (service + undo state) **entirely in-process**: no `ui.run`, no port bound, no
network, no external API — it's a unit test in everything but its filename. **Run it freely
as part of the normal `pytest` run. Do not ask permission first.**

This overrides the global rule that gates integration tests behind a permission prompt. That
rule guards against *disruptive* tests — a server launch on the user's port, or slow /
external / side-effecting runs. None of that can happen here, so the prompt is pure ceremony
that wastes a round-trip. (If a genuinely disruptive test is ever added — one that binds a
port or calls out — the global rule applies again to that test; see the port section above.)

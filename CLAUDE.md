# RTT — Project Instructions

The RTT monolith is a microtonal/RTT engine with a NiceGUI web front end
(`rtt/web/app.py`). Launch it with `python app.py` (optionally `python app.py <port>`).

## The design mockup is the source of truth — never invent UI

The files `RTT design mockup - default.png` and `RTT design mockup - maximized.png` (repo
root) are the **authoritative spec** for what the spreadsheet contains. Every row, column,
tile, caption, symbol and control that exists is in the mockup; the mockup is what the user
is building toward.

**Do not invent UI structure that is not in the mockup.** This is a hard rule, not a
nice-to-have:

- Before adding *any* row, column, tile, or labelled quantity, **find it in the mockup
  first.** Open the relevant PNG (crop/zoom with PIL if needed) and confirm it's there. If
  it isn't, it does not belong — full stop. Don't add it "for completeness," "for symmetry
  with an existing tile," or because the math would support it. The mockup already decided.
- This applies hardest to the **chapter-9 superspace block**, which is mathematically open-
  ended (you *could* lift almost anything into the superspace). The mockup shows exactly two
  superspace rows — **superspace interval vectors** (B_L) and **superspace mapping** (M_L) —
  plus the superspace *tuning* maps in the tuning block. It does **not** contain "superspace
  target intervals", "superspace complexity prescaling", or any other lifted-conversion row.
  An agent previously invented those two rows; they were torn out. Do not recreate them or
  anything like them.
- If you believe something genuinely *should* exist but isn't in the mockup, **stop and ask
  the user** — don't ship it on your own judgment. Adding unrequested, unspecified UI is a
  serious error here: it pollutes a carefully-designed surface and the user has to notice and
  demand its removal.

## Use the persistent `.venv` — don't rebuild a throwaway one

The repo keeps a persistent virtualenv at `.venv/` (gitignored). All deps (runtime **and**
test: `pytest`, `pytest-asyncio`, `nicegui` are pinned right in `requirements.txt`) are
already installed there, so `.venv/bin/python -m pytest -q` "just works" (~2,400 tests).
Always use `.venv/bin/python` — the bare `python`/`python3` on PATH is system 3.9, too old
for the `numpy`/`scipy`/`sympy`/`nicegui` pins (which need Python ≥ 3.10).

If `.venv/` is ever missing, rebuild it once with a 3.10+ interpreter (this machine has
`/opt/homebrew/bin/python3.14`; `.python-version` pins 3.11.9 to match the Render build):

```bash
/opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## When work is done, merge to main — that's how the user sees it

The user validates everything on **their own `python app.py` running on 8137**, which serves
the **main checkout** and hot-reloads on `*.py`/`*.css` changes. Work that lives only on a
worktree branch is **invisible to them**. So the job isn't done until the branch is on `main`:

- When a task is complete (and tests pass), **fast-forward the branch onto `main`**:
  `git -C <main-checkout> merge --ff-only <branch>`. The main instance reloads and the user
  can validate immediately on 8137 — no extra steps from them.
- **Don't make the user think about branches, worktrees, or verification ports.** They don't
  need a play-by-play of which 8200+ port you used to check your work — just land it on main.
  Mention the merge (and whether you pushed to `origin`), nothing more.
- This is a git merge, not an edit of the main checkout — it does **not** violate "all edits
  go in the worktree." Never hand-edit files in the main checkout; only ever `git merge` into it.

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

# RTT — Project Instructions

The RTT monolith is a microtonal/RTT engine with a NiceGUI web front end
(`rtt/app/app.py`). Launch it with `python app.py` (optionally `python app.py <port>`).

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

## Run the fast suite while iterating; the full suite is a merge gate

Tests live in three folders: **`tests/library/unit/`** (the pure math library — ~1,260 tests,
~10s), **`tests/app/unit/`** (web logic without a live page: Editor / layout / spreadsheet
building), and **`tests/app/integration/`** (cross-layer scenarios run in-process — see the
last section). Convention: a test is *integration* only if it drives multiple layers through a
whole scenario — currently just the two files in `tests/app/integration/`; everything else,
library and app alike, is *unit*, and the library has no integration tests. Place new tests
accordingly.

The full suite is ~2,530 tests in **~3–5 min** (it drifts with parallel-agent CPU load), but
**one file is ~67% of that wall-clock**: `tests/app/integration/test_web_render.py` — 171
in-process page-render tests (NiceGUI's `User` plugin) that rebuild the whole spreadsheet page
and re-run the RTT math on every `await user.open("/")` (~0.8s each). The other ~2,360 tests —
all the library, service, editor and spreadsheet-layout checks — finish in ~75s. So split the loop:

- **While iterating, run the fast pass** — skip the one heavy file:
  `.venv/bin/python -m pytest -q --ignore=tests/app/integration/test_web_render.py` (~75s). Use it for quick
  inner-loop feedback on math/service/spreadsheet work.
- **Run the render tests — i.e. the full `.venv/bin/python -m pytest -q` — before the ff-merge
  to main, and whenever your change touches `rtt/app/`** (the renderer those tests cover). They
  guard the exact UI the user validates on 8137 and that the mockup governs, so **a green full
  run is the gate for the merge**: never land a web change on main on the strength of the fast
  pass alone.
- This only changes how *agents pace their own runs*. Do **not** add an `-m`/`addopts` default
  that makes a bare `pytest` silently skip the render tests — the user's own runs and CI must
  stay complete.

**Render runs take turns automatically — let them queue, don't kill them.** With many agents
in parallel, all firing the render gate at once pins every core and nobody ever finishes. So
`tests/app/integration/conftest.py` meters render runs through a **counting semaphore**: at most
`RTT_RENDER_GATE_SLOTS` of them (default **1** — render tests are CPU-bound, so running several
at once just multiplies everyone's wall-clock; one-at-a-time finishes each run fastest) run at
once; the rest queue and take turns. Any pytest session that collected render tests drops a FIFO
**ticket** (`/tmp/rtt-render-gate.d/`) and waits until it's among the N lowest live tickets, then
runs and removes its ticket at the end. While queued you'll see `[render-gate] waiting our turn…
position 2 of 5 queued (1 slot busy …)` on stderr — your **exact place in line** — then
`[render-gate] slot acquired`. That
wait is correct and expected; **do not treat it as a hang, and do not `pkill` other agents'
render runs to jump the queue** — ordering is FIFO/fair, so just wait your turn. The fast pass
(`--ignore=…/test_web_render.py`) collects no render tests, so it never queues and stays fast.
The gate self-heals (a killed holder's ticket is reclaimed on the next scan) and never blocks
forever (`RTT_RENDER_GATE_WAIT`, default 3600s, then it proceeds anyway). Tune concurrency with
`RTT_RENDER_GATE_SLOTS`; `RTT_RENDER_GATE_NOLOCK=1` opts a run out. Don't wrap the gate in `/tmp`
scripts to dodge it or sibling kills — that's the dogpile this prevents.

## Git: you're on a fast-moving team — rebase onto main, then ff-merge

You work in your own worktree on a `claude/<name>` branch. Several agents run in parallel and
`main` moves every few minutes; the user is the **manager**, who deliberately assigns
**separable** tasks — so when you sync with `main`, conflicts are rare and superficial. The
user validates everything on **their own `python app.py` on 8137**, which serves the **main
checkout** and hot-reloads, so work on your branch is invisible until it lands on `main`. Work
like a normal engineer on that team — branch, rebase onto main, merge. No `reset` gymnastics,
no fear:

- **Commit as you go** (and `git add` new files) — always before you rebase or land. A commit
  on your branch is the safe, recoverable home for work; only uncommitted / untracked files in
  a worktree are fragile.
- **Stay on your `claude/<name>` branch.** Never `git checkout` / `switch main`, and never
  hand-edit the main checkout — it's the live app the user is using (a hook blocks such edits).
- **Sync by rebasing onto main.** On a clean (committed) tree: `git rebase main`. It replays
  your commits on top of main's current tip and keeps you on your branch (it does NOT strand
  your worktree). Resolve the (superficial) conflicts and `git rebase --continue` — don't
  `--abort` and start over, don't `reset --hard` to escape. Rebase again whenever `main` moves.
- **Land it when the task is done and tests pass.** A final `git rebase main` makes your branch
  exactly `main + your commits`, so fast-forward main onto it:
  `git -C <main-checkout> merge --ff-only <your-branch>`. The live app reloads and the user
  validates on 8137. If the ff-merge is rejected because `main` moved again, just `git rebase
  main` and retry — a teammate landed first, nothing more.
- **Never `reset --soft`/`--hard main`, `clean -fd`, or `stash` to "tidy" or "fix."**
  `reset --soft main` only does what you want when your base already IS `main`; once `main` has
  moved past your base it silently **reverts every teammate's commit since that base** into your
  squash (this has bitten us — it reverted a whole feature, and even reverted THIS very section
  once, when an agent committed on a stale base). Rebase is the clean tool. Want one commit
  instead of a `wip:` chain? Squash only your OWN commits:
  `git reset --soft $(git merge-base main HEAD) && git commit` — never plain `reset --soft main`.
- **After any ff-merge, sanity-check** `git diff <prev-main> <new-main> --stat` shows only the
  files you meant to change — a stale-base squash shows up here as a pile of unrelated reverts.
- **Just report the merge** — not the 8200+ port you tested on, not branch/worktree mechanics,
  and not `main`-vs-`origin` or push status (the user handles pushing).

## Web app port: 8137 is the user's — agents launch on their own port

Port **8137** belongs to the **human user**: they keep `python app.py` running there to
actually use the app. It is also the app's canonical default (`rtt.app.app.main()`), which
`tests/app/unit/test_web_app_smoke.py` locks — keep that green. Do **not** change the default.

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

## The integration tests run in-process — run them, don't ask

`tests/app/integration/` holds the project's integration tests — the ones that drive whole
user scenarios across layers: `test_web_integration.py` (the `Editor`: service + undo state)
and `test_web_render.py` (the live page, via NiceGUI's `User` plugin). They are integration
tests **by scope**, but they run **entirely in-process**: no `ui.run` server, no port bound,
no network, no external API. That in-process fact — *not* their scope — is what matters here,
so **run them freely as part of the normal `pytest` run. Do not ask permission first.**
(`test_web_render.py` is also the slow one — see the fast-suite section above for pacing.)

This overrides the global rule that gates integration tests behind a permission prompt. That
rule guards against *disruptive* tests — a server launch on the user's port, or slow /
external / side-effecting runs. Neither file does any of that — in-process, no I/O — so the
prompt is pure ceremony that wastes a round-trip. (If a genuinely disruptive test is ever
added — one that binds a port or calls out — the global rule applies again to that test; see
the port section above.)

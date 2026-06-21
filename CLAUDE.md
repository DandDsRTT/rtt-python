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

### Mockup deviations (user-directed — do NOT "restore" to match the mockup)

A few things in the running app deliberately diverge from the mockup because the user asked for
the change after the mockup was drawn. They are NOT bugs or omissions — do not "fix" them back to
the mockup:

- **No optimize button / freeze-at-optimum state.** Optimization is always on (two states:
  scheme-driven and manual override; a scheme pick clears manual). The mockup still shows an
  optimize button; it was removed deliberately (see `rtt/app/editor.py` `generator_tuning` docs).
- **Editable weight row + "custom weights" toggle.** Manual per-target damage weights (the
  mockup's "custom weight … interactive white boxes") are exposed as a **Show toggle** ("custom
  weights", a sibling of all-interval / alt. complexity under weighting), not as a 4th
  damage-weight-slope dropdown option. Turning it on makes box 𝒘's cells editable. custom-weights is
  the LONE "mode toggle" (a Show toggle that IS a tuning mode). **all-interval, by contrast, is a
  two-step in-grid checkbox** (its Show toggle only reveals the box-𝐓 checkbox; the checkbox enters
  the mode via `Editor.set_all_interval`) — it was briefly fused into a one-step mode toggle, but that
  made all-interval + custom-weights a mutually-exclusive PAIR of mode toggles and **broke "select
  all"**, so it was reverted. **Don't re-fuse it, and don't add a Show-toggle mutual-exclusion
  mechanism:** all-interval ↔ custom-weights exclusivity is BEHAVIOR-level only (`set_all_interval`
  drops custom weights; entering custom weights is a no-op while all-interval).
- **Tuning-panel nesting.** weighting and tuning ranges nest under **optimization** (Mode A), so
  **projection** reads as the peer-alternative to the whole optimization branch (D&D's
  optimize-vs-construct fork). The mockup draws these flatter.
- **"tile features" title over the dummy tile.** The general Show group's dummy tile carries a
  bold section title, **"tile features"** (`rtt-show-tiletitle`, built in `rtt/app/app.py`), the way
  "show | example" heads the specific column. The mockup draws no header over this group — the user
  asked for it after the fact. Don't remove it for "matching the mockup."
- **"decimals" toggle + the stacked value's decimal sub-part.** A general Show layer, **`decimals`**
  (sub-control of `quantities`), whose own clickable part in the dummy tile is the ".955" beneath the
  "701" (the value renders as the grid's stacked whole-over-.fraction cents face; its whole part is
  `quantities`, its fraction `decimals`). Off, **every displayed value in the app rounds to the
  nearest integer** — a DISPLAY setting, threaded through the single `service.cents` / `prescale_text`
  chokepoint (grid cells, plain-text EBK strings, range-chart labels); the underlying floats keep
  full precision, so turning it back on restores 3-dp. Not in the mockup — user-requested.

## Only tests and names document — no comments, no docstrings

**Tests and object names are the only documentation allowed in this project.** Comments and
docstrings both rot: the code changes and the prose silently keeps its old claim, becoming a lie.
A test can't do that — when behavior changes the test fails — and a name can't drift from the thing
it names. So knowledge lives in exactly two places, plus the guide for the math:

- **What the code does and must keep doing** lives in `tests/` — the executable specification,
  named and asserted. This is *the* documentation of behavior.
- **What every value, function, class, module, and file IS** lives in its **name**, chosen per the
  guide's conventions so a reader recognizes `superspace_rank`, `raises_the_nullity`, `M_jL`
  without a gloss. A good name is documentation that can't go stale.
- **The RTT math, units, notation, and naming conventions** live in the guide —
  `guide/Dave Keenan & Douglas Blumeyer's guide to RTT/` (esp. ch. 10). The guide — not a
  docstring — is where the domain is explained.

**No docstrings.** Module, class, and function docstrings are banned for the same reason as
comments: they are prose that drifts out of sync with the code. If a function needs a docstring to
be understood, it needs a clearer name, smaller scope, or a test that demonstrates it — not a
paragraph that will later mislead. When you remove a docstring that described behavior, first make
sure a test pins that behavior (write it if it's missing); then the name + the test carry it.

**No explanatory comments.** If you reach for a comment to explain a value, a formula, a matrix, a
unit, or a step, that is a **smell that the code is not yet clear enough** — rename, restructure, or
extract until the comment is unnecessary. A comment that re-derives `rL = r + (dL − d)` belongs in
the guide; the code should read so the identity is obvious from the names, and a test pins the value.

**The one narrow exception.** A short comment is allowed *only* when a limitation of the language,
the browser, NiceGUI, or another critical dependency *forces* code to be written in a way that is
not clean, and a reader would otherwise reasonably "fix" it back and break something — e.g.
*"NiceGUI re-imports rtt.\* on reload, so importing at module top duplicates the class."* That names
an external constraint; it is not documentation of our own behavior. If the awkwardness is ours and
not the platform's, fix the code instead of annotating it.

**Never write change-narration.** The *story of an edit* belongs in the **commit message**, never in
code — *"this aligns the value with the documented intent"*, *"the bug this fixes"*, *"the merge
regression"*, *"X used to ride Y but now owns its own"*. A past mistake worth warning about is a sign
the code should make the wrong path impossible (a type, an assertion, a single source of truth), not
a sign to leave a war story.

**The workflow this implies (TDD).** Lock behavior with a test first or alongside the change, let
the test name + assertions carry the spec, point domain knowledge at the guide, and let names carry
the rest. When you feel the urge to write a comment or docstring, improve the code and the tests
until the urge is gone.

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

## Take the merge lock to land — hold it across the WHOLE critical section

The render gate above serializes the render *runs*, but **not the merges**. Without a merge lock,
agents validate speculatively in parallel (the render-gate queue grows 10+ deep) and then race to
`git merge --ff-only`. Whoever loses the race has `main` move under them with an `rtt/app/` change,
so the green render run they just finished no longer validates the exact merged state. The fix is
an **exclusive (single-holder) merge lock**, `bin/with-merge-lock`, covering the whole
`rebase main → render gate → ff-merge → release` critical section: only the lock-holder
validates-and-merges at a time, so the render-gate queue stays ~1 deep, **you validate the exact
state you land** (no chase), and no speculative run is wasted.

**Hold the lock continuously across separate tool calls — do NOT wrap it around one `bash -c`.**
The earlier one-command form had a hole: if the queued `git rebase main` hits a conflict (because
`main` moved while you were queued — the wait can be 400s+), you can't resolve it inside the single
wrapped command, so `set -e` exits, the lock releases, and **the entire long queue-wait is burned
before reaching the gate**. Instead `acquire` once, then run each step as its own tool call while
you keep holding:

```bash
# 1. CHEAP pre-checks FIRST, OUTSIDE the lock — don't burn a held slot on a run you could have
#    known would fail. The fast pass (touches no render tests, so it never queues):
.venv/bin/python -m pytest -q --ignore=tests/app/integration/test_web_render.py

# 2. Take the lock. Blocks ONCE until held; main is now frozen for everyone else.
bin/with-merge-lock acquire

git rebase main          # resolve any conflict at leisure, across as many tool calls as you need —
                         # nobody can move main while you hold the lock

bin/with-merge-lock renew && .venv/bin/python -m pytest -q   # the render gate, on the EXACT state
                         # you will land. Run the FULL gate ONLY here, under the lock.

bin/with-merge-lock renew && \
  git -C <main-checkout> merge --ff-only <your-branch>       # guaranteed: nothing moved

bin/with-merge-lock release        # free it for the next agent
```

- **`renew` before the gate and before the ff-merge.** `renew` both extends your hold *and verifies
  you still hold it* — it exits non-zero if you somehow lost the lock, so you re-`acquire` instead
  of merging on a stale hold. Renew again during a long conflict resolution if it drags past ~10 min.
- **Run the FULL render gate ONLY under the lock**, as your land-time validation; the fast pass is
  the inner loop. Don't run the full gate speculatively outside the lock — it's redundant with the
  guaranteed-exact under-lock run and just re-creates the contention the lock exists to kill.
- **Always `release`** when you finish or abandon the attempt.
- The legacy single-command form still works (and CI uses it): `bin/with-merge-lock bash -c '…'`
  holds the lock for the wrapped command and releases on exit / failure / signal.

How it holds across tool calls: `acquire` spawns a detached, lease-renewing **holder daemon**; an
atomic `.holder` marker (NOT ticket order — `time_ns` is only µs-granular here and collides) is the
real mutex, with FIFO fairness tickets in `/tmp/rtt-merge-gate.d/` (the same boring no-`flock` `/tmp`
mechanism as the render gate). Three self-heal backstops free a wedged lock automatically: a crashed
daemon (PID death, seconds), a hung daemon (lease + grace, ~minutes), and an **abandoned** hold —
agent/session gone without `release` — frees within `RTT_MERGE_GATE_GAP` (15 min) of the last
`renew`, hard-capped at `RTT_MERGE_GATE_TTL` (40 min) from acquisition. `[merge-gate] waiting …` on
stderr is your place in line — **that wait is correct, not a hang; don't `pkill` to jump it.**
`bin/with-merge-lock status` shows the holder + queue. The lock is exclusive by design (no `SLOTS`
knob — the merge must not race); even so, `git merge --ff-only` is the atomic ref-CAS backstop that
keeps `main` safe if anything ever slips. Validate the lock itself in isolation with
`bin/with-merge-lock-selftest` (spawns real daemons in throwaway dirs; not a pytest test). Knobs:
`RTT_MERGE_GATE_WAIT` (3600s, then it FAILS — it never "proceeds unlocked"), `RTT_MERGE_GATE_LEASE`/
`GRACE`/`RENEW`/`GAP`/`TTL`/`READY`, `RTT_MERGE_GATE_NOLOCK=1` to opt out, `RTT_MERGE_LOCK_ID` for an
explicit lock identity.

**The orthogonal-files softener — skip a re-run when `main` moved harmlessly.** Even outside the
lock, if your ff-merge is rejected because `main` moved, you do **not** always need to re-run the
gate. If `main` advanced *only* in files that can't affect your change's rendered output, your
prior green render run still validates the merged state. This generalizes the long-standing
"test-only move → prior green run still validates" judgment. Check it mechanically from your
worktree:

```bash
bin/merge-safe-check        # diffs merge-base(main,HEAD)..main; exit 0 = SAFE to ff-merge, 1 = RE-RUN
```

`merge-base(main, HEAD)` is exactly the old main tip your green run was built on, so the diff is
precisely what landed under you. Render-**relevant** (forces a re-run) = the whole `rtt/` tree,
`app.py`, the rootdir `conftest.py`, `pytest.ini`, `requirements.txt`, and — conservatively —
anything else not on the irrelevant whitelist (`tests/**`, `guide/**`, `.claude/**`, `bin/**`,
`*.md`, `*.png`/`*.csv`, a few top-level non-code files). The default is *relevant*: when unsure,
re-run. (The lock makes this rare — it's the fallback for the occasional move that slips in.)

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
- **Stay on your `claude/<name>` branch.** Never `git checkout` / `switch` / `reset` / `rebase` in
  the **main checkout** (or any sibling worktree), and never hand-edit it — it's the live app the
  user is using. A `git checkout <commit>` there *detaches the running app's HEAD* and hides
  everyone's landed work (this has bitten us). Two hooks now enforce it: one blocks edits into the
  main checkout, one blocks state-changing git aimed at it from a worktree — the only allowed
  main-checkout write is the landing `git -C <main> merge --ff-only <your-branch>`. Inspect another
  branch read-only (`git -C <main> show/diff/log`) or just build in your own worktree (it already
  has your commit).
- **Never hand subagents / Workflow agents the main-checkout path.** Give them THIS worktree's path
  as cwd and tell them explicitly: read-only git, never `cd` into or `git checkout`/`reset` the main
  checkout, validate by in-process builds in the worktree. A review agent once `cd`'d into the main
  checkout to "validate" a branch and ran `git checkout`, detaching the live app. (Also: prefer
  targeted `git add <paths>` over `git add -A` after running agents — they leave stray crop/temp
  files in the worktree root that `-A` will sweep into your commit.)
- **Sync by rebasing onto main.** On a clean (committed) tree: `git rebase main`. It replays
  your commits on top of main's current tip and keeps you on your branch (it does NOT strand
  your worktree). Resolve the (superficial) conflicts and `git rebase --continue` — don't
  `--abort` and start over, don't `reset --hard` to escape. Rebase again whenever `main` moves.
- **If a teammate landed overlapping work, resolve it INSIDE the rebase — never reset-and-reapply.**
  When someone got there first, your `git rebase main` may conflict, or your version may now be
  redundant. The fix is *always* to resolve it within the rebase: keep what's still unique, take
  theirs where they landed it first (`git checkout --theirs <file>` then `git add <file>`), or
  `git rebase --continue` past a commit that rebase has made empty (it drops it for you; use
  `git rebase --skip` if it doesn't). Do **NOT** "reset my branch to main and re-apply only my
  unique contributions" — that is a manual, error-prone reinvention of what rebase already does
  for you (replay *only* your changes on top of their work), it throws away your commits, and it
  is exactly the `reset`-to-dig-out move this section forbids. **No matter how deep the collision
  looks, rebase and resolve — never merge to sync and never reset to escape.** An agent once hit a
  deep second collision, judged the merge "error-prone," and reset-to-main + cherry-picked its
  unique work; that detour is the bug this bullet exists to prevent.
- **Land it when the task is done and tests pass**, holding the merge lock across the whole
  `acquire → rebase → renew+gate → renew+ff-merge → release` sequence (see "Take the merge lock to
  land" above). Because `main` is frozen while you hold the lock, the final
  `git -C <main-checkout> merge --ff-only <your-branch>` is *guaranteed* to fast-forward — no chase.
  The live app reloads and the user validates on 8137. (If you ever ff-merge *without* holding the
  lock and it's rejected because `main` moved, `bin/merge-safe-check` is the fallback: if `main`
  moved only in render-orthogonal files your green run still stands and you can ff-merge as-is;
  otherwise `git rebase main`, re-run the gate, retry. A teammate landed first, nothing more.)
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

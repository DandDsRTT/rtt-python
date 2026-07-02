# RTT — Project Instructions

The RTT monolith is a microtonal/RTT engine with a NiceGUI web front end
(`rtt/app/app.py`). Launch it with `python app.py` (optionally `python app.py <port>`) — but
**agents must pass a port in the 8200+ range, never the bare default** (8137 is the user's; see the
port rule below).

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

## Reuse the app's existing UI assets — search before you hand-roll a control

Before building **any** UI control — a radio, a chooser, a checkbox, a tile, a button, a hover
card, a colored region — **search the codebase for an existing implementation and reuse it.** This
app has a deliberately small, shared vocabulary of widgets (the `rtt-rangemode`/`rtt-rangeopt`
radio used by the chapter-9 nonstandard-domain **approach** control, the shared `gridvalue` editable
cell, the preset `ui.select` choosers, the `rtt-show-item` checkboxes, the tile-feature parts, the
zoom-hover/guide-hover cards, …). A second, hand-rolled version of something we already have is a
**snowflake**: it diverges in styling and behavior, doubles the maintenance, and is exactly the kind
of thing the user has to notice and send back. Hand-rolling a fresh `ui.radio` when
`build_rangemode_radio` already exists is a real example of this failure.

So, as a hard step before writing a new widget:

- **Grep first.** Look for the CSS class, the builder function, the `mark()` name, or a visually
  similar control already in `rtt/app/_page_parts.py`, `rtt/app/building.py`, the `_recon_*` /
  `render_html_*` files, and `rtt/app/assets/rtt.css`. If something close exists, **reuse or extend
  it** (factor a shared helper if two callers now need it) rather than starting fresh.
- Only build a genuinely new widget when nothing reusable exists — and if you must, build it so the
  *next* agent can reuse it (a named helper + a CSS class), not as a one-off.
- If you're unsure whether an existing asset fits, **ask** rather than hand-rolling on a guess.

This complements the mockup rule above: the mockup governs *what* UI exists; this governs *how* you
build it — out of the parts we already have.

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
already installed there, so `.venv/bin/python -m pytest -q` "just works" (~2,530 tests).
Always use `.venv/bin/python` — the bare `python`/`python3` on PATH is system 3.9, too old
for the `numpy`/`scipy`/`sympy`/`nicegui` pins (which need Python ≥ 3.10).

If `.venv/` is ever missing, rebuild it once with a 3.10+ interpreter (this machine has
`/opt/homebrew/bin/python3.14`; `.python-version` pins 3.11.9 to match the Render build):

```bash
/opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Run the fast suite while iterating; CI is the merge gate

Tests live in three folders: **`tests/library/unit/`** (the pure math library — ~1,260 tests,
~10s), **`tests/app/unit/`** (web logic without a live page: Editor / layout / spreadsheet
building), and **`tests/app/integration/`** (cross-layer scenarios run in-process — see the
last section). Convention: a test is *integration* only if it drives multiple layers through a
whole scenario — currently just the two files in `tests/app/integration/`; everything else,
library and app alike, is *unit*, and the library has no integration tests. Place new tests
accordingly.

The full suite is ~2,530 tests, of which **one file is ~67% of the wall-clock**:
`tests/app/integration/test_web_render.py` — in-process page-render tests (NiceGUI's `User`
plugin) that rebuild the whole spreadsheet page and re-run the RTT math on every
`await user.open("/")` (~0.8s each). The other ~2,360 tests — all the library, service, editor and
spreadsheet-layout checks — finish in ~75s. **The merge queue runs the full suite in CI**
(`.github/workflows/merge-gate.yml`); that CI run is *the* merge gate, so you do **not** need to
run the slow render file locally to land. Split your *local* loop accordingly:

- **While iterating, run the fast pass** — skip the one heavy file:
  `.venv/bin/python -m pytest -q --ignore=tests/app/integration/test_web_render.py` (~75s). This is
  your inner-loop feedback on math/service/spreadsheet work.
- **Run the full `.venv/bin/python -m pytest -q` locally only when you want render feedback before
  pushing** (e.g. your change touches `rtt/app/`). It is optional — CI runs it on every PR and
  every queued merge regardless — but a quick local full run can save a round-trip through CI.
- Do **not** add an `-m`/`addopts` default that makes a bare `pytest` silently skip the render
  tests — the user's own runs and CI must stay complete.

## Land by opening a PR — the merge queue gates and merges it

Landing is a **GitHub merge queue**, not a local merge. You never merge into the main checkout,
never hold a lock, never run a render gate to land. You push your branch, open a PR, and enqueue
it; the queue runs the full CI suite on the exact merged result and fast-forwards `main` only when
green. The old bespoke local coordination layer (merge lock, render-gate semaphore, green-token
guard, `bin/land`) has been **deleted** in favor of this — there is no `bin/land`, no
`bin/with-merge-lock`, no `/tmp` ticket queue anymore.

```bash
# from your worktree, on your claude/<name> branch, with your work committed:
git push -u origin HEAD                       # publish your branch
gh pr create --fill --base main               # open the PR
gh pr merge --auto                            # enqueue; the queue lands it when CI is green
                                              # (no --squash: this repo's queue sets its own strategy)
```

Enqueuing is **not** the finish line — **landing on `main` is.** The queue:

- builds the candidate merge of your PR onto the current `main`,
- runs `.github/workflows/merge-gate.yml` (the full suite, including the render file) on that
  candidate,
- fast-forwards `main` only if green; if red, it drops your PR from the queue and reports on the
  PR — fix and re-enqueue.

Because CI validates the *candidate merge* (your branch + the `main` it will land on), you always
land the exact state that was validated — the property the old merge lock hand-built. Serialization
and fairness are the queue's job now; there is no local lock to take and no queue position to watch.

**See the PR through to merge — don't drop the task at `gh pr merge`.** The auto-merge you armed is
not a guarantee: on a fast-moving `main`, your branch routinely goes **`DIRTY`** ("This branch has
conflicts that must be resolved") or gets **dropped from the queue on a red candidate**, and then it
just sits there unmerged forever unless you act. So your task is not finished until `main` actually
contains your commit. **Watch the PR to a terminal state, then act on whatever it became.**

**The watcher must judge BOTH the `merge_group` candidate run AND the PR's own checks — keying on
either one alone is blind.** Two different failures each leave the PR sitting unmerged forever, and
they surface in *different* places:

- A **candidate (`merge_group`) failure.** The queue builds a synthetic candidate branch
  (`gh-readonly-queue/main/pr-N-<sha>` = your PR merged onto current `main`) and runs the gate on it.
  Its pass/fail **never appears in `gh pr checks`**. When it fails, the queue drops the PR and
  un-arms auto-merge, leaving it OPEN with green PR-checks, "merge when ready" forever. A watcher
  polling only `gh pr checks` is blind to this.
- A **PR-event check failure.** This repo *also* runs the full suite as a `pull_request` check
  (`full-suite`), which **does** appear in `gh pr checks`. When it fails (e.g. a teammate's just-
  landed change added a test your branch now breaks — surfaced because the check tests your branch
  *merged with main*), the PR goes **`BLOCKED`** (not `DIRTY`), never enters the queue, and
  auto-merge stays armed but **never fires**. A watcher keyed only on the `merge_group` run is blind
  to THIS: no candidate run is ever created, so it loops forever (a real lapse this has caused — an
  agent waited on a merge that a failed `full-suite` had already doomed). `BLOCKED` is also the
  normal state while a required check is still *pending*, so distinguish: exit only on a check whose
  state is actually `fail`, not merely on `BLOCKED`.

So watch both — exit on a failed PR-event check OR a failed candidate run OR `DIRTY` OR a terminal
PR state:

```bash
# Run in the background. Exits — and re-engages you — ONLY when there's something to do:
#   0  merged             → report "PR #N merged" once, then stop
#   10 conflicts(DIRTY)   → rebase onto main, push --force-with-lease, re-enqueue, re-arm
#   11 candidate failed   → read the merge_group run log, fix, push, re-enqueue, re-arm
#   12 closed             → unexpected; surface to the user
#   13 PR check failed    → read the failing pull_request run log, fix, push (auto-merge stays armed)
pr=$(gh pr view --json number -q .number)
mg() { gh run list --event merge_group --limit 20 --json databaseId,status,conclusion,headBranch \
  -q "[.[]|select(.headBranch|contains(\"pr-$pr-\"))]|sort_by(.databaseId)|last|\"\(.databaseId) \(.conclusion//\"none\")\""; }
base=$(mg); base=${base%% *}; base=${base:-0}   # ignore candidate runs from superseded fixes
while :; do
  st=$(gh pr view "$pr" --json state -q .state)
  [ "$st" = MERGED ] && exit 0
  [ "$st" = CLOSED ] && exit 12
  [ "$(gh pr view "$pr" --json mergeStateStatus -q .mergeStateStatus)" = DIRTY ] && exit 10
  # a PR-event required check that has actually concluded `fail` (NOT merely pending/BLOCKED):
  if gh pr checks "$pr" 2>/dev/null | grep -qiw fail; then exit 13; fi
  latest=$(mg); rid=${latest%% *}
  if [ -n "$rid" ] && [ "${rid:-0}" -gt "$base" ] 2>/dev/null; then
    case "$latest" in *failure) exit 11;; esac
  fi
  sleep 45
done
```

When the watcher exits, do the matching action; for the DIRTY / candidate-fail / PR-check-fail cases
**fix and re-push, then re-arm it** (recompute `base` first) — loop until the PR is genuinely merged.
For exit 13 the fix is the same shape as a candidate fail: read the failing run
(`gh run view <id> --log-failed`), fix, push (`--force-with-lease` after a rebase); auto-merge is
still armed, so no re-enqueue is needed unless it also got dequeued. Break silence only to report the
merge or ask a decision you genuinely can't make.

**Resolving a `DIRTY` or candidate-failed PR.** A candidate fails for one of two reasons, both fixed
by rebase-and-repush so the queue re-validates a fresh candidate:
- **A `git` conflict (`DIRTY`)** — `main` moved under you.
- **Concurrent-`main` drift your branch never saw** — the candidate is `your branch + current main`,
  so a teammate's just-landed change can break it even when your branch is green in isolation (e.g.
  they added a file the doc-policy gate now flags, or changed a count an exact gate pins). Read the
  failing `merge_group` run (`gh run view <id> --log-failed`) — the fix is usually one more line.

```bash
git rebase main                    # resolve any conflicts INSIDE the rebase; never reset to escape
# ...apply the one-line fix the candidate log demanded, if any...
git push --force-with-lease        # REJECTED while the PR is still queued — dequeue first (below)
gh pr merge --auto                 # re-enqueue. Use --auto ALONE: --merge/--squash trip
                                   # "merge strategy is set by the merge queue" and may NOT enqueue.
```

**To update a branch that is still in the queue you must dequeue it first** — a `push
--force-with-lease` is rejected ("protected branch hook declined") while queued. Remove it, then
push and re-enqueue:

```bash
gh api graphql -f query='mutation($id:ID!){dequeuePullRequest(input:{id:$id}){mergeQueueEntry{position}}}' \
  -f id="$(gh pr view "$pr" --json id -q .id)"
```

**Clean up your branch once the PR is terminal.** A `claude/<name>` branch is throwaway — it exists
only to carry one PR. So as the final step after the PR reaches a terminal state (**merged**, or you
**closed** it), delete its **remote** branch so the remote doesn't fill up with dead `claude/*`
heads. Do it idempotently — the merge queue may already have auto-deleted the head branch on merge:

```bash
git ls-remote --exit-code origin "$br" >/dev/null 2>&1 \
  && git push origin --delete "$br"          # $br = your claude/<name>; skip if already gone
```

**Verify a real merge before you delete — deleting an OPEN PR's head branch AUTO-CLOSES it
unmerged.** `git push origin --delete "$br"` on a PR that has NOT actually merged does not just fail
to confirm the merge — it closes the still-open PR, and your work silently never ships (this
happened: a masked watcher exit code was read as "merged", the delete auto-closed the open PR, and
the agent reported success). So gate the delete on a POSITIVE merge check, never on a watcher exit
code or a task-notification alone (a `bash pr-watch.sh; echo EXIT=$?` wrapper makes the notification
always report exit 0 — run the watcher bare and read its output file):

```bash
gh pr view "$pr" --json state,mergedAt -q '.state + " " + (.mergedAt // "null")'
# proceed to delete ONLY when this prints "MERGED <timestamp>" (state MERGED and mergedAt non-null).
# Anything else (OPEN/CLOSED, or mergedAt null) means it did NOT merge — do not delete, do not report merged.
```

Don't try to delete the **local** branch or tear down the **worktree** you're running in — you're
checked out on that branch, and the worktree is your live workspace; leaving those for the user /
orchestrator to reap is correct. Cleanup is the remote branch only, and only after terminal — never
delete a branch whose PR is still open or in the queue.

**The user refreshes their own 8137 app.** Landing now happens on the remote `main`, not the local
main checkout, so the user's `python app.py` on 8137 no longer auto-updates when you land — that is
**by design**. The user pulls when they want to see new work (`git -C <main-checkout> pull`), or
uses the deployed `danddsrtt-app.onrender.com`. You never touch their checkout.

**Previewing UNLANDED branch work for the user.** Under the old flow agents merged to the local main
and the user saw the change on 8137 before it went remote; the merge queue removes that — your work
sits on a `claude/<name>` branch in your worktree, which the user **cannot** `git checkout` (it is
"already used by worktree …") and which their 8137 never shows. So when the user wants to *see* a
change before it lands, **launch the app from your worktree on a 8200+ port and hand them the
`http://localhost:<port>/` URL** — this is the sanctioned way for the user to view branch work, not
just for your own verification. Launch it with `reload=False` (set `PORT=<port>` in the env, which
takes the hosted-mode `ui.run` path — bare `app.py <port>` turns hot-reload ON, which the port rule
below bans for agent launches). It is a long-lived server the user drives, so start it in the
background and leave it up; never use 8137/8188/8189 (see the port section). This does **not** relax
"never launch on 8137" — it is an explicit case of the existing 8200+ rule, now also serving the user.

## "Spawn an agent" / "break this out" means a TASK CHIP — never a hidden subagent

When the user asks you to **spawn an agent**, **break out** unrelated work, or **hand something off
to a separate agent** to be handled on its own, create a **task chip** with `spawn_task`
(`mcp__ccd_session__spawn_task`). The chip is what the user expects: they click it to open an
**independent, interactive session** (its own worktree) that they can read and steer themselves.
Write the chip a full, self-contained brief — the spawned session has none of this conversation's
context.

Do **NOT** fulfill such a request with the **`Agent` tool**. That tool launches a *background
subagent that runs inside your session, reports only to you, and is invisible and un-steerable to the
user* — the opposite of what "spawn an agent" means here. Never silently use a background `Agent`
subagent to carry out user-facing delegated work or to write/land code on the user's behalf. The
`Agent` tool is only for **your own** internal sub-tasks whose result *you* consume (read-only
exploration, a quick search) — not for breaking off a stream of work the user wants to own.

Two more reasons the background-`Agent` path is actively wrong for code work here: (1) a subagent
working in a worktree trips the **concurrent-worktree sync race** — its *uncommitted* edits bleed
into your worktree and get committed under your branch, corrupting both (this has happened); (2) you
cannot honestly report its status, because it lands PRs you can't see. If you ever believe a
background `Agent` subagent is genuinely the right tool for something user-facing, **ask first** —
never just do it.

## Changed a workflow rule? Hand the user a broadcast for in-flight agents

This file is loaded into an agent's context **at spawn**. So an edit here reaches every *newly*
spawned agent automatically — but the agents **already running** still hold the old text and will not
re-read this file on their own. A workflow change therefore silently misses exactly the mid-task
agents who most need it (they'll keep landing the old way until their next spawn).

So whenever you change a **workflow/process rule** other agents act on — how work lands, how to sync
with `main`, which ports to use, the dev/test loop, anything procedural in this file — **also end
your turn with a short, paste-ready broadcast the user can forward to currently-running agents.**
Emit it as raw markdown inside a fenced ` ```markdown ` code block (so headers/lists survive the
copy-paste), and make it state: what changed, what to do differently now, and which CLAUDE.md
section to re-read. Keep it to the delta — not a re-explanation of the whole workflow. This applies
to *process* changes only; a pure code/feature change needs no broadcast.

**One-time setup (already required for the flow above):** `gh` must be installed and authenticated
on this machine (`brew install gh && gh auth login`), and the merge queue + branch protection must
be enabled on `main` in GitHub. See `MERGE_QUEUE_MIGRATION.md`.

## Git: rebase onto main — the RTT specifics

The cross-project git flow — commit as you go, sync by **rebasing** onto `main` (never merge),
resolve overlap *inside* the rebase (never reset-and-reapply), and never `reset --soft/--hard main`
or `stash`/`clean -fd` to tidy or escape — lives in the global `CLAUDE.md`; follow it. What's
specific to this repo:

- **Never write to the main checkout — ever.** Landing is on the remote queue, so nothing you do
  should touch it. Don't `git checkout`/`switch`/`reset`/`rebase` there or hand-edit it — it's the
  live app the user runs on 8137, and a stray `git checkout <commit>` *detaches the running app's
  HEAD* and hides everyone's landed work (this has bitten us). Two hooks enforce it. Inspect other
  branches read-only (`git -C <main> show/diff/log`); build in your own worktree (it already has
  your commit).
- **Never hand subagents / Workflow agents the main-checkout path.** Give them THIS worktree as
  cwd and tell them explicitly: read-only git, never `cd` into or `checkout`/`reset` the main
  checkout, validate by in-process builds here. (A review agent once `cd`'d in to "validate" a
  branch, ran `git checkout`, and detached the live app.) Prefer targeted `git add <paths>` over
  `git add -A` after running agents — they leave stray crop/temp files that `-A` would sweep in.
- **Just report the task + its PR** — not the 8200+ port you tested on, not branch/worktree
  mechanics, and not `main`-vs-`origin` push status beyond whether the PR landed.

## Web app port: 8137 is the user's — agents launch on their own port

Port **8137** belongs to the **human user**: they keep `python app.py` running there to
actually use the app. It is also the app's canonical default (`rtt.app.app.main()`), which
`tests/app/unit/test_web_app_smoke.py` locks — keep that green. Do **not** change the default.

**Never launch a server on 8137 yourself.** When any agent starts the app to verify a
change — `python app.py`, an ad-hoc `ui.run(port=...)`, a preview/run harness, or an
integration test — a second instance on 8137 collides with the user's running session and
refreshes their browser constantly, making the app unusable for them. This is the single
biggest way agents disrupt the user. So, for **every** agent-initiated launch:

- **Pick a port and PROVE it's free BEFORE you bind — this is a hard gate, run it every
  launch.** Default to the **8200+** range, one per worktree so parallel sessions don't fight.
  **Never 8137** (the user's), **never 8188** (reserved for **ComfyUI** in the sibling
  Origenerator project — squatting it 404s ComfyUI's clients and breaks its websocket), and
  **avoid 8189** (one fat-finger from 8188). Then run the LISTEN check below and read it: if
  **anything** is already listening, that port is a **sibling agent's or the user's server** —
  **pick a different port and NEVER kill what's there to make room.** Do not "reuse" an occupied
  port on the assumption it's a stale instance of your own; you cannot tell from the port whose it
  is.
- **Pass `reload=False`.** Hot-reload watches the whole repo tree — worktrees included — so
  a `reload=True` agent instance churns on every edit (yours and other agents') and orphans
  workers that keep the port bound. Agents relaunch deliberately; they don't need reload.
  (reload=False also keeps the server a single process, so the PID you capture at launch — below —
  is the exact one holding the port.)

**Never kill a server you did not start — this has knocked over sibling agents' servers twice.**
Two patterns cause it, both banned:

1. **Broad kills.** **Never** run `pkill -f app.py`, `pkill -f python`, `killall python`,
   `pkill -f rtt`, or any match not pinned to one port — a broad match murders everyone else's app.
2. **Killing a port to "free" it.** **Never** run `lsof -ti tcp:<port> | xargs kill` to reclaim a
   port for your own launch. `lsof` cannot tell you *whose* server is on that port, so this kills a
   sibling agent's or the user's server the moment your assumption "that port is mine" is wrong (it
   was, twice). If the port you wanted is occupied, the fix is **a different port, never a kill.**

To restart **your own** server, kill the **PID you recorded when you launched it** — never a PID
rediscovered from the port:

```bash
# 1. PROVE the port is free (empty output = free). If it prints a row, pick another port — do NOT kill it.
lsof -nP -iTCP:<port> -sTCP:LISTEN
# 2. Launch detached (survives your turn ending) and RECORD your own PID:
nohup env PORT=<port> PYTHONPATH="$PWD" .venv/bin/python rtt/app/app.py > <log> 2>&1 < /dev/null & disown
echo $! > <log>.pid
# 3. CONFIRM *your* process bound — a curl 200 alone does NOT (it may be the server you collided
#    with). Trust the log: "NiceGUI ready" present AND "address already in use" absent.
grep -q "NiceGUI ready" <log> && ! grep -q "address already in use" <log> && echo BOUND || echo "DID NOT BIND — do not kill anything; pick another port and relaunch"
# 4. To stop/restart ONLY your own server later:
kill "$(cat <log>.pid)"
```

(`setsid` is unavailable on macOS — use `nohup … & disown`.) Never block the launch tool waiting on
the server; run the `grep`/`curl` liveness check as a *separate* command, or the launch can hang to
its timeout. And if step 3 says DID NOT BIND, your launch collided with an existing server — **leave
it alone**, pick a fresh verified-free port, and relaunch there.

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

# Workflow consolidation analysis — how much coordination code is deletable by fixing root causes

*Analysis only. This document changes nothing in `bin/`, `CLAUDE.md`, or the gate code. It is
a design deliverable for the human to review and decide on.*

## TL;DR

The repo carries roughly **4,200 lines of bespoke multi-agent coordination code** — ~3,670
lines across `bin/` (everything but `bin/lint`) plus the 530-line render-gate
`tests/app/integration/conftest.py` — and ~340 lines of protocol prose in `CLAUDE.md`
(lines 127–469). Almost none of it is essential complexity. It exists because of **three
fixable root causes**, and they are nested: the outermost fix dissolves the inner two.

| Root cause | What it forces into existence | Deletable LOC if fixed |
|---|---|---|
| **1. Hardware oversubscription** (12–18 CPU-bound agents on 6 cores) | load admission, orphan reaping, SIGKILL survival, the heartbeat/stuck-holder/load-gated-bypass half of the render gate, process-group teardown | **~1,050** |
| **2. Slow merge gate** (`test_web_render.py` ≈ 67% of suite wall-clock) | the render-gate semaphore itself; makes the merge lock painful enough to need the whole optimistic-lock dance | unblocks #1 and #3; ~0 deleted directly, but halving runtime ≈ halving contention |
| **3. Hand-rolled merge queue** (lock + green-token + FIFO tickets + ff-merge guard) | a from-scratch reimplementation of GitHub Merge Queue / Mergify | **~2,900** |
| *(4. Agent-reliability guardrails — NOT coordination)* | "don't `reset --hard`", "don't `pkill` siblings", "don't detach main", "don't invent UI" | keep, but move enforcement to hooks |

**The single highest-leverage move is to move the merge gate off the dev box** (CI + a hosted
merge queue). That one change attacks causes 1, 2, and 3 at once: nothing CPU-heavy runs on the
6-core box anymore (cause 1 evaporates), the gate's wall-clock stops blocking local agents
(cause 2 stops mattering locally), and the queue/serialization/green-evidence problem is handed
to a service built for it (cause 3). It would let the repo **delete ~3,900 of the ~4,200 lines**.

---

## Root cause 1 — Hardware oversubscription

### The evidence is already written down

`RESOURCE_GOVERNANCE_DIAGNOSIS.md:13-29` captures it live: `loadavg 35.82` on 6 cores (~6×
oversubscribed), **14 concurrent `bin/land` processes** where ~3 were intended, two orphaned
land trees alive >10 min, and ~68 MB free RAM driving exit-137 OOM kills. Every mechanism below
exists *only* because the box is saturated — none of it would be written for a 3-agents-on-6-cores
world, and none is needed if the heavy work doesn't run on the dev box at all.

### What exists purely for saturation

- **`bin/gate-load` (171 lines)** — machine-wide admission governor. Its own header
  (`bin/gate-load:5-10`) says it exists because "the TOTAL concurrent CPU/memory load on the box
  is unbounded, which is how a 6-core machine reached loadavg 35." `cmd_wait` (`:126-143`) blocks
  a new suite until `loadavg/core < RTT_GATE_ADMIT_MAXLOAD` (default 2.0) and free memory is
  above a floor. **100% saturation-driven.**

- **`bin/reap-orphan-gates` (229 lines)** — sweeps `pytest`/`bin/land` trees that OOM-SIGKILL
  reparented to PID 1 (`:1-14`). The "self-feeding leak" it fixes (`:7-13`) only happens because
  the OS is killing heavy processes under memory pressure. With adequate capacity nothing gets
  SIGKILLed, nothing orphans, and the PPID-1 sweeper has nothing to sweep. **100%
  saturation-driven.**

- **`bin/persistent-land` (110 lines)** — relaunch-until-landed wrapper. Its sole reason to exist
  (`bin/persistent-land:7-13`): "the OS SIGKILLs heavy processes under memory pressure (exit 137)
  … so a `bin/land` can die mid-gate and NOTHING relaunches it." Remove the memory pressure and a
  single `bin/land` invocation suffices. **100% saturation-driven.**

- **`bin/governance-selftest` (243 lines)** — tests the three above. Deletable with them.

- **The saturation half of `tests/app/integration/conftest.py`** (~200 of 530 lines). The file's
  *purpose* — a counting semaphore so render runs "take turns" (`conftest.py:1-12`) — is itself a
  pure saturation artifact: "a handful of simultaneous runs pins every core and *nobody* finishes."
  With cores to spare you would run the render suite N-ways parallel, not 1-at-a-time. Specifically
  saturation-only:
  - heartbeat + stuck-holder bypass: `_take_slot` (`:315-318`), `_classify` (`:284-312`),
    `pytest_runtest_logstart/logreport` progress stamping (`:520-525`)
  - load-gated bypass: `_bypass_allowed` (`:260-270`), `_proceed_at_cap` (`:273-281`) and their
    long rationale comments (`:53-70`, `:115-124`)
  - orphan reaping at gate entry: `_reap_orphans` (`:321-328`)
  - machine-wide admission shim: `_admit` (`:331-341`)
  - the merge-lock-holder priority slot: `_my_merge_lock_id` (`:177-192`), `_holds_merge_lock`
    (`:195-215`), the priority branch in `_acquire` (`:355-362`) — this is a *priority inversion*
    fix (`:72-84`) that only bites because the gate is slow AND the slot is contended.

- **Process-group teardown in `bin/land` (`:72-137`)** — `_active_groups`, `_killpg`,
  `_run_managed`, `_install_signal_cleanup`, `_reap_orphans`. Exists to prevent the orphan leak
  (`bin/land:67-71`). Saturation-driven.

### What becomes deletable

If the heavy gate no longer runs on the contended box (move it to CI — see the recommended
sequence) **or** the box simply has enough cores for the agent count:

| Delete | LOC |
|---|---|
| `bin/gate-load` | 171 |
| `bin/reap-orphan-gates` | 229 |
| `bin/persistent-land` | 110 |
| `bin/governance-selftest` | 243 |
| conftest saturation logic (heartbeat/bypass/admit/reap/priority) | ~200 |
| `bin/land` process-group + reap machinery (`:72-137`) | ~65 |
| **Subtotal** | **~1,020** |

Plus the `CLAUDE.md` prose that documents all of it: the render-gate semaphore description and the
"queue wait is NORMAL / never NOLOCK / evict a wedged holder" sections (`CLAUDE.md:160-198`,
`382-434`) — another ~150 lines of protocol the human currently has to keep in their head.

**Effort:** Low if the lever is "buy/rent more cores" (delete-only, no code to write). Medium if
the lever is "move the gate to CI," because the green-evidence path (cause 3) has to move with it.
**Risk:** Low. This code is all *governance layered on top of* correctness
(`RESOURCE_GOVERNANCE_DIAGNOSIS.md:94-102` is explicit that none of it changes what serializes or
what may merge). Deleting it cannot corrupt `main`; the worst case is the contention it was
papering over, which is exactly what the hardware/CI fix removes.

---

## Root cause 2 — The merge gate is slow

### The 67% is real and structural

`tests/app/integration/test_web_render.py` is ~67% of suite wall-clock
(`CLAUDE.md:138-140`). The file now holds **242 `async def test_` functions and 183
`user.open(...)` calls** (the "171" figure in `conftest.py:5` and `CLAUDE.md:139` is stale and
worth refreshing). Each NiceGUI `User`-plugin test is **function-scoped**, so every
`await user.open("/")` rebuilds the *entire* spreadsheet page and re-runs the full RTT solve from
scratch (`test_web_render.py:1-13`) — ~0.8 s each, ~150 s of pure rebuild.

The merge lock is only painful *because* it serializes (or is held across) this slow gate.
`MERGE_CONCURRENCY_ANALYSIS.md:51-62` says it directly: "The remaining structural cost is the
serialization itself… the merge lock's extra job is only 'no one lands between my gate finishing
and my ff-merge.' That window is seconds." The gate's *duration* is what turns a seconds-long
critical section into a minutes-long queue.

### Concrete speedups (in rough order of payoff)

1. **Build the page once per parameter-family, assert many times.** Most render tests open `/`,
   toggle one Show feature, and assert one cell. They are 242 separate page builds that share an
   identical base build. `test_enabling_a_feature_renders_its_cell` is *already* parametrized
   (`test_web_render.py:165-166`) but still rebuilds per case. Collapsing read-only assertions onto
   a small number of shared built pages (session- or module-scoped fixtures returning a built page;
   `copy.deepcopy` the state for the few mutating cases) could cut builds from ~242 to a few dozen.
   **Biggest single win; medium effort** (the `User` fixture is function-scoped by NiceGUI design,
   so this needs a deliberate shared-page harness, not just a scope bump).

2. **`pytest-xdist`.** Not currently pinned (`requirements.txt` has no xdist). `-n auto` would
   parallelize the 242 cases — but *only* helps if cores exist, which is exactly what cause 1
   denies locally. xdist is the right tool **once the gate runs in CI** (dedicated runners), not on
   the shared dev box. **Low effort, but gated on causes 1/3.**

3. **Memoize the RTT solve across cases.** The default-document solve is identical for every test
   that doesn't edit the temperament; caching it removes the redundant math from ~all read-only
   cases. **Medium effort, medium risk** (must not leak frozen state between tests — see the memory
   note that render tests evict `rtt.*` modules and break frozen-dataclass `==`).

4. **Split the render gate to CI entirely.** Keep the fast pass (~75 s, `CLAUDE.md:163-165`) as the
   local inner loop; make the 242 render rebuilds a *required CI check* rather than a local
   pre-merge gate. This is the structural fix and it overlaps with the recommended sequence below.

### What halving the gate buys

Halving render runtime roughly halves the merge-lock hold time and the render-gate queue depth,
which compounds: shorter holds → shallower queue → fewer chases/relaunches → less of cause 1's
load. It doesn't delete code by itself, but it removes the *pressure* that justified
`persistent-land`, the stuck-holder bypass, and the priority-slot inversion fix. **Effort:**
Medium for #1/#3, Low for #2 (once cores exist). **Risk:** Low–Medium — shared-page fixtures can
mask state-bleed bugs the per-build isolation currently catches, so the harness needs careful
teardown.

---

## Root cause 3 — The hand-rolled merge queue is a reimplementation of off-the-shelf infra

This is the largest bucket: ~2,900 lines. The lock + green-token + FIFO-ticket + ff-merge-guard
stack is, component for component, **GitHub Merge Queue / Mergify**. Every correctness property it
hand-builds is a property those services provide as a managed primitive.

### Component-by-component mapping

| Bespoke component | LOC | What it does | Off-the-shelf equivalent | Correctness property |
|---|---|---|---|---|
| `bin/with-merge-lock` | 1,114 | exclusive single-holder lock; lease-renewing detached daemon; FIFO tickets; 4-layer self-heal; `evict` | Merge Queue's serialized queue / Mergify queue | **mutual exclusion + fairness** (one lander at a time, FIFO) |
| `bin/with-merge-lock-selftest` | 527 | proves the daemon/lease/takeover logic | the provider tests their own queue | — |
| `bin/land` | 327 | optimistic short-lock: validate lockless, lock only for ff-merge, chase on render-relevant moves | Merge Queue speculative batching | **validate-exact-landed-tree** |
| `bin/land-selftest` | 214 | proves the land state machine | — | — |
| `bin/merge-green-check` | 132 | "did the full gate run green on *this exact tree*?" | required status check on the queue's test branch | **validate-exact-landed-tree** |
| `bin/merge-guard-hook` | 115 | `reference-transaction` hook vetoing an ungated ff-merge | branch protection: "require status checks to pass before merging" | **fail-closed** (no red tree reaches main) |
| `bin/install-merge-guard-hook` | 119 | installs the hook into the shared hooks dir | N/A (server-side, nothing to install) | — |
| `bin/merge-guard-selftest` | 218 | proves the guard rejects ungated/stale trees | — | — |
| `bin/merge-safe-check` | 113 | "did main move only in render-orthogonal files?" | path-filtered required checks (`paths-ignore`) | optimization, not safety |
| `bin/_render_relevance.py` | 42 | the orthogonal-files whitelist | `paths`/`paths-ignore` in the workflow | optimization |
| green-token minting in `conftest.py` (`_mint_green_token` `:470-506`, `_clean_tree_sha` `:445-453`, `_prune_green` `:456-467`) | ~60 | mints the tree-keyed green token the guard consults | the CI run *is* the evidence — keyed to the commit by the provider | **fail-closed + validate-exact-tree** |
| **Total** | **~2,980** | | | |

The key realization, stated in the repo's own analysis: the merge lock exists because *the gate
runs locally and agents race to ff-merge* (`bin/with-merge-lock:3-15`). A hosted merge queue
**owns the test-and-merge step**, so there is no race to serialize, no token to mint, no hook to
install, and no "validate the exact tree" hole to close — the queue tests the candidate merge
commit and fast-forwards only that. The green-token guard
(`green-token-ffmerge-guard` in memory; `bin/merge-guard-hook`) is a from-scratch rebuild of
"required status checks," and `merge-safe-check`/`_render_relevance` is a from-scratch rebuild of
`paths-ignore`.

### What becomes deletable

If `main` is protected by branch protection + a merge queue (GitHub native or Mergify):

- Delete all 11 components above (~2,980 lines).
- Delete the green-token minting from `conftest.py` (~60 lines).
- Delete the `CLAUDE.md` merge-protocol prose: "Take the merge lock to land" through "The
  green-gate guard" (`CLAUDE.md:199-469`) — the entire ~270-line landing protocol the human
  currently maintains collapses to "push your branch; the queue lands it."

**Effort:** Medium. The mechanism is a managed service, but the migration is real: enable branch
protection, define the required check, point agents at "push + enqueue" instead of `bin/land`. The
subtlety is that agents currently *merge into a local main checkout the user runs live on 8137* —
a merge queue lands on the **remote**, so the local "live app reloads on ff-merge" workflow
(`CLAUDE.md:470-532`) changes shape (the user would pull, or run against the remote). That's the
main design question to resolve, not a code problem.
**Risk:** Low for `main`'s integrity (the provider's queue is at least as safe as `--ff-only` +
hand-rolled lease daemon — and the repo has *already been bitten* by the hand-rolled version: a
~55-min wedged-but-alive holder, `MERGE_CONCURRENCY_ANALYSIS.md:9-16`, and the green-token hole
that let a red tooltip change land, `bin/merge-green-check:8-14`). Risk is in the **workflow
change** for the local-live-app habit, not in correctness.

---

## Category 4 — Agent-reliability guardrails (NOT coordination architecture)

These are not distributed-systems machinery. They compensate for *destructive agent behavior* —
an agent doing something a careful human never would. They should be kept, but they belong in
**hooks (mechanical enforcement)**, not in prose an agent may skim past:

- "Never `git reset --soft/--hard main`, `clean -fd`, `stash` to tidy" (`CLAUDE.md` global +
  project git sections) — *already* enforced by `git-rebase-guard.sh` PreToolUse hook
  (`rebase-always-no-merge-task` in memory). Good model: the prose explains, the hook enforces.
- "Never `git checkout`/`reset` the main checkout; never edit it" (`CLAUDE.md:474-491`) — *already*
  enforced by the global worktree-guard hooks (`global-worktree-guard-hook` in memory).
- "Don't `pkill` sibling agents' runs to jump the queue" (`CLAUDE.md:175-180`, `420-426`) — prose
  only. **Recommend a hook** (or, better, removing the *reason* to want to: a hosted queue has no
  local processes to kill).
- "Don't invent UI not in the mockup" (`CLAUDE.md:6-66`) — domain guardrail, inherently prose
  (a hook can't diff against a PNG mockup). Keep as prose; it's the one category that genuinely
  can't be mechanized.
- "Never write 'honest'", port 8137 rules, "no comments/docstrings" — same: behavioral, keep as
  prose or lint where mechanizable (the no-comments rule is already partly a lint concern).

**Recommendation:** wherever a guardrail is *mechanizable* (git operations, file targets,
process kills), move enforcement into a hook and keep one sentence of prose pointing at it. The
prose-only guardrails that have already become hooks (reset, worktree, rebase) are the proof this
works — and crucially, **these survive all three root-cause fixes**: even with a perfect merge
queue and infinite cores, you still don't want an agent detaching the live checkout. Don't let the
consolidation sweep them away; they are orthogonal to the coordination problem.

---

## Recommended sequence (highest leverage first)

1. **Move the merge gate off the dev box → CI + a hosted merge queue.** *This is the keystone.* It
   attacks all three causes simultaneously: no heavy work on the 6-core box (cause 1 dissolves),
   the gate's wall-clock stops blocking local agents (cause 2 stops mattering locally), and the
   queue replaces the entire hand-rolled lock/token/guard stack (cause 3). Resolve one design
   question first — how the user keeps their live-on-8137 workflow when landing moves to the remote.
   **Deletes ~3,900 of ~4,200 lines** (cause-1 governance + cause-3 queue + most of the
   `CLAUDE.md` protocol). Effort: Medium. Risk: Low for `main`; the real work is the workflow
   change.

2. **If keeping the gate local for now: speed it up first (cause 2).** Shared-page fixtures /
   solve memoization (#1, #3 above) to cut the 242 rebuilds, then `pytest-xdist`. Halving runtime
   halves contention and removes the *pressure* that justifies `persistent-land`, the stuck-holder
   bypass, and the priority-slot inversion fix — making their later deletion safe. Effort: Medium.
   Risk: Low–Medium (state-bleed in shared fixtures).

3. **Then collapse the saturation governance (cause 1).** Once the gate is in CI *or* fast enough
   that local concurrency stops thrashing, delete `gate-load`, `reap-orphan-gates`,
   `persistent-land`, `governance-selftest`, the conftest bypass/admit/priority logic, and
   `bin/land`'s process-group machinery (~1,020 lines + ~150 prose). Effort: Low (delete-only).
   Risk: Low.

4. **Migrate the remaining guardrails to hooks (category 4).** Independent of 1–3; do anytime.
   Convert the mechanizable prose rules (`pkill` siblings, any remaining git footguns) to hooks;
   keep the domain rules (mockup, naming) as prose. Effort: Low. Risk: Low.

**Why this order:** step 1 makes 3 and most of 2 unnecessary, so doing it first avoids investing in
optimizations (shared fixtures, xdist) that a CI move would partly obsolete. If step 1 is blocked
on the local-live-app design question, fall back to step 2 → 3, which delivers the cause-1
deletions without touching the merge model. Step 4 is orthogonal and survives every other fix.

### Stopping point

The irreducible core after all four steps is small: the fast unit/library suite, the
`_render_relevance` whitelist *if* kept as a CI `paths-ignore` filter (~42 lines, or zero if
expressed natively in the workflow), the domain guardrails as prose, and the mechanizable
guardrails as hooks. The ~4,200 lines of homegrown distributed-systems code is **accidental
complexity** standing in for two purchases (more cores / CI minutes) and one managed service (a
merge queue) — not essential to what this repo is building.

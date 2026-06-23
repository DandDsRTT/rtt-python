# Multi-agent test/land resource governance — diagnosis & fixes

The land/render-gate machinery is *correct* (FIFO-fair merge lock, atomic `--ff-only`,
tree-keyed green-token guard). What it lacked is **resource governance**: nothing cleaned up
the heavy `pytest` process trees a killed/abandoned run leaves behind, and nothing kept the
*total* concurrent CPU/memory load under the box's capacity. On a 6-core machine with only
~3 intended agents, this let load average climb to 9.45–33 with ~17 concurrent python
processes and SIGKILLs (exit 137) under memory pressure. This document records the three root
causes (with live evidence captured on this machine), then the fixes.

## Evidence (captured live, 6-core box)

```
$ sysctl -n vm.loadavg hw.ncpu
{ 35.82 18.88 13.82 }          # 1-min loadavg 35.82 on 6 cores  → ~6× oversubscribed
6

$ ps -axo pid=,ppid=,command= | grep -c bin/land
14                              # 14 concurrent bin/land processes (intended: ~3)

$ ps -axo pid=,ppid=,etime=,command= | awk '$2==1 && /bin\/land/'
13564  1  10:46  ...Python bin/land -- .../.venv/bin/python -m pytest -q
13696  1  10:37  ...Python bin/land -- .../.venv/bin/python -m pytest -q
                                # TWO orphaned land trees (PPID 1), each alive >10 min,
                                # each still driving a full render suite child (13593, 13725)

$ vm_stat | head
Pages free: 4180.  (page size 16384)  → ~68 MB free   # memory exhausted → exit-137 kills
```

The render-gate ticket dir confirms the orphans still occupy slots:

```
/tmp/rtt-render-gate.d/
  1782244161714945000-13593      # ticket for orphan #1's pytest child — PID alive
  1782244172259795000-13725      # ticket for orphan #2's pytest child — PID alive
```

Because those PIDs are *alive* (just reparented), `conftest._scan()` keeps their tickets —
`_scan` only reclaims **dead** PIDs — so each dead-work suite counts as a live render slot.

## Cause 1 (primary): orphaned gate process trees — a self-feeding leak

When a land or its render gate is killed — by the harness (over-time background job), a user
TaskStop, a timeout, or the OS OOM killer under memory pressure — the `pytest` child is **not**
cleaned up. It reparents to PID 1 and keeps running a full 171-page in-process render suite
(very CPU/RAM heavy). It is now invisible to the gate's own accounting in two ways:

- its render-gate ticket's PID is alive, so `_scan()` never reclaims it → it pins a slot;
- it has no live parent to ever kill it.

Over a session of stop/relaunch cycles these accumulate (2 observed above, each >10 min old).
So "3 agents" becomes 10–17 concurrent heavy processes → load spike → more get OOM-killed →
more orphans. A self-feeding leak.

**Root reason:** neither `bin/land`, `bin/with-merge-lock` (legacy wrapped-command path), nor
the gate runner put their child in a kill-on-exit process group, and nothing ever swept the
orphans a hard SIGKILL inevitably leaves behind. (The render tests are *in-process* — no
grandchild subprocesses — so the only thing that leaks is the `pytest` process itself plus its
launcher; cleaning those two is sufficient.)

**Fix:** §b process-group cleanup in the launchers + §c an orphan sweeper.

## Cause 2: render-gate bypass dogpile, re-triggerable on a stale base

The stuck-holder bypass (a stale heartbeat → next waiter reuses the slot) was made
load-gated in `176da4dc` (`RTT_RENDER_GATE_BYPASS_MAXLOAD`): under saturation a stale
heartbeat means *starved*, not *hung*, so bypassing just starts a 2nd CPU-bound suite, which
starves both further → both miss heartbeats → a 3rd starts… the self-feeding pile-up that
once pinned load at 33. That governor lives in `tests/app/integration/conftest.py`, which each
agent runs **from its own worktree** — so an agent on a base *older* than `176da4dc` runs the
old, ungoverned conftest and can re-trigger the dogpile.

**Fix (§d):** the dogpile is hardest to re-trigger from the sanctioned path because `bin/land`
**rebases onto `main` before it ever runs the gate**, so the gate always executes the current
conftest. We harden the remaining gap by making the load governor a single shared helper
(`bin/gate-load`) that both the conftest *and* `bin/land` consult, and by adding a machine-wide
**admission wait** at gate entry (below) that holds, not bypasses, when the box is already
saturated — independent of which conftest minted the bypass logic.

## Cause 3: no machine-wide admission control for heavy suites

The render-gate semaphore (`RTT_RENDER_GATE_SLOTS=1`) only serializes sessions that *collected*
the render file. A plain `pytest -q` from a non-rebased agent, an orphaned suite, or any other
heavy python work is not counted. So even with the semaphore behaving, total concurrent heavy
load is unbounded.

**Fix (§e):** a machine-wide load/memory governor (`bin/gate-load`) keyed on real loadavg-per-
core (and best-effort free memory). A *new* gate that is not the merge-lock holder **waits**
(it does not bypass) until the box has capacity, bounded by `RTT_RENDER_GATE_WAIT` so it can
never deadlock, and skipped entirely for the merge-lock holder's priority gate (so we never
reintroduce the priority inversion fixed in `65cd4280`).

## What is intentionally NOT changed

Correctness is untouched: FIFO fairness, the exclusive merge lock, the atomic `--ff-only`
backstop, the green-token ff-merge guard, and `bin/with-merge-lock evict` (gated manual
reclaim) all stand. This work is resource *governance and cleanup* layered on top — it changes
how runs are **paced and cleaned up**, never what **serializes** or what is allowed to merge.
The existing `bin/with-merge-lock-selftest`, `bin/land-selftest`, `bin/merge-guard-selftest`,
and `tests/app/unit/test_render_gate_bypass.py` stay green; new selftests
(`bin/reap-orphan-gates --selftest`) cover the reaper and process-group cleanup.

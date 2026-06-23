# Graceful degradation of the merge lock + render gate under heavy contention

The lock + gate are *correct* (FIFO fairness, self-heal, atomic `git merge --ff-only`
backstop). Under a 7-deep merge queue with `main` advancing every few minutes, three
weaknesses collapsed throughput. None is a correctness bug; all three are
graceful-degradation/fairness bugs. This documents each, confirms or refutes it, and
records the fix that landed.

## #1 — A wedged-but-alive holder pinned the lock for the full 40-min TTL — CONFIRMED

The daemon's self-heal frees a *dead* holder in seconds (PID death → `_reap_dead_marker`)
and a *hung* daemon via lease+grace. But a daemon that is **alive and renewing its lease**
while its gate *work* is wedged is reclaimed only by the un-bumpable `ABS_MAX` (40 min).
The lease auto-renews every `RENEW`s regardless of whether the gate advances, and the
agent's `renew` only proves the *agent* is alive, not that the *gate* is moving — so a
crawling/hung pytest under a timer-renewing agent stalls the whole queue for 40 min.

Root cause: there was no signal distinguishing **real forward progress of the gate** from
**liveness of the daemon/agent**. Lease renewal and `renew` are both liveness.

**Fix (opt-in work-progress reclaim, `bin/with-merge-lock`).** When the land protocol
exports `RTT_MERGE_PROGRESS_FILE`, the held render gate (the conftest) stamps that file as
it queues and on every test. The holder daemon self-exits if the file goes stale for
`RTT_MERGE_GATE_PROGRESS` (default 300s) — *keyed to the file's mtime alone, never to
`renew`* — so a timer-renewing agent can no longer keep a wedged gate alive, while a
crawling-but-progressing gate (which stamps sub-second) is never falsely reclaimed. Unset
→ behavior is byte-for-byte the old lease/GAP/ABS_MAX. Reclaim window: 40 min → ~5 min.
Covered by selftest `t_progress_reclaim` (freed in ~3s with a 3s threshold, *while*
spamming `renew`) and `t_progress_disabled_default` (inert when unset).

## #2 — `RTT_RENDER_GATE_NOLOCK` is a footgun that manufactures a CPU dogpile — CONFIRMED

NOLOCK is documented for one narrow case (a stuck render holder *and* you hold the merge
lock), but under contention agents reach for it to skip the render-gate semaphore — the
exact mechanism that serializes render runs to avoid CPU saturation. Several NOLOCK runs
at once thrash every core; each gate slows ~10-20× (observed ~6% of the suite in 10 min vs
a ~9-min baseline). That feeds back: slower gates → longer holds → deeper queue → more
NOLOCK. The legitimate need NOLOCK was papering over is "a stuck holder is pinning the
single slot and I can't get past it."

**Fix (auto-bypass, `tests/app/integration/conftest.py`).** A slot holder now stamps a
heartbeat (`.hb-<ns>-<pid>`) on taking the slot and at the start/end of every test. A
holder whose heartbeat is older than `RTT_RENDER_GATE_STUCK` (default 240s) is presumed
wedged and **stops counting against the slot budget** — the next waiter proceeds past it,
*without* anyone disabling the semaphore. FIFO among the remaining waiters is preserved
(only the wedged *runner* is bypassed; an earlier true waiter still goes first — see
`tests/app/unit/test_render_gate_bypass.py`). A healthy run stamps sub-second so it is
never falsely bypassed; the wedged run is left alive (we never kill another agent's
process). No agent needs manual NOLOCK to get past a stuck holder anymore.

## #3 — The merge lock is held across the entire ~9-min render gate — CONFIRMED, mitigated

Holding the lock across `rebase → full gate → ff-merge` serializes *every* land behind the
slowest render run, even render-orthogonal ones. The framing of "hot-file starvation" is
really the compound of #1 (a 40-min wedge at the front) and #2 (the dogpile inflating every
hold) on top of this serialization; the merge lock's FIFO already bounds *ordering*
fairness, so with #1 and #2 fixed the acute starvation is gone.

The remaining structural cost is the serialization itself. Note the render-gate semaphore
is **already** 1-slot, so render runs are serialized *regardless of the merge lock* — the
merge lock's extra job is only "no one lands between my gate finishing and my ff-merge."
That window is seconds. So the lock does **not** need to wrap the gate.

**Mitigation (optimistic short-lock, documented in `CLAUDE.md`).** Validate lock-free under
the render semaphore, then take the merge lock only for the brief `merge-safe-check` +
`ff-merge`:

```
while not landed:
  git rebase main
  .venv/bin/python -m pytest -q                 # full gate, serialized by the render semaphore
  bin/with-merge-lock acquire                   # brief, FIFO-fair
  if bin/merge-safe-check ; then                # main moved only render-orthogonally since rebase
      git -C <main> merge --ff-only <branch>    # atomic backstop; if it loses the race, re-loop
      bin/with-merge-lock release ; break
  else
      bin/with-merge-lock release               # relevant move: rebase + re-gate
  fi
```

This shrinks the merge-lock critical section from ~9 min to ~seconds and lets orthogonal
lands flow without queuing behind a render-relevant gate. The cost is a possible re-gate
("chase") when `main` moves *render-relevantly* during your gate; because the render
semaphore serializes gates, at most ~one competing land completes per gate, so the chase is
bounded (~one extra iteration per competitor), and `merge-safe-check` removes it entirely
for orthogonal moves. The long-lock subcommands still work unchanged and remain the simple
no-chase choice for an `rtt/app/` change you expect to be outrun; short-lock is the faster
default for orthogonal / non-render lands.

## What was deliberately NOT changed

The atomic `git merge --ff-only` ref-CAS backstop and the FIFO fairness tickets are what
keep `main` safe and unstarvable; both are untouched. Every new mechanism is opt-in or
strictly loosens *who waits*, never *what is allowed to land*. `WAIT_MAX` still FAILS rather
than proceeding unlocked. The goal here was shorter, self-healing waits — not weaker safety.

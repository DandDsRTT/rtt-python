"""Make the heavy render gate take turns across parallel agents.

Several agents run in parallel on this machine and all reach for the full render
suite (``tests/app/integration/test_web_render.py``) at the same time. Each run
rebuilds the whole spreadsheet page ~171 times, so a handful of simultaneous
runs pins every core and *nobody* finishes — the suite that is supposed to be a
merge gate becomes a CPU traffic jam.

This conftest meters those runs through a **counting semaphore**: at most
``RTT_RENDER_GATE_SLOTS`` render runs (default 1 — render runs are CPU-bound, so
running several at once just multiplies everyone's wall-clock; one-at-a-time
finishes each run fastest) execute at once; the rest queue and take turns.
Raise ``RTT_RENDER_GATE_SLOTS`` if the machine genuinely has spare cores. The
metering lives *inside* pytest collection, so it catches a
render run no matter how it was launched — a direct ``pytest``, a ``-k`` subset
that selects render tests, or an in-process ``pytest.main([...])`` wrapper.

Sessions that never touch the render file (the fast inner-loop pass, which runs
with ``--ignore=.../test_web_render.py``) collect no render items and so never
queue — fast feedback stays fast.

How it works (no ``flock``, which macOS lacks): on arrival each run drops a
**ticket** file named ``<wall-clock-ns>-<pid>`` in ``/tmp/rtt-render-gate.d/``.
The N live tickets with the lowest timestamps are the ones allowed to run; the
rest poll until enough of those ahead finish (and remove their tickets). Because
a ticket's timestamp is fixed at arrival, ordering is **FIFO and fair** — new
arrivals always queue *behind* you, so you can't be starved, and a run can report
exactly how many are ahead of it. Tickets from dead PIDs are reclaimed on every
scan, so a crashed/killed holder frees its slot automatically and the queue never
wedges.

PROGRESS HEARTBEAT — auto-bypass a STUCK holder (no manual ``NOLOCK`` needed)
============================================================================
A *dead* holder (PID gone) is reclaimed in seconds. But a holder that is ALIVE
yet WEDGED — its pytest hung, or it is crawling so slowly under CPU thrash that
it makes no forward progress — used to pin the single render slot until the whole
queue gave up at ``RTT_RENDER_GATE_WAIT`` (3600s). Agents reached for
``RTT_RENDER_GATE_NOLOCK=1`` to skip the gate and jump such a holder — which is
the exact mechanism that serializes runs to avoid CPU saturation, so several
NOLOCK runs at once thrash every core and slow *everyone's* gate ~10-20×.

So a running holder now stamps a **heartbeat** (``.hb-<ns>-<pid>``, a dotfile so
the ticket parser ignores it): created the instant it takes a slot, and re-touched
at the start and end of every test. A healthy run touches it sub-second, so it is
never falsely flagged. A run whose heartbeat is older than ``RTT_RENDER_GATE_STUCK``
seconds (default 240) is presumed wedged and **stops counting against the slot
budget** — the next waiter proceeds past it (FIFO among the remaining waiters is
preserved; only the wedged *runner* is bypassed). The wedged run is left alone (we
never kill another agent's process); if it later un-wedges we briefly overcommit
by one run, then it finishes. With this, no agent ever needs manual ``NOLOCK`` to
get past a stuck holder.

LOAD-GATED BYPASS — don't let the bypass become a dogpile
=========================================================
The bypass above assumes a stale heartbeat means *hung*. Under sustained overload it
usually means *starved*: a perfectly healthy suite the OS isn't scheduling. If we bypass
a starved holder we start a SECOND CPU-bound suite, which starves both further, so both
miss their heartbeats and get bypassed, so a THIRD starts… a self-feeding pile-up that
defeats the 1-slot semaphore entirely (seen once pinning load at 33 with four concurrent
multi-hour suites). So the bypass is **gated on spare capacity**: a stale holder is
bypassed only while 1-minute load per core is below ``RTT_RENDER_GATE_BYPASS_MAXLOAD``;
above it we WAIT for the holder instead of piling on. A genuinely hung holder is still
bypassed once load drops (CPU is then free, so a flat heartbeat really is wedged), and a
DEAD holder is reclaimed by ``_scan`` regardless of load — so crash recovery is unaffected.

The hard wait-cap (``RTT_RENDER_GATE_WAIT``) carries the SAME load gate (``_proceed_at_cap``):
proceeding past the semaphore at the cap is just a slower second door to the same dogpile — under
sustained load the slot-holder is itself starved and can't finish within the hour, so a waiter that
"proceeds anyway" starts a concurrent second suite — so we only burst past the cap when the box is
idle (a holder still unfinished then really is wedged), and otherwise keep waiting until load drops.

MERGE-LOCK HOLDER PRIORITY — fixes the priority inversion
=========================================================
A held-lock land runs the render gate AS its validation *while holding the exclusive merge
lock*. If that gate queues here behind speculative non-holder runs, the merge lock sits
IDLE for the whole wait — stalling every other agent's merge (observed: a holder pinned the
lock ~19 min while its gate sat at 0% CPU, queued behind a non-holder's gate). That is a
priority inversion: the critical-path run (the lock holder, serializing everyone) waits on
lower-priority speculative work. So a run that holds the merge lock — detected by reading
the lock marker in ``RTT_MERGE_GATE_DIR`` and matching this worktree's token against a LIVE
holder daemon — takes a slot IMMEDIATELY instead of queuing. It is bounded to exactly +1
over ``SLOTS`` because the merge lock is exclusive (one holder ever), and it still registers
a heartbeat so other runs count it and don't pile on. This is the automatic, verified
replacement for the old manual ``RTT_RENDER_GATE_NOLOCK=1`` on the under-lock gate.

Env knobs:
  * ``RTT_RENDER_GATE_SLOTS``  how many run concurrently (default 1)
  * ``RTT_RENDER_GATE_WAIT``   max seconds to queue before proceeding anyway (default 3600);
                              the proceed-anyway burst is itself gated on spare load (see above)
  * ``RTT_RENDER_GATE_STUCK``  no-progress seconds after which a holder is bypassed (default 240)
  * ``RTT_RENDER_GATE_BYPASS_MAXLOAD``  bypass a stuck holder only while loadavg/core is
                              below this (default 1.0); above it, wait instead of piling on
  * ``RTT_MERGE_GATE_DIR``    merge-lock marker dir, read to grant the holder a priority slot
                              (default ``/tmp/rtt-merge-gate.d``; matches ``bin/with-merge-lock``)
  * ``RTT_RENDER_GATE_NOLOCK`` set to ``1`` to opt a run out entirely

``RTT_MERGE_PROGRESS_FILE`` (optional): when the land protocol exports it, this
gate also bumps that file as it queues and on every test, so the merge-lock holder
daemon can tell a crawling-but-progressing gate from a wedged one and reclaim only
the latter (see ``bin/with-merge-lock``). Unset → ignored; this gate is unaffected.
"""

import gc
import hashlib
import json
import os
import subprocess
import sys
import time

_RENDER_FILE = "test_web_render.py"
_GATE_DIR = "/tmp/rtt-render-gate.d"
_SLOTS = max(1, int(os.environ.get("RTT_RENDER_GATE_SLOTS", "1")))
_WAIT_MAX = int(os.environ.get("RTT_RENDER_GATE_WAIT", "3600"))  # seconds willing to queue
_STUCK = int(os.environ.get("RTT_RENDER_GATE_STUCK", "240"))  # no-progress → bypass holder
# A stale-heartbeat holder is BYPASSED (its slot reused by the next waiter) only when the
# machine has spare capacity to absorb another concurrent render suite. Under saturation a
# stale heartbeat almost always means the holder is STARVED, not hung — so starting another
# CPU-bound suite past it just deepens the thrash, and every running suite then misses its
# heartbeat and gets bypassed too: a self-feeding pile-up that defeats the 1-slot semaphore
# (observed pinning load at 33 with four concurrent multi-hour suites). So we bypass only
# when 1-minute load per core is below this factor; above it we WAIT for the holder instead.
# A genuinely hung holder is still bypassed once load falls (CPU is then free, so flatness
# really is wedged), and a DEAD holder is reclaimed by _scan regardless of load.
_BYPASS_MAXLOAD = float(os.environ.get("RTT_RENDER_GATE_BYPASS_MAXLOAD", "1.0"))
_POLL = 3  # seconds between attempts
_REPORT_EVERY = 15  # seconds between "still waiting" lines
_DISABLED = os.environ.get("RTT_RENDER_GATE_NOLOCK") == "1"
_MERGE_PROGRESS_FILE = os.environ.get("RTT_MERGE_PROGRESS_FILE") or None

# Green-token minting — the mechanical evidence that THIS exact tree passed the full
# render gate. ``bin/merge-green-check`` / ``bin/merge-guard-hook`` consult it to refuse
# an ungated render-relevant ff-merge of main (see those files). A token is an empty
# file named by the git tree sha the session validated.
_GREEN_DIR = os.environ.get("RTT_RENDER_GREEN_DIR", "/tmp/rtt-render-green.d")
_GREEN_TTL = int(os.environ.get("RTT_RENDER_GREEN_TTL", str(7 * 24 * 3600)))

# Priority for the merge-lock HOLDER's gate (fixes the priority inversion). A held-lock
# land runs the render gate AS its validation while holding the exclusive merge lock; if
# that gate queues in this semaphore behind speculative non-holder runs, the merge lock
# sits IDLE for the whole wait, stalling every other agent's merge. So a run that holds
# the merge lock takes a slot IMMEDIATELY (it is the critical path — finishing it unblocks
# all merges), bounded to exactly +1 over SLOTS because the merge lock is exclusive (one
# holder ever). This replaces the old manual ``RTT_RENDER_GATE_NOLOCK=1`` convention for
# the under-lock gate: automatic, verified against the lock marker, and still VISIBLE to
# other runs (so they count it and don't pile on), unlike NOLOCK which hid the run entirely.
_MERGE_GATE_DIR = os.environ.get("RTT_MERGE_GATE_DIR", "/tmp/rtt-merge-gate.d")
_MERGE_MARKER = os.path.join(_MERGE_GATE_DIR, ".holder")

# Resource governance, delegated to the shared bin helpers so the policy lives in ONE place
# (and so a stale conftest can't carry a divergent copy): before queuing we sweep orphaned
# gate trees a SIGKILLed run left behind (they pin slots because their PID is still alive —
# `_scan` reclaims only DEAD pids), and a non-holder gate WAITS for machine capacity rather
# than piling onto a saturated box. The merge-lock holder skips the admission wait — its gate
# is the critical path and must never queue behind load (the priority inversion fix). See
# RESOURCE_GOVERNANCE_DIAGNOSIS.md and bin/{reap-orphan-gates,gate-load}.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REAPER = os.path.join(_REPO_ROOT, "bin", "reap-orphan-gates")
_GATE_LOAD = os.path.join(_REPO_ROOT, "bin", "gate-load")
_NOADMIT = os.environ.get("RTT_RENDER_GATE_NOADMIT") == "1"

# Freeze the warm static heap before the render suite runs. Each ``user`` fixture wraps its
# test in NiceGUI's ``nicegui_reset_globals``, which calls ``gc.collect()`` on entry AND exit
# — 2 full collections per test, 342 across the 171-test suite. Each collection walks the whole
# tracked heap, ~160k objects of which are the long-lived imports (numpy/scipy/sympy/nicegui/
# fastapi/rtt and their module state) that live for the entire session and can never be collected
# anyway. ``gc.freeze()`` moves those into a permanent generation gc never rescans, so each
# per-test collection walks only the small per-test garbage instead of the whole static heap —
# the dominant fixed per-test cost, removed without doing any less checking.
_GCFREEZE = os.environ.get("RTT_RENDER_GATE_GCFREEZE") != "0"
_frozen = False

_ticket = None       # path to this run's ticket file once created
_ticket_name = None  # its <ns>-<pid> basename
_heartbeat = None    # path to this run's heartbeat file once it holds a slot
_collected_render = False  # did this session collect the render file at all?


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    return True


def _my_merge_lock_id():
    """This worktree's merge-lock token — sha1 of the git top-level (or of an explicit
    ``RTT_MERGE_LOCK_ID``), IDENTICAL to ``bin/with-merge-lock``'s ``_token`` so we can
    tell whether the marker on disk names US. None if it can't be determined."""
    explicit = os.environ.get("RTT_MERGE_LOCK_ID")
    if explicit:
        return hashlib.sha1(explicit.encode("utf-8")).hexdigest()[:16]
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    root = r.stdout.strip() if r.returncode == 0 else None
    if not root:
        return None
    return hashlib.sha1(root.encode("utf-8")).hexdigest()[:16]


def _holds_merge_lock():
    """True iff THIS worktree currently holds the merge lock — so its gate is the critical
    path that the exclusive merge lock is blocking everyone else on, and must not queue
    behind speculative non-holder runs. Reads the merge-lock marker directly (no dependency
    on ``bin/with-merge-lock``); matches BOTH the token and a live daemon, so a stale marker
    never grants false priority."""
    mine = _my_merge_lock_id()
    if not mine:
        return False
    try:
        with open(_MERGE_MARKER) as f:
            m = json.loads(f.read() or "{}")
    except (OSError, ValueError):
        return False
    if not isinstance(m, dict) or m.get("token") != mine:
        return False
    pid = m.get("daemon_pid", 0)
    try:
        return _alive(int(pid)) if pid else False
    except (TypeError, ValueError):
        return False


def _hb_path(name):
    return os.path.join(_GATE_DIR, ".hb-" + name)


def _bump(path):
    """Create `path` if absent and refresh its mtime — the progress stamp."""
    try:
        with open(path, "a"):
            pass
        os.utime(path, None)
    except OSError:
        pass


def _scan():
    """Return live tickets as a list of ``(ns, pid, filename)`` sorted FIFO,
    removing any ticket whose PID is dead (and its heartbeat), reclaiming its slot."""
    live = []
    try:
        names = os.listdir(_GATE_DIR)
    except OSError:
        return live
    for name in names:
        if name.startswith("."):
            continue  # heartbeats / temp files — never tickets
        try:
            ns_s, pid_s = name.rsplit("-", 1)
            ns, pid = int(ns_s), int(pid_s)
        except ValueError:
            continue
        if _alive(pid):
            live.append((ns, pid, name))
        else:
            for p in (os.path.join(_GATE_DIR, name), _hb_path(name)):
                try:
                    os.remove(p)
                except OSError:
                    pass
    live.sort()
    return live


def _bypass_allowed():
    """True iff the machine has spare capacity to start another concurrent render suite,
    so bypassing a stale-heartbeat holder is safe rather than thrash-inducing. Measured as
    1-minute load average per core; fail-open (True) if load can't be read, preserving the
    original always-bypass behavior. See `_BYPASS_MAXLOAD` for why this gate exists."""
    try:
        load1 = os.getloadavg()[0]
        ncpu = os.cpu_count() or 1
    except (OSError, ValueError):
        return True
    return load1 < ncpu * _BYPASS_MAXLOAD


def _proceed_at_cap(waited, bypass_ok):
    """At the hard wait-cap, burst past the semaphore only when the machine is NOT saturated
    (`bypass_ok`). A holder that hasn't finished within `_WAIT_MAX` under load is STARVED, not
    deadlocked — proceeding starts a SECOND CPU-bound suite that starves both further, the exact
    dogpile `_bypass_allowed` already prevents on the stuck-holder bypass path. So this is the
    SAME load gate, on the wait-cap door: idle at the cap ⇒ a still-unfinished holder genuinely
    is wedged and bursting past is the right deadlock-breaker; saturated at the cap ⇒ keep waiting
    (the loop re-checks, and proceeds once load drops or the holder finishes — so it still drains)."""
    return waited >= _WAIT_MAX and bypass_ok


def _classify(live, my_name, now, bypass_ok):
    """Split the FIFO queue around me. Returns (running_fresh, waiters_ahead, wedged):
    a *running* ticket holds a slot (fresh heartbeat), a *wedged* one has a heartbeat
    older than STUCK AND `bypass_ok` is set (a stuck holder we bypass — counted toward
    neither the slot budget nor my position), and a ticket with no heartbeat yet is a true
    waiter. `wedged` is counted directly (NOT derived by subtraction), so a later-arriving
    true waiter is never miscounted as stuck. When `bypass_ok` is False (machine saturated),
    a stale holder is NOT bypassed — it keeps counting as a running slot so we WAIT for it
    instead of piling another suite onto an already-thrashing box."""
    my_key = next(((ns, pid) for ns, pid, name in live if name == my_name), None)
    running_fresh = 0
    waiters_ahead = 0
    wedged = 0
    for ns, pid, name in live:
        try:
            age = now - os.path.getmtime(_hb_path(name))
            has_hb = True
        except OSError:
            has_hb = False
            age = 0
        if has_hb and age <= _STUCK:
            running_fresh += 1
        elif has_hb and bypass_ok:
            wedged += 1  # stale heartbeat + spare capacity → stuck holder, safe to bypass
        elif has_hb:
            running_fresh += 1  # stale but saturated → treat as a live slot; wait, don't pile on
        elif name != my_name and my_key is not None and (ns, pid) < my_key:
            waiters_ahead += 1
    return running_fresh, waiters_ahead, wedged


def _take_slot():
    global _heartbeat
    _heartbeat = _hb_path(_ticket_name)
    _bump(_heartbeat)


def _reap_orphans():
    """Sweep orphaned gate trees a SIGKILLed/abandoned run left behind, so their slots free
    up before we count how many are busy. Best-effort and quiet — never blocks the gate."""
    try:
        subprocess.run([sys.executable, _REAPER, "--quiet"], timeout=60,
                       stdout=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def _admit():
    """Machine-wide admission: wait until the box has CPU/memory capacity before starting this
    suite. Delegated to bin/gate-load so the policy is shared and stale-base-robust. Bounded by
    RTT_RENDER_GATE_WAIT inside gate-load, so it can never deadlock. Skipped for the merge-lock
    holder (handled by the caller) and when RTT_RENDER_GATE_NOADMIT=1."""
    if _NOADMIT:
        return
    try:
        subprocess.run([sys.executable, _GATE_LOAD, "wait"], timeout=_WAIT_MAX + 120)
    except (OSError, subprocess.SubprocessError):
        pass


def _acquire():
    global _ticket, _ticket_name
    os.makedirs(_GATE_DIR, exist_ok=True)
    _reap_orphans()  # clear abandoned suites that pin slots (alive PID → _scan won't reclaim)
    _ticket_name = f"{time.time_ns()}-{os.getpid()}"
    _ticket = os.path.join(_GATE_DIR, _ticket_name)
    try:
        open(_ticket, "x").close()
    except OSError:
        pass

    if _holds_merge_lock():
        _take_slot()  # register a fresh heartbeat so other runs count us and don't pile on
        print(
            f"[render-gate] merge-lock holder (PID {os.getpid()}) — taking a priority slot "
            f"now; the merge lock must not idle queued behind speculative runs",
            file=sys.stderr,
        )
        return

    _admit()  # non-holder: don't pile onto a saturated box — wait for machine capacity first

    waited = 0
    last_report = -_REPORT_EVERY
    while True:
        now = time.time()
        live = _scan()
        names = [n for _, _, n in live]
        if _ticket_name not in names:  # got reclaimed under us; re-stake our place
            try:
                open(_ticket, "x").close()
            except OSError:
                pass
            continue
        bypass_ok = _bypass_allowed()
        running_fresh, waiters_ahead, wedged = _classify(live, _ticket_name, now, bypass_ok)
        free = _SLOTS - running_fresh
        if free > 0 and waiters_ahead < free:
            _take_slot()
            extra = f" after waiting {waited}s" if waited else ""
            print(
                f"[render-gate] slot acquired (PID {os.getpid()}){extra}; "
                f"running render suite ({_SLOTS} run concurrently)",
                file=sys.stderr,
            )
            return
        if _proceed_at_cap(waited, bypass_ok):
            _take_slot()
            print(
                f"[render-gate] waited {_WAIT_MAX}s (still position {waiters_ahead + 1} "
                f"in line); proceeding anyway",
                file=sys.stderr,
            )
            return
        if waited - last_report >= _REPORT_EVERY:
            note = f"; bypassing {wedged} stuck" if wedged else ""
            if not bypass_ok:
                note += ("; past wait-cap but holding off (machine saturated)"
                         if waited >= _WAIT_MAX else "; holding off bypass (machine saturated)")
            print(
                f"[render-gate] waiting our turn… position {waiters_ahead + 1} "
                f"({running_fresh}/{_SLOTS} slots busy{note}; {waited}s elapsed)",
                file=sys.stderr,
            )
            last_report = waited
        if _MERGE_PROGRESS_FILE:
            _bump(_MERGE_PROGRESS_FILE)  # queuing is forward progress for the merge daemon
        time.sleep(_POLL)
        waited += _POLL


def _progress():
    """Stamp our heartbeat (and the optional merge-progress file) — called as
    each test starts and finishes, so a healthy run never looks wedged."""
    if _heartbeat is None:
        return
    _bump(_heartbeat)
    if _MERGE_PROGRESS_FILE:
        _bump(_MERGE_PROGRESS_FILE)


def _release():
    global _ticket, _heartbeat
    for path in (_heartbeat, _ticket):
        if path is not None:
            try:
                os.remove(path)
            except OSError:
                pass
    _ticket = None
    _heartbeat = None


def _git_out(*args):
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _clean_tree_sha():
    """git tree sha of HEAD, but only if no TRACKED file is modified — so HEAD's tree
    faithfully represents what the gate ran against and what an ff-merge would land.
    Untracked files are ignored (they are in no commit, so they don't change the tree
    nor what ``rtt`` imports). None if dirty or git unavailable."""
    status = _git_out("status", "--porcelain", "--untracked-files=no")
    if status is None or status != "":
        return None
    return _git_out("rev-parse", "HEAD^{tree}")


def _prune_green(now):
    try:
        names = os.listdir(_GREEN_DIR)
    except OSError:
        return
    for n in names:
        p = os.path.join(_GREEN_DIR, n)
        try:
            if now - os.path.getmtime(p) > _GREEN_TTL:
                os.remove(p)
        except OSError:
            pass


def _mint_green_token(config, exitstatus):
    """On a full, green render-gate session over a clean tree, record the validated
    tree sha so the ff-merge guard can prove the gate ran on exactly this tree. A
    partial run (``-k``/``-m``/``--lf``) must NOT mint — it didn't validate the whole
    render suite — so we refuse those."""
    if not _collected_render or int(exitstatus) != 0:
        return
    opt = config.option
    if (getattr(opt, "keyword", "") or getattr(opt, "markexpr", "")
            or getattr(opt, "lf", False) or getattr(opt, "failedfirst", False)
            or getattr(opt, "last_failed", False)):
        return
    if any("::" in a for a in getattr(opt, "file_or_dir", []) or []):
        return
    tree = _clean_tree_sha()
    if not tree:
        return
    now = time.time()
    try:
        os.makedirs(_GREEN_DIR, exist_ok=True)
        _prune_green(now)
        payload = json.dumps({
            "kind": "render-green",
            "tree": tree,
            "head": _git_out("rev-parse", "HEAD"),
            "pid": os.getpid(),
            "time": now,
        })
        path = os.path.join(_GREEN_DIR, tree)
        tmp = "%s.tmp-%d" % (path, os.getpid())
        with open(tmp, "w") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        pass


def _freeze_static_heap():
    """Move the warm static heap into gc's permanent generation so the per-test
    ``gc.collect()`` in ``nicegui_reset_globals`` stops rescanning it. Idempotent and
    opt-out via ``RTT_RENDER_GATE_GCFREEZE=0``. Called after collection (deps already
    imported by collecting the render module) and before the first ``user`` fixture, so
    everything heavy is warm and captured. The first re-imported ``rtt.*`` set is frozen
    along with the deps; render_main re-imports a fresh set each test, which stays
    collectable, so test-to-test object identity is unchanged."""
    global _frozen
    if _frozen or not _GCFREEZE:
        return
    import rtt.app.app  # noqa: F401 — ensure the heavy deps are warm before we freeze
    gc.collect()
    gc.freeze()
    _frozen = True


def pytest_collection_modifyitems(session, config, items):
    global _collected_render
    _collected_render = any(
        _RENDER_FILE in str(getattr(item, "fspath", "")) for item in items
    )
    if _DISABLED:
        return
    if _collected_render:
        _freeze_static_heap()
        _acquire()


def pytest_runtest_logstart(nodeid, location):
    _progress()


def pytest_runtest_logreport(report):
    _progress()


def pytest_sessionfinish(session, exitstatus):
    _release()
    _mint_green_token(session.config, exitstatus)

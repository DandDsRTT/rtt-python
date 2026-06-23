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

Env knobs:
  * ``RTT_RENDER_GATE_SLOTS``  how many run concurrently (default 1)
  * ``RTT_RENDER_GATE_WAIT``   max seconds to queue before proceeding anyway (default 3600)
  * ``RTT_RENDER_GATE_STUCK``  no-progress seconds after which a holder is bypassed (default 240)
  * ``RTT_RENDER_GATE_NOLOCK`` set to ``1`` to opt a run out entirely

``RTT_MERGE_PROGRESS_FILE`` (optional): when the land protocol exports it, this
gate also bumps that file as it queues and on every test, so the merge-lock holder
daemon can tell a crawling-but-progressing gate from a wedged one and reclaim only
the latter (see ``bin/with-merge-lock``). Unset → ignored; this gate is unaffected.
"""

import os
import sys
import time

_RENDER_FILE = "test_web_render.py"
_GATE_DIR = "/tmp/rtt-render-gate.d"
_SLOTS = max(1, int(os.environ.get("RTT_RENDER_GATE_SLOTS", "1")))
_WAIT_MAX = int(os.environ.get("RTT_RENDER_GATE_WAIT", "3600"))  # seconds willing to queue
_STUCK = int(os.environ.get("RTT_RENDER_GATE_STUCK", "240"))  # no-progress → bypass holder
_POLL = 3  # seconds between attempts
_REPORT_EVERY = 15  # seconds between "still waiting" lines
_DISABLED = os.environ.get("RTT_RENDER_GATE_NOLOCK") == "1"
_MERGE_PROGRESS_FILE = os.environ.get("RTT_MERGE_PROGRESS_FILE") or None

_ticket = None       # path to this run's ticket file once created
_ticket_name = None  # its <ns>-<pid> basename
_heartbeat = None    # path to this run's heartbeat file once it holds a slot


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    return True


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


def _classify(live, my_name, now):
    """Split the FIFO queue around me. Returns (running_fresh, waiters_ahead, wedged):
    a *running* ticket holds a slot (fresh heartbeat), a *wedged* one has a heartbeat
    older than STUCK (a stuck holder we bypass — counted toward neither the slot budget
    nor my position), and a ticket with no heartbeat yet is a true waiter. `wedged` is
    counted directly (NOT derived by subtraction), so a later-arriving true waiter is
    never miscounted as stuck."""
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
        elif has_hb:
            wedged += 1  # stale heartbeat → stuck holder, bypassed
        elif name != my_name and my_key is not None and (ns, pid) < my_key:
            waiters_ahead += 1
    return running_fresh, waiters_ahead, wedged


def _take_slot():
    global _heartbeat
    _heartbeat = _hb_path(_ticket_name)
    _bump(_heartbeat)


def _acquire():
    global _ticket, _ticket_name
    os.makedirs(_GATE_DIR, exist_ok=True)
    _ticket_name = f"{time.time_ns()}-{os.getpid()}"
    _ticket = os.path.join(_GATE_DIR, _ticket_name)
    try:
        open(_ticket, "x").close()
    except OSError:
        pass

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
        running_fresh, waiters_ahead, wedged = _classify(live, _ticket_name, now)
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
        if waited >= _WAIT_MAX:
            _take_slot()
            print(
                f"[render-gate] waited {_WAIT_MAX}s (still position {waiters_ahead + 1} "
                f"in line); proceeding anyway",
                file=sys.stderr,
            )
            return
        if waited - last_report >= _REPORT_EVERY:
            note = f"; bypassing {wedged} stuck" if wedged else ""
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


def pytest_collection_modifyitems(session, config, items):
    if _DISABLED:
        return
    if any(_RENDER_FILE in str(getattr(item, "fspath", "")) for item in items):
        _acquire()


def pytest_runtest_logstart(nodeid, location):
    _progress()


def pytest_runtest_logreport(report):
    _progress()


def pytest_sessionfinish(session, exitstatus):
    _release()

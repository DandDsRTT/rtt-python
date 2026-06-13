"""Make the heavy render gate take turns across parallel agents.

Several agents run in parallel on this machine and all reach for the full render
suite (``tests/app/integration/test_web_render.py``) at the same time. Each run
rebuilds the whole spreadsheet page ~171 times, so a handful of simultaneous
runs pins every core and *nobody* finishes — the suite that is supposed to be a
merge gate becomes a CPU traffic jam.

This conftest meters those runs through a **counting semaphore**: at most
``RTT_RENDER_GATE_SLOTS`` render runs (default 3) execute at once; the rest queue
and take turns. The metering lives *inside* pytest collection, so it catches a
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

Env knobs:
  * ``RTT_RENDER_GATE_SLOTS``  how many run concurrently (default 3)
  * ``RTT_RENDER_GATE_WAIT``   max seconds to queue before proceeding anyway (default 3600)
  * ``RTT_RENDER_GATE_NOLOCK`` set to ``1`` to opt a run out entirely
"""

import os
import sys
import time

_RENDER_FILE = "test_web_render.py"
_GATE_DIR = "/tmp/rtt-render-gate.d"
_SLOTS = max(1, int(os.environ.get("RTT_RENDER_GATE_SLOTS", "3")))
_WAIT_MAX = int(os.environ.get("RTT_RENDER_GATE_WAIT", "3600"))  # seconds willing to queue
_POLL = 3  # seconds between attempts
_REPORT_EVERY = 15  # seconds between "still waiting" lines
_DISABLED = os.environ.get("RTT_RENDER_GATE_NOLOCK") == "1"

_ticket = None  # path to this run's ticket file once created


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    return True


def _scan():
    """Return live tickets as a list of ``(ns, pid, filename)`` sorted FIFO,
    removing any ticket whose PID is dead (reclaiming its slot)."""
    live = []
    try:
        names = os.listdir(_GATE_DIR)
    except OSError:
        return live
    for name in names:
        try:
            ns_s, pid_s = name.rsplit("-", 1)
            ns, pid = int(ns_s), int(pid_s)
        except ValueError:
            continue
        if _alive(pid):
            live.append((ns, pid, name))
        else:
            try:
                os.remove(os.path.join(_GATE_DIR, name))
            except OSError:
                pass
    live.sort()
    return live


def _acquire():
    global _ticket
    os.makedirs(_GATE_DIR, exist_ok=True)
    my_name = f"{time.time_ns()}-{os.getpid()}"
    _ticket = os.path.join(_GATE_DIR, my_name)
    try:
        open(_ticket, "x").close()
    except OSError:
        pass

    waited = 0
    last_report = -_REPORT_EVERY
    while True:
        live = _scan()
        names = [n for _, _, n in live]
        if my_name not in names:  # got reclaimed under us; re-stake our place
            try:
                open(_ticket, "x").close()
            except OSError:
                pass
            continue
        idx = names.index(my_name)
        if idx < _SLOTS:
            extra = f" after waiting {waited}s" if waited else ""
            print(
                f"[render-gate] slot acquired (PID {os.getpid()}){extra}; "
                f"running render suite ({_SLOTS} run concurrently)",
                file=sys.stderr,
            )
            return
        if waited >= _WAIT_MAX:
            print(
                f"[render-gate] waited {_WAIT_MAX}s (still position {idx - _SLOTS + 1} "
                f"in line); proceeding anyway",
                file=sys.stderr,
            )
            return
        if waited - last_report >= _REPORT_EVERY:
            position = idx - _SLOTS + 1
            waiting = max(0, len(live) - _SLOTS)
            ahead = [p for _, p, _ in live[:idx]]
            print(
                f"[render-gate] waiting our turn… position {position} of {waiting} queued "
                f"({_SLOTS} slots busy; {waited}s elapsed). PIDs ahead: {ahead}",
                file=sys.stderr,
            )
            last_report = waited
        time.sleep(_POLL)
        waited += _POLL


def _release():
    global _ticket
    if _ticket is None:
        return
    try:
        os.remove(_ticket)
    except OSError:
        pass
    _ticket = None


def pytest_collection_modifyitems(session, config, items):
    if _DISABLED:
        return
    if any(_RENDER_FILE in str(getattr(item, "fspath", "")) for item in items):
        _acquire()


def pytest_sessionfinish(session, exitstatus):
    _release()

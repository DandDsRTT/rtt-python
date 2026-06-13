"""Make the heavy render gate take turns across parallel agents.

Several agents run in parallel on this machine and all reach for the full render
suite (``tests/app/integration/test_web_render.py``) at the same time. Each run
rebuilds the whole spreadsheet page ~171 times, so a handful of simultaneous
runs pins every core and *nobody* finishes — the suite that is supposed to be a
merge gate becomes an infinite CPU traffic jam.

This conftest serializes those runs with one machine-wide lock: any pytest
session that has collected render tests grabs the lock before the tests run and
releases it at the end, so render runs queue and take turns instead of dogpiling.
Crucially the lock lives *inside* pytest collection, so it catches a render run
no matter how it was launched — a direct ``pytest``, a ``-k`` subset that selects
render tests, or an in-process ``pytest.main([...])`` wrapper.

Sessions that never touch the render file (the fast inner-loop pass, which runs
with ``--ignore=.../test_web_render.py``) collect no render items and so never
take the lock — fast feedback stays fast.

The lock is an atomic ``mkdir`` on a fixed ``/tmp`` path (no ``flock``, which
macOS lacks) with a PID file, so a crashed/killed holder's lock is reclaimed
instead of wedging the queue forever. Set ``RTT_RENDER_GATE_NOLOCK=1`` to opt out
(e.g. when you know you're the only run), or ``RTT_RENDER_GATE_WAIT=<seconds>`` to
cap how long a run will queue before giving up and running anyway.
"""

import os
import sys
import time

_RENDER_FILE = "test_web_render.py"
_LOCK_DIR = "/tmp/rtt-render-gate.lock"
_PID_FILE = os.path.join(_LOCK_DIR, "pid")
_WAIT_MAX = int(os.environ.get("RTT_RENDER_GATE_WAIT", "3600"))  # seconds willing to queue
_POLL = 5  # seconds between attempts
_DISABLED = os.environ.get("RTT_RENDER_GATE_NOLOCK") == "1"

_held = False


def _holder():
    """Return the live holder PID, ``False`` if the recorded holder is dead,
    or ``None`` if the holder is unknown (no/garbled PID file)."""
    try:
        with open(_PID_FILE) as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return pid  # alive, just not ours to signal
    return pid


def _reclaim_stale():
    for path, remove in ((_PID_FILE, os.remove), (_LOCK_DIR, os.rmdir)):
        try:
            remove(path)
        except OSError:
            pass


def _acquire():
    global _held
    waited = 0
    while True:
        try:
            os.mkdir(_LOCK_DIR)
        except FileExistsError:
            holder = _holder()
            if holder is False:
                print("[render-gate] reclaiming a stale lock from a dead run", file=sys.stderr)
                _reclaim_stale()
                continue
            if waited >= _WAIT_MAX:
                print(
                    f"[render-gate] waited {_WAIT_MAX}s for PID {holder}; running anyway",
                    file=sys.stderr,
                )
                return  # never block a run forever — proceed unlocked
            if waited % 30 == 0:
                print(
                    f"[render-gate] another render run holds the lock (PID {holder}); "
                    f"waiting our turn… {waited}s elapsed",
                    file=sys.stderr,
                )
            time.sleep(_POLL)
            waited += _POLL
            continue
        # mkdir succeeded — the lock is ours
        try:
            with open(_PID_FILE, "w") as fh:
                fh.write(str(os.getpid()))
        except OSError:
            pass
        _held = True
        print(f"[render-gate] lock acquired (PID {os.getpid()}); running render suite", file=sys.stderr)
        return


def _release():
    global _held
    if not _held:
        return
    _reclaim_stale()
    _held = False


def pytest_collection_modifyitems(session, config, items):
    if _DISABLED:
        return
    if any(_RENDER_FILE in str(getattr(item, "fspath", "")) for item in items):
        _acquire()


def pytest_sessionfinish(session, exitstatus):
    _release()

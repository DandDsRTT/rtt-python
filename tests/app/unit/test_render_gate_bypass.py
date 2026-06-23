"""The render-gate counting semaphore must bypass a STUCK slot holder — but only when
the machine has spare capacity, never under saturation.

These pin the pure FIFO-classification rule in ``tests/app/integration/conftest.py``
without spawning any process or sleeping: build synthetic ticket + heartbeat files,
then assert how ``_classify`` divides the queue around a given waiter. A holder with
a fresh heartbeat occupies a slot; one whose heartbeat is older than ``_STUCK`` is
presumed wedged and bypassed *when ``bypass_ok``*; a ticket with no heartbeat is a true
waiter and keeps its FIFO place. The ``bypass_ok`` gate is what stops a starved holder
from being mistaken for a hung one under load and spawning a second concurrent suite
(the pile-up that defeats the 1-slot semaphore). (The timing/process behavior of the
live gate is exercised by running the real suite, like the merge lock's self-test.)
"""

import importlib.util
import json
import os

import pytest

_CONFTEST = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "integration", "conftest.py"
)


@pytest.fixture
def gate(tmp_path):
    spec = importlib.util.spec_from_file_location("_render_gate_conftest", _CONFTEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._GATE_DIR = str(tmp_path)
    mod._STUCK = 240
    return mod


def _ticket(gate, ns, pid):
    name = f"{ns}-{pid}"
    open(os.path.join(gate._GATE_DIR, name), "w").close()
    return (ns, pid, name)


def _heartbeat(gate, name, age):
    path = gate._hb_path(name)
    open(path, "w").close()
    now = os.path.getmtime(os.path.join(gate._GATE_DIR, name))
    os.utime(path, (now - age, now - age))


def test_lone_waiter_takes_the_only_slot(gate):
    me = _ticket(gate, 100, 1)
    now = os.path.getmtime(os.path.join(gate._GATE_DIR, me[2]))
    running, ahead, wedged = gate._classify([me], me[2], now, bypass_ok=True)
    assert (running, ahead, wedged) == (0, 0, 0)  # no one running/ahead/stuck → I go


def test_fresh_holder_blocks_a_later_waiter(gate):
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=1)  # actively progressing
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(gate._hb_path(holder[2])) + 1
    running, ahead, wedged = gate._classify([holder, me], me[2], now, bypass_ok=True)
    assert running == 1  # the slot is busy; with _SLOTS=1 I must wait
    assert ahead == 0    # the holder is running, not a waiter ahead of me
    assert wedged == 0   # a fresh holder is not stuck


def test_stuck_holder_is_bypassed_when_capacity_is_spare(gate):
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=gate._STUCK + 60)  # wedged: no progress
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(gate._hb_path(holder[2])) + gate._STUCK + 60
    running, ahead, wedged = gate._classify([holder, me], me[2], now, bypass_ok=True)
    assert running == 0  # wedged holder no longer counts → a slot is free for me
    assert ahead == 0
    assert wedged == 1   # and it is reported as exactly one stuck holder


def test_stuck_holder_is_NOT_bypassed_under_saturation(gate):
    # The dogpile fix: under load a stale heartbeat means STARVED, not hung. The holder
    # keeps its slot so we WAIT for it rather than starting a second CPU-bound suite.
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=gate._STUCK + 60)
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(gate._hb_path(holder[2])) + gate._STUCK + 60
    running, ahead, wedged = gate._classify([holder, me], me[2], now, bypass_ok=False)
    assert running == 1  # stale-but-not-bypassed → still occupies the slot
    assert ahead == 0
    assert wedged == 0   # nothing is bypassed under saturation


def test_earlier_true_waiter_keeps_its_place(gate):
    earlier = _ticket(gate, 100, 1)  # a waiter with no heartbeat, ahead of me
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(os.path.join(gate._GATE_DIR, me[2]))
    running, ahead, wedged = gate._classify([earlier, me], me[2], now, bypass_ok=True)
    assert running == 0
    assert ahead == 1   # FIFO preserved: I defer to the earlier waiter, not bypass it
    assert wedged == 0


def test_bypass_does_not_jump_an_earlier_waiter(gate):
    # A wedged holder frees the slot, but an earlier true waiter still goes first.
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=gate._STUCK + 60)
    earlier = _ticket(gate, 150, 2)  # true waiter, earlier than me
    me = _ticket(gate, 200, 3)
    now = os.path.getmtime(gate._hb_path(holder[2])) + gate._STUCK + 60
    running, ahead, wedged = gate._classify([holder, earlier, me], me[2], now, bypass_ok=True)
    assert running == 0  # holder bypassed
    assert ahead == 1    # but the earlier waiter is ahead of me → I still wait
    assert wedged == 1


def test_later_waiter_is_not_miscounted_as_stuck(gate):
    # Regression for the report miscount: a waiter who arrived BEHIND me (later ns, no
    # heartbeat) must count toward NEITHER waiters_ahead NOR wedged — it is not stuck.
    me = _ticket(gate, 100, 1)
    behind = _ticket(gate, 200, 2)  # arrived after me, still just waiting
    now = os.path.getmtime(os.path.join(gate._GATE_DIR, behind[2]))
    running, ahead, wedged = gate._classify([me, behind], me[2], now, bypass_ok=True)
    assert (running, ahead, wedged) == (0, 0, 0)  # nobody running, ahead, or stuck


def test_bypass_allowed_tracks_load_per_core(gate, monkeypatch):
    gate._BYPASS_MAXLOAD = 1.0
    monkeypatch.setattr(gate.os, "cpu_count", lambda: 10)
    monkeypatch.setattr(gate.os, "getloadavg", lambda: (5.0, 5.0, 5.0))
    assert gate._bypass_allowed() is True   # 5 < 10 cores → spare capacity, bypass OK
    monkeypatch.setattr(gate.os, "getloadavg", lambda: (33.0, 30.0, 25.0))
    assert gate._bypass_allowed() is False  # 33 > 10 cores → saturated, do not pile on


def test_bypass_allowed_fails_open_without_loadavg(gate, monkeypatch):
    def _boom():
        raise OSError("no loadavg")
    monkeypatch.setattr(gate.os, "getloadavg", _boom)
    assert gate._bypass_allowed() is True   # can't measure → preserve original behavior


# --- merge-lock holder priority (fixes the priority inversion) ----------------------------

def _write_marker(gate, tmp_path, token, daemon_pid):
    marker = tmp_path / "holder"
    gate._MERGE_MARKER = str(marker)
    marker.write_text(json.dumps({"token": token, "daemon_pid": daemon_pid}))
    return marker


def test_holds_merge_lock_true_for_matching_live_marker(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "_my_merge_lock_id", lambda: "abc123")
    monkeypatch.setattr(gate, "_alive", lambda pid: True)
    _write_marker(gate, tmp_path, token="abc123", daemon_pid=999)
    assert gate._holds_merge_lock() is True


def test_holds_merge_lock_false_for_a_different_worktrees_token(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "_my_merge_lock_id", lambda: "mine")
    monkeypatch.setattr(gate, "_alive", lambda pid: True)
    _write_marker(gate, tmp_path, token="theirs", daemon_pid=999)
    assert gate._holds_merge_lock() is False  # someone else holds it → no priority for us


def test_holds_merge_lock_false_when_daemon_is_dead(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "_my_merge_lock_id", lambda: "mine")
    monkeypatch.setattr(gate, "_alive", lambda pid: False)
    _write_marker(gate, tmp_path, token="mine", daemon_pid=999)
    assert gate._holds_merge_lock() is False  # stale marker never grants false priority


def test_holds_merge_lock_false_without_a_marker(gate, tmp_path, monkeypatch):
    gate._MERGE_MARKER = str(tmp_path / "absent")
    monkeypatch.setattr(gate, "_my_merge_lock_id", lambda: "mine")
    assert gate._holds_merge_lock() is False


def test_merge_lock_holder_takes_priority_slot_without_waiting(gate, monkeypatch):
    # A fresh non-holder already occupies the only slot; a NORMAL run would block forever.
    # The merge-lock holder must take a slot immediately so the lock never idles.
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=1)
    monkeypatch.setattr(gate, "_holds_merge_lock", lambda: True)
    monkeypatch.setattr(gate, "_SLOTS", 1)
    gate._acquire()  # returns immediately via the priority short-circuit (no wait loop)
    assert gate._heartbeat is not None
    assert os.path.exists(gate._heartbeat)  # we stamped our own heartbeat → visible to others


def test_non_holder_does_not_get_priority(gate, monkeypatch):
    # Sanity: when we do NOT hold the merge lock, the lone-waiter path still runs normally.
    monkeypatch.setattr(gate, "_holds_merge_lock", lambda: False)
    monkeypatch.setattr(gate, "_SLOTS", 1)
    gate._acquire()  # lone waiter, no one ahead → takes the slot the normal way
    assert gate._heartbeat is not None

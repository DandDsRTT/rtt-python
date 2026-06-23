"""The render-gate counting semaphore must bypass a STUCK slot holder.

These pin the pure FIFO-classification rule in ``tests/app/integration/conftest.py``
without spawning any process or sleeping: build synthetic ticket + heartbeat files,
then assert how ``_classify`` divides the queue around a given waiter. A holder with
a fresh heartbeat occupies a slot; one whose heartbeat is older than ``_STUCK`` is
presumed wedged and bypassed; a ticket with no heartbeat is a true waiter and keeps
its FIFO place. (The timing/process behavior of the live gate is exercised by running
the real suite, like the merge lock's own standalone self-test.)
"""

import importlib.util
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
    running, ahead = gate._classify([me], me[2], now)
    assert (running, ahead) == (0, 0)  # no one running, no one ahead → I go


def test_fresh_holder_blocks_a_later_waiter(gate):
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=1)  # actively progressing
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(gate._hb_path(holder[2])) + 1
    running, ahead = gate._classify([holder, me], me[2], now)
    assert running == 1  # the slot is busy; with _SLOTS=1 I must wait
    assert ahead == 0    # the holder is running, not a waiter ahead of me


def test_stuck_holder_is_bypassed(gate):
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=gate._STUCK + 60)  # wedged: no progress
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(gate._hb_path(holder[2])) + gate._STUCK + 60
    running, ahead = gate._classify([holder, me], me[2], now)
    assert running == 0  # wedged holder no longer counts → a slot is free for me
    assert ahead == 0


def test_earlier_true_waiter_keeps_its_place(gate):
    earlier = _ticket(gate, 100, 1)  # a waiter with no heartbeat, ahead of me
    me = _ticket(gate, 200, 2)
    now = os.path.getmtime(os.path.join(gate._GATE_DIR, me[2]))
    running, ahead = gate._classify([earlier, me], me[2], now)
    assert running == 0
    assert ahead == 1  # FIFO preserved: I defer to the earlier waiter, not bypass it


def test_bypass_does_not_jump_an_earlier_waiter(gate):
    # A wedged holder frees the slot, but an earlier true waiter still goes first.
    holder = _ticket(gate, 100, 1)
    _heartbeat(gate, holder[2], age=gate._STUCK + 60)
    earlier = _ticket(gate, 150, 2)  # true waiter, earlier than me
    me = _ticket(gate, 200, 3)
    now = os.path.getmtime(gate._hb_path(holder[2])) + gate._STUCK + 60
    running, ahead = gate._classify([holder, earlier, me], me[2], now)
    assert running == 0  # holder bypassed
    assert ahead == 1    # but the earlier waiter is ahead of me → I still wait

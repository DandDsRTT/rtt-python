import gc

import pytest


@pytest.fixture(autouse=True)
def _collect_render_garbage():
    # The render tests rebuild the whole page per test under NiceGUI's User simulation, and
    # render_main re-imports rtt.* each time, churning ~20k short-lived gc-tracked objects per
    # test. nicegui_reset_globals' own gc.collect() runs mid-teardown while those are still
    # reachable, so they survive into the next test and every later reset's collect scans an
    # ever-bigger heap (gc.collect() cost scales with live-object count) — the suite's runtime
    # climbs test over test. Collecting once here, after the user fixture has fully torn down,
    # frees that cycle's garbage so each test starts from a flat heap.
    yield
    gc.collect()

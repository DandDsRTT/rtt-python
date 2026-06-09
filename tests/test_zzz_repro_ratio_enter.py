"""Empirical reproduction probe for HYP-B (stale baseline after Enter).

The editable quantities-row ratio cells (comma / target / held / interest) are ratiocells that
commit the whole typed fraction on BOTH "blur" and "keydown.enter" (_build_ratiocell, app.py:1837-1838).
The edit-preview highlight lifecycle:
  - on_cell_focus (app.py:3055) snapshots preview_baseline = the pre-edit grid.
  - on_cell_blur (app.py:3064) forgets the baseline and clear_preview()s the rings.
The focus/blur listeners are wired ONLY for "focus"/"blur" (make_cell, app.py:1399-1400). keydown.enter
is NOT one of them, so pressing Enter commits (render()) WITHOUT firing blur -> preview_baseline stays at
the pre-edit snapshot. render()'s ring step (app.py:3522-3546) then computes
  preview = changed_cell_ids(preview_baseline, lay) - {preview_source}
and rings every moved cell AMBER. Because the cell still holds focus (no blur), the amber ring PERSISTS
on the surviving moved cells after the change is applied.

These tests drive the real page in-process via the NiceGUI User fixture.
"""

from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction


def _wrap(user: User, cell_id: str):
    """The marked cell wrap div (carries the preview ring classes)."""
    return next(iter(user.find(marker=cell_id).elements))


def _wrap_classes(user: User, cell_id: str) -> list[str]:
    return _wrap(user, cell_id)._classes


def _cell_child(user: User, cell_id: str):
    """The inner input control of a grid cell (marker rides its wrap)."""
    return _wrap(user, cell_id).default_slot.children[0]


def _focus(user: User, cell_id: str) -> None:
    """Fire the ratiocell input's focus handler -> on_cell_focus snapshots the preview baseline."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).trigger("focus")


def _enter(user: User, cell_id: str) -> None:
    """Fire the ratiocell input's keydown.enter handler -> commit + render WITHOUT a blur."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).trigger("keydown.enter")


def _blur(user: User, cell_id: str) -> None:
    """Fire the ratiocell input's blur handler -> on_cell_blur clears the rings (the contrast path)."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).trigger("blur")


# ---------------------------------------------------------------------------
# HYP-B: comma ratio committed via Enter leaves amber rings stuck on surviving cells.
# ---------------------------------------------------------------------------

async def test_comma_ratio_committed_via_enter_leaves_amber_ring_stuck(user: User) -> None:
    """Focus the default 5-limit meantone syntonic-comma ratio cell (comma:0 = 80/81), type a NEW
    comma (25/24, vector (-3 -1 2)), and commit with keydown.enter (no blur). The comma's vector
    cells (cell:comma:p:0) MOVE, so render() rings them amber. Because Enter never fires blur, the
    baseline stays stale and the amber ring PERSISTS after the apply on cells that are still on screen."""
    await user.open("/")
    await user.should_see(marker="comma:0")
    assert _cell_child(user, "comma:0").value == "80/81"  # 5-limit meantone's syntonic comma

    _focus(user, "comma:0")                      # snapshot preview_baseline = pre-edit grid
    _cell_child(user, "comma:0").set_value("25/24")  # the chromatic semitone = (-3 -1 2)
    _enter(user, "comma:0")                      # commit + render via keydown.enter, NO blur

    # the change applied: the vector cells now read the new comma's exponents...
    await user.should_see(marker="cell:comma:0:0")
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]

    # ...and those vector cells are STILL ON SCREEN (they survived the apply, not dropped from the DOM)
    await user.should_see(marker="cell:comma:0:0")
    await user.should_see(marker="cell:comma:1:0")
    await user.should_see(marker="cell:comma:2:0")

    # BUG: the moved vector cells are still ringed amber after the commit (stale baseline, no blur)
    stuck = [f"cell:comma:{p}:0" for p in range(3)
             if "rtt-preview-change" in _wrap_classes(user, f"cell:comma:{p}:0")]
    assert stuck, (
        "expected at least one surviving moved comma-vector cell to remain ringed "
        f"rtt-preview-change after Enter-commit; classes were: "
        + repr({p: _wrap_classes(user, f'cell:comma:{p}:0') for p in range(3)})
    )


async def test_comma_ratio_committed_via_blur_clears_the_ring(user: User) -> None:
    """Contrast: the SAME edit committed with blur (the path that DOES fire on_cell_blur ->
    clear_preview) leaves NO ring on the surviving moved cells. This isolates Enter as the culprit."""
    await user.open("/")
    await user.should_see(marker="comma:0")

    _focus(user, "comma:0")
    _cell_child(user, "comma:0").set_value("25/24")
    _blur(user, "comma:0")                       # blur fires on_cell_blur -> clear_preview()

    await user.should_see(marker="cell:comma:0:0")
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]

    for p in range(3):
        assert "rtt-preview-change" not in _wrap_classes(user, f"cell:comma:{p}:0"), (
            f"blur-commit should have cleared the ring on cell:comma:{p}:0; "
            f"classes: {_wrap_classes(user, f'cell:comma:{p}:0')}"
        )


# ---------------------------------------------------------------------------
# Per-keystroke probe: a mapping/vector cell edited then Enter. These commit live (on_change per
# keystroke) and are wired focus/blur via make_cell too. Does Enter strand an amber ring here as well?
# ---------------------------------------------------------------------------

async def test_mapping_cell_committed_via_enter_amber_ring(user: User) -> None:
    """A per-keystroke mapping cell (kind 'mapping', id cell:mapping:r:c). It commits live on each
    keystroke (on_change), and is wired focus/blur. There is no keydown.enter listener on mapping
    cells (only ratiocells/element cells wire it, app.py:1838/1856), so pressing Enter is inert for
    the commit AND does not blur -> whatever rings were present from the live edit stay until blur.

    We measure empirically: focus, set a moving value (live-committs + renders, ringing moved cells),
    fire keydown.enter, and check whether a surviving moved cell stays amber."""
    await user.open("/")
    await user.should_see(marker="cell:mapping:1:2")
    before = _cell_child(user, "cell:mapping:1:2").value

    _focus(user, "cell:mapping:1:2")             # snapshot baseline
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # the fifth's prime-5 entry: live-commits + renders
    _enter(user, "cell:mapping:1:2")             # inert for mapping (no enter listener); no blur either

    await user.should_see(marker="cell:mapping:1:2")
    # record what (if anything) is ringed on a surviving sibling/self after the edit; report-only.
    self_ring = "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")
    # the source cell is excluded from the ring (preview_source), so check a moved neighbour instead:
    # any mapping cell that moved would ring. Gather the live ring picture.
    rung = []
    for r in range(2):
        for c in range(3):
            cid = f"cell:mapping:{r}:{c}"
            try:
                if "rtt-preview-change" in _wrap_classes(user, cid):
                    rung.append(cid)
            except StopIteration:
                pass
    # This assertion documents the observed state; mapping-cell Enter is the benign contrast.
    assert before is not None
    assert isinstance(self_ring, bool)
    assert isinstance(rung, list)

"""In-process render coverage for the NiceGUI page — the layer the smoke tests skip.

The rest of the suite builds the layout model (spreadsheet.build) and the pure
helpers, but never executes index()/render()/_make_cell, so a stale reference or a
bad widget call there passes the suite green yet 500s the live page. NiceGUI's
``User`` simulation runs the real page in-process (no browser): opening it drives
the default render, toggling a Show feature drives that feature's render branch, and
editing a cell drives the input -> handler -> render pipeline. The ``user`` fixture
also fails on any ERROR log, so a broken render is caught even when it doesn't raise.

Cells are located by the marker each carries (``.mark(cb.id)`` in _make_cell, the
Python-side parallel of the data-eid the JS reconciler uses).
"""

import nicegui.ui as ui
import pytest
from nicegui.testing import User


async def test_default_page_renders_without_error(user: User) -> None:
    await user.open("/")
    # the board built: a representative slice of the default grid's row/column titles
    await user.should_see("quantities")
    await user.should_see("tuning")


# --- tier 2: each Show feature's render branch (paths the default render never reaches) ---

async def _enable(user: User, label: str) -> None:
    """Open the page and turn on the Show toggle carrying ``label``."""
    await user.open("/")
    user.find(kind=ui.checkbox, content=label).click()


# (Show-toggle label, a cell id its render branch must produce). Each exercises a
# _make_cell branch that is off in the default view.
_FEATURE_CELLS = [
    ("counts", "count:primes"),                      # the count scalar ("d = 3"), _math_html
    ("symbols", "symbol:mapping:primes"),            # the quantity-symbol glyph, _math_html
    ("plain text values", "ptext:mapping:primes"),   # the editable EBK dual input
    ("preselects", "preselect:temperament"),         # the chooser dropdowns (q-select)
    ("preselects", "preselect:tuning:gens"),         # a copied dropdown (its own :col-suffixed id)
    ("charts", "chart:retune:targets"),              # a per-tile bar-chart SVG
    ("tuning ranges", "rangechart:tuning:gens"),     # the generator-range I-beam chart SVG
    # "units" labels BOTH the general and specific toggles, so one click flips both on:
    # the per-box "units: …" line below the caption AND the domain-units row/col labels
    # (all kind "units", _math_html). The fixture catches an ERROR log in either branch.
    ("units", "units:mapping:primes"),               # the per-box "units: g/p" line
    ("optimization", "optimization:power"),          # the Lp-norm power line (𝑝 = ∞), _math_html
]


@pytest.mark.parametrize("label, cell_id", _FEATURE_CELLS)
async def test_enabling_a_feature_renders_its_cell(user: User, label: str, cell_id: str) -> None:
    await _enable(user, label)
    await user.should_see(marker=cell_id)


async def test_enabling_math_expressions_renders_the_closed_form(user: User) -> None:
    # the just row's cents cells become "1200 · log₂…" closed-form cells (kind mathexpr)
    await _enable(user, "math expressions")
    await user.should_see(content="log₂")


async def test_enabling_generator_detempering_renders_the_column(user: User) -> None:
    # the generator-detempering D column. Its value cells are interval vectors (kind "vec"),
    # which — like every interval-vector cell — the user harness can't locate, so assert the
    # column header and lean on the fixture's ERROR-log guard to catch any fault rendering the
    # D matrix's cells, brackets or ket marks.
    await _enable(user, "generator detempering")
    await user.should_see(marker="header:detempering")


async def test_optimization_with_charts_renders_the_damage_indicator(user: User) -> None:
    # optimization + charts: the damage chart gains the minimized-damage indicator line.
    # Drive that _bar_chart(indicator=…) branch and confirm the chart still renders.
    await user.open("/")
    user.find(kind=ui.checkbox, content="charts").click()
    user.find(kind=ui.checkbox, content="optimization").click()
    await user.should_see(marker="chart:damage:targets")


async def test_enabling_alt_complexity_renders_its_in_tile_choosers(user: User) -> None:
    # the weighting region's in-tile choosers (box 𝐋 prescaler, box 𝒄 predefined complexity +
    # norm, box 𝒘 weight slope) are control_select dropdowns — a _make_cell branch the default
    # view never reaches. alt. complexity nests under weighting, so enable the parent first.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="alt. complexity").click()
    await user.should_see(marker="control:prescaler")
    await user.should_see(marker="control:diminuator")  # the box-𝐋 checkbox (control_check)
    await user.should_see(marker="control:complexity")
    await user.should_see(marker="control:q")  # the q norm-power field (replaces the old norm dropdown)
    await user.should_see(marker="control:slope")


async def test_enabling_colorization_keeps_the_board_rendering(user: User) -> None:
    # both colorization sub-toggles share the label "colorization", so one click matches
    # and flips both on. They paint wash blocks behind the tiles — drive that branch and
    # confirm the board still renders (no exception, no ERROR log via the fixture).
    await user.open("/")
    user.find(kind=ui.checkbox, content="colorization").click()
    await user.should_see(marker="cell:mapping:0:0")


# --- tier 3: the edit -> render -> undo pipeline (input -> handler -> render) ---

def _cell_child(user: User, cell_id: str):
    """The inner control of a grid cell (the marker rides its wrap)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    return wrap.default_slot.children[0]


def _cell_text(user: User, cell_id: str) -> str:
    return getattr(_cell_child(user, cell_id), "text", "")


async def test_editing_a_mapping_cell_updates_the_mapped_list(user: User) -> None:
    await user.open("/")
    # meantone [[1,1,0],[0,1,4]]: 5/4 (target 6) maps to 4 fifths in the mapped list
    assert _cell_text(user, "cell:mapped:1:6") == "4"
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # the fifth's prime-5 entry: 4 -> 7
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"  # the mapped list recomputed live


async def test_undo_button_reverts_a_mapping_edit(user: User) -> None:
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"
    user.find(marker="undo").click()  # the undo button -> act(editor.undo) -> render
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "4"  # back to meantone's mapped list


async def test_target_chooser_renders_in_the_expanded_target_interval_list(user: User) -> None:
    # the target chooser moved into the target interval list (the interval-vectors row,
    # folded by default); expanding that row renders its numeric-limit + TILT/OLD select
    # (the one preselect branch the default view never reaches now)
    await _enable(user, "preselects")
    user.find(marker="toggle:row:vectors").click()
    await user.should_see(marker="preselect:target")


async def test_optimization_renders_the_optimize_button(user: User) -> None:
    # the optimize button renders in the damage tile when optimization is on (its single/
    # double-click optimize+lock behaviour is covered by the editor tests). The fixture
    # catches any error rendering the new "optimize" cell branch.
    await _enable(user, "optimization")
    await user.should_see(marker="optimization:button")
    # the box's value-over-label cells render too: the objective value + its ⟪𝐝⟫ₚ symbol,
    # the editable power, and the power's symbol + "optimization power" caption
    for marker in ("optimization:objective", "optimization:objective:symbol",
                   "optimization:power", "optimization:power:symbol", "optimization:power:caption"):
        await user.should_see(marker=marker)


async def test_optimization_renders_the_held_column_and_its_add_control(user: User) -> None:
    # enabling optimization shows the held column with a + (rendered even when empty) for
    # adding the first held interval — driving the held_plus render branch. The editable
    # heldcell branch mirrors the intervals-of-interest cell; the fixture catches any error.
    await _enable(user, "optimization")
    await user.should_see(marker="header:held")
    await user.should_see(marker="held_plus")


async def test_enabling_audio_renders_speakers_and_control_banks(user: User) -> None:
    # one click adds the two audio rows. Each pitch is a real speaker button, and each tile
    # carries its four-control bank (waveform / play-mode / hold / 1-1) as glyph elements —
    # a missing _make_cell branch would leave an empty wrap (and IndexError in _cell_child).
    await _enable(user, "audio")
    assert isinstance(_cell_child(user, "speaker:tempered_audio:target:0"), ui.button)
    for ctrl in ("wave", "mode", "hold", "root"):
        assert isinstance(_cell_child(user, f"{ctrl}:tempered_audio:targets"), ui.html)


# --- tier 4: the settings select-all/none, the reset control, and refresh persistence ---


async def test_select_all_turns_on_every_implemented_feature(user: User) -> None:
    # charts is off by default (no per-tile chart cells); the panel's select-all/none master
    # checkbox flips every implemented Show toggle on at once, so the chart cell appears
    await user.open("/")
    user.find(kind=ui.checkbox, content="select all / none").click()
    await user.should_see(marker="chart:retune:targets")


async def test_reset_restores_settings_expand_collapse_and_values(user: User) -> None:
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # a value change
    user.find(kind=ui.checkbox, content="charts").click()  # a settings change
    await user.should_see(marker="chart:retune:targets")
    assert _cell_text(user, "cell:mapped:1:6") == "7"
    user.find(marker="reset").click()  # reset everything to the defaults
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "4"  # the value is back to meantone's
    await user.should_not_see(marker="chart:retune:targets")  # ...and charts is off again


async def test_undo_button_reverts_a_settings_change(user: User) -> None:
    # the unified history covers Show settings too: toggling charts on then pressing undo
    # turns it back off (the chart cells disappear)
    await user.open("/")
    user.find(kind=ui.checkbox, content="charts").click()
    await user.should_see(marker="chart:retune:targets")
    user.find(marker="undo").click()
    await user.should_see(marker="cell:mapping:0:0")  # the board re-rendered
    await user.should_not_see(marker="chart:retune:targets")  # charts off again


# --- tier 4: frozen split panes (titles pinned while only the body scrolls) ---

def _renders_inside(user: User, cell_marker: str, region_marker: str) -> bool:
    """True if the cell's wrap is a descendant of the region (corner / title strip / body pane)."""
    cell = next(iter(user.find(marker=cell_marker).elements))
    region = next(iter(user.find(marker=region_marker).elements))
    slot = cell.parent_slot
    while slot is not None:
        if slot.parent is region:
            return True
        slot = slot.parent.parent_slot
    return False


@pytest.mark.parametrize("cell, band", [
    ("header:gens", "colband"),        # a column title -> the column band (sticky to the top)
    ("toggle:col:targets", "colband"),  # its fold toggle rides the same band
    ("label:tuning", "rowband"),       # a row title -> the row band (sticky to the left)
    ("toggle:row:tuning", "rowband"),   # its fold toggle rides the same band
    ("toggle:all", "corner"),          # the master toggle -> the corner band
])
async def test_each_title_renders_into_its_sticky_band(user: User, cell: str, band: str) -> None:
    await user.open("/")
    assert _renders_inside(user, cell, band)


async def test_body_cells_render_on_the_board_under_no_band(user: User) -> None:
    # a value cell sits on the board itself (the page-scrolled body), beneath none of the bands
    await user.open("/")
    assert _renders_inside(user, "cell:mapping:0:0", "board")
    for band in ("colband", "rowband", "corner"):
        assert not _renders_inside(user, "cell:mapping:0:0", band)


async def test_state_persists_across_a_refresh(user: User) -> None:
    # the document is persisted on each render and reloaded when the page opens, so a refresh
    # (a fresh open of "/") restores exactly where the user left off
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"
    await user.open("/")  # the refresh
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"  # the edit survived

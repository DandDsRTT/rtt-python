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

from rtt.web.editor import Editor


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


async def test_enabling_all_interval_renders_the_target_controls_checkbox(user: User) -> None:
    # the show-panel "all-interval" entry (now interactive, nested under weighting) reveals the
    # target-controls "all-interval" checkbox — a control_check in the target list controls. Those
    # ride the vectors row (folded by default), so expand it, enable weighting (the entry's parent
    # in the panel), then the entry itself, and drive the checkbox's render branch.
    await user.open("/")
    user.find(marker="toggle:row:vectors").click()  # expand the target-list row (folded by default)
    user.find(kind=ui.checkbox, content="weighting").click()  # reveal the nested all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()
    await user.should_see(marker="control:all_interval")


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


def _stacked_face(user: User, cell_id: str):
    """The (int label, fraction label) of an editable cents cell's stacked face — the
    overlay that makes the value read like a read-only tval cell (the whole part big, the
    decimal small and below). The editable input is child[0]; the face is child[1] (a
    .rtt-tval div holding the .rtt-cents-int / .rtt-cents-frac labels)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    face = wrap.default_slot.children[1]
    return face.default_slot.children[0], face.default_slot.children[1]


async def test_tuning_preselect_offers_only_lp_while_alternatives_are_shelved(user: User) -> None:
    # alternative-complexity schemes are gated behind the (shelved) alt. complexity setting,
    # so with it off the tuning chooser offers only the strictly log-product scheme. (The chooser's
    # options are {value: label}, the labels 𝑇-prefixed when target-based; here the default scheme
    # is all-interval, so check the offered values.)
    await user.open("/")
    user.find(kind=ui.checkbox, content="preselects").click()
    await user.should_see(marker="preselect:tuning")
    assert list(_cell_child(user, "preselect:tuning").options) == ["minimax-S"]


async def test_editing_a_mapping_cell_updates_the_mapped_list(user: User) -> None:
    await user.open("/")
    # meantone [[1,1,0],[0,1,4]]: 5/4 (target 6) maps to 4 fifths in the mapped list
    assert _cell_text(user, "cell:mapped:1:6") == "4"
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # the fifth's prime-5 entry: 4 -> 7
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"  # the mapped list recomputed live


async def test_editing_a_generator_tuning_cell_applies_an_override(user: User) -> None:
    await user.open("/")
    # the generator tuning map cells are editable: typing a cents value overrides that generator
    # (on_gentuning_change -> editor -> render). With no override the cell would re-render to the
    # computed optimum, so seeing the typed 700.000 survive the render proves the override applied
    _cell_child(user, "tuning:gen:1").set_value("700.000")
    await user.should_see(marker="tuning:gen:1")
    assert _cell_child(user, "tuning:gen:1").value == "700.000"


async def test_editable_gen_tuning_cell_renders_a_stacked_cents_face(user: User) -> None:
    # the generator tuning map cells are editable inputs, but a 3-dp cents value (e.g. 697.564)
    # overflows the 30px square as a single line. They must show the same stacked int-over-
    # fraction face as the read-only cents cells — the whole part big over a smaller dot-led
    # fraction — so the value fits. Assert the live value splits across the two face labels.
    await user.open("/")
    value = _cell_child(user, "tuning:gen:1").value  # the single-line cents value, e.g. "697.564"
    int_lbl, frac_lbl = _stacked_face(user, "tuning:gen:1")
    assert "." not in int_lbl.text                  # the whole part stands alone (no decimal)
    assert frac_lbl.text.startswith(".")            # the fraction stacks under, dot-led
    assert int_lbl.text + frac_lbl.text == value    # and the two reconstruct the cell's value


async def test_editing_a_target_cell_overrides_the_set(user: User) -> None:
    await user.open("/")
    user.find(marker="toggle:row:vectors").click()  # expand the target interval list row
    # the target interval list cells are editable: overriding a component freezes the set as an
    # explicit override. The default first target is 2/1 = (1 0 0); typing 2 there survives the
    # render only if the override applied (else the cell reverts to the default's component)
    _cell_child(user, "cell:vec:targets:0:0").set_value("2")
    await user.should_see(marker="cell:vec:targets:0:0")
    assert _cell_child(user, "cell:vec:targets:0:0").value == "2"


async def test_typing_the_prescaler_plain_text_overrides_the_scheme(user: User) -> None:
    # the bare prescaler 𝐿 tile's plain-text box is the OTHER editable surface (alongside
    # the diagonal cells): typing a d×d matrix EBK with all off-diagonal entries zero parses
    # to a d-tuple diagonal (on_ptext_edit -> editor.set_custom_prescaler_text), which then
    # drives every downstream consumer. The diagonal grid cell must reflect the typed value
    # on re-render — would otherwise be the scheme's log₂3 = 1.585 default.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens the prescaling row
    user.find(kind=ui.checkbox, content="plain text values").click()  # the ptext band
    await user.should_see(marker="ptext:prescaling:primes")
    _cell_child(user, "ptext:prescaling:primes").set_value("[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩")
    await user.should_see(marker="cell:prescaling:primes:1:1")
    # the diagonal cell now reads the typed value (rather than reverting to the scheme's 1.585)
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "4"


async def test_unparseable_prescaler_plain_text_reddens_the_box(user: User) -> None:
    # an off-diagonal nonzero is invalid (𝐿 is diagonal), so the input box flags the typed
    # text via the rtt-ptext-error class instead of mangling the override — mirroring the
    # mapping / comma-basis duals' validation path. The override stays untouched (the editor
    # would otherwise have written a non-diagonal 𝐿, which the math layer can't honour).
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="plain text values").click()
    await user.should_see(marker="ptext:prescaling:primes")
    _cell_child(user, "ptext:prescaling:primes").set_value("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩")
    # the input box surfaces the rejection via the same red-outline class the other duals use
    classes = _cell_child(user, "ptext:prescaling:primes").classes
    assert "rtt-ptext-error" in classes
    # the diagonal grid cell stays at its scheme-derived 1.585 (no override applied)
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"


async def test_editing_a_prescaler_diagonal_cell_overrides_the_scheme(user: User) -> None:
    # the bare prescaler 𝐿's diagonal cells (prescalercell kind) are editable: typing into one
    # routes through on_prescaler_change -> set_custom_prescaler_entry, threads as the
    # custom_prescaler kwarg into spreadsheet.build, and re-renders. The 5-limit default scheme
    # seeds the diagonal at log₂2/log₂3/log₂5 = (1, 1.585, 2.322); overriding prime 3 to 4.0
    # must survive the render in the diagonal cell AND retune the comma column's product tile
    # (𝐿C reads the same diagonal, so its prime-3 row goes from -4·1.585 = -6.340 to -4·4 = -16).
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # the prescaling row is gated on weighting
    await user.should_see(marker="cell:prescaling:primes:1:1")
    _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
    await user.should_see(marker="cell:prescaling:primes:1:1")
    # the typed value rode the override back to the diagonal cell on re-render (it would
    # otherwise have reverted to the scheme's 1.585), and the off-diagonal "0" stays read-only
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "4"  # bare (no fractional part)
    # the off-diagonal cell is plain tval "0" (the rtt-tval div, no editable input); a render
    # error in that branch would surface here via the fixture's ERROR-log guard
    await user.should_see(marker="cell:prescaling:primes:0:1")


async def test_editable_prescaler_cell_renders_a_stacked_cents_face(user: User) -> None:
    # the bare prescaler 𝐋 diagonal cells are editable too; the 5-limit default seeds prime 3's
    # diagonal at log₂3 = 1.585, a 3-dp value that overflows the square as a single line. It must
    # read as the same stacked int-over-fraction face. Enable weighting (gates the prescaling row).
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    await user.should_see(marker="cell:prescaling:primes:1:1")
    value = _cell_child(user, "cell:prescaling:primes:1:1").value  # the single-line value, e.g. "1.585"
    int_lbl, frac_lbl = _stacked_face(user, "cell:prescaling:primes:1:1")
    assert "." not in int_lbl.text                  # the whole part stands alone
    assert frac_lbl.text.startswith(".")            # the fraction stacks under, dot-led
    assert int_lbl.text + frac_lbl.text == value    # and the two reconstruct the cell's value


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


async def test_chooser_popups_open_wide_enough_for_one_line_entries(user: User) -> None:
    # A chooser's open popup must grow to fit its longest entry on one line
    # (popup-content-style width:max-content), never capped at the trigger cell's width —
    # long names (e.g. the "established tuning scheme" list) were truncating. The popup
    # still stays at least as wide as the trigger (a min-width floor), so the open list is
    # never narrower than the box it drops from.
    await _enable(user, "preselects")
    for cell_id in ("preselect:temperament", "preselect:tuning"):
        style = _cell_child(user, cell_id)._props["popup-content-style"]
        assert "width:max-content" in style, f"{cell_id}: {style}"
        assert style.startswith("min-width:"), f"{cell_id}: {style}"


async def test_temperament_divider_rows_render_as_disabled_options(user: User) -> None:
    # the prime-limit divider rows (the "N-limit" headers) read as headers, not choices: each is
    # passed to Quasar with disable=True, so the q-item takes no hover highlight and a
    # click on it neither picks it nor closes the popup. The named presets stay pickable.
    await _enable(user, "preselects")
    select = _cell_child(user, "preselect:temperament")
    option_by_value = dict(zip(select._values, select._props["options"]))
    assert option_by_value["hdr:5"]["disable"] is True
    assert option_by_value["hdr:13"]["disable"] is True
    assert "disable" not in option_by_value["13:Marvel"]


async def test_temperament_chooser_omits_the_offlist_prompt_from_its_list(user: User) -> None:
    # the "-" prompt is a placeholder, not a temperament. The open list holds only the
    # prime-limit dividers and their presets — there is no pickable "-" row, and no ""
    # sentinel value sitting behind one.
    await _enable(user, "preselects")
    select = _cell_child(user, "preselect:temperament")
    assert "" not in select._values
    assert "-" not in select._labels


async def test_temperament_chooser_shows_the_prompt_as_a_placeholder_when_no_preset_matches(user: User) -> None:
    # the prompt lives in the closed box, not the list: with a preset active (the default
    # meantone) the box shows that preset and no override; once the mapping leaves every
    # preset the box falls back to "-" via Quasar's display-value.
    await _enable(user, "preselects")
    assert "display-value" not in _cell_child(user, "preselect:temperament")._props
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # 4 -> 7 leaves the meantone preset
    await user.should_see(marker="preselect:temperament")
    assert _cell_child(user, "preselect:temperament")._props.get("display-value") == "-"


async def test_tuning_chooser_shows_the_prompt_as_a_placeholder_when_off_list(user: User) -> None:
    # the tuning chooser names the active scheme; refine it past the named list (here by
    # setting a finite optimization power, which resolves to an unnamed spec) and the closed
    # box falls back to "-" via Quasar's display-value — never a blank field, never a row.
    await user.open("/")
    user.find(kind=ui.checkbox, content="preselects").click()
    user.find(kind=ui.checkbox, content="optimization").click()
    assert "display-value" not in _cell_child(user, "preselect:tuning")._props
    _cell_child(user, "optimization:power").set_value("2")  # minimax (∞) -> a miniRMS spec (no name)
    await user.should_see(marker="preselect:tuning")
    assert _cell_child(user, "preselect:tuning")._props.get("display-value") == "-"


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


# --- tier 4: frozen split panes (titles frozen outside the body scroller) ---

def _renders_inside(user: User, cell_marker: str, region_marker: str) -> bool:
    """True if the cell's wrap is a descendant of the region (corner / column strip / body board)."""
    cell = next(iter(user.find(marker=cell_marker).elements))
    region = next(iter(user.find(marker=region_marker).elements))
    slot = cell.parent_slot
    while slot is not None:
        if slot.parent is region:
            return True
        slot = slot.parent.parent_slot
    return False


@pytest.mark.parametrize("cell, region", [
    ("header:gens", "colheadinner"),       # a column title -> the column-title strip (above the body)
    ("toggle:col:targets", "colheadinner"),  # its fold toggle rides the same strip
    ("label:tuning", "rowband"),           # a row title -> the sticky-left row band (inside the body)
    ("toggle:row:tuning", "rowband"),       # its fold toggle rides the same band
    ("toggle:all", "corner"),              # the master toggle -> the corner (frozen both)
])
async def test_each_title_renders_into_its_frozen_region(user: User, cell: str, region: str) -> None:
    await user.open("/")
    assert _renders_inside(user, cell, region)


async def test_body_cells_render_on_the_board_under_no_frozen_region(user: User) -> None:
    # a value cell sits on the board (.rtt-gridcontent, the body scroll content), beneath none of
    # the frozen regions that sit outside / sticky-within the scroller
    await user.open("/")
    assert _renders_inside(user, "cell:mapping:0:0", "board")
    for region in ("colheadinner", "rowband", "corner"):
        assert not _renders_inside(user, "cell:mapping:0:0", region)


async def test_settings_frozen_header_matches_the_grid_column_strip_height(user: User) -> None:
    # "exactly the same height as the frozen part of the main app pane": render() sizes the settings
    # pane's frozen header to the layout's freeze_y — the very value the grid's frozen column strip
    # is sized to — so the two frozen/scrolling seams sit at the same height across the app.
    await user.open("/")
    frozen = next(iter(user.find(marker="showfrozen").elements))
    colhead = next(iter(user.find(marker="colhead").elements))
    assert frozen._style.get("height")  # the header is sized (not left to hug its content)...
    assert frozen._style.get("height") == colhead._style.get("height")  # ...to the strip's height


def _px(el, prop: str) -> float:
    return float(el._style.get(prop).rstrip("px"))


async def test_grid_pane_hugs_the_grid_with_a_margin_all_round(user: User) -> None:
    # the grey grid pane hugs the grid + a _PAD (12px) margin on EVERY side, so its grey shows past
    # the gridlines all round (white beyond). The body still fills to the pane's right/bottom edges
    # (so a scrolling grid's scrollbars sit flush there, no grey stranded outside them) — the margin
    # comes from sizing the PANE _PAD larger than the body content, not from insetting the body. On
    # the right the pane also clears the last column's title overhang (it renders unwrapped past the
    # narrow interest column), so the long header shows instead of clipping. width = board width +
    # title overhang + 2·PAD; height = board + the column strip + 2·PAD.
    await user.open("/")
    lay = Editor().layout()  # exactly the layout the fresh-page default render builds
    pane = next(iter(user.find(marker="gridpane").elements))
    board = next(iter(user.find(marker="board").elements))
    colhead = next(iter(user.find(marker="colhead").elements))
    assert _px(board, "width") == lay.width                          # the rendered board IS the footprint
    assert lay.right_overhang > 0                                    # the interest title does overhang
    assert _px(pane, "width") == _px(board, "width") + lay.right_overhang + 24   # footprint + overhang + both margins
    assert _px(pane, "height") == _px(board, "height") + _px(colhead, "height") + 24  # body + strip + both margins


async def test_settings_body_caps_below_the_window_so_it_doesnt_scroll_when_it_fits(user: User) -> None:
    # the settings body sizes to its own content but render() caps it at the window less the inset and
    # the frozen header (calc(100vh - (12 + freeze_y)px)), so it scrolls only once its content genuinely
    # exceeds that — a self-contained cap that doesn't depend on the flex hug rounding out exactly.
    await user.open("/")
    scroll = next(iter(user.find(marker="showscroll").elements))
    colhead = next(iter(user.find(marker="colhead").elements))
    fy = _px(colhead, "height")  # the frozen header / column-strip height (freeze_y)
    assert scroll._style.get("max-height") == f"calc(100vh - {12 + fy}px)"


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

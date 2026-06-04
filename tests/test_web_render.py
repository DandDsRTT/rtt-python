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
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web.editor import Editor


async def test_default_page_renders_without_error(user: User) -> None:
    await user.open("/")
    # the board built: a representative slice of the default grid's row/column titles
    await user.should_see("quantities")
    await user.should_see("tuning")


# --- tier 2: each Show feature's render branch (paths the default render never reaches) ---

# The "general" Show layers are toggled by clicking their part of the dummy tile (located by
# key); the "specific boxes & controls" group is still a checkbox column (located by label).
# _toggle hides that split so a test just names the layer it wants and doesn't care which.
_GENERAL_KEY_BY_LABEL = {label: key for key, label, _d in dict(show_settings.SHOW_GROUPS)["general"]}


def _toggle(user: User, label: str) -> None:
    """Flip the Show layer carrying ``label`` — a general layer via its dummy-tile part, a
    specific-group layer via its checkbox."""
    key = _GENERAL_KEY_BY_LABEL.get(label)
    if key is not None:
        user.find(marker=f"showpart:{key}").click()
    else:
        user.find(kind=ui.checkbox, content=label).click()


async def _enable(user: User, label: str) -> None:
    """Open the page and turn on the Show toggle carrying ``label``."""
    await user.open("/")
    _toggle(user, label)


# (Show-toggle label, a cell id its render branch must produce). Each exercises a
# _make_cell branch that is off in the default view.
_FEATURE_CELLS = [
    ("counts", "count:primes"),                      # the count scalar ("d = 3"), _math_html
    ("symbols", "symbol:mapping:primes"),            # the quantity-symbol glyph, _math_html
    ("plain text values", "ptext:mapping:primes"),   # the editable EBK dual input
    ("presets", "preset:temperament"),         # the chooser dropdowns (q-select)
    ("presets", "preset:tuning:gens"),         # a copied dropdown (its own :col-suffixed id)
    ("charts", "chart:retune:targets"),              # a per-tile bar-chart SVG
    ("tuning ranges", "rangechart:tuning:gens"),     # the generator-range I-beam chart SVG
    # "units" labels BOTH the general and specific toggles, so one click flips both on:
    # the per-box "units: …" line below the caption AND the domain-units row/col labels
    # (all kind "units", _math_html). The fixture catches an ERROR log in either branch.
    ("units", "units:mapping:primes"),               # the per-box "units: g/p" line
    ("optimization", "optimization:power"),          # the editable Lp-power field (∞ over "(max)"), powerinput
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
    _toggle(user, "charts")
    user.find(kind=ui.checkbox, content="optimization").click()
    await user.should_see(marker="chart:damage:targets")


async def test_enabling_all_interval_renders_the_target_controls_checkbox(user: User) -> None:
    # the show-panel "all-interval" entry (now interactive, nested under weighting) reveals the
    # target-controls "all-interval" checkbox — a control_check in the target list controls. Those
    # ride the vectors row (open by default), so enable weighting (the entry's parent in the
    # panel), then the entry itself, and drive the checkbox's render branch.
    await user.open("/")
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


async def test_settings_and_controls_carry_hover_tooltips(user: User) -> None:
    # the Show toggles and the interactive grid controls all get explanatory hover text
    # (rtt.web.tooltips). A tooltip renders hidden until hover, so the User sim's visible-only
    # search can't see one — scan the client's element registry for the attached Tooltips.
    await user.open("/")
    tips = [el.text for el in user.client.elements.values() if isinstance(el, Tooltip)]
    assert any("name caption" in t for t in tips)       # the "names" Show toggle's help (now a tile part)
    assert any("map to this prime" in t for t in tips)  # the always-present mapping cells' help


async def test_hover_tooltips_wait_before_appearing(user: User) -> None:
    # the tooltips defaulted to Quasar's 0 ms show delay, popping the instant the cursor crossed
    # any control and burying the dense grid in hover help. Every tooltip now shares one show
    # delay (set on the Tooltip element's default props) so the help waits for a deliberate hover
    # rather than flashing on every passing cursor. The whole population carries it, chrome and
    # grid controls alike, so no path can slip back to instant.
    await user.open("/")
    tips = [el for el in user.client.elements.values() if isinstance(el, Tooltip)]
    assert tips  # the page does build tooltips
    assert all(int(el._props.get("delay", 0)) >= 500 for el in tips)


def _part_classes(user: User, key: str) -> list[str]:
    """The CSS classes render() has put on the general dummy tile's part for ``key``."""
    return next(iter(user.find(marker=f"showpart:{key}").elements))._classes


async def test_dummy_tile_parts_reflect_and_drive_the_live_show_state(user: User) -> None:
    # the general tile is the checkbox column's alternative: render() must paint each part by the
    # live setting (black-on / grey-off), keep a value-cell part inert until its host cell shows,
    # and — for mnemonics specifically — track the NAME's colour while only the underline tracks
    # the mnemonics toggle (so a shown name with mnemonics off isn't greyed mid-word). A click on
    # a part flips that layer; a refinement (equivalences/mnemonics) also pulls its base layer on.
    await user.open("/")
    # default view: names + gridded values shown, symbols hidden
    assert "rtt-part-on" in _part_classes(user, "names")
    assert "rtt-part-on" in _part_classes(user, "gridded_values")
    assert "rtt-part-off" in _part_classes(user, "symbols")
    # a refinement is never inert: equivalences is a live click target even with symbols hidden
    assert "rtt-part-inert" not in _part_classes(user, "equivalences")
    # mnemonics' colour follows the shown name (on), but its underline is off until toggled
    assert "rtt-part-on" in _part_classes(user, "mnemonics")
    assert "rtt-mnem-underline" not in _part_classes(user, "mnemonics")
    # click the equivalence -> it pulls its base symbol layer on too (both now shown)
    user.find(marker="showpart:equivalences").click()
    assert "rtt-part-on" in _part_classes(user, "equivalences")
    assert "rtt-part-on" in _part_classes(user, "symbols")
    # the surviving inert relationship is containment: the value/closed-form parts live INSIDE the
    # gridded cell, so hiding it leaves them nowhere to draw -> inert until the cell is shown again
    user.find(marker="showpart:gridded_values").click()
    assert "rtt-part-off" in _part_classes(user, "gridded_values")
    assert "rtt-part-inert" in _part_classes(user, "math_expressions")
    assert "rtt-part-inert" in _part_classes(user, "quantities")
    user.find(marker="showpart:gridded_values").click()  # restore the cell
    # click the mnemonic letter (name already shown) -> the name's underline turns on
    user.find(marker="showpart:mnemonics").click()
    assert "rtt-mnem-underline" in _part_classes(user, "mnemonics")
    # turning the name off cascades mnemonics off (set_show) and re-greys its letter with the name,
    # but the letter stays a live target (a refinement is never inert)
    user.find(marker="showpart:names").click()
    assert "rtt-part-off" in _part_classes(user, "names")
    assert "rtt-mnem-underline" not in _part_classes(user, "mnemonics")
    assert "rtt-part-inert" not in _part_classes(user, "mnemonics")
    # clicking it again pulls the name back on and underlines it
    user.find(marker="showpart:mnemonics").click()
    assert "rtt-part-on" in _part_classes(user, "names")
    assert "rtt-mnem-underline" in _part_classes(user, "mnemonics")


# --- tier 3: the edit -> render -> undo pipeline (input -> handler -> render) ---

def _cell_child(user: User, cell_id: str):
    """The inner control of a grid cell (the marker rides its wrap)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    return wrap.default_slot.children[0]


def _wrap_classes(user: User, cell_id: str) -> list[str]:
    """The CSS classes on a grid cell's wrap (e.g. rtt-alert when its value is flagged red)."""
    return next(iter(user.find(marker=cell_id).elements))._classes


def _click_glyph(user: User, cell_id: str) -> None:
    """Click a grid glyph control (held_plus, …) whose click handler rides the inner element
    rather than the marked wrap, so the marker-based click the fixture exposes can't reach it."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).click()


def _commit(user: User, cell_id: str) -> None:
    """Fire a ratiocell input's blur handler. The editable quantities-row ratios commit the whole
    typed fraction on blur / Enter (not per keystroke — parsing "2" of "25/24" would momentarily
    retune to 2/1), so a test sets the value then commits it here."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).trigger("blur")


def _cell_text(user: User, cell_id: str) -> str:
    return getattr(_cell_child(user, cell_id), "text", "")


def _stacked_face(user: User, cell_id: str):
    """The (main label, sub label) of an editable cell's stacked face — the overlay that makes
    the value read like a read-only tval cell (the main glyph big, a small line below). A cents
    cell stacks the whole part over the decimal; a power cell stacks ∞ over "(max)". The
    editable input is child[0]; the face is child[1] (a .rtt-tval div holding the
    .rtt-stacked-main / .rtt-stacked-sub labels)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    face = wrap.default_slot.children[1]
    return face.default_slot.children[0], face.default_slot.children[1]


def _ratio_face(user: User, cell_id: str):
    """The (numerator, denominator) labels of an editable ratio cell's overlaid fraction face —
    the stacked num-over-den that makes the editable input read like a read-only ratio until
    focused. The input is child[0]; the face (an rtt-ratio.rtt-cellface) is child[1], holding the
    rtt-frac div whose two labels are the numerator and denominator."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    frac = wrap.default_slot.children[1].default_slot.children[0]
    return frac.default_slot.children[0], frac.default_slot.children[1]


def _target_preset(user: User):
    """The (numeric-limit, TILT/OLD family-select) pair of the target chooser — the one
    preset that nests two controls in a flex div inside its cell wrap."""
    container = _cell_child(user, "preset:target")  # the rtt-preset-target div
    num, sel = container.default_slot.children
    return num, sel


async def test_tuning_preset_offers_only_lp_while_alternatives_are_shelved(user: User) -> None:
    # alternative-complexity schemes are gated behind the (shelved) alt. complexity setting, so with
    # it off the tuning chooser offers only the log-product family — but at all three weight slopes
    # (its simplicity / unity / complexity variants), since the target-based default is unity. (The
    # chooser's options are {value: label}, the labels T-prefixed; check the offered values.)
    await user.open("/")
    _toggle(user, "presets")
    await user.should_see(marker="preset:tuning")
    assert list(_cell_child(user, "preset:tuning").options) == ["minimax-S", "minimax-U", "minimax-C"]


async def test_checking_all_interval_drops_the_T_prefix_from_the_scheme_chooser(user: User) -> None:
    # the chooser's option LABELS T-prefix only while target-based; checking the all-interval box
    # must flip them to the bare names. The options are recomputed on the toggle (not just the
    # value), so the label updates — regression for them going stale on re-render.
    await user.open("/")
    _toggle(user, "presets")  # show the chooser dropdowns
    user.find(kind=ui.checkbox, content="weighting").click()   # reveal the nested all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()  # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    assert _cell_child(user, "preset:tuning").options["minimax-S"] == "T minimax-S"  # target-based default
    _cell_child(user, "control:all_interval").set_value(True)  # check the box -> all-interval
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning").options["minimax-S"] == "minimax-S"  # T prefix dropped


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
    # the target interval list cells are editable: overriding a component freezes the set as an
    # explicit override. The default first target is 2/1 = (1 0 0); typing 2 there survives the
    # render only if the override applied (else the cell reverts to the default's component)
    _cell_child(user, "cell:vec:targets:0:0").set_value("2")
    await user.should_see(marker="cell:vec:targets:0:0")
    assert _cell_child(user, "cell:vec:targets:0:0").value == "2"


async def test_editing_a_comma_ratio_updates_the_basis(user: User) -> None:
    # the quantities-row comma ratio is editable — the scalar twin of the comma vector below it.
    # Committing a new fraction (on blur) re-parses to that comma's vector, so the cells follow.
    await user.open("/")
    assert _cell_child(user, "comma:0").value == "80/81"  # 5-limit meantone's syntonic comma
    _cell_child(user, "comma:0").set_value("25/24")        # the chromatic semitone = (-3 -1 2)
    _commit(user, "comma:0")                               # blur commits the whole fraction
    await user.should_see(marker="cell:comma:0:0")
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]
    assert _cell_child(user, "comma:0").value == "25/24"   # and the ratio cell reflects the edit


async def test_an_out_of_limit_comma_ratio_toasts_and_reverts(user: User) -> None:
    # a fraction carrying a prime outside the 2.3.5 domain (82 = 2·41) can't be a comma vector
    # there: a red toast NAMES the reason (outside the prime limit), the field snaps BACK to the
    # current ratio on blur, and the basis stays at the syntonic comma (4 -4 1).
    await user.open("/")
    _cell_child(user, "comma:0").set_value("82/81")
    _commit(user, "comma:0")
    await user.should_see("outside the 2.3.5 domain")     # the toast explains the prime-limit failure
    assert _cell_child(user, "comma:0").value == "80/81"  # reverted, not left showing the bad 82/81
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["4", "-4", "1"]


async def test_an_unparseable_comma_ratio_toasts_that_its_invalid(user: User) -> None:
    # the other failure mode reads differently: garbage that isn't a fraction at all toasts
    # "not a valid ratio" (vs the out-of-limit wording), and likewise reverts the field
    await user.open("/")
    _cell_child(user, "comma:0").set_value("12three")
    _commit(user, "comma:0")
    await user.should_see("not a valid ratio")
    assert _cell_child(user, "comma:0").value == "80/81"


async def test_editing_a_target_ratio_overrides_the_set(user: User) -> None:
    # the quantities-row target ratio is editable: committing a fraction overrides the target set,
    # like editing the target vector. The typed value survives the render only if the override held.
    await user.open("/")
    assert _cell_child(user, "target:0").value == "2/1"
    _cell_child(user, "target:0").set_value("5/4")
    _commit(user, "target:0")
    await user.should_see(marker="target:0")
    assert _cell_child(user, "target:0").value == "5/4"


async def test_editing_a_held_ratio_updates_the_interval(user: User) -> None:
    # the held interval's ratio is editable too: committing a fraction re-parses to its held vector.
    # First commit a held interval via the draft flow (fill its vector cells), then edit the ratio.
    await user.open("/")
    _toggle(user, "optimization")                    # show the optimization box's held column
    _click_glyph(user, "held_plus")                  # start a blank red held-interval draft
    _cell_child(user, "cell:held:0:0").set_value("-1")  # fill it to 3/2 = (-1 1 0) -> commits
    _cell_child(user, "cell:held:1:0").set_value("1")
    _cell_child(user, "cell:held:2:0").set_value("0")
    await user.should_see(marker="held:0")
    _cell_child(user, "held:0").set_value("5/4")      # edit the committed ratio to 5/4 = (-2 0 1)
    _commit(user, "held:0")
    await user.should_see(marker="cell:held:0:0")
    assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-2", "0", "1"]


async def test_editing_an_interest_ratio_updates_the_interval(user: User) -> None:
    # the interval-of-interest ratio is editable, like the comma/held ratios; commit one via the
    # draft flow first (its column and the interval-vectors row are open by default)
    await user.open("/")
    _click_glyph(user, "interest_plus")              # start a blank red draft
    _cell_child(user, "cell:interest:0:0").set_value("1")  # fill it to 6/5 = (1 1 -1) -> commits
    _cell_child(user, "cell:interest:1:0").set_value("1")
    _cell_child(user, "cell:interest:2:0").set_value("-1")
    await user.should_see(marker="interest:0")
    _cell_child(user, "interest:0").set_value("5/4")  # edit the committed ratio to 5/4 = (-2 0 1)
    _commit(user, "interest:0")
    await user.should_see(marker="cell:interest:0:0")
    assert [_cell_child(user, f"cell:interest:{p}:0").value for p in range(3)] == ["-2", "0", "1"]


async def test_typing_a_ratio_into_a_pending_draft_fills_it(user: User) -> None:
    # Bug 3: a new interval's pending "?/?" cell is itself an editable ratiocell — typing a fraction
    # into it fills (and commits) the draft, just like filling its vector cells does. Drive the
    # held column: add a draft, then commit a fraction into its "?/?" head.
    await user.open("/")
    _toggle(user, "optimization")                    # show the held column
    _click_glyph(user, "held_plus")                  # start a blank draft -> the "?/?" head appears
    await user.should_see(marker="held:pending")
    assert "rtt-pending" in _wrap_classes(user, "held:pending")  # the draft head reads red
    assert _cell_child(user, "held:pending").value == "?/?"  # pre-filled, so you edit "?/?" not a blank box
    _cell_child(user, "held:pending").set_value("3/2")  # type the fraction into the draft head
    _commit(user, "held:pending")                       # blur commits it = (-1 1 0)
    await user.should_see(marker="held:0")
    assert _cell_child(user, "held:0").value == "3/2"   # the draft committed to a real held interval
    assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-1", "1", "0"]


async def test_editable_ratio_cell_renders_a_stacked_fraction_face(user: User) -> None:
    # the editable comma ratio is an input (the white box + black outline) carrying the SAME
    # stacked num-over-den fraction face as the read-only ratios, shown until the cell is focused
    await user.open("/")
    assert isinstance(_cell_child(user, "comma:0"), ui.input)  # the editable box, not a static label
    num, den = _ratio_face(user, "comma:0")
    assert (num.text, den.text) == ("80", "81")                # the overlaid syntonic-comma fraction


async def test_typing_the_prescaler_plain_text_overrides_the_scheme(user: User) -> None:
    # the bare prescaler 𝐿 tile's plain-text box is the OTHER editable surface (alongside
    # the diagonal cells): typing a d×d matrix EBK with all off-diagonal entries zero parses
    # to a d-tuple diagonal (on_ptext_edit -> editor.set_custom_prescaler_text), which then
    # drives every downstream consumer. The diagonal grid cell must reflect the typed value
    # on re-render — would otherwise be the scheme's log₂3 = 1.585 default.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens the prescaling row
    _toggle(user, "plain text values")  # the ptext band
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
    _toggle(user, "plain text values")
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
    # open by default); that row renders its numeric-limit + TILT/OLD select
    # (the one preset branch the default view never reaches now)
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")


async def test_chooser_popups_open_wide_enough_for_one_line_entries(user: User) -> None:
    # A chooser's open popup must grow to fit its longest entry on one line
    # (popup-content-style width:max-content), never capped at the trigger cell's width —
    # long names (e.g. the "established tuning scheme" list) were truncating. The popup
    # still stays at least as wide as the trigger (a min-width floor), so the open list is
    # never narrower than the box it drops from.
    await _enable(user, "presets")
    for cell_id in ("preset:temperament", "preset:tuning"):
        style = _cell_child(user, cell_id)._props["popup-content-style"]
        assert "width:max-content" in style, f"{cell_id}: {style}"
        assert style.startswith("min-width:"), f"{cell_id}: {style}"


async def test_temperament_divider_rows_render_as_disabled_options(user: User) -> None:
    # the rank/limit divider rows (the "rank R, L-limit" headers) read as headers, not choices:
    # each is passed to Quasar with disable=True, so the q-item takes no hover highlight and a
    # click on it neither picks it nor closes the popup. The named presets stay pickable.
    await _enable(user, "presets")
    select = _cell_child(user, "preset:temperament")
    option_by_value = dict(zip(select._values, select._props["options"]))
    assert option_by_value["hdr:2:5"]["disable"] is True
    assert option_by_value["hdr:3:13"]["disable"] is True
    assert "disable" not in option_by_value["13:Marvel"]


async def test_temperament_chooser_omits_the_offlist_prompt_from_its_list(user: User) -> None:
    # the "-" prompt is a placeholder, not a temperament. The open list holds only the
    # rank/limit dividers and their presets — there is no pickable "-" row, and no ""
    # sentinel value sitting behind one.
    await _enable(user, "presets")
    select = _cell_child(user, "preset:temperament")
    assert "" not in select._values
    assert "-" not in select._labels


async def test_temperament_chooser_shows_the_prompt_as_a_placeholder_when_no_preset_matches(user: User) -> None:
    # the prompt lives in the closed box, not the list: with a preset active (the default
    # meantone) the box shows that preset and no override; once the mapping leaves every
    # preset the box falls back to "-" via Quasar's display-value.
    await _enable(user, "presets")
    assert "display-value" not in _cell_child(user, "preset:temperament")._props
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # 4 -> 7 leaves the meantone preset
    await user.should_see(marker="preset:temperament")
    assert _cell_child(user, "preset:temperament")._props.get("display-value") == "-"


async def test_tuning_chooser_shows_the_prompt_as_a_placeholder_when_off_list(user: User) -> None:
    # the tuning chooser names the active scheme; refine it past the named list (here by
    # setting a finite optimization power, which resolves to an unnamed spec) and the closed
    # box falls back to "-" via Quasar's display-value — never a blank field, never a row.
    await user.open("/")
    _toggle(user, "presets")
    user.find(kind=ui.checkbox, content="optimization").click()
    assert "display-value" not in _cell_child(user, "preset:tuning")._props
    _cell_child(user, "optimization:power").set_value("2")  # minimax (∞) -> a miniRMS spec (no name)
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"


async def test_tuning_chooser_shows_the_prompt_when_the_generator_tuning_is_overridden(user: User) -> None:
    # hand-editing the generator tuning map freezes a manual tuning that deviates from the
    # scheme's optimum, so the shown tuning no longer realises the selected scheme — BOTH
    # tuning-scheme dropdowns (under the tuning map 𝒕 and the generator tuning map 𝒈) fall
    # back to "-", even though the scheme name (minimax-U) is unchanged.
    await user.open("/")
    _toggle(user, "presets")
    both = ("preset:tuning", "preset:tuning:gens")
    assert all("display-value" not in _cell_child(user, cid)._props for cid in both)
    _cell_child(user, "tuning:gen:1").set_value("700.000")  # off the minimax-U optimum fifth
    await user.should_see(marker="preset:tuning")
    assert all(_cell_child(user, cid)._props.get("display-value") == "-" for cid in both)


async def test_selecting_a_scheme_clears_a_manual_tuning_override(user: User) -> None:
    # after hand-editing the generator tuning map (the dropdown shows "-"), re-picking the scheme
    # from the dropdown must re-apply it: the override clears, the tuning snaps back to the
    # scheme's optimum, and the box shows the scheme name again.
    await user.open("/")
    _toggle(user, "presets")
    optimum = _cell_child(user, "tuning:gen:1").value  # the default (minimax-U) optimum fifth
    _cell_child(user, "tuning:gen:1").set_value("700.000")  # deviate
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"
    _cell_child(user, "preset:tuning").set_value("minimax-U")  # re-select the scheme
    await user.should_see(marker="preset:tuning")
    assert "display-value" not in _cell_child(user, "preset:tuning")._props  # name shown again
    assert _cell_child(user, "tuning:gen:1").value == optimum  # tuning snapped back to the optimum


async def test_prescaler_chooser_shows_the_prompt_when_a_diagonal_is_overridden(user: User) -> None:
    # the prescaler preset names the scheme's prescaler; hand-editing the bare prescaler 𝐿
    # diagonal freezes a custom override deviating from it, so the closed box falls back to "-"
    # via Quasar's display-value — the same fallback the tuning chooser uses for a manual tuning.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens the prescaling row (box 𝐋)
    _toggle(user, "presets")  # the chooser dropdowns
    await user.should_see(marker="preset:prescaler")
    assert "display-value" not in _cell_child(user, "preset:prescaler")._props  # names log-prime
    _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")  # deviate from log₂3 = 1.585
    await user.should_see(marker="preset:prescaler")
    assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"


async def test_picking_a_prescaler_clears_a_manual_diagonal_override(user: User) -> None:
    # after hand-editing the prescaler diagonal (the chooser shows "-"), re-picking "log-prime"
    # from the chooser clears the override and snaps the diagonal back to the scheme's value —
    # set_complexity_prescaler is the reset path, like re-selecting a tuning scheme.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    _toggle(user, "presets")
    await user.should_see(marker="cell:prescaling:primes:1:1")
    seed = _cell_child(user, "cell:prescaling:primes:1:1").value  # the scheme's log₂3 = 1.585
    _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")  # deviate
    await user.should_see(marker="preset:prescaler")
    assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"
    _cell_child(user, "preset:prescaler").set_value("log-prime")  # re-pick the named prescaler
    await user.should_see(marker="preset:prescaler")
    assert "display-value" not in _cell_child(user, "preset:prescaler")._props  # name shown again
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == seed  # diagonal snapped back


async def test_target_chooser_shows_the_prompt_when_an_interval_is_overridden(user: User) -> None:
    # the target chooser names the live TILT/OLD family + its limit; hand-editing a target
    # interval column freezes an explicit list no named family realises, so BOTH parts fall
    # back to "-" — the family select via Quasar's display-value, the numeric limit blanked to
    # its "-" placeholder — the same fallback the tuning and prescaler choosers use for an edit.
    await _enable(user, "presets")
    await user.should_see(marker="cell:vec:targets:0:0")
    num, sel = _target_preset(user)
    assert "display-value" not in sel._props  # names the live family
    assert num.value is not None              # shows the family's limit
    _cell_child(user, "cell:vec:targets:0:0").set_value("3")  # deviate from the TILT list
    await user.should_see(marker="preset:target")
    num, sel = _target_preset(user)
    assert sel._props.get("display-value") == "-"
    assert num.value is None  # the numeral blanks to its "-" placeholder


async def test_selecting_a_target_family_clears_an_interval_override(user: User) -> None:
    # after hand-editing a target interval (the chooser shows "-"), re-picking the family from
    # the dropdown must re-apply it: the override clears and the list snaps back to the family's.
    # The override blanks the select to None, so re-picking "TILT" is a real change the handler
    # acts on — not the same-value no-op that made the pick look ignored.
    await _enable(user, "presets")
    await user.should_see(marker="cell:vec:targets:0:0")
    original = _cell_child(user, "cell:vec:targets:0:0").value  # the TILT list's first cell
    _cell_child(user, "cell:vec:targets:0:0").set_value("3")  # deviate -> override
    await user.should_see(marker="preset:target")
    _, sel = _target_preset(user)
    assert sel._props.get("display-value") == "-"
    sel.set_value("TILT")  # re-pick the family
    await user.should_see(marker="cell:vec:targets:0:0")
    _, sel = _target_preset(user)
    assert "display-value" not in sel._props  # family named again
    assert _cell_child(user, "cell:vec:targets:0:0").value == original  # list restored to TILT


async def test_weighting_complexity_chooser_renders_its_live_value(user: User) -> None:
    # the box-𝒄 complexity chooser is a control_select — a distinct kind from the preset
    # dropdowns, with no other direct render coverage. Enabling weighting must build it carrying
    # its live complexity value (not blank) and a populated option list. A dropped control_select
    # build branch would leave an empty wrap; the value/option assertions catch that desync.
    # (With alt. complexity shelved the list is just log-product, so this checks build, not a swap;
    # the slope chooser below exercises the update branch.)
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens box 𝒄 (the complexity chooser)
    await user.should_see(marker="control:complexity")
    chooser = _cell_child(user, "control:complexity")
    assert chooser.value          # built reflecting the live complexity (not blank)
    assert list(chooser.options)  # ...with its option list populated


async def test_weight_slope_chooser_mirrors_a_scheme_change(user: User) -> None:
    # the box-𝒘 weight-slope chooser is the other control_select. Its value tracks the scheme's
    # weight slope, so picking a different slope variant of the scheme through the tuning preset
    # (minimax-U default -> minimax-C) must flip the slope chooser on re-render — without the user
    # touching that chooser. A dropped control_select update branch leaves it stale at the old slope.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # box 𝒘 (the slope chooser)
    _toggle(user, "presets")                                # the tuning scheme dropdown
    await user.should_see(marker="control:slope")
    await user.should_see(marker="preset:tuning")
    before = _cell_child(user, "control:slope").value
    _cell_child(user, "preset:tuning").set_value("minimax-C")  # the complexity-weighted variant
    await user.should_see(marker="control:slope")
    assert _cell_child(user, "control:slope").value != before  # the slope chooser mirrored the change


async def test_all_interval_greys_and_locks_the_weight_slope_chooser(user: User) -> None:
    # in all-interval mode the weight is simplicity by construction, so the box-𝒘 slope chooser
    # is not a free choice: rather than vanish (reflowing the tile), it stays rendered but greys
    # out, locked to simplicity. Target-based it is live; flipping all-interval on must disable it
    # in place and set its value — the _update_control_select branch that re-applies enabled state.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()    # box 𝒘 (the slope chooser) + the all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()  # reveal the target-controls checkbox
    await user.should_see(marker="control:slope")
    assert _cell_child(user, "control:slope").enabled           # live while target-based
    _cell_child(user, "control:all_interval").set_value(True)   # flip to all-interval
    await user.should_see(marker="control:slope")
    chooser = _cell_child(user, "control:slope")
    assert not chooser.enabled                                  # greyed (locked, non-interactive)
    assert chooser.value == "simplicity-weight"                 # pinned to the forced simplicity weight
    # its caption greys too (rtt-caption-disabled), so the "damage weight slope" label is the same
    # disabled grey as the locked value, not darker — the _update_caption branch that toggles it
    assert "rtt-caption-disabled" in _cell_child(user, "caption:slope")._classes


async def test_range_mode_selector_highlights_the_live_mode(user: User) -> None:
    # the monotone/tradeoff selector (rangemode kind) renders under the ranges chart; its render
    # branch fills exactly the live mode's square (rtt-rangeopt-on) and clears the other's. No
    # other test asserts that fill, so a dropped rangemode update branch — leaving neither square
    # highlighted, or both — would slip through (it doesn't raise, so the ERROR-log guard misses it).
    await _enable(user, "tuning ranges")
    await user.should_see(marker="rangemode:tuning:gens")
    wrap = next(iter(user.find(marker="rangemode:tuning:gens").elements))
    on = [c for c in wrap.default_slot.children if "rtt-rangeopt-on" in c._classes]
    assert len(on) == 1  # exactly the live mode (monotone, the default) is highlighted


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


async def test_minimax_power_stacks_a_max_annotation_below_infinity(user: User) -> None:
    # the power cell reads ∞ for the default minimax scheme; like every gridded value it stacks
    # a small line below the main glyph — here "(max)", naming what ∞ means (the max norm)
    await _enable(user, "optimization")
    main, sub = _stacked_face(user, "optimization:power")
    assert (main.text, sub.text) == ("∞", "(max)")
    # a finite power (miniRMS, p = 2) shows bare — no annotation, like a plain numeric value
    _cell_child(user, "optimization:power").set_value("2")
    main, sub = _stacked_face(user, "optimization:power")
    assert (main.text, sub.text) == ("2", "")


async def test_all_interval_renders_the_locked_power_as_a_read_only_value(user: User) -> None:
    # all-interval locks the optimization power at ∞ (the solver minimaxes over every interval), so it
    # renders as a read-only value with the SAME ∞-over-"(max)" stacked face as the editable input —
    # just no white box (no input). rtt-cell-input on the wrap marks the editable powerinput; the
    # read-only powerdisplay lacks it but keeps the identical face (both ∞ AND the "(max)" sub-line).
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()   # reveal the power cell
    user.find(kind=ui.checkbox, content="weighting").click()      # reveal the all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()   # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")  # editable input while target-based
    edit_main, edit_sub = _stacked_face(user, "optimization:power")       # editable face: ∞ over (max)
    assert (edit_main.text, edit_sub.text) == ("∞", "(max)")
    _cell_child(user, "control:all_interval").set_value(True)     # check it -> all-interval
    await user.should_see(marker="optimization:power")
    assert "rtt-cell-input" not in _wrap_classes(user, "optimization:power")  # read-only value, no input
    face = _cell_child(user, "optimization:power")                # the .rtt-tval stacked face div
    main, sub = face.default_slot.children[0], face.default_slot.children[1]
    assert (main.text, sub.text) == ("∞", "(max)")               # identical face: ∞ over (max), kept
    _cell_child(user, "control:all_interval").set_value(False)    # back to target-based
    await user.should_see(marker="optimization:power")
    assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")  # editable input again


async def test_objective_tooltip_tracks_the_all_interval_mode(user: User) -> None:
    # the optimization objective is read-only but carries help, and that help names a different
    # quantity per mode: target-based the minimized damage ⟪𝐝⟫ₚ, all-interval the retuning
    # magnitude. The objective cells are NOT rebuilt when the mode flips, so render() must swap
    # the tooltip text in place. Scan the client's Tooltip registry (it holds even un-hovered
    # tooltips, which the visible-only search can't reach).
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()  # reveal the objective box

    def objective_tips() -> list[str]:
        return [el.text for el in user.client.elements.values()
                if isinstance(el, Tooltip) and "Optimization objective" in el.text]

    assert any("⟪𝐝⟫ₚ" in t for t in objective_tips())                 # the target-based wording
    assert not any("retuning magnitude" in t for t in objective_tips())

    user.find(kind=ui.checkbox, content="weighting").click()          # reveal the all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()       # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    _cell_child(user, "control:all_interval").set_value(True)         # check it -> flip to all-interval

    assert any("retuning magnitude" in t for t in objective_tips())   # the wording swapped in place
    assert not any("⟪𝐝⟫ₚ" in t for t in objective_tips())


async def test_all_interval_disables_the_target_chooser_and_falls_back_to_dash(user: User) -> None:
    # all-interval targets every interval, so the "target interval set scheme" chooser doesn't apply:
    # both parts fall back to "-" (the family select's display-value, the limit's "-" placeholder) and
    # the whole control greys out non-interactive. Unchecking restores the live family and interactivity.
    await _enable(user, "presets")
    user.find(kind=ui.checkbox, content="weighting").click()     # reveal the all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()  # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    num, sel = _target_preset(user)
    assert sel.enabled and "display-value" not in sel._props      # live family, interactive
    _cell_child(user, "control:all_interval").set_value(True)     # check it -> all-interval
    await user.should_see(marker="preset:target")
    num, sel = _target_preset(user)
    assert not sel.enabled and not num.enabled                    # greyed + locked
    assert sel._props.get("display-value") == "-" and num.value is None  # both fall back to "-"
    _cell_child(user, "control:all_interval").set_value(False)    # back to target-based
    await user.should_see(marker="preset:target")
    num, sel = _target_preset(user)
    assert sel.enabled and "display-value" not in sel._props      # restored & interactive


async def test_optimization_renders_the_held_column_and_its_add_control(user: User) -> None:
    # enabling optimization shows the held column with a + (rendered even when empty) for
    # adding the first held interval — driving the held_plus render branch. The editable
    # heldcell branch mirrors the intervals-of-interest cell; the fixture catches any error.
    await _enable(user, "optimization")
    await user.should_see(marker="header:held")
    await user.should_see(marker="held_plus")


async def test_unheld_held_interval_renders_red_until_reoptimized(user: User) -> None:
    # a held interval the current tuning no longer holds renders red (rtt-alert on its cells);
    # re-optimizing restores the held-just tuning and clears it. Drives the whole user flow:
    # add a held interval, make it the fifth 3/2, then hand-tune a generator off the held optimum.
    await user.open("/")
    _toggle(user, "optimization")                          # show the optimization box's held column
    _click_glyph(user, "held_plus")                        # start a blank, red held-interval draft
    await user.should_see(marker="cell:held:0:0")
    _cell_child(user, "cell:held:0:0").set_value("-1")     # make it the fifth 3/2 = (-1 1 0)
    _cell_child(user, "cell:held:1:0").set_value("1")
    _cell_child(user, "cell:held:2:0").set_value("0")      # every component filled -> the draft commits
    _cell_child(user, "tuning:gen:1").set_value("700.000")  # freeze a tuning ~2¢ off the held fifth
    await user.should_see(marker="retune:held:0")
    assert "rtt-alert" in _wrap_classes(user, "retune:held:0")  # the retuning-error cell reddens...
    assert "rtt-alert" in _wrap_classes(user, "held:0")         # ...and so does the whole interval (its ratio)
    user.find(kind=ui.button, content="optimize").click()       # re-optimize -> hold the fifth again
    await user.should_see(marker="retune:held:0")
    assert "rtt-alert" not in _wrap_classes(user, "retune:held:0")  # back to happy black
    assert "rtt-alert" not in _wrap_classes(user, "held:0")


async def test_adding_a_held_interval_drops_the_scheme_chooser_to_dash(user: User) -> None:
    # the live bug: adding a held interval re-optimizes the tuning off the bare scheme, so the
    # established-tuning-scheme chooser must drop to "-" — it kept showing the scheme name because
    # the deviation check only watched manual generator overrides. Drives the exact user path.
    await user.open("/")
    _toggle(user, "presets")             # show the chooser dropdowns
    _toggle(user, "optimization")        # ...and the held-interval column
    assert _cell_child(user, "preset:tuning").value == "minimax-U"  # the default scheme, named
    _click_glyph(user, "held_plus")                  # start a blank held-interval draft
    await user.should_see(marker="cell:held:0:0")
    _cell_child(user, "cell:held:0:0").set_value("-1")  # make it the fifth 3/2 -> deviates the tuning
    _cell_child(user, "cell:held:1:0").set_value("1")
    _cell_child(user, "cell:held:2:0").set_value("0")   # every component filled -> the draft commits
    await user.should_see(marker="preset:tuning")
    sel = _cell_child(user, "preset:tuning")
    assert sel.value is None                          # the displayed tuning is off the named list...
    assert sel.props.get("display-value") == "-"      # ...so the chooser shows the "-" prompt


async def test_adding_an_interval_of_interest_commits_when_filled(user: User) -> None:
    # the whole user flow: + opens a blank red draft, and filling every vector component commits
    # it (an interval of interest is no longer a pre-filled 1/1 — it stays a draft until complete)
    await user.open("/")
    _click_glyph(user, "interest_plus")               # start a blank red draft
    await user.should_see(marker="cell:interest:0:0")
    assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes  # the draft cell is red
    _cell_child(user, "cell:interest:0:0").set_value("-1")  # make it 3/2 = (-1 1 0)
    _cell_child(user, "cell:interest:1:0").set_value("1")
    _cell_child(user, "cell:interest:2:0").set_value("0")   # every component filled -> commits
    await user.should_see(marker="interest:0")              # the committed ratio now heads the column
    assert _cell_child(user, "cell:interest:0:0").value == "-1"  # the vector committed


async def test_adding_a_target_commits_when_filled(user: User) -> None:
    # the same flow for the target list; its draft rides at index k (past the TILT defaults), and
    # filling it materializes the spec set into an override with the new interval appended
    k = len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, Editor().state.domain_basis))
    await user.open("/")
    _click_glyph(user, "target_plus")               # start a blank red target draft
    await user.should_see(marker=f"cell:vec:targets:{k}:0")
    assert "rtt-pending" in _cell_child(user, f"cell:vec:targets:{k}:0")._classes
    _cell_child(user, f"cell:vec:targets:{k}:0").set_value("-1")  # make it 3/2 = (-1 1 0)
    _cell_child(user, f"cell:vec:targets:{k}:1").set_value("1")
    _cell_child(user, f"cell:vec:targets:{k}:2").set_value("0")   # every component filled -> commits
    await user.should_see(marker=f"target:{k}")  # the new target now heads its own column
    assert _cell_child(user, f"cell:vec:targets:{k}:0").value == "-1"


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
    _toggle(user, "charts")  # a settings change
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
    _toggle(user, "charts")
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


@pytest.mark.parametrize("cell, region", [
    ("plus", "colheadinner"),         # the domain + rides the column strip with its fan-out bus
    ("minus", "colheadinner"),        # ...and the hover − reveal on that same strip
    ("gen_plus", "colheadinner"),     # the generators + too
    ("target_plus", "colheadinner"),  # ...and the target-list +
    ("map_plus", "rowband"),          # a mapping-row + rides the sticky-left row band
    ("map_minus:0", "rowband"),       # ...and the per-row − reveal on that same band
])
async def test_branch_controls_render_into_their_frozen_region(user: User, cell: str, region: str) -> None:
    # the always-shown + and the hover − now ride the frozen branch bands with their gridlines
    # (column controls in the column strip, mapping/basis controls in the row band), so they
    # stay put while the value tiles scroll under them. The renderer routes each cell to its
    # pane by its POSITION — which band its top-left falls in — not a hand-kept kind list (which
    # couldn't anyway: the column + and the basis + share the kind "plus" but freeze in different
    # bands).
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


# --- tier 3: the #3 drift guard. _make_cell builds each cell-kind, render() fills each kind,
# in two parallel cb.kind ladders. For the kinds whose visible content is a single ui.html the
# renderer must populate (built empty in _make_cell), a dropped render branch leaves the cell
# silently blank — should_see only checks the wrap is present, so it slips through. One
# representative cell per such kind, asserting the html actually carries content. ---

# Off-by-default html kinds: enable the Show layer that surfaces the kind, then assert a
# representative cell's html actually carries content. Each exercises a distinct fill-in-render
# path — _math_html (count/symbol), _units_html (units), _bar_chart / _range_chart SVGs.
_ENABLE_HTML_CELLS = [
    ("counts", "count:primes"),                   # _math_html "d = 3"
    ("symbols", "symbol:mapping:primes"),         # _math_html quantity glyph
    ("units", "units:mapping:primes"),            # _units_html "units: g/p"
    ("charts", "chart:retune:targets"),           # _bar_chart SVG
    ("tuning ranges", "rangechart:tuning:gens"),  # _range_chart SVG
]


@pytest.mark.parametrize("label, cell_id", _ENABLE_HTML_CELLS)
async def test_enabled_html_cell_renders_non_blank_content(user: User, label: str, cell_id: str) -> None:
    await _enable(user, label)
    await user.should_see(marker=cell_id)
    assert getattr(_cell_child(user, cell_id), "content", ""), \
        f"{cell_id} rendered with empty html content — did render() drop its kind's branch?"


# On-by-default html kinds, present in the plain opened page: the tile-name captions
# (_underline_html) and the matrix-frame EBK bracket SVGs (_ebk_svg, the most numerous kind).
_DEFAULT_HTML_CELLS = ["caption:mapping:primes", "bracket:map:0:l"]


@pytest.mark.parametrize("cell_id", _DEFAULT_HTML_CELLS)
async def test_default_view_html_cell_renders_non_blank_content(user: User, cell_id: str) -> None:
    await user.open("/")
    await user.should_see(marker=cell_id)
    assert getattr(_cell_child(user, cell_id), "content", ""), \
        f"{cell_id} rendered with empty html content — did render() drop its kind's branch?"


async def test_a_maximal_render_dispatches_every_emitted_cell_kind(user: User) -> None:
    # the cell-kind registry (audit #3) indexes cell_kinds[cb.kind] with no fallback, so any kind the
    # layout emits without a registered build/update handler raises rather than rendering a silent
    # blank cell. Drive a broad render — every implemented Show layer on, and the vector rows
    # open by default so the comma / target / interest / held vector cells and their ± controls emit.
    # A missing handler crashes the render, which the user fixture surfaces (any raised error fails it).
    await user.open("/")
    user.find(kind=ui.checkbox, content="select all / none").click()  # every implemented feature on
    await user.should_see(marker="cell:mapping:0:0")                  # the board re-rendered, no dispatch error

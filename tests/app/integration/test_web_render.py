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

import asyncio
import copy
import logging
import sys
from fractions import Fraction

import nicegui.ui as ui
import pytest
from nicegui import core
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from rtt.app import app as web_app
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app.editor import Editor


def test_rowlabel_renders_a_hard_newline_as_a_line_break():
    # the "complexity pretransforming" row title carries a hard \n ("... pre-\ntransforming") so it
    # wraps at full font instead of shrinking; the rtt-rowlabel must be white-space:pre-line for the
    # \n to render as a break (default `normal` would collapse it to a space)
    import os
    import re
    css_path = os.path.join(os.path.dirname(spreadsheet.__file__), "assets", "rtt.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    rule = re.search(r"\.rtt-rowlabel\s*\{[^}]*\}", css).group(0)
    assert "white-space:pre-line" in rule.replace(" ", "")


async def test_default_page_renders_without_error(user: User) -> None:
    await user.open("/")
    # the board built: a representative slice of the default grid's row/column titles
    await user.should_see("quantities")
    await user.should_see("tuning")


async def test_grid_pane_publishes_its_base_size_for_the_scrollbar_fit(user: User) -> None:
    # the scrollbar-fit pass (rttFreeze.fit) reserves a scrollbar's width so one bar never forces a
    # second; to do that it must reset the pane to its UN-reserved size before measuring the window
    # caps. render publishes that base size as data-base-w/-h, which must equal the inline width/height
    # it sets — the value the JS resets to (see assets/freeze.js, tests in test_web_app_smoke).
    await user.open("/")
    pane = next(iter(user.find(marker="gridpane").elements))
    base_w, base_h = pane._props.get("data-base-w"), pane._props.get("data-base-h")
    fit_w = pane._props.get("data-fit-w")
    assert base_w is not None and base_h is not None and fit_w is not None
    assert float(base_w) == float(pane._style["width"].rstrip("px"))
    assert float(base_h) == float(pane._style["height"].rstrip("px"))
    # fit-w is the gridlines' own width — base-w minus the last column title's right overhang — so it
    # never exceeds base-w; a horizontal scrollbar is owed only when the pane is capped below it.
    assert 0 < float(fit_w) <= float(base_w)


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
    # counts ships ON now, so it's no longer an enable-an-off-feature case (its render is covered
    # by the default page + the spreadsheet tests).
    ("symbols", "symbol:mapping:primes"),            # the quantity-symbol glyph, _math_html
    ("row/col header symbols", "matlabel:row:mapping:primes:0"),  # the matrix row header label (header_symbols)
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


async def test_generators_column_collapses_a_whole_ratio_but_keeps_its_approx_tilde(user: User) -> None:
    # the generators quantities-row ratios are a READ-ONLY ~APPROXIMATE ratio face (genratio). The
    # default meantone's detempering D = (2/1, 3/2): the octave is a WHOLE ratio, so it renders as a
    # bare "2" (not the stacked "2 over 1") — but, being an approximate tile, it KEEPS its ~ ("~2"),
    # just like the fraction generator (~3/2). Only the bar + denominator collapse, never the ~.
    await user.open("/")
    num, _den, collapsed = _ro_ratio_face(user, "qgen:0")
    assert collapsed and num == "2"            # 2/1 -> bare integer (bar + denominator dropped)
    assert _approx_markers(user, "qgen:0")     # ...but the ~ still rides the collapsed integer
    _n, _d, gen_collapsed = _ro_ratio_face(user, "qgen:1")
    assert not gen_collapsed and _approx_markers(user, "qgen:1")  # the fifth stays a stacked ~3/2
    # both the collapse AND its ~ survive a re-render: toggling an unrelated layer drives qgen:0
    # through _update_ratio (the persisted-cell rebuild path, distinct from the initial build)
    _toggle(user, "symbols")
    num2, _d2, still = _ro_ratio_face(user, "qgen:0")
    assert still and num2 == "2" and _approx_markers(user, "qgen:0")


async def test_detempering_column_collapses_a_whole_ratio_to_a_bare_integer(user: User) -> None:
    # the generator-detempering quantities-row ratios are a READ-ONLY ratio face (commaratio) — the
    # column the user named. Its octave detempering 2/1 must collapse to a bare "2" too. Unlike the
    # generators, detempering is NOT an approximate tile, so its bare integer carries no ~.
    await _enable(user, "generator detempering")
    await user.should_see(marker="detempering:0")
    num, _den, collapsed = _ro_ratio_face(user, "detempering:0")
    assert collapsed and num == "2"            # 2/1 -> bare integer
    assert not _approx_markers(user, "detempering:0")  # detempering is exact — no ~ on the integer
    _n, _d, fifth_collapsed = _ro_ratio_face(user, "detempering:1")
    assert not fifth_collapsed                  # the fifth (3/2) stays a stacked fraction


async def test_enabling_projection_renders_the_box(user: User) -> None:
    # the projection box P = GM (a tuning-boxes sub-control). Assert the row label renders, and
    # lean on the fixture's ERROR-log guard to catch any fault building the d×d matrix's cells,
    # ⟨ … ] map brackets or spanning frame — the page must not 500 with projection on.
    await _enable(user, "projection")
    await user.should_see(marker="label:projection")
    await user.should_see(marker="cell:proj:2:1")  # the 1/4 entry (mapped kind, locatable like the mapping)


async def test_projection_renders_the_projected_column_tiles(user: User) -> None:
    # the projection row's projected vector lists: P·D (= the embedding G) over the detempering column
    # and P·T over the targets. The default meantone is quarter-comma (holds 2/1, 5/4), so they fill —
    # P·d₂ = 5^(1/4) = [0 0 1/4]. Read-only "mapped" cells, locatable like P; lean on the fixture's
    # ERROR-log guard to catch any fault building the projected cells, { … ]/[ … ] brackets or ket marks.
    await _enable(user, "projection")
    _toggle(user, "generator detempering")
    await user.should_see(marker="cell:proj_pd:1:2")  # P·D's second column, bottom prime
    assert _cell_text(user, "cell:proj_pd:1:2") == "1/4"
    await user.should_see(marker="cell:proj_pt:0:0")  # P·T's first column (the octave)


async def test_projection_renders_the_embedding_and_its_choosers(user: User) -> None:
    # projection + presets: the generator embedding G renders beside P, with the established-
    # projection (under P) and established-embedding (under G) choosers. They are one selection —
    # picking a named tuning re-forms BOTH P and G (P = GM) — so both choosers track it.
    await user.open("/")
    _toggle(user, "presets")
    user.find(kind=ui.checkbox, content="projection").click()
    await user.should_see(marker="cell:embed:2:1")          # G's entry, locatable like P
    await user.should_see(marker="preset:projection")       # established projection, under P
    await user.should_see(marker="preset:projection:gens")  # established embedding, under G
    # the default meantone (TILT minimax-U) IS quarter-comma — it holds 2/1 and 5/4 — so the choosers
    # read 1/4-comma and P/G fill in (the 5^(1/4) entries), NOT dashes
    assert _cell_child(user, "preset:projection").value == "1/4-comma"
    # P and G are read-only "mapped" cells now (edited via their plain-text bands) — read the cell text
    assert _cell_text(user, "cell:proj:2:1") == "1/4"
    assert _cell_text(user, "cell:embed:2:1") == "1/4"
    # pick 1/3-comma -> P and G re-form (it holds 6/5), both choosers track it, and the genmap
    # actually re-solves to third-comma (1200, 694.786)
    _cell_child(user, "preset:projection").set_value("1/3-comma")
    await user.should_see(marker="cell:embed:2:1")
    assert _cell_text(user, "cell:proj:2:1") == "1/3"
    assert _cell_text(user, "cell:embed:2:1") == "1/3"
    assert _cell_child(user, "preset:projection:gens").value == "1/3-comma"
    assert _cell_child(user, "tuning:gen:1").value == "694.786"  # the dropdown changed the tuning


async def test_back_to_scheme_button_reverts_a_picked_projection(user: User) -> None:
    # the always-present "back to scheme" button on the projection tile hands a picked tuning back to
    # the scheme + target list: pick 1/3-comma (target list hidden), click it, and the target list
    # returns and the tuning is the scheme optimum (1/4-comma) again
    await user.open("/")
    _toggle(user, "presets")
    user.find(kind=ui.checkbox, content="projection").click()
    await user.should_see(marker="scheme:primes")          # the button is there regardless of presets
    await user.should_see(marker="target:0")               # default: the target list shows
    _cell_child(user, "preset:projection").set_value("1/3-comma")
    await user.should_not_see(marker="target:0")           # deviated onto a projection → target list gone
    _click_glyph(user, "scheme:primes")                    # back to scheme
    await user.should_see(marker="target:0")               # the target list is restored
    assert _cell_child(user, "preset:projection").value == "1/4-comma"  # back at the scheme optimum


async def test_back_to_scheme_button_shows_without_the_presets_setting(user: User) -> None:
    # "not gated by the presets setting": the button is on the projection tiles even when presets is
    # off (so the established-projection chooser is hidden)
    await _enable(user, "projection")
    await user.should_see(marker="scheme:primes")
    await user.should_see(marker="scheme:gens")
    await user.should_not_see(marker="preset:projection")  # presets off → no chooser, but the button stays


async def test_editing_the_unchanged_basis_retunes(user: User) -> None:
    # the unchanged basis U is editable when the tuning is a full rational projection (like the comma
    # basis): the default meantone holds {2/1, 5/4}; retype its second column as 6/5 = (1, 1, -1) and
    # the tuning re-solves to the projection that holds {2/1, 6/5} — third-comma (1200, 694.786)
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:1")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"   # default = 1/4-comma
    _cell_child(user, "cell:unchanged:0:1").set_value("1")        # prime 2
    _cell_child(user, "cell:unchanged:1:1").set_value("1")        # prime 3
    _cell_child(user, "cell:unchanged:2:1").set_value("-1")       # prime 5  → column is now 6/5
    _commit(user, "cell:unchanged:2:1")                            # blur commits the edited basis
    assert _cell_child(user, "tuning:gen:1").value == "694.786"   # retuned to third-comma


async def test_editing_the_unchanged_ratio_retunes(user: User) -> None:
    # the unchanged intervals are editable in their RATIO form too (the quantities row), not only as
    # vectors: retype the default meantone's second unchanged ratio from 5/4 to 6/5 and it retunes to
    # third-comma — the scalar twin of editing the U vectors
    await _enable(user, "projection")
    await user.should_see(marker="unchanged:1")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"   # default = 1/4-comma
    _cell_child(user, "unchanged:1").set_value("6/5")
    _commit(user, "unchanged:1")                                   # blur commits the typed fraction
    assert _cell_child(user, "tuning:gen:1").value == "694.786"   # retuned to third-comma


async def test_editing_the_generator_embedding_retunes(user: User) -> None:
    # G's gridded cells are read-only (a single entry can't keep 𝑀𝐺 = 𝐼); editing is via its
    # plain-text band, which commits on SUBMIT (blur). Type 1/3-comma's G as a vector-list EBK string
    # and the tuning re-solves to third-comma (1200, 694.786).
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:gens")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"
    _cell_child(user, "ptext:projection:gens").set_value("{[1 0 0⟩[1/3 -1/3 1/3⟩]")  # 1/3-comma G
    _commit(user, "ptext:projection:gens")
    assert _cell_child(user, "tuning:gen:1").value == "694.786"   # retuned to third-comma


async def test_editing_the_projection_matrix_retunes(user: User) -> None:
    # P's gridded cells are read-only too (a single entry can't keep P idempotent); editing is via its
    # plain-text band. Type 1/3-comma's P as a map-list EBK string and the tuning re-solves to third-comma.
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:primes")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"
    _cell_child(user, "ptext:projection:primes").set_value("[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩")  # 1/3-comma P
    _commit(user, "ptext:projection:primes")
    assert _cell_child(user, "tuning:gen:1").value == "694.786"   # retuned to third-comma


async def test_a_projection_plain_text_edit_is_unmolested_until_submit(user: User) -> None:
    # the whole point of the plain-text edit: while you TYPE (before blur/Enter) an in-progress string
    # neither retunes, reddens, nor toasts — only SUBMITTING validates. An invalid value left
    # uncommitted does nothing; committing it THEN reddens and toasts.
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:primes")
    _cell_child(user, "ptext:projection:primes").set_value("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩")  # invalid, but not submitted
    assert "rtt-ptext-error" not in _cell_child(user, "ptext:projection:primes").classes  # unmolested
    assert _cell_child(user, "tuning:gen:1").value == "696.578"                            # not retuned
    _commit(user, "ptext:projection:primes")                                              # NOW submit
    await user.should_see("isn't a valid projection")
    assert "rtt-ptext-error" in _cell_child(user, "ptext:projection:primes").classes


async def test_an_invalid_projection_plain_text_toasts_and_reddens(user: User) -> None:
    # a submitted P string that parses but ISN'T a valid projection (a 2 on the diagonal breaks
    # idempotency P² = P) toasts the reason at top and reddens the band — the tuning stays put.
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:primes")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"   # 1/4-comma
    _cell_child(user, "ptext:projection:primes").set_value("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩")  # P[0][0]=2 → P²≠P
    _commit(user, "ptext:projection:primes")
    await user.should_see("isn't a valid projection")           # the red toast names the reason
    assert "rtt-ptext-error" in _cell_child(user, "ptext:projection:primes").classes
    assert _cell_child(user, "tuning:gen:1").value == "696.578"  # tuning unchanged


async def test_an_invalid_embedding_plain_text_toasts_and_reddens(user: User) -> None:
    # a submitted G string that parses but isn't a valid embedding (a zeroed column → 𝑀𝐺 ≠ 𝐼) toasts
    # the reason and reddens — the embedding counterpart of the invalid-projection case.
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:gens")
    assert _cell_child(user, "tuning:gen:1").value == "696.578"
    _cell_child(user, "ptext:projection:gens").set_value("{[0 0 0⟩[0 0 1/4⟩]")  # zeroed column → 𝑀𝐺 ≠ 𝐼
    _commit(user, "ptext:projection:gens")
    await user.should_see("isn't a valid embedding")
    assert "rtt-ptext-error" in _cell_child(user, "ptext:projection:gens").classes
    assert _cell_child(user, "tuning:gen:1").value == "696.578"  # tuning unchanged


async def test_an_unparseable_projection_plain_text_reddens_without_a_toast(user: User) -> None:
    # garbage that isn't even a parseable map string just reddens the band on submit (its shape is the
    # feedback) — no toast, like the mapping / comma-basis / prescaler duals. The tuning stays put.
    await _enable(user, "projection")
    _toggle(user, "plain text values")
    await user.should_see(marker="ptext:projection:primes")
    _cell_child(user, "ptext:projection:primes").set_value("not a matrix")
    _commit(user, "ptext:projection:primes")
    assert "rtt-ptext-error" in _cell_child(user, "ptext:projection:primes").classes
    assert _cell_child(user, "tuning:gen:1").value == "696.578"  # tuning unchanged


async def test_projection_renders_the_consolidated_v_and_scaling_factors(user: User) -> None:
    # projection also consolidates the commas + unchanged basis U into V = C|U and adds the
    # scaling-factors row λ. Assert the new cells render (and lean on the ERROR-log guard for any
    # fault building the appended unchanged columns / λ list / their EBK marks).
    await _enable(user, "projection")
    await user.should_see(marker="label:scaling_factors")
    await user.should_see(marker="cell:scaling:u0")            # λ₂ = 1 (a held interval; the U half rides u{j})
    await user.should_see(marker="cell:unchanged:0:0")         # the first unchanged-basis vector cell
    await user.should_see(marker="cell:mapped_unchanged:1:1")  # M·U appended to the mapping row over V


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


async def test_off_diagonal_pretransformer_edit_keeps_the_all_interval_weight_a_list(user: User) -> None:
    # the full live pipeline behind the weight tile: in all-interval mode with alt complexity on, the
    # pretransformer square is editable; typing an OFF-diagonal entry promotes 𝑋 to a non-diagonal
    # matrix. The weight stays the per-target LIST (never a matrix) — only its tile symbol changes to
    # 𝑆 = 𝑋⁻¹. Exercises input → on_prescaler_change → set_custom_prescaler_entry → re-render end-to-end.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()       # show the weight row
    user.find(kind=ui.checkbox, content="all-interval").click()    # reveal the all-interval control
    _cell_child(user, "control:all_interval").set_value(True)      # enter all-interval mode (targets = primes)
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # make the whole square editable
    await user.should_see(marker="cell:prescaling:primes:1:0")     # the editable off-diagonal cell
    await user.should_see(marker="weight:target:0")                # before: the per-target weight LIST
    _cell_child(user, "cell:prescaling:primes:1:0").set_value("0.3")  # type an off-diagonal entry → 𝑋 non-diagonal
    await user.should_see(marker="weight:target:0")                # after the re-render: still the LIST
    await user.should_not_see(marker="cell:weight:targets:0:0")    # ...never promoted to a matrix


async def test_interval_columns_render_draggable_reorder_grips(user: User) -> None:
    # the target list shows by default, so its reorder grip renders with no setup: a draggable
    # ⠿ over each column (also the drop target). Drive the builder and confirm it's a drag source.
    await user.open("/")
    await user.should_see(marker="grip:targets:0")
    grip = next(iter(user.find(marker="grip:targets:0").elements))
    assert grip._props.get("draggable")  # the wrap is the HTML5 drag source


async def test_dragging_a_target_onto_the_held_columns_gridline_moves_it_in(user: User) -> None:
    # the user's flow: drag a target interval INTO the held column — even when held is empty — by
    # dropping on its gridline "add" zone (grip:held:add), the SAME "drop on the gridline" gesture as
    # reordering. An empty list has no per-column grip, so the gridline zone is the consistent target
    # (no special header / + drop). Drop target 0 onto the empty held list → it becomes held's column.
    await user.open("/")
    _toggle(user, "optimization")                          # reveal the (empty) held column
    await user.should_see(marker="grip:held:add")          # ...whose gridline drop zone is present
    await user.should_not_see(marker="grip:held:0")        # held starts empty: no per-column grip yet
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:held:add").elements), None).trigger("drop.prevent")
    await user.should_see(marker="grip:held:0")            # the dropped target is now held's first column


def _cell_left(user: User, cell_id: str) -> float:
    """A grid cell's current x (the inline left the reconciler placed it at), in px."""
    return float(next(iter(user.find(marker=cell_id).elements))._style["left"].rstrip("px"))


async def test_hovering_a_reorder_target_previews_the_move_then_reverts(user: User) -> None:
    # the drag previews on HOVER: entering a target column slides the columns open to show where the
    # drop will land, before releasing. Releasing off a target (dragend) reverts it, nothing committed.
    await user.open("/")
    x0, x2 = _cell_left(user, "target:0"), _cell_left(user, "target:2")
    assert x0 < x2  # token 0 starts left of token 2
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger("dragenter.prevent")
    assert _cell_left(user, "target:0") > _cell_left(user, "target:2")  # previewed: token 0 moved past token 2
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragend")
    assert _cell_left(user, "target:0") == x0  # reverted to its original slot — nothing committed


async def test_dropping_after_a_preview_commits_the_move(user: User) -> None:
    # hovering previews, dropping commits: the previewed arrangement persists (and as one undo step).
    await user.open("/")
    x0 = _cell_left(user, "target:0")
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger("dragenter.prevent")
    UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger("drop.prevent")
    assert _cell_left(user, "target:0") > _cell_left(user, "target:2")  # committed: token 0 sits past token 2
    assert _cell_left(user, "target:0") != x0


async def test_a_within_list_reorder_preview_rings_nothing(user: User) -> None:
    # a within-list reorder is value-neutral (same set, only positions change), so its hover preview
    # glides the columns but rings NO cell — no misleading "this changed" flags from re-solve noise.
    await user.open("/")
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger("dragenter.prevent")
    assert _cell_left(user, "target:0") > _cell_left(user, "target:2")     # the columns glided...
    assert "rtt-preview-change" not in _wrap_classes(user, "target:0")     # ...but nothing rings
    assert "rtt-preview-change" not in _wrap_classes(user, "target:1")


async def test_dragging_across_lists_rings_the_changes_it_will_make(user: User) -> None:
    # a SET-changing move (across lists, or into/out of commas) re-optimizes the temperament, so
    # hovering it rings the cells whose value the drop will change — like the edit & combine previews.
    await user.open("/")
    _toggle(user, "optimization")                          # reveal the (empty) held list as a drop target
    await user.should_see(marker="grip:held:add")
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:held:add").elements), None).trigger("dragenter.prevent")
    assert "rtt-preview-change" in _wrap_classes(user, "held:0")  # the moved interval previews (new) in held → rings
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragend")
    await user.should_not_see(marker="held:0")            # reverted: the hover preview didn't commit


async def test_editing_a_ratio_after_a_reorder_edits_the_column_it_heads(user: User) -> None:
    # regression: the quantities ratio cells are keyed by interval identity, so after a reorder the
    # cell heading a slot carries the MOVED column's token, not the slot index. Committing a fraction
    # must edit the column the cell now heads — the bug this guards read the token straight back as a
    # list index and edited whatever interval sat at that index (a different column).
    await user.open("/")
    assert _ratio_value(user, "target:0") == "2"   # 2/1 rests as the big-integer view (den 1 collapses)
    assert _ratio_value(user, "target:1") == "3"
    # swap the first two targets: drag target 0's grip onto target 1's, so token 1 (the 3/1) now
    # heads the FIRST slot while token 0 (the 2/1) heads the second
    UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger("dragstart")
    UserInteraction(user, set(user.find(marker="grip:targets:1").elements), None).trigger("drop.prevent")
    await user.should_see(marker="target:1")
    _cell_child(user, "target:1").set_value("9/8")   # edit the cell now heading the first slot
    _commit(user, "target:1")
    await user.should_see(marker="target:1")
    assert _ratio_value(user, "target:1") == "9/8"   # the edit stuck to the column it heads...
    assert _ratio_value(user, "target:0") == "2"     # ...not the one at token-as-index 1


async def test_enabling_colorization_keeps_the_board_rendering(user: User) -> None:
    # both colorization sub-toggles share the label "colorization", so one click matches
    # and flips both on. They paint wash blocks behind the tiles — drive that branch and
    # confirm the board still renders (no exception, no ERROR log via the fixture).
    await user.open("/")
    user.find(kind=ui.checkbox, content="colorization").click()
    await user.should_see(marker="cell:mapping:0:0")


async def test_edge_washes_also_render_into_the_frozen_panes(user: User) -> None:
    # A wash overhangs the freeze seam, so the top-row and left-column washes spill past it. Rendered
    # only into the body they are shaved at those edges — the column strip clips the top spill, the
    # row band paints over the left spill. So each also renders a copy into the frozen pane it spills
    # into (id suffixed #col / #row), the way a gridline crossing the seam does. Drive the colorization
    # branch and confirm both frozen copies exist (the body copy keeps the bare id).
    await user.open("/")
    user.find(kind=ui.checkbox, content="colorization").click()
    # counts is the top row now, so it's the one whose wash spills up into the column strip
    await user.should_see(marker="wash:temperament:counts:gens")        # the body copy
    await user.should_see(marker="wash:temperament:counts:gens#col")    # the column-strip copy (top spill)
    await user.should_see(marker="wash:temperament:mapping:quantities#row")  # the row-band copy (left spill)


async def test_settings_and_controls_carry_hover_tooltips(user: User) -> None:
    # the Show toggles and the interactive grid controls all get explanatory hover text
    # (rtt.app.tooltips). A tooltip renders hidden until hover, so the User sim's visible-only
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


def _row_classes(user: User, key: str) -> list[str]:
    """The CSS classes on the specific-group toggle row for ``key`` (the chapter slider hides a
    row by adding ``rtt-chap-hidden``)."""
    return next(iter(user.find(marker=f"showrow:{key}").elements))._classes


async def test_the_guide_chapter_slider_gates_the_panel_by_chapter_at_the_default(user: User) -> None:
    # the chapter slider opens at the default position (ch4) and reveal-gates the panel's controls.
    # A show/example row past the slider COLLAPSES (rtt-chap-hidden / display:none); a dummy-tile
    # part past it stays in place but INVISIBLE (rtt-chap-invisible / visibility:hidden) so the tile
    # keeps its shape. The hiding is a CSS class (the in-process User plugin reads the Python tree,
    # not CSS), so this checks the class directly — what a real browser keys off.
    await user.open("/")
    slider = next(iter(user.find(marker="chapterslider").elements))
    assert slider.value == show_settings.CHAPTER_DEFAULT  # the as-shipped slider position (ch4)
    # ch2/3/4 specific rows are revealed at the default (the ch3 tuning sub-controls included)...
    for key in ("counts", "tuning_boxes", "optimization", "weighting", "interest",
                "domain_quantities", "domain_units"):
        assert "rtt-chap-hidden" not in _row_classes(user, key), key
    # ...while the ch9 / outside-guide (★) rows are collapsed. (These are all top-level rows, or
    # — projection — a sub-control of the on-by-default tuning boxes, so they're present/findable;
    # a sub-control of an OFF parent, like all-interval under weighting, is hidden by its own
    # visibility binding and so isn't found regardless of chapter.)
    for key in ("nonstandard_domain", "projection", "generator_detempering", "identity_objects"):
        assert "rtt-chap-hidden" in _row_classes(user, key), key
    # the dummy tile's parts are gated the space-preserving way: an early layer shows, a ch5 one is
    # invisible-but-in-place (visibility:hidden, NOT display:none)
    assert "rtt-chap-invisible" not in _part_classes(user, "gridded_values")  # ch2
    assert "rtt-chap-invisible" in _part_classes(user, "units")               # ch5
    # the audio bank rides the tile and is available from the first notch, so it shows at the default
    assert "rtt-chap-invisible" not in next(iter(user.find(marker="audiobank").elements))._classes
    # a hidden (unrevealed) toggle is DISABLED too, not merely hidden — its checkbox carries the
    # `disable` prop; a revealed one does not.
    def _box(key):
        return next(iter(user.find(marker=f"showbox:{key}").elements))
    assert "disable" in _box("nonstandard_domain")._props  # ch9 — hidden + disabled at ch4
    assert "disable" not in _box("counts")._props          # ch2 — revealed + enabled
    # the live readout reads "<n>: <title>" (no "ch " prefix)
    reading = next(iter(user.find(marker="chapterreading").elements))
    assert reading.text == "4: Exploring temperaments"


async def test_sliding_the_chapter_down_disables_the_advanced_layers_in_the_grid(user: User) -> None:
    # a hidden setting is DISABLED, not just hidden: with the slider at ★ and select-all on, an
    # advanced layer (units, ch5) renders its content; sliding the slider down to ch2 turns that
    # layer off, so its content drops out of the grid (not merely its panel control).
    await user.open("/")
    slider = next(iter(user.find(marker="chapterslider").elements))
    slider.set_value(show_settings.CHAPTER_STAR)            # reveal everything (fires on_chapter_change)
    next(iter(user.find(marker="showall").elements)).set_value(True)  # select-all over all revealed
    await user.should_see(marker="units:mapping:primes")   # the per-box "units: …" line is now shown
    slider.set_value(2)                                    # slide down to ch2
    await user.should_not_see(marker="units:mapping:primes")  # units (ch5) is disabled -> content gone
    # the readout tracked the move, and the master is still "all (available) on" for ch2
    assert next(iter(user.find(marker="chapterreading").elements)).text == "2: Mappings"


async def test_reset_restores_the_guide_chapter_slider_to_the_default(user: User) -> None:
    # Reset clears the document AND the guide-chapter slider — move the slider off ch4, hit Reset,
    # and the thumb (and readout) return to the default chapter.
    await user.open("/")
    slider = next(iter(user.find(marker="chapterslider").elements))
    slider.set_value(show_settings.CHAPTER_STAR)
    assert slider.value == show_settings.CHAPTER_STAR
    user.find(marker="reset").click()
    assert slider.value == show_settings.CHAPTER_DEFAULT
    assert next(iter(user.find(marker="chapterreading").elements)).text == "4: Exploring temperaments"


async def test_toggling_gridded_values_off_at_runtime_removes_the_grid_value_cells(user: User) -> None:
    # the user's own action: open the live page, then click the gridded-values part to turn it OFF.
    # The dummy-tile test above only checks the PART's class flips; this drives the whole reconcile
    # and asserts the actual grid value cells leave the DOM (render's orphan sweep drops every eid no
    # longer in the layout). Guards the runtime-toggle path the fresh-load render tests never exercise
    # — a value cell that survived a toggle (a kind missing from GRIDDED_KINDS) would be caught here.
    await user.open("/")
    await user.should_see(marker="prime:0")    # a quantities-row domain header cell (kind "prime")
    await user.should_see(marker="target:0")   # a quantities-row interval-ratio cell (kind "ratiocell")
    user.find(marker="showpart:gridded_values").click()  # turn gridded values OFF
    await user.should_not_see(marker="prime:0")   # the value cells are gone, not just greyed
    await user.should_not_see(marker="target:0")
    user.find(marker="showpart:gridded_values").click()  # back on
    await user.should_see(marker="prime:0")


def _approx_markers(user: User, cell_id: str) -> list:
    """The ``rtt-approx`` "~" labels rendered inside a cell (the approximate-ratio marker). Walks the
    cell wrap's descendants — the ~ rides the ``.rtt-ratio`` face, not the wrap itself."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    found, stack = [], list(wrap.default_slot.children)
    while stack:
        el = stack.pop()
        if "rtt-approx" in getattr(el, "_classes", []):
            found.append(el)
        slot = getattr(el, "default_slot", None)
        stack.extend(slot.children if slot is not None else [])
    return found


async def test_quantities_off_at_runtime_does_not_strand_a_tilde_on_blanked_generator_ratios(user: User) -> None:
    # generator / mapping quantities are ~approximate stacked fractions (genratio). Turning quantities
    # off at runtime BLANKS them, which must clear the whole face: the old update path patched the
    # fraction's numbers in place and left the "~" stranded over an empty fraction bar — a meaningless
    # "~-". Drive the runtime toggle and assert no approximate marker survives on a blanked generator
    # cell (the fresh-load render never hits this — only the in-place value update does). The octave
    # generator is a whole ratio that collapses to a bare "2" but, being an approximate tile, keeps
    # its ~ ("~2") — so it carries a marker to strand, making it a valid (and the natural) subject.
    await user.open("/")
    assert _approx_markers(user, "gen:0")      # mapping-row quantity shows ~2 (the octave) by default
    assert _approx_markers(user, "qgen:0")     # generator-col quantity likewise
    user.find(marker="showpart:quantities").click()   # turn general quantities OFF (the dummy-tile part)
    assert not _approx_markers(user, "gen:0")  # blanked: the whole face cleared, no stray ~ (nor bar)
    assert not _approx_markers(user, "qgen:0")
    user.find(marker="showpart:quantities").click()   # back on
    assert _approx_markers(user, "gen:0")      # the ~2 face is rebuilt


# --- tier 3: the edit -> render -> undo pipeline (input -> handler -> render) ---

def _cell_child(user: User, cell_id: str):
    """The inner control of a grid cell (the marker rides its wrap). An editable stacked-fraction
    cell wraps its numerator + denominator inputs in a .rtt-frac-edit box; the NUMERATOR is the
    "primary" control the marker-based interactions drive (and, headless, a whole ``"3/2"`` typed
    into it still commits — cell_value rejoins it with the empty denominator)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    child = wrap.default_slot.children[0]
    if "rtt-frac-edit" in getattr(child, "_classes", []):
        return child.default_slot.children[0]  # the numerator input
    return child


def _frac_inputs(user: User, cell_id: str):
    """The (numerator, denominator) input fields of an editable stacked-fraction cell — the two
    separate fields that replaced the old overlaid num-over-den face. The .rtt-frac-edit box is the
    wrap's first child; its children are num, the bar div, den."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    box = wrap.default_slot.children[0]
    return box.default_slot.children[0], box.default_slot.children[2]


def _ratio_value(user: User, cell_id: str) -> str:
    """The committed ratio a stacked-fraction cell shows, rejoined from its numerator + denominator
    inputs the way cell_value does (a blank/1 denominator is the big-integer view, so it returns the
    bare numerator)."""
    num, den = _frac_inputs(user, cell_id)
    return num.value if den.value in ("", "1") else f"{num.value}/{den.value}"


def _wrap_classes(user: User, cell_id: str) -> list[str]:
    """The CSS classes on a grid cell's wrap (e.g. rtt-preview-change when an edit moves its value)."""
    return next(iter(user.find(marker=cell_id).elements))._classes


def _ro_ratio_face(user: User, cell_id: str):
    """A READ-ONLY ratio face (genratio / commaratio: detempering, generators, unchanged auto-list)
    as ``(numerator_text, denominator_text, collapsed)``. ``collapsed`` is True when the value is a
    whole ratio ``"n/1"`` shown as a bare integer — flagged by ``rtt-frac-whole`` on the .rtt-frac
    div (the ~ omitted, the bar and denominator hidden). The wrap's first child is the .rtt-ratio
    container (a label-only "–" placeholder has no .rtt-frac, so callers pass it only when the value
    is a real ratio)."""
    face = _cell_child(user, cell_id)  # the .rtt-ratio div
    frac = next(c for c in face.default_slot.children if "rtt-frac" in getattr(c, "_classes", []))
    collapsed = "rtt-frac-whole" in getattr(frac, "_classes", [])
    num, den = frac.default_slot.children[0], frac.default_slot.children[1]
    return num.text, den.text, collapsed


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
    the value read like a read-only tuning value cell (the main glyph big, a small line below). A cents
    cell stacks the whole part over the decimal; a power cell stacks ∞ over "(max)". The
    editable input is child[0]; the face is child[1] (a .rtt-tuning-value div holding the
    .rtt-stacked-main / .rtt-stacked-sub labels)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    face = wrap.default_slot.children[1]
    return face.default_slot.children[0], face.default_slot.children[1]


def _gentuning_face(user: User, cell_id: str):
    """The (sign, whole, fraction) labels of a generator-tuning cell's signed cents face. Unlike
    the other cents cells, the genmap shows an explicit, clickable sign glyph (+ ordinarily
    assumed, − when negative) on a row with the big whole part, the small dot-led fraction
    stacked below. The input is child[0]; the face (rtt-tuning-value.rtt-cellface) is child[1], holding
    the sign+whole row (children[0]) over the fraction label (children[1])."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    face = wrap.default_slot.children[1]
    row = face.default_slot.children[0]
    return row.default_slot.children[0], row.default_slot.children[1], face.default_slot.children[1]


def _ratio_face(user: User, cell_id: str):
    """The (numerator, denominator) INPUT fields of an editable stacked-fraction cell. The cell is
    now edited in place (no overlay face): the numerator and denominator are two real inputs, so the
    face's "text" is each input's ``.value``."""
    return _frac_inputs(user, cell_id)


def _target_preset(user: User):
    """The (numeric-limit, TILT/OLD family-select) pair of the target chooser — the one
    preset that nests two controls in a flex div inside its cell wrap."""
    container = _cell_child(user, "preset:target")  # the rtt-preset-target div
    num, sel = container.default_slot.children
    return num, sel


async def test_single_option_tuning_chooser_is_a_disabled_dropdown(user: User) -> None:
    # the default view has both gates off: alternative-complexity schemes are gated behind the alt.
    # complexity setting (no minimax-EU etc.), and the simplicity/complexity weight slopes behind the
    # weighting feature (only the unity variant) — leaving a single option, T minimax-U. A chooser with
    # no real choice is not interactive: it renders as a DISABLED dropdown (greyed, non-pickable, still
    # left-justified), the same style as the all-interval-locked target / weight-slope choosers.
    await user.open("/")
    _toggle(user, "presets")
    await user.should_see(marker="preset:tuning")
    tuning = _cell_child(user, "preset:tuning")
    assert not tuning.enabled            # greyed, non-interactive (not a hardcoded bare value)
    assert tuning.value == "minimax-U"   # the lone scheme held in the disabled box (label "T minimax-U")
    # the caption greys with it, like the locked slope chooser
    assert "rtt-caption-disabled" in _cell_child(user, "block:preset:tuning:label")._classes


async def test_checking_all_interval_drops_the_T_prefix_from_the_scheme_chooser(user: User) -> None:
    # the chooser's option LABELS T-prefix only while target-based; checking the all-interval box
    # must flip them to the bare names. The options are recomputed on the toggle (not just the
    # value), so the label updates — regression for them going stale on re-render. alt. complexity
    # is on so the all-interval list keeps several schemes (it stays a multi-option dropdown rather
    # than collapsing to a single hardcoded value, which is what we want to inspect here).
    await user.open("/")
    _toggle(user, "presets")  # show the chooser dropdowns
    user.find(kind=ui.checkbox, content="weighting").click()       # reveal the nested entries
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # ≥2 all-interval schemes -> stays a dropdown
    user.find(kind=ui.checkbox, content="all-interval").click()    # show the target-controls checkbox
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
    _commit(user, "cell:mapping:1:2")                     # commit on blur (typing only previews now)
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"  # the mapped list recomputed on commit


async def test_editing_a_generator_tuning_cell_applies_an_override(user: User) -> None:
    await user.open("/")
    # the generator tuning map cells are editable: typing a cents value overrides that generator
    # (on_gentuning_change -> editor -> render). With no override the cell would re-render to the
    # computed optimum, so seeing the typed 700.000 survive the render proves the override applied
    _cell_child(user, "tuning:gen:1").set_value("700.000")
    await user.should_see(marker="tuning:gen:1")
    assert _cell_child(user, "tuning:gen:1").value == "700.000"


async def test_scrolling_a_generator_tuning_cell_nudges_it_by_a_thousandth_cent(user: User) -> None:
    await user.open("/")
    # hover-and-scroll fine-adjust: a wheel notch over the cell nudges that generator by 1/1000 of
    # a cent (on_gentuning_wheel -> editor.nudge -> render). The wheel listener rides the cell wrap
    # (so it also catches scrolls over the overlaid cents face), so trigger it on the marked wrap.
    before = float(_cell_child(user, "tuning:gen:1").value)
    user.find(marker="tuning:gen:1").trigger("wheel.prevent", {"deltaY": -100})  # scroll up = raise
    await user.should_see(marker="tuning:gen:1")
    assert round(float(_cell_child(user, "tuning:gen:1").value) - before, 3) == 0.001
    user.find(marker="tuning:gen:1").trigger("wheel.prevent", {"deltaY": 100})  # scroll down = lower
    await user.should_see(marker="tuning:gen:1")
    assert round(float(_cell_child(user, "tuning:gen:1").value) - before, 3) == 0.0


async def test_scrolling_an_integer_cell_steps_it_by_one(user: User) -> None:
    await user.open("/")
    # an editable integer matrix entry steps by ±1 per wheel notch while focused (scroll up = +1,
    # down = −1) — the coarse-integer counterpart to the generator-tuning cell's thousandth-cent
    # fine-adjust. The wheel listener rides the cell wrap, so trigger it on the marked wrap.
    before = int(_cell_child(user, "cell:mapping:1:2").value)  # the fifth's prime-5 entry (meantone: 4)
    user.find(marker="cell:mapping:1:2").trigger("wheel", {"deltaY": -100})  # scroll up = +1
    await user.should_see(marker="cell:mapping:0:0")
    assert int(_cell_child(user, "cell:mapping:1:2").value) == before + 1
    user.find(marker="cell:mapping:1:2").trigger("wheel", {"deltaY": 100})  # scroll down = −1
    await user.should_see(marker="cell:mapping:0:0")
    assert int(_cell_child(user, "cell:mapping:1:2").value) == before


async def test_the_integer_wheel_step_is_generic_over_cell_kinds(user: User) -> None:
    await user.open("/")
    # the ±1 wheel step is wired by cell KIND, not a hardcoded column, so any integer entry gets it.
    # Here a comma-basis vector component: stepping it fires the cell's own on_comma_change, which
    # re-derives the temperament — proving the step rides whatever apply path the cell already has.
    before = int(_cell_child(user, "cell:comma:0:0").value)  # the syntonic comma's prime-2 exponent (4)
    user.find(marker="cell:comma:0:0").trigger("wheel", {"deltaY": -50})  # one notch up = +1
    await user.should_see(marker="cell:comma:0:0")
    assert int(_cell_child(user, "cell:comma:0:0").value) == before + 1


async def test_scrolling_the_optimization_power_steps_a_finite_power_and_leaves_infinity(user: User) -> None:
    # the norm power is wired into the SAME _WHEEL_STEPS table as the matrix cells, stepping by 1.
    # ∞ (the default minimax power) can't be reached by a wheel, so a notch leaves it untouched; a
    # finite power steps. Same mechanism, no per-input handler. (The power is an editable input only
    # with alt. complexity on — else it locks read-only.)
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="alt. complexity").click()
    await user.should_see(marker="optimization:power")
    assert _cell_child(user, "optimization:power").value == "∞"
    user.find(marker="optimization:power").trigger("wheel", {"deltaY": -100})  # scroll up on ∞
    await user.should_see(marker="optimization:power")
    assert _cell_child(user, "optimization:power").value == "∞"   # unchanged — you type ∞, not scroll to it
    _cell_child(user, "optimization:power").set_value("2")        # a finite power
    await user.should_see(marker="optimization:power")
    user.find(marker="optimization:power").trigger("wheel", {"deltaY": -100})  # scroll up = +1
    await user.should_see(marker="optimization:power")
    assert _cell_child(user, "optimization:power").value == "3"


async def test_scrolling_a_prescaler_weight_nudges_it_by_a_thousandth(user: User) -> None:
    # the complexity prescaler is in the same _WHEEL_STEPS table too, with a fractional step (0.001,
    # its thousandths display) instead of 1 — the float counterpart to the integer cells, wired and
    # stepped by the one shared mechanism rather than a snowflake handler.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()              # gates the prescaling row
    _cell_child(user, "control:slope").set_value("simplicity-weight")     # a non-unity slope reveals it
    await user.should_see(marker="cell:prescaling:primes:1:1")
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"  # log₂3, shown to 3 dp
    user.find(marker="cell:prescaling:primes:1:1").trigger("wheel", {"deltaY": -100})  # up = +0.001
    await user.should_see(marker="cell:prescaling:primes:1:1")
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.586"
    user.find(marker="cell:prescaling:primes:1:1").trigger("wheel", {"deltaY": 100})   # down = −0.001
    await user.should_see(marker="cell:prescaling:primes:1:1")
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"


async def test_scrolling_the_target_limit_steps_then_commits(user: User, monkeypatch) -> None:
    # a wheel notch on the TILT/OLD limit steps the shown number at once (like the matrix cells),
    # then DEBOUNCES the heavy commit (rebuild the target set, re-solve) so a fast scroll can't grind
    # the app. With the debounce zeroed the commit still lands and the stepped limit sticks — a
    # reverted/failed commit would snap it back, and the user fixture fails on any render error. The
    # chooser nests two controls, so the listener rides the limit input itself.
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 0)
    await _enable(user, "presets")  # reveal the chooser dropdowns
    await user.should_see(marker="preset:target")
    num, _sel = _target_preset(user)
    before = int(num.value)
    UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": -100})  # scroll up = +1
    num, _sel = _target_preset(user)
    assert int(num.value) == before + 1            # the shown number steps immediately
    await asyncio.sleep(0.05)                       # drain the zero-delay debounced commit task
    num, _sel = _target_preset(user)
    assert int(num.value) == before + 1            # committed, not reverted


async def test_positive_gen_tuning_cell_shows_an_explicit_plus_sign(user: User) -> None:
    # the generator tuning map shows each generator's sign as an explicit glyph — the "+" of a
    # positive generator (ordinarily assumed) made visible, so it can be clicked to flip. The
    # default scheme's period and fifth are both positive.
    await user.open("/")
    sign_lbl, _, _ = _gentuning_face(user, "tuning:gen:1")
    assert sign_lbl.text == "+"


async def test_clicking_the_sign_flips_the_generator_and_its_mapping_row(user: User) -> None:
    # clicking a generator-tuning cell's sign glyph reverses that generator's direction: its
    # cents value negates and the glyph swaps + for −, AND its mapping row negates in lockstep
    # (the same quantity) — so the prime tuning map stays put. Meantone row 1 is the fifth (0 1 4).
    await user.open("/")
    before = float(_cell_child(user, "tuning:gen:1").value)
    assert before > 0  # the default fifth is positive
    assert _cell_child(user, "cell:mapping:1:2").value == "4"  # the fifth's prime-5 mapping entry
    sign_lbl, _, _ = _gentuning_face(user, "tuning:gen:1")
    UserInteraction(user, {sign_lbl}, None).click()
    await user.should_see(marker="tuning:gen:1")
    assert float(_cell_child(user, "tuning:gen:1").value) == -before  # the generator's size flipped
    sign_lbl, _, _ = _gentuning_face(user, "tuning:gen:1")
    assert sign_lbl.text == "−"  # the glyph now shows the minus
    assert _cell_child(user, "cell:mapping:1:2").value == "-4"  # its mapping row flipped too


async def test_editable_gen_tuning_cell_renders_a_stacked_cents_face(user: User) -> None:
    # the generator tuning map cells are editable inputs, but a 3-dp cents value (e.g. 697.564)
    # overflows the 30px square as a single line. They must show the same stacked int-over-
    # fraction face as the read-only cents cells — the whole part big over a smaller dot-led
    # fraction — so the value fits. Assert the live value splits across the two face labels.
    await user.open("/")
    value = _cell_child(user, "tuning:gen:1").value  # the single-line cents value, e.g. "697.564"
    _sign_lbl, int_lbl, frac_lbl = _gentuning_face(user, "tuning:gen:1")
    assert "." not in int_lbl.text                  # the whole part stands alone (no decimal)
    assert frac_lbl.text.startswith(".")            # the fraction stacks under, dot-led
    assert int_lbl.text + frac_lbl.text == value    # and the two reconstruct the cell's value (sign aside)


async def test_editing_a_target_cell_overrides_the_set(user: User) -> None:
    await user.open("/")
    # the target interval list cells are editable: overriding a component freezes the set as an
    # explicit override. The default first target is 2/1 = (1 0 0); typing 2 there survives the
    # render only if the override applied (else the cell reverts to the default's component)
    _cell_child(user, "cell:vec:targets:0:0").set_value("2")
    _commit(user, "cell:vec:targets:0:0")              # commit on blur (typing only previews now)
    await user.should_see(marker="cell:vec:targets:0:0")
    assert _cell_child(user, "cell:vec:targets:0:0").value == "2"


async def test_editing_a_comma_ratio_updates_the_basis(user: User) -> None:
    # the quantities-row comma ratio is editable — the scalar twin of the comma vector below it.
    # Committing a new fraction (on blur) re-parses to that comma's vector, so the cells follow.
    await user.open("/")
    assert _ratio_value(user, "comma:0") == "80/81"  # 5-limit meantone's syntonic comma
    _cell_child(user, "comma:0").set_value("25/24")        # the chromatic semitone = (-3 -1 2)
    _commit(user, "comma:0")                               # blur commits the whole fraction
    await user.should_see(marker="cell:comma:0:0")
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]
    assert _ratio_value(user, "comma:0") == "25/24"   # and the ratio cell reflects the edit


async def test_an_out_of_limit_comma_ratio_toasts_and_reverts(user: User) -> None:
    # a fraction carrying a prime outside the 2.3.5 domain (82 = 2·41) can't be a comma vector
    # there: a red toast NAMES the reason (outside the prime limit), the field snaps BACK to the
    # current ratio on blur, and the basis stays at the syntonic comma (4 -4 1).
    await user.open("/")
    _cell_child(user, "comma:0").set_value("82/81")
    _commit(user, "comma:0")
    await user.should_see("outside the 2.3.5 domain")     # the toast explains the prime-limit failure
    assert _ratio_value(user, "comma:0") == "80/81"  # reverted, not left showing the bad 82/81
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["4", "-4", "1"]


async def test_an_unparseable_comma_ratio_toasts_that_its_invalid(user: User) -> None:
    # the other failure mode reads differently: garbage that isn't a fraction at all toasts
    # "not a valid ratio" (vs the out-of-limit wording), and likewise reverts the field
    await user.open("/")
    _cell_child(user, "comma:0").set_value("12three")
    _commit(user, "comma:0")
    await user.should_see("not a valid ratio")
    assert _ratio_value(user, "comma:0") == "80/81"


async def test_editing_a_target_ratio_overrides_the_set(user: User) -> None:
    # the quantities-row target ratio is editable: committing a fraction overrides the target set,
    # like editing the target vector. The typed value survives the render only if the override held.
    await user.open("/")
    assert _ratio_value(user, "target:0") == "2"   # 2/1 rests as the big-integer view
    _cell_child(user, "target:0").set_value("5/4")
    _commit(user, "target:0")
    await user.should_see(marker="target:0")
    assert _ratio_value(user, "target:0") == "5/4"


async def test_editing_a_held_ratio_updates_the_interval(user: User) -> None:
    # the held interval's ratio is editable too: committing a fraction re-parses to its held vector.
    # First commit a held interval via the draft flow (fill its vector cells), then edit the ratio.
    await user.open("/")
    _toggle(user, "optimization")                    # show the optimization box's held column
    _click_glyph(user, "held_plus")                  # start a blank green held interval draft
    _cell_child(user, "cell:held:0:0").set_value("-1")  # fill it to 3/2 = (-1 1 0)
    _cell_child(user, "cell:held:1:0").set_value("1")
    _cell_child(user, "cell:held:2:0").set_value("0")
    _commit(user, "cell:held:2:0")                    # commit the draft on blur (filling only previews)
    await user.should_see(marker="held:0")
    _cell_child(user, "held:0").set_value("5/4")      # edit the committed ratio to 5/4 = (-2 0 1)
    _commit(user, "held:0")
    await user.should_see(marker="cell:held:0:0")
    assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-2", "0", "1"]


async def test_editing_an_interest_ratio_updates_the_interval(user: User) -> None:
    # the interval-of-interest ratio is editable, like the comma/held ratios; commit one via the
    # draft flow first (its column and the interval-vectors row are open by default)
    await user.open("/")
    _click_glyph(user, "interest_plus")              # start a blank green draft
    _cell_child(user, "cell:interest:0:0").set_value("1")  # fill it to 6/5 = (1 1 -1)
    _cell_child(user, "cell:interest:1:0").set_value("1")
    _cell_child(user, "cell:interest:2:0").set_value("-1")
    _commit(user, "cell:interest:2:0")                # commit the draft on blur (filling only previews)
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
    assert "rtt-pending" in _wrap_classes(user, "held:pending")  # the draft head reads green
    assert _ratio_value(user, "held:pending") == "?/?"  # pre-filled, so you edit "?/?" not a blank box
    _cell_child(user, "held:pending").set_value("3/2")  # type the fraction into the draft head
    _commit(user, "held:pending")                       # blur commits it = (-1 1 0)
    await user.should_see(marker="held:0")
    assert _ratio_value(user, "held:0") == "3/2"   # the draft committed to a real held interval
    assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-1", "1", "0"]


async def test_typing_a_bare_integer_into_a_pending_draft_fills_it(user: User) -> None:
    # the "?/?" draft splits into two fields (numerator "?" over denominator "?"). Typing a bare
    # INTEGER into only the numerator (the octave 2 = 2/1) must commit the integer — NOT "2/?" — so
    # the untouched "?" denominator collapses like a blank/1 (cell_value treats it as no denominator).
    await user.open("/")
    _toggle(user, "optimization")
    _click_glyph(user, "held_plus")
    await user.should_see(marker="held:pending")
    num, den = _frac_inputs(user, "held:pending")
    assert (num.value, den.value) == ("?", "?")          # both fields pre-filled with the placeholder
    num.set_value("2")                                   # type the octave into the NUMERATOR only
    _commit(user, "held:pending")                        # blur commits it = 2/1 = (1 0 0)
    await user.should_see(marker="held:0")
    assert _ratio_value(user, "held:0") == "2"           # committed the bare integer, not "2/?"
    assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["1", "0", "0"]


async def test_editable_ratio_cell_renders_a_stacked_fraction_face(user: User) -> None:
    # the editable comma ratio is an in-place stacked fraction: two separate inputs (numerator over a
    # bar over denominator), not an overlaid face on one input — the syntonic comma reads 80 over 81
    await user.open("/")
    assert isinstance(_cell_child(user, "comma:0"), ui.input)  # the editable numerator box, not a static label
    num, den = _ratio_face(user, "comma:0")
    assert (num.value, den.value) == ("80", "81")              # the two fraction fields


async def test_clicking_a_non_last_comma_minus_un_tempers_that_comma(user: User) -> None:
    # each comma carries its own − now: clicking a NON-last comma's − un-tempers THAT comma, not the
    # last. End-to-end through the live page: the click → app._build_list_minus → editor.remove_comma
    # (index) wiring must route the clicked column's index. Drive meantone (81/80) to two commas by
    # adding the diesis 128/125 = (7 0 -3), then click the FIRST comma's −.
    await user.open("/")
    _click_glyph(user, "comma_plus")                        # open the draft comma column (cell:comma:*:1)
    _cell_child(user, "cell:comma:0:1").set_value("7")      # fill the diesis vector (7 0 -3)…
    _cell_child(user, "cell:comma:1:1").set_value("0")
    _cell_child(user, "cell:comma:2:1").set_value("-3")
    _commit(user, "cell:comma:2:1")                         # …commit on blur → two commas, rank 1
    await user.should_see(marker="comma_minus:1")           # the 2nd comma now carries its own −
    # the same two-comma temperament built straight from the service, to predict each removal. The
    # page renders state.comma_basis in canonical order and removes that same index, so comparing
    # against service.remove_comma(·, 0) holds whatever order the basis canonicalises to.
    two = service.from_comma_basis(((4, -4, 1), (7, 0, -3)))
    drop0, drop_last = service.remove_comma(two, 0), service.remove_comma(two, -1)
    keep0, keep_last = service.comma_ratios(drop0.comma_basis)[0], service.comma_ratios(drop_last.comma_basis)[0]
    assert keep0 != keep_last                               # dropping the first vs the last genuinely differ
    _click_glyph(user, "comma_minus:0")                     # click the FIRST comma's − (not the last)
    await user.should_not_see(marker="comma_minus:0")       # comma 0 is gone — and its id went WITH it:
    # the survivor keeps its own identity token (1), so its cells keep their ids and the remove
    # preview/diff blames the removed column, not the one that slid into its slot
    assert _ratio_value(user, "comma:1") == keep0           # the index-0 removal rendered, NOT the last-comma one


def test_ratio_font_shrinks_a_long_fraction_to_fit_its_square() -> None:
    # the stacked fraction face sits at a fixed comfortable size, but a long numerator or
    # denominator (e.g. 65536 = the target 2/1 re-vectored to [16 0 0⟩) can outgrow the COL_W
    # square. _ratio_font caps a short fraction at the comfortable size and shrinks a long one
    # until its longer line plus the fraction-bar padding fits the cell — num and den scaled together.
    import math
    from rtt.app.app import _ratio_font, _RATIO_MAX_FONT, _RATIO_DIGIT_EM, _RATIO_PAD
    cell = spreadsheet.COL_W
    assert _ratio_font("2", "1", cell) == _RATIO_MAX_FONT          # 1-digit: sits at the cap
    assert _ratio_font("128", "125", cell) == _RATIO_MAX_FONT      # 3-digit still fits the cap
    # the fewest digits whose line can't fit the cell at the comfortable cap — so it MUST shrink
    # (derived from the cell width, so this holds at any COL_W rather than a hard-coded length)
    overflow = math.floor((cell - _RATIO_PAD) / (_RATIO_DIGIT_EM * _RATIO_MAX_FONT)) + 1
    for num, den in [("9" * overflow, "1"), ("1", "9" * overflow), ("9" * (overflow + 2), "1")]:
        font = _ratio_font(num, den, cell)
        assert font < _RATIO_MAX_FONT                             # a long fraction shrinks
        longest = max(len(num), len(den))
        assert longest * _RATIO_DIGIT_EM * font + _RATIO_PAD <= cell + 1e-9  # ...enough to fit
    widths = [_ratio_font("9" * n, "1", cell) for n in range(1, 9)]
    assert widths == sorted(widths, reverse=True)                 # longer never grows the font


async def test_a_long_ratio_face_shrinks_to_fit_its_cell(user: User) -> None:
    # Bug: a value whose numerator/denominator outgrows the 30px square — e.g. the target 2/1
    # re-vectored to [16 0 0⟩ = 65536/1, which collapses to the big-integer view "65536" — spilled
    # past the cell at the fixed font. The fitted font shrinks to fit, and the two fraction fields
    # share one size.
    await user.open("/")
    num, den = _ratio_face(user, "target:0")
    assert (num.value, den.value) == ("2", "")                    # 2/1 collapses to the big-integer view
    assert "font-size" in num._style, "the fraction field must carry a fitted font size"
    big = float(num._style["font-size"].rstrip("px"))             # the comfortable 1-digit size
    _cell_child(user, "target:0").set_value("65536/1")            # 2^16 = the [16 0 0⟩ target vector
    _commit(user, "target:0")
    await user.should_see(marker="target:0")
    num, den = _ratio_face(user, "target:0")
    assert num.value == "65536"
    small = float(num._style["font-size"].rstrip("px"))
    assert small < big                                            # the 5-digit value shrank to fit
    assert num._style["font-size"] == den._style["font-size"]     # num and den share one size


async def test_typing_the_prescaler_plain_text_overrides_the_scheme(user: User) -> None:
    # the bare prescaler 𝐿 tile's plain-text box is the OTHER editable surface (alongside
    # the diagonal cells): typing a d×d matrix EBK with all off-diagonal entries zero parses
    # to a d-tuple diagonal (on_ptext_edit -> editor.set_custom_prescaler_text), which then
    # drives every downstream consumer. The diagonal grid cell must reflect the typed value
    # on re-render — would otherwise be the scheme's log₂3 = 1.585 default.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens the prescaling row
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
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
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
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
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
    await user.should_see(marker="cell:prescaling:primes:1:1")
    _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
    await user.should_see(marker="cell:prescaling:primes:1:1")
    # the typed value rode the override back to the diagonal cell on re-render (it would
    # otherwise have reverted to the scheme's 1.585), and the off-diagonal "0" stays read-only
    assert _cell_child(user, "cell:prescaling:primes:1:1").value == "4"  # bare (no fractional part)
    # the off-diagonal cell is plain tuning value "0" (the rtt-tuning-value div, no editable input); a render
    # error in that branch would surface here via the fixture's ERROR-log guard
    await user.should_see(marker="cell:prescaling:primes:0:1")


async def test_editable_prescaler_cell_renders_a_stacked_cents_face(user: User) -> None:
    # the bare prescaler 𝐋 diagonal cells are editable too; the 5-limit default seeds prime 3's
    # diagonal at log₂3 = 1.585, a 3-dp value that overflows the square as a single line. It must
    # read as the same stacked int-over-fraction face. Enable weighting (gates the prescaling row).
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
    await user.should_see(marker="cell:prescaling:primes:1:1")
    value = _cell_child(user, "cell:prescaling:primes:1:1").value  # the single-line value, e.g. "1.585"
    int_lbl, frac_lbl = _stacked_face(user, "cell:prescaling:primes:1:1")
    assert "." not in int_lbl.text                  # the whole part stands alone
    assert frac_lbl.text.startswith(".")            # the fraction stacks under, dot-led
    assert int_lbl.text + frac_lbl.text == value    # and the two reconstruct the cell's value


async def test_a_bare_integer_value_fills_the_cell_not_the_reduced_whole_part_size(user: User) -> None:
    # A cents value stacks a small whole part over a smaller .fraction so the pair fits the square.
    # But a value with NO fractional part is a plain integer: it must fill the cell at the full
    # value-cell font (like the mapping / mapped integers), NOT sit at the reduced whole-part size
    # with empty space below — which made integers read as shrunken, "as if they had a decimal part".
    # The prescaler matrix is mostly integers: its off-diagonal 0s are read-only tuning value cells.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # reveal the prescaling row
    await user.should_see(marker="cell:prescaling:primes:0:1")
    zero_face = _cell_child(user, "cell:prescaling:primes:0:1")        # read-only tuning value: child[0] IS the face
    zero_main = zero_face.default_slot.children[0]
    assert zero_main.text == "0"
    assert "rtt-stacked-solo" in zero_main._classes    # the bare integer takes the full-size (solo) face
    # the diagonal log₂3 = 1.585 keeps the stacked whole-over-.fraction face, so it is NOT solo
    diag_main, _ = _stacked_face(user, "cell:prescaling:primes:1:1")
    assert "rtt-stacked-solo" not in diag_main._classes


async def test_a_finite_power_fills_the_cell_when_re_synced_from_infinity(user: User) -> None:
    # the optimization power is the same stacked face, but reached through the UPDATE path: the cell
    # is re-synced (not rebuilt) when the power changes, so the full-size toggle must fire on sync
    # too. ∞ keeps its small "(max)" sub (NOT solo); editing it to a finite power makes a bare
    # integer that must flip to the full-size (solo) face on that re-sync. The power is editable only
    # with alt. complexity on (else it locks read-only), so enable that to type into it.
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="alt. complexity").click()
    main, sub = _stacked_face(user, "optimization:power")
    assert (main.text, sub.text) == ("∞", "(max)")
    assert "rtt-stacked-solo" not in main._classes        # ∞ keeps its stacked "(max)" annotation
    _cell_child(user, "optimization:power").set_value("2")
    await user.should_see(marker="optimization:power")
    main, sub = _stacked_face(user, "optimization:power")
    assert (main.text, sub.text) == ("2", "")
    assert "rtt-stacked-solo" in main._classes             # the finite power fills the cell on re-sync


async def test_undo_button_reverts_a_mapping_edit(user: User) -> None:
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")
    _commit(user, "cell:mapping:1:2")                     # commit on blur (typing only previews now)
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
    # never narrower than the box it drops from. (Weighting on so the tuning chooser has its three
    # weight-slope variants — a real dropdown, not the single-option hardcoded value.)
    await _enable(user, "presets")
    _toggle(user, "weighting")
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
    _commit(user, "cell:mapping:1:2")                     # commit on blur (typing only previews now)
    await user.should_see(marker="preset:temperament")
    assert _cell_child(user, "preset:temperament")._props.get("display-value") == "-"


async def test_tuning_chooser_shows_the_prompt_as_a_placeholder_when_off_list(user: User) -> None:
    # the tuning chooser names the active scheme; refine it past the named list (here by
    # setting a finite optimization power, which resolves to an unnamed spec) and the closed
    # box falls back to "-" via Quasar's display-value — never a blank field, never a row.
    await user.open("/")
    _toggle(user, "presets")
    user.find(kind=ui.checkbox, content="optimization").click()
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # 𝑝 editable (else read-only)
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


async def test_picking_a_scheme_clears_the_manual_tuning_and_retunes(user: User) -> None:
    # picking a scheme from the dropdown ESTABLISHES it: with no Optimize button the pick must
    # apply itself, so it clears the hand-edited manual tuning and the grid retunes to the picked
    # scheme's optimum — the dropdown recovers the name instead of staying "-" (set_tuning_scheme
    # is the reset path, like re-picking a prescaler).
    await user.open("/")
    _toggle(user, "presets")
    seed = _cell_child(user, "tuning:gen:1").value          # the scheme's optimum fifth
    _cell_child(user, "tuning:gen:1").set_value("700.000")  # deviate -> dropdown shows "-"
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"
    _cell_child(user, "preset:tuning").set_value("minimax-U")  # re-pick the scheme
    await user.should_see(marker="preset:tuning")
    assert "display-value" not in _cell_child(user, "preset:tuning")._props  # named again: the pick applied
    assert _cell_child(user, "tuning:gen:1").value == seed  # the hand-typed cents replaced by the optimum


async def test_prescaler_chooser_shows_the_prompt_when_a_diagonal_is_overridden(user: User) -> None:
    # the prescaler preset names the scheme's prescaler; hand-editing the bare prescaler 𝐿
    # diagonal freezes a custom override deviating from it, so the closed box falls back to "-"
    # via Quasar's display-value — the same fallback the tuning chooser uses for a manual tuning.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()  # opens the prescaling row (box 𝐋)
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
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
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals the prescaling/complexity rows
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


async def test_editing_the_prescaler_wipes_then_restores_the_complexity_chooser(user: User) -> None:
    # the complexity is built on the prescaler, so hand-editing the prescaler diagonal off log-prime
    # (the prescaler chooser drops to "-") wipes the predefined-complexity chooser downstream too: its
    # value flips from the named "lp (log-product)" to "custom". Re-picking "log-prime" snaps the
    # diagonal back, and the complexity recovers its name.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # reveals box 𝒄 + the prescaling row
    _toggle(user, "presets")  # the complexity + prescaler choosers are presets
    await user.should_see(marker="control:complexity")
    assert _cell_child(user, "control:complexity").value == "lp (log-product)"  # log-prime -> lp
    _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")  # deviate from log₂3 = 1.585
    await user.should_see(marker="control:complexity")
    assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"  # prescaler deviates
    assert _cell_child(user, "control:complexity").value == "custom"  # ...and the complexity wipes
    _cell_child(user, "preset:prescaler").set_value("log-prime")  # snap the prescaler back
    await user.should_see(marker="control:complexity")
    assert _cell_child(user, "control:complexity").value == "lp (log-product)"  # complexity recovers


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
    _commit(user, "cell:vec:targets:0:0")                     # commit on blur (typing only previews now)
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
    _commit(user, "cell:vec:targets:0:0")                     # commit on blur (typing only previews now)
    await user.should_see(marker="preset:target")
    _, sel = _target_preset(user)
    assert sel._props.get("display-value") == "-"
    sel.set_value("TILT")  # re-pick the family
    await user.should_see(marker="cell:vec:targets:0:0")
    _, sel = _target_preset(user)
    assert "display-value" not in sel._props  # family named again
    assert _cell_child(user, "cell:vec:targets:0:0").value == original  # list restored to TILT


async def test_weighting_complexity_chooser_is_disabled_when_lp_only(user: User) -> None:
    # the box-𝒄 complexity chooser offers a single option (log-product) until alt. complexity opens
    # the full measure list — so with alt. complexity off (the default) it has no real choice and
    # renders as a DISABLED dropdown (greyed) showing the live complexity, like the locked slope
    # chooser. (Its enabled multi-option form + option swap are the next test, with alt. complexity on.)
    await user.open("/")
    _toggle(user, "presets")  # the dropdown is a preset, so it needs the presets layer on
    user.find(kind=ui.checkbox, content="weighting").click()  # box 𝒘's slope chooser shows under weighting
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals box 𝒄
    await user.should_see(marker="control:complexity")
    chooser = _cell_child(user, "control:complexity")
    assert not chooser.enabled                  # greyed, non-interactive
    assert chooser.value == "lp (log-product)"  # the live complexity, held as its sole option
    assert "rtt-caption-disabled" in _cell_child(user, "caption:complexity")._classes


async def test_alt_complexity_enables_and_widens_the_complexity_chooser(user: User) -> None:
    # the box-𝒄 "predefined complexities" chooser is disabled (one option, log-product) until alt.
    # complexity opens the whole measure list. Turning alt. complexity on while it is already shown must
    # ENABLE it and widen its OPTIONS in place — the control_select update branch re-applies the enabled
    # state and refreshes the list. Without that it stays a disabled lone log-product entry — the bug
    # this guards. The live value is preserved across the change.
    await user.open("/")
    _toggle(user, "presets")  # the dropdown is a preset, so it needs the presets layer on
    user.find(kind=ui.checkbox, content="weighting").click()
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals box 𝒄
    await user.should_see(marker="control:complexity")
    assert not _cell_child(user, "control:complexity").enabled  # one option -> disabled
    assert list(_cell_child(user, "control:complexity").options) == ["lp (log-product)"]
    user.find(kind=ui.checkbox, content="alt. complexity").click()      # open the full measure list
    await user.should_see(marker="control:complexity")
    widened = _cell_child(user, "control:complexity")
    assert widened.enabled                                              # now a live choice
    assert set(widened.options) == set(service.COMPLEXITY_DISPLAYS.values()) | {"custom"}  # full list + off-preset sentinel
    assert widened.value == "lp (log-product)"  # the live value is preserved across the change


async def test_typing_the_q_field_drives_the_complexity_norm(user: User) -> None:
    # the q field (box 𝒄) is an editable powerinput ONLY with alt. complexity on (it switches the
    # scheme's Lq complexity); typing then routes through on_power_change -> set_complexity_norm_power
    # -> re-render. dual(q) is DERIVED from q (dual(1)=∞, dual(2)=2) and shows as a read-only
    # powerdisplay in all-interval mode, so switching q taxicab -> Euclidean must flip dual(q) ∞ -> 2,
    # proving the typed q drove the norm.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()        # reveal the nested all-interval + alt entries
    user.find(kind=ui.checkbox, content="all-interval").click()     # show the target-controls checkbox
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # make q an editable powerinput
    await user.should_see(marker="control:all_interval")
    _cell_child(user, "control:all_interval").set_value(True)       # all-interval -> simplicity + dual(q) shown
    await user.should_see(marker="control:dual")
    assert _cell_child(user, "control:q").value == "1"              # taxicab default
    assert _cell_child(user, "control:dual").default_slot.children[0].text == "∞"  # dual of taxicab (q=1), read-only face
    _cell_child(user, "control:q").set_value("2")                  # taxicab (q=1) -> Euclidean (q=2)
    await user.should_see(marker="control:dual")
    assert _cell_child(user, "control:q").value == "2"             # the field reflects the new q
    assert _cell_child(user, "control:dual").default_slot.children[0].text == "2"  # dual(2)=2 -> the typed q drove the norm


async def test_q_norm_power_is_read_only_until_alt_complexity(user: User) -> None:
    # the user-facing contract: with alt. complexity OFF you cannot type a new norm power 𝑞 (editing it
    # would switch the scheme's complexity, which alt. complexity gates). So 𝑞 renders as a read-only
    # value — the SAME ∞-over-(max) stacked face as the editable input, just no white box (no rtt-cell-
    # input, no input element) — exactly like the all-interval-locked optimization power. Turning alt.
    # complexity on swaps it to the editable powerinput.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()           # box 𝒘's slope chooser shows
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # a non-unity slope reveals box 𝒄 + 𝑞
    await user.should_see(marker="control:q")
    assert "rtt-cell-input" not in _wrap_classes(user, "control:q")  # alt. complexity OFF -> read-only, no input
    assert _cell_child(user, "control:q").default_slot.children[0].text == "1"  # the read-only face shows q=1
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # turn it on -> q becomes editable
    await user.should_see(marker="control:q")
    assert "rtt-cell-input" in _wrap_classes(user, "control:q")      # now an editable powerinput
    assert _cell_child(user, "control:q").value == "1"              # the input mirrors the same value


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


async def test_changing_the_weight_slope_renames_the_established_scheme_chooser(user: User) -> None:
    # the reported bug, end to end: picking complexity-weight in the box-𝒘 slope chooser re-
    # establishes the scheme, so the established-tuning-scheme chooser must show its complexity-
    # weighted variant (minimax-U -> minimax-C) rather than blanking to "-". Both choosers set the
    # same scheme trait, and the scheme-driven tuning retunes to the new variant's optimum.
    await user.open("/")
    _toggle(user, "presets")                                  # the established-scheme dropdown
    user.find(kind=ui.checkbox, content="weighting").click()  # the box-𝒘 slope chooser + the -S/-C variants
    await user.should_see(marker="control:slope")
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning").value == "minimax-U"  # default, unity-weighted
    _cell_child(user, "control:slope").set_value("complexity-weight")
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning").value == "minimax-C"  # tracked the slope, not "-"
    _cell_child(user, "control:slope").set_value("simplicity-weight")
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "preset:tuning").value == "minimax-S"


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


async def test_optimization_renders_the_mean_damage_and_power(user: User) -> None:
    # the optimization box's value-over-label cells render when optimization is on: the mean
    # damage value + its ⟪𝐝⟫ₚ symbol, the editable power, and the power's symbol + "optimization
    # power" caption. The fixture catches any error rendering those cell branches.
    await _enable(user, "optimization")
    for marker in ("optimization:mean_damage", "optimization:mean_damage:symbol",
                   "optimization:power", "optimization:power:symbol", "optimization:power:caption"):
        await user.should_see(marker=marker)
    # there is NO optimize button: optimization is always invisibly on (the grid recomputes the
    # scheme's optimum on every change), so nothing renders for the retired "optimization:button"
    await user.should_not_see(marker="optimization:button")


async def test_minimax_power_stacks_a_max_annotation_below_infinity(user: User) -> None:
    # the power cell reads ∞ for the default minimax scheme; like every gridded value it stacks a
    # small line below the main glyph — here "(max)", naming what ∞ means (the max norm). The power is
    # editable only with alt. complexity on (else it locks read-only), so turn that on to type into it.
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="alt. complexity").click()
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
    user.find(kind=ui.checkbox, content="optimization").click()     # reveal the power cell
    user.find(kind=ui.checkbox, content="weighting").click()        # reveal the all-interval + alt entries
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # 𝑝 editable while target-based
    user.find(kind=ui.checkbox, content="all-interval").click()     # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")  # editable input while target-based
    edit_main, edit_sub = _stacked_face(user, "optimization:power")       # editable face: ∞ over (max)
    assert (edit_main.text, edit_sub.text) == ("∞", "(max)")
    _cell_child(user, "control:all_interval").set_value(True)     # check it -> all-interval
    await user.should_see(marker="optimization:power")
    assert "rtt-cell-input" not in _wrap_classes(user, "optimization:power")  # read-only value, no input
    face = _cell_child(user, "optimization:power")                # the .rtt-tuning-value stacked face div
    main, sub = face.default_slot.children[0], face.default_slot.children[1]
    assert (main.text, sub.text) == ("∞", "(max)")               # identical face: ∞ over (max), kept
    _cell_child(user, "control:all_interval").set_value(False)    # back to target-based
    await user.should_see(marker="optimization:power")
    assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")  # editable input again


async def test_mean_damage_tooltip_tracks_the_all_interval_mode(user: User) -> None:
    # the optimization mean damage is read-only but carries help, and that help names a different
    # quantity per mode: target-based the minimized damage ⟪𝐝⟫ₚ, all-interval the retuning
    # magnitude. The mean damage cells are NOT rebuilt when the mode flips, so render() must swap
    # the tooltip text in place. Scan the client's Tooltip registry (it holds even un-hovered
    # tooltips, which the visible-only search can't reach).
    await user.open("/")
    user.find(kind=ui.checkbox, content="optimization").click()  # reveal the mean damage box

    def mean_damage_tips() -> list[str]:
        return [el.text for el in user.client.elements.values()
                if isinstance(el, Tooltip) and "the tuning minimizes over" in el.text]

    assert any("⟪𝐝⟫ₚ" in t for t in mean_damage_tips())                 # the target-based wording
    assert not any("retuning magnitude" in t.lower() for t in mean_damage_tips())

    user.find(kind=ui.checkbox, content="weighting").click()          # reveal the all-interval entry
    user.find(kind=ui.checkbox, content="all-interval").click()       # show the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    _cell_child(user, "control:all_interval").set_value(True)         # check it -> flip to all-interval

    assert any("retuning magnitude" in t.lower() for t in mean_damage_tips())   # the wording swapped in place
    assert not any("⟪𝐝⟫ₚ" in t for t in mean_damage_tips())


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


async def test_a_held_interval_retunes_the_grid_immediately(user: User) -> None:
    # optimization is always invisibly on: committing a held interval retunes the grid right away —
    # the displayed generator tuning moves to the held-constrained optimum (holding 3/2 makes the
    # fifth generator pure, 701.955¢), with no Optimize step in between. That held optimum no longer
    # realises the bare scheme, so the established-tuning-scheme chooser drops to "-".
    await user.open("/")
    _toggle(user, "presets")             # show the chooser
    _toggle(user, "optimization")        # ...and the held interval column
    assert _cell_child(user, "preset:tuning").value == "minimax-U"  # the default scheme, named
    assert _cell_child(user, "tuning:gen:1").value != "701.955"     # the unheld optimum fifth is tempered
    _click_glyph(user, "held_plus")                  # start a blank held interval draft
    await user.should_see(marker="cell:held:0:0")
    _cell_child(user, "cell:held:0:0").set_value("-1")  # make it the fifth 3/2
    _cell_child(user, "cell:held:1:0").set_value("1")
    _cell_child(user, "cell:held:2:0").set_value("0")
    _commit(user, "cell:held:2:0")                      # commit the draft on blur (filling only previews)
    await user.should_see(marker="preset:tuning")
    assert _cell_child(user, "cell:held:0:0").value == "-1"          # the held interval is committed...
    assert _cell_child(user, "tuning:gen:1").value == "701.955"      # ...and the grid retuned to hold 3/2 just
    assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"  # off the bare scheme -> "-"


async def test_adding_an_interval_of_interest_commits_when_filled(user: User) -> None:
    # the whole user flow: + opens a blank green draft, and filling every vector component commits
    # it (an interval of interest is no longer a pre-filled 1/1 — it stays a draft until complete)
    await user.open("/")
    _click_glyph(user, "interest_plus")               # start a blank green draft
    await user.should_see(marker="cell:interest:0:0")
    assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes  # the draft cell is green
    _cell_child(user, "cell:interest:0:0").set_value("-1")  # make it 3/2 = (-1 1 0)
    _cell_child(user, "cell:interest:1:0").set_value("1")
    _cell_child(user, "cell:interest:2:0").set_value("0")
    _commit(user, "cell:interest:2:0")                      # commit the draft on blur (filling only previews)
    await user.should_see(marker="interest:0")              # the committed ratio now heads the column
    assert _cell_child(user, "cell:interest:0:0").value == "-1"  # the vector committed


async def test_adding_a_target_commits_when_filled(user: User) -> None:
    # the same flow for the target list; its draft rides at index k (past the TILT defaults), and
    # filling it materializes the spec set into an override with the new interval appended
    k = len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, Editor().state.domain_basis))
    await user.open("/")
    _click_glyph(user, "target_plus")               # start a blank green target draft
    await user.should_see(marker=f"cell:vec:targets:{k}:0")
    assert "rtt-pending" in _cell_child(user, f"cell:vec:targets:{k}:0")._classes
    _cell_child(user, f"cell:vec:targets:{k}:0").set_value("-1")  # make it 3/2 = (-1 1 0)
    _cell_child(user, f"cell:vec:targets:{k}:1").set_value("1")
    _cell_child(user, f"cell:vec:targets:{k}:2").set_value("0")
    _commit(user, f"cell:vec:targets:{k}:2")                      # commit the draft on blur (filling only previews)
    await user.should_see(marker=f"target:{k}")  # the new target now heads its own column
    assert _cell_child(user, f"cell:vec:targets:{k}:0").value == "-1"


async def test_audio_bank_is_always_live_with_a_leading_mute(user: User) -> None:
    # the waveform / play-mode / hold / 1-1 bank rides the settings panel's dummy tile and is now
    # ALWAYS live — mute (its leading control) is the on/off gate, so there is no audio Show toggle
    # and no greyed bank. All five controls render, mute first.
    await user.open("/")
    assert "rtt-bank-off" not in next(iter(user.find(marker="audiobank").elements))._classes
    for ctrl in ("mute", "wave", "mode", "hold", "root"):
        assert user.find(marker=f"audioctrl:{ctrl}").elements  # the five controls sit on the dummy tile


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
    _commit(user, "cell:mapping:1:2")                     # commit on blur (typing only previews now)
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


async def test_settings_frozen_header_plus_chrome_bar_matches_the_grid_column_strip_height(user: User) -> None:
    # "exactly the same height as the frozen part of the main app pane": the settings frozen header now
    # sits BELOW the chrome title bar, so the two together must span the grid's frozen column strip
    # height (freeze_y) for the settings and grid frozen/scrolling seams to sit at the same height
    # across the app. render() therefore sizes the header to freeze_y MINUS the chrome bar. (The title-
    # bar rework regressed this by leaving the header at the full freeze_y, so its seam sat a chrome-
    # bar's height below the grid's — this guard now accounts for the bar above it.)
    await user.open("/")
    frozen = next(iter(user.find(marker="showfrozen").elements))
    colhead = next(iter(user.find(marker="colhead").elements))
    assert frozen._style.get("height")  # the header is sized (not left to hug its content)...
    assert _px(frozen, "height") == _px(colhead, "height") - web_app._CHROME_H  # ...to strip minus the bar


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
    # the frozen band — the chrome title bar + frozen header together span the inset+freeze_y, same as
    # the grid — (calc(100vh - (pad + freeze_y)px)), so it scrolls only once its content genuinely
    # exceeds that — a self-contained cap that doesn't depend on the flex hug rounding out exactly.
    await user.open("/")
    scroll = next(iter(user.find(marker="showscroll").elements))
    colhead = next(iter(user.find(marker="colhead").elements))
    fy = _px(colhead, "height")  # the frozen header / column-strip height (freeze_y)
    assert scroll._style.get("max-height") == f"calc(100vh - {web_app._PAD + fy}px)"


async def test_state_persists_across_a_refresh(user: User) -> None:
    # the document is persisted on each render and reloaded when the page opens, so a refresh
    # (a fresh open of "/") restores exactly where the user left off
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")
    _commit(user, "cell:mapping:1:2")                     # commit on blur (typing only previews now)
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"
    await user.open("/")  # the refresh
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"  # the edit survived


async def test_dragging_a_generator_row_onto_another_adds_it_in(user: User) -> None:
    # the drag pipeline: dragstart on row A's GRIP records it; dropping onto another ROW's cells (the
    # row itself is the drop target, not a tiny grip) adds A into that row and the page re-renders.
    # Meantone: drop row 0 (the octave) onto row 1 (the fifth) → row 1's mapping becomes (1, 2, 4).
    await _enable(user, "drag to combine")  # the feature is off by default
    row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
    assert row1() == ["0", "1", "4"]
    grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
    cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
    assert next(iter(grip(0)))._props.get("draggable")  # the browser starts a drag from the grip
    UserInteraction(user, grip(0), None).trigger("dragstart")        # grab the octave row's grip
    UserInteraction(user, cell(1, 0), None).trigger("drop.prevent")  # drop onto the fifth row's cells
    await user.should_see(marker="cell:mapping:1:0")
    assert row1() == ["1", "2", "4"]  # row 1 absorbed row 0


async def test_dropping_a_row_grip_directly_onto_another_grip_merges(user: User) -> None:
    # the PROVEN drop path, mirroring the working column-reorder grips: the grip is BOTH the drag
    # source AND a drop target, so dropping one row's grip directly onto another row's grip merges
    # them — independent of whether the input cells accept a native drop. Row 0 onto row 1 → (1,2,4).
    await _enable(user, "drag to combine")
    row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
    assert row1() == ["0", "1", "4"]
    grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
    UserInteraction(user, grip(0), None).trigger("dragstart")     # grab row 0's grip
    UserInteraction(user, grip(1), None).trigger("drop.prevent")  # drop onto row 1's grip
    await user.should_see(marker="cell:mapping:1:0")
    assert row1() == ["1", "2", "4"]  # row 1 absorbed row 0


async def test_dropping_an_interval_grip_directly_onto_another_grip_merges(user: User) -> None:
    # the column twin of the proven grip-to-grip path: drop one interval's grip onto another's grip.
    await _enable(user, "drag to combine")
    tuning_value = lambda i: _cell_child(user, f"target:{i}").value
    before0, before1 = tuning_value(0), tuning_value(1)
    grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
    UserInteraction(user, grip(0), None).trigger("dragstart")     # grab target 0's grip
    UserInteraction(user, grip(1), None).trigger("drop.prevent")  # drop onto target 1's grip
    await user.should_see(marker="target:1")
    assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)  # target 1 is the product


async def test_dragging_an_interval_onto_another_combines_them(user: User) -> None:
    # the column twin: dragstart on interval A's grip, drop onto another interval's COLUMN cells
    # combines them into their product. Drag target 0 onto target 1 → target 1 is the product.
    await _enable(user, "drag to combine")  # the feature is off by default
    tuning_value = lambda i: _cell_child(user, f"target:{i}").value
    before0, before1 = tuning_value(0), tuning_value(1)
    grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
    cell = lambda i, p: set(user.find(marker=f"cell:vec:targets:{i}:{p}").elements)
    assert next(iter(grip(0)))._props.get("draggable")  # the browser starts a drag from the grip
    UserInteraction(user, grip(0), None).trigger("dragstart")        # grab target 0's grip
    UserInteraction(user, cell(1, 0), None).trigger("drop.prevent")  # drop onto target 1's column
    await user.should_see(marker="target:1")
    assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)  # target 1 is the product
    assert tuning_value(0) == before0  # the dragged target is unchanged


async def test_dragging_over_an_interval_previews_the_product_then_reverts(user: User) -> None:
    # the column twin of the row preview: hovering another interval's COLUMN cells previews their
    # product without committing; releasing off it (dragend) reverts.
    await _enable(user, "drag to combine")
    tuning_value = lambda i: _cell_child(user, f"target:{i}").value
    before0, before1 = tuning_value(0), tuning_value(1)
    grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
    cell = lambda i, p: set(user.find(marker=f"cell:vec:targets:{i}:{p}").elements)
    UserInteraction(user, grip(0), None).trigger("dragstart")             # pick up target 0
    UserInteraction(user, cell(1, 0), None).trigger("dragenter.prevent")  # hover target 1's column → preview
    assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)  # previews the product
    UserInteraction(user, grip(0), None).trigger("dragend")              # released → revert
    assert tuning_value(1) == before1  # reverted, nothing committed


async def test_dragging_over_a_row_previews_the_change_then_reverts(user: User) -> None:
    # hovering (dragenter) a target ROW previews the would-be combine — the moved cells show their new
    # values AND the dropped-on row is highlighted (its editable cells ring, even though they're input
    # cells the value-diff wouldn't catch) — WITHOUT committing; releasing off a target (dragend)
    # reverts it. The changed derived gen-ratio rings too.
    await _enable(user, "drag to combine")
    row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
    assert row1() == ["0", "1", "4"]
    grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
    cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
    UserInteraction(user, grip(0), None).trigger("dragstart")             # pick up row 0 (the octave)
    UserInteraction(user, cell(1, 0), None).trigger("dragenter.prevent")  # hover row 1 → preview
    assert row1() == ["1", "2", "4"]  # the matrix cells preview their new values...
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:0")  # ...the dropped-on ROW is highlighted...
    assert "rtt-preview-change" in _wrap_classes(user, "gen:0")            # ...and the changed gen ratio rings
    UserInteraction(user, grip(0), None).trigger("dragend")              # released off a target → revert
    assert row1() == ["0", "1", "4"]  # reverted, nothing committed
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:0")  # the highlight cleared
    assert "rtt-preview-change" not in _wrap_classes(user, "gen:0")


async def test_dropping_a_row_on_its_own_cells_does_nothing(user: User) -> None:
    # a row dropped on ITSELF is not a meaningful operation — hovering or dropping on the dragged
    # row's own cells neither previews nor commits anything (the no-self guard).
    await _enable(user, "drag to combine")
    row0 = lambda: [_cell_child(user, f"cell:mapping:0:{p}").value for p in range(3)]
    assert row0() == ["1", "1", "0"]
    grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
    cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
    UserInteraction(user, grip(0), None).trigger("dragstart")             # grab row 0
    UserInteraction(user, cell(0, 0), None).trigger("dragenter.prevent")  # hover its OWN cells
    assert row0() == ["1", "1", "0"]  # no preview — self is not a valid target
    UserInteraction(user, cell(0, 0), None).trigger("drop.prevent")       # drop on itself
    assert row0() == ["1", "1", "0"]  # unchanged


# --- tier 3: the #3 drift guard. _make_cell builds each cell-kind, render() fills each kind,
# in two parallel cb.kind ladders. For the kinds whose visible content is a single ui.html the
# renderer must populate (built empty in _make_cell), a dropped render branch leaves the cell
# silently blank — should_see only checks the wrap is present, so it slips through. One
# representative cell per such kind, asserting the html actually carries content. ---

# Off-by-default html kinds: enable the Show layer that surfaces the kind, then assert a
# representative cell's html actually carries content. Each exercises a distinct fill-in-render
# path — _math_html (count/symbol), _units_html (units), _bar_chart / _range_chart SVGs.
_ENABLE_HTML_CELLS = [
    # counts ships ON now (its _math_html "d = 3" renders by default); symbols still covers _math_html
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
# (_underline_html) and the matrix-frame EBK bracket SVGs (ebk_svg, the most numerous kind).
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


# --- the edit-preview highlight: while a cell is focused, ring the cells its edit changes ---

async def test_editing_a_cell_previews_the_ripple_then_commits_on_blur(user: User) -> None:
    # the editable matrix/vector integer cells PREVIEW as you type and COMMIT on Enter/blur (like the
    # ratio + domain-element cells), rather than re-solving on every keystroke. Focusing a cell captures
    # a baseline; typing then rings every OTHER cell whose value the edit WOULD move (rtt-preview-change)
    # WITHOUT applying it — the focused cell itself is never ringed — and the value lands only on blur
    # (or Enter), which also clears the preview.
    await user.open("/")
    assert _cell_text(user, "cell:mapped:1:6") == "4"    # the committed mapped value (meantone)
    src = _cell_child(user, "cell:mapping:1:2")          # the fifth's prime-5 entry (meantone: 4)
    UserInteraction(user, {src}, None).trigger("focus")  # capture the pre-edit baseline
    src.set_value("7")                                   # TYPE 4 -> 7: previews only, not yet committed
    await user.should_see(marker="cell:mapped:1:6")
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6")        # the moved cell is ringed...
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")   # ...the source is not
    assert _cell_text(user, "cell:mapped:1:6") == "4"    # ...and the edit is NOT applied yet (preview only)
    UserInteraction(user, {src}, None).trigger("blur")   # blur COMMITS the edit and clears the preview
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"                            # now applied
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")    # and the ring cleared


async def test_repeated_edits_keep_previewing(user: User) -> None:
    # the live preview must keep working across repeated edit-commit cycles, not just the first. Each
    # commit ends the preview (blur), and re-focusing re-arms it. (Enter is wired to blur the input —
    # see make_cell — precisely so it routes through this proven blur path rather than committing while
    # focus is retained, which desynced the input and stopped the browser firing on_change after the
    # first edit: the reported "preview works only once until I refresh" bug.)
    await user.open("/")
    src = _cell_child(user, "cell:mapping:1:2")
    # cycle 1
    UserInteraction(user, {src}, None).trigger("focus")
    src.set_value("7")                                   # previews
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6")
    UserInteraction(user, {src}, None).trigger("blur")   # commit (Enter does this too, via blur)
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"    # applied
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")  # ring cleared
    # cycle 2 — re-focus and edit again: the preview must ring AGAIN (it broke here before)
    src = _cell_child(user, "cell:mapping:1:2")
    UserInteraction(user, {src}, None).trigger("focus")
    src.set_value("9")
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6"), \
        "the live preview must keep working on later edits, not only the first"
    assert _cell_text(user, "cell:mapped:1:6") == "7"    # still a preview (not yet committed)
    UserInteraction(user, {src}, None).trigger("blur")
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "9"    # cycle-2 commit applied


async def test_opening_a_comma_draft_previews_the_rank_drop_on_the_mapping(user: User) -> None:
    # the comma basis and the mapping are duals: adding a comma drops the rank, so the last mapping
    # (generator) row LEAVES and the survivors RECOMBINE. That structural preview fires the instant
    # the green draft opens — value-independent, before anything is typed — the doomed row reds
    # (rtt-preview-remove), the survivor ambers (rtt-preview-change). (The draft column itself is the
    # green newborn, already rendered.)
    await user.open("/")
    _click_glyph(user, "comma_plus")                          # open the draft comma column — nothing typed
    await user.should_see(marker="cell:comma:0:1")
    await user.should_see(marker="cell:mapping:1:0")          # meantone is rank 2: row 1 on screen
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:0")  # doomed generator row → red
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:2")
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")  # the survivor recombines → amber
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:2")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0")  # the survivor is not red
    # it clears when the draft is cancelled (its − )
    _click_glyph(user, "comma_minus:pending")
    await user.should_see(marker="cell:mapping:1:0")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:1:0")


async def test_opening_a_mapping_row_draft_previews_the_dropped_comma(user: User) -> None:
    # the dual of the above: adding a generator raises the rank, so a comma LEAVES. Opening the green
    # mapping-row draft reds the doomed comma (meantone has one comma, so it just reds — no survivor
    # to amber). The draft row itself is the green newborn.
    await user.open("/")
    _click_glyph(user, "gen_plus")                            # open the draft mapping row — nothing typed
    await user.should_see(marker="cell:mapping:2:0")
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")  # the doomed comma → red
    assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")         # ...its ratio too
    _click_glyph(user, "map_minus:pending")                  # cancel the draft
    await user.should_see(marker="cell:comma:0:0")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")


async def test_hovering_a_comma_minus_previews_the_born_generator(user: User) -> None:
    # removing a comma raises the rank: a generator is BORN and the surviving rows recombine.
    # Hovering a comma − reflows that dual preview — the hovered comma reds, every mapping row ambers,
    # and a new green ghost generator row appears below the matrix — without committing. (Bullet 2 of
    # the QA report: the green newborn the no-reflow ring diff could never show.)
    await user.open("/")
    await user.should_not_see(marker="cell:mapping:2:0")                    # meantone is rank 2
    btn = set(user.find(marker="comma_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    await user.should_see(marker="cell:mapping:2:0")                        # the born generator row reflows in
    assert "rtt-pending" in _wrap_classes(user, "cell:mapping:2:0")         # ...green (a newborn)
    # the op is known, so the born generator's coords are COMPUTED and shown: dropping the syntonic
    # comma un-tempers to JI, whose third generator is prime 5 → ⟨0 0 1]
    assert [_cell_text(user, f"cell:mapping:2:{p}") for p in range(3)] == ["0", "0", "1"]
    # ...and the row's DERIVED mapped cells are computed too (not left blank): the born generator's
    # image of each interval is filled across the band
    assert _cell_text(user, "cell:mapped:2:0") != ""
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")    # the hovered comma → red
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")  # a survivor recombines → amber
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:0")
    # where the red comma column crosses the green ghost row, red wins (the value vanishes with it)
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapped_comma:2:0")
    assert "rtt-pending" not in _wrap_classes(user, "cell:mapped_comma:2:0")
    UserInteraction(user, btn, None).trigger("mouseleave")
    await user.should_not_see(marker="cell:mapping:2:0")                    # the ghost clears on mouse-out
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")


async def test_hovering_a_mapping_minus_previews_the_born_comma(user: User) -> None:
    # the dual (bullet 4): removing a generator raises the nullity — a comma is BORN, surviving commas
    # recombine. Hovering a mapping row − reflows that — the hovered row reds, every comma ambers, and
    # a new green ghost comma column appears to the right of the basis. Leaving clears it.
    await user.open("/")
    await user.should_not_see(marker="cell:comma:0:1")                      # meantone has one comma
    btn = set(user.find(marker="map_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    await user.should_see(marker="cell:comma:0:1")                          # the born comma column reflows in
    assert "rtt-pending" in _wrap_classes(user, "cell:comma:0:1")           # ...green (a newborn)
    # its quantities-row ratio face (a read-only commaratio showing the COMPUTED ratio) greens too —
    # rings its wrap like every sibling value cell down the column, not just the vector/derived rows
    assert "rtt-pending" in _wrap_classes(user, "comma:pending")
    # the born comma's coords are COMPUTED and shown (dropping meantone's generator un-tempers to the
    # rank-1 ET whose extra comma is [0 -4 1⟩)
    assert [_cell_text(user, f"cell:comma:{p}:1") for p in range(3)] == ["0", "-4", "1"]
    # ...and the column's DERIVED mapped cells are computed: M[surviving row]·newborn = 0 (the
    # rank-reduced mapping tempers the born comma out). (Its tuning SIZES are checked in the unit
    # test — a tuningvalue face isn't readable through _cell_text.)
    assert _cell_text(user, "cell:mapped_comma:1:1") == "0"
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:0:0")  # the hovered row → red
    assert "rtt-preview-change" in _wrap_classes(user, "cell:comma:0:0")    # the survivor comma recombines → amber
    # where the red mapping row crosses the green ghost comma, red wins
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapped_comma:0:1")
    assert "rtt-pending" not in _wrap_classes(user, "cell:mapped_comma:0:1")
    UserInteraction(user, btn, None).trigger("mouseleave")
    await user.should_not_see(marker="cell:comma:0:1")                      # the ghost clears on mouse-out
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0")


async def test_hovering_a_mapping_minus_in_projection_dooms_the_last_unchanged_interval(user: User) -> None:
    # in projection the V column splits C|U with #unchanged = rank, so a mapping − (which drops the
    # rank) deletes the last unchanged interval — preview it red, the U-half dual of the comma born on
    # the C side. (A comma − raises the rank instead, birthing a U interval — the dual born case.)
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:1")            # meantone rank 2 → two unchanged columns
    btn = set(user.find(marker="map_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:unchanged:0:1")       # the last U interval → red
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:unchanged:0:0")   # the earlier one survives
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:unchanged:0:1")   # cleared on mouse-out


async def test_hovering_a_comma_minus_in_projection_births_an_unchanged_interval(user: User) -> None:
    # the dual of the doomed case: a comma − raises the rank, so in projection the U half grows — a
    # held interval is BORN (green), the U-half dual of the generator born on the mapping axis. It
    # reflows in to the right of the existing unchanged columns; leaving clears it.
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:1")        # meantone rank 2 → two unchanged columns
    await user.should_not_see(marker="cell:unchanged:0:2")    # ...not a third yet
    btn = set(user.find(marker="comma_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    await user.should_see(marker="cell:unchanged:0:2")        # the born held interval reflows in...
    assert "rtt-pending" in _wrap_classes(user, "cell:unchanged:0:2")   # ...green (a newborn)
    UserInteraction(user, btn, None).trigger("mouseleave")
    await user.should_not_see(marker="cell:unchanged:0:2")    # cleared on mouse-out


async def test_blurring_an_incomplete_draft_cell_keeps_the_other_typed_cells(user: User) -> None:
    # tabbing between draft cells fires a non-committing blur each hop (the comma isn't complete yet).
    # That blur must NOT re-render: a render would push the still-blank editor draft back over the
    # cells, wiping the digits already typed into the siblings. So an uncommitted draft blur is inert
    # and the typed values stand until the comma completes and commits.
    await user.open("/")
    _click_glyph(user, "comma_plus")
    await user.should_see(marker="cell:comma:0:1")
    _cell_child(user, "cell:comma:0:1").set_value("7")
    UserInteraction(user, {_cell_child(user, "cell:comma:0:1")}, None).trigger("blur")  # hop away, incomplete
    await user.should_see(marker="cell:comma:0:1")
    assert _cell_child(user, "cell:comma:0:1").value == "7"       # the typed digit survives the blur


async def test_hovering_a_non_last_comma_minus_reds_that_comma_not_the_last(user: User) -> None:
    # each comma column owns its id (identity-keyed, like the reorderable lists), so the remove
    # preview blames the comma actually being removed: hovering the FIRST comma's − reds ITS cells,
    # not whichever comma happens to sit last. (Index-keyed ids slid the survivor into the freed
    # slot, so the diff used to red the LAST column whatever you hovered — the reported bug.)
    await user.open("/")
    _click_glyph(user, "comma_plus")                        # open the draft comma column
    for p, v in zip(range(3), ("7", "0", "-3")):            # the diesis 128/125 = (7 0 -3)
        _cell_child(user, f"cell:comma:{p}:1").set_value(v)
    _commit(user, "cell:comma:2:1")                         # commit → two commas, rank 1
    await user.should_see(marker="comma_minus:1")
    btn = set(user.find(marker="comma_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")  # hover the FIRST comma's −
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")   # the hovered comma reds...
    assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")          # ...its ratio too
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:1")  # the survivor does NOT
    assert "rtt-preview-remove" not in _wrap_classes(user, "comma:1")
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")  # cleared on mouse-out


async def test_hovering_a_non_last_mapping_row_minus_reds_that_row_not_the_last(user: User) -> None:
    # the row twin: mapping rows are identity-keyed by their content (remove_mapping_row keeps the
    # survivors verbatim), so hovering the FIRST row's − reds that row — its matrix cells, its
    # generator ratio and its tuning cents — while the surviving row keeps its id and doesn't ring.
    await user.open("/")
    btn = set(user.find(marker="map_minus:0").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")     # hover row 0's − (meantone: 2 rows)
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:0:0")  # the hovered row reds...
    assert "rtt-preview-remove" in _wrap_classes(user, "gen:0")             # ...its generator ratio
    assert "rtt-preview-remove" in _wrap_classes(user, "tuning:gen:0")      # ...and its tuning cents
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:1:0")  # the survivor does NOT
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0")  # cleared on mouse-out


async def test_adding_a_mapping_row_previews_the_rank_raise_while_the_draft_is_green(user: User) -> None:
    # the row twin of the comma-draft preview: typing a complete, independent generator row into the
    # green draft previews its commit — the un-tempered comma's column reds (the rank raise consumes
    # it) and the re-solved cells ring amber — while the draft stays green and uncommitted until blur.
    await user.open("/")
    _click_glyph(user, "gen_plus")                            # open the green draft mapping row
    await user.should_see(marker="cell:mapping:2:0")
    for p, v in zip(range(2), ("0", "0")):
        _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
    last = _cell_child(user, "cell:mapping:2:2")
    UserInteraction(user, {last}, None).trigger("focus")      # arm the edit gesture
    last.set_value("1")                                       # ⟨0 0 1] — independent → previews the commit
    await user.should_see(marker="cell:comma:0:0")
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")  # the comma it un-tempers → red
    assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")
    assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes  # the draft is STILL green
    UserInteraction(user, {last}, None).trigger("blur")       # blur commits → rank 3, comma gone
    await user.should_see(marker="cell:mapping:2:0")
    await user.should_not_see(marker="comma_minus:0")         # nothing tempered any more


async def test_typing_a_target_limit_rings_the_rows_it_moves(user: User) -> None:
    # the target chooser's numeric limit is an editable control, so it drives the same edit-preview as a
    # grid cell: focusing it captures a baseline, and typing a new limit (which commits live and
    # re-derives the target set) rings the rows the change brings in, while leaving clears them. From the
    # 5-limit default (6-TILT, 8 targets) typing a 9 grows the set, so the new target rows ring — and the
    # scheme-driven tuning re-optimizes over the grown set, so the generator tuning rings as moved too;
    # an unmoved mapping entry does not. The chooser is the source and so is never rung itself.
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")    # capture the pre-edit baseline
    num.set_value("9")                                     # grow 6-TILT -> 9-TILT, adding target rows
    await user.should_see(marker="retune:target:8")        # a target row the larger limit brings in
    assert "rtt-preview-change" in _wrap_classes(user, "retune:target:8")     # ...rings as moved
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:gen:0")        # the retuned generator rings too
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")  # an unmoved cell does not
    UserInteraction(user, {num}, None).trigger("blur")     # leaving the field clears the preview
    assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:8")


# --- lowering the limit reddens the target rows it drops, BEFORE they reflow away ---
# The test above proves a GROWING limit rings the survivors that move (amber). A SHRINKING limit must
# do the other half the user asked for: light up RED the intervals it's about to delete, while they're
# still on screen. That preview can't ride the post-commit render — the reflow has already removed those
# cells — so on_target_limit_wheel paints it in place the instant it steps the number, SYNCHRONOUSLY
# (unlike the debounced commit, which lands in a background task the fixture can't observe). So a wheel-
# then-ring assertion IS reliable for the red, asserted before the debounce ever fires.

async def test_scrolling_the_target_limit_down_reddens_the_dropped_target_rows(
        user: User, monkeypatch) -> None:
    # the reported bug: stepping the TILT limit DOWN sheds target intervals, and those going away must
    # flash red before they vanish. From the 5-limit default (6-TILT, 8 targets: …5/4, 6/5) one notch
    # down to 5-TILT drops 6/5 (target index 7); its row must redden in place. The debounce is pinned
    # far out so the heavy commit can't reflow the row away mid-assertion — only the synchronous,
    # no-reflow remove-preview is under test (the commit itself is covered by the steps-then-commits test).
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 100)
    await _enable(user, "presets")
    await user.should_see(marker="retune:target:7")           # the 6/5 row exists at the 6-TILT default
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")        # snapshot the 6-TILT baseline + own the preview
    UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": 100})   # scroll down = -1 → 6-TILT to 5-TILT
    num, _sel = _target_preset(user)
    assert int(num.value) == 5                                 # the shown number stepped down at once
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")  # the dropped 6/5 row → red
    assert "rtt-preview-remove" in _wrap_classes(user, "target:7")         # …its target interval cell too
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")  # a surviving row is untouched


async def test_typing_the_target_limit_down_reddens_the_dropped_target_rows(
        user: User, monkeypatch) -> None:
    # the reported gesture (the bug as filed: "changing the TILT from 8 to 6 doesn't preview the
    # intervals going away in red"). Typing the limit DOWN sheds target intervals, and those going
    # away must flash red before the debounced commit reflows them off. Unlike the wheel, the typing
    # preview can't ride on_change (that's the debounced COMMIT, which set_value would fire and which
    # would reflow the row away); nor the RAW DOM `input` event (a Quasar QInput never forwards it to a
    # NiceGUI `.on()` listener — verified in-browser: it produces no socket emit, so the preview silently
    # never ran). It rides `keyup` (which DOES fire on the QInput) with a js_handler that emits the live
    # `e.target.value`, since NiceGUI's `args=` only filters top-level event keys and can't pull the
    # nested value. So drive `keyup` with the lowered value the way the js_handler packs it (a bare
    # string), from the 6-TILT default down to 5, dropping 6/5 (target index 7). The structural wiring
    # itself is locked by test_the_typed_target_limit_preview_rides_keyup_not_input below — this test
    # only exercises the value path. Pin the debounce far out so no commit can reflow mid-assertion.
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 100)
    await _enable(user, "presets")
    await user.should_see(marker="retune:target:7")            # the 6/5 row exists at the 6-TILT default
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")        # snapshot the 6-TILT baseline + own the preview
    UserInteraction(user, {num}, None).trigger("keyup", "5")   # TYPE the limit down to 5-TILT, dropping 6/5
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")  # the dropped 6/5 row → red
    assert "rtt-preview-remove" in _wrap_classes(user, "target:7")         # …its target interval cell too
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")  # a surviving row is untouched


async def test_the_typed_target_limit_preview_rides_keyup_not_input(user: User) -> None:
    # REGRESSION GUARD for the wiring the value-path test above can't see. The typed-limit preview was
    # first wired to the DOM `input` event with args=[["target","value"]] — and silently NEVER FIRED:
    # a Quasar QInput doesn't forward a native `input` to a NiceGUI `.on()` listener (verified in-browser:
    # zero socket emits), and NiceGUI's `args=` only filters top-level event keys, so it can't pull the
    # nested target.value either. The in-process tests passed regardless, because triggering the handler
    # directly injects the value and bypasses BOTH the browser event and the arg extraction. So lock the
    # wiring STRUCTURALLY: the field must carry a `keyup` listener whose js_handler emits the live
    # target.value, and must NOT lean on `input`. This is the assertion that would have caught the bug.
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")
    num, _sel = _target_preset(user)
    listeners = list(num._event_listeners.values())
    types = {listener.type for listener in listeners}
    assert "keyup" in types, f"typed-limit preview must ride keyup; got {sorted(types)}"
    assert "input" not in types, "native `input` never fires on a QInput — the preview must not rely on it"
    keyup = next(listener for listener in listeners if listener.type == "keyup")
    assert keyup.js_handler and "target.value" in keyup.js_handler, \
        f"keyup must emit the live target.value via a js_handler; got {keyup.js_handler!r}"


async def test_the_dropped_target_red_preview_clears_when_the_limit_field_is_left(
        user: User, monkeypatch) -> None:
    # leaving the limit field ends the gesture: on_cell_blur clears the remove-preview, so the red a
    # scroll-down armed does not outlive the edit. (Were the debounce allowed to fire it would commit
    # the lower limit and delete the row outright; pin it out so the BLUR is what clears the red.)
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 100)
    await _enable(user, "presets")
    await user.should_see(marker="retune:target:7")
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")
    UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": 100})   # arm the red on the dropped 6/5 row
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")
    UserInteraction(user, {num}, None).trigger("blur")         # leaving the field clears the preview
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:7")


async def test_the_target_remove_preview_diffs_the_on_screen_grid_not_the_focus_snapshot(
        user: User, monkeypatch) -> None:
    # the remove-preview (the red on the rows a lowered limit would drop) must diff against the grid
    # ACTUALLY on screen, not the frozen focus-time snapshot. The limit field commits IN PLACE while
    # still focused — a wheel notch / a typed value lands and reflows the grid WITHOUT ending the
    # gesture (it ends on blur) — so the on-screen grid can differ from the snapshot the focus took.
    # _gesture_rings must therefore compute RED as removed_cell_ids(CURRENT layout, hypothetical), not
    # against the stale focus base. The sharpest case is a focused commit that GREW the set: from the
    # 6-TILT default (8 targets, rows 0..7) commit UP to 8-TILT (10 targets, adding rows 8 and 9),
    # then preview the limit back DOWN — those just-added rows are exactly what the lower limit drops,
    # so they MUST redden. Against the stale 6-TILT snapshot they're invisible (it never had rows 8/9),
    # so the red was silently missing — the bug. (_TARGET_LIMIT_DEBOUNCE is pinned small so the typed
    # commit lands, then pinned out so the follow-up preview stays a pure no-reflow preview.)
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 0.01)
    await _enable(user, "presets")
    await user.should_see(marker="retune:target:7")           # the 6-TILT default is on screen
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")        # baseline = the 6-TILT grid (8 rows)
    num.set_value("8")                                         # commit UP to 8-TILT while focused: grows to 10 rows
    await user.should_see(marker="retune:target:9")            # row 9 is one of the rows the grow added
    # now preview the limit back DOWN to 6 (without leaving the field): rows 8 and 9 are dropped, so
    # they must redden. Pin the debounce out so this stays a pure no-reflow preview, no commit.
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 100)
    UserInteraction(user, {num}, None).trigger("keyup", "6")   # type the limit back down to 6
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:8"), \
        "a preview after a focused commit must diff the on-screen (8-TILT) grid, not the focus snapshot"
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:9")  # the other added row reddens too
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")  # a surviving row is untouched


async def test_scrolling_the_target_limit_up_reddens_no_target_rows(user: User, monkeypatch) -> None:
    # the mirror guard: GROWING the limit removes nothing, so the remove-preview must stay empty — a
    # raised limit only adds rows (off-screen until committed) and re-solves the survivors. No red
    # anywhere, even though the re-solve does move survivors (those would ring amber, not red).
    monkeypatch.setattr(web_app, "_TARGET_LIMIT_DEBOUNCE", 100)
    await _enable(user, "presets")
    await user.should_see(marker="retune:target:7")
    num, _sel = _target_preset(user)
    UserInteraction(user, {num}, None).trigger("focus")
    UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": -100})  # scroll up = +1 → 6-TILT to 7-TILT
    num, _sel = _target_preset(user)
    assert int(num.value) == 7                                 # stepped up
    for idx in range(8):                                       # none of the 6-TILT rows go away → no red
        assert "rtt-preview-remove" not in _wrap_classes(user, f"retune:target:{idx}")


async def test_an_invalid_target_limit_stays_reddened_through_the_edit_preview_gesture(user: User) -> None:
    # the limit field carries two independent signals that must coexist: it reddens in place when the
    # displayed (family, limit) is invalid (an even limit for the odd-limit diamond), and it drives the
    # edit-preview while focused. The preview rings OTHER cells, never the field itself, so its focus/blur
    # gesture must not strip the validation reddening — a reddened field stays red across it.
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")
    _num, sel = _target_preset(user)
    sel.set_value("OLD")                                   # the even default limit (6) is invalid for OLD
    await user.should_see(marker="preset:target")
    num, _sel = _target_preset(user)
    assert "rtt-limit-error" in num._classes               # the validation reddening is on
    UserInteraction(user, {num}, None).trigger("focus")    # the edit-preview gesture: arm then leave
    UserInteraction(user, {num}, None).trigger("blur")
    num, _sel = _target_preset(user)
    assert "rtt-limit-error" in num._classes               # ...and never strips the reddening


# --- characterization net for the six interval-grid edit handlers (audit cluster C, Phase-2 Lane B) ---
# Before the later phase consolidates on_mapping/comma/unchanged/interest/held/target_cells_change into
# one factory, these lock the arms the rest of the suite leaves uncovered: the PREVIEW (no-commit) arm,
# the INVALID-entry arm (toast+revert vs silent revert), the DRAFT arm's materialization, and the guard
# only on_mapping_change carries. They pin what the code does TODAY — including silent reverts — so the
# consolidation cannot drift them. (The differences between handlers are deliberate; each test preserves
# its own handler's shape.)


async def test_mapping_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_mapping_change(preview=True): focusing a mapping cell arms the edit gesture, and a keystroke
    # (set_value -> on_change -> preview) only ARMS the would-be change — it does NOT mutate the
    # document. The mapped list still reads the pre-edit value; the new value lands only on blur.
    await user.open("/")
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # meantone: 5/4 maps to 4 fifths
    cell = _cell_child(user, "cell:mapping:1:2")
    UserInteraction(user, {cell}, None).trigger("focus")       # arm the edit gesture
    cell.set_value("7")                                        # a preview keystroke, NOT a commit
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # still the pre-edit value — no commit
    UserInteraction(user, {cell}, None).trigger("blur")        # NOW commit
    await user.should_see(marker="cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "7"          # the value landed on blur


async def test_an_improper_mapping_commit_toasts_and_reverts_the_cells(user: User) -> None:
    # on_mapping_change commit arm with an IMPROPER matrix: making row 1 a copy of row 0 (dependent
    # generators) is not a valid temperament, so committing it toasts _INVALID_TEMPERAMENT (a negative
    # ui.notify) AND reverts the cells — the row snaps back to meantone's (0 1 4), document untouched.
    await user.open("/")
    for p, v in zip(range(3), ("1", "1", "0")):                # set row 1 == row 0 -> dependent, improper
        _cell_child(user, f"cell:mapping:1:{p}").set_value(v)
    _commit(user, "cell:mapping:1:2")
    await user.should_see(web_app._INVALID_TEMPERAMENT)        # the negative toast names the failure
    assert [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)] == ["0", "1", "4"]  # reverted
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # the document stayed meantone


async def test_an_improper_mapping_preview_rings_nothing_and_does_not_toast(user: User) -> None:
    # the dual of the above on the preview path: an improper in-progress matrix previewed (focus +
    # keystroke, no blur) must ring NOTHING and NOT toast — only the commit toasts. Pin that no
    # preview-ring appears on the cells the would-be change touches and the document is unchanged.
    await user.open("/")
    UserInteraction(user, {_cell_child(user, "cell:mapping:1:0")}, None).trigger("focus")
    _cell_child(user, "cell:mapping:1:0").set_value("1")       # row 1 -> (1 1 4): independent of row 0?
    # drive the cells to a genuinely improper matrix while focused: row1 = row0 = (1 1 0)
    _cell_child(user, "cell:mapping:1:1").set_value("1")
    cell = _cell_child(user, "cell:mapping:1:2")
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("0")                                        # row 1 now equals row 0 -> improper
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")  # an improper preview rings nothing
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # ...and never touched the document (no commit)


async def test_a_mapping_row_draft_commit_materializes_a_new_generator_row(user: User) -> None:
    # on_mapping_change DRAFT branch: opening a green draft row and typing a complete, independent
    # generator into it materializes the draft into a real row the moment the vector completes — the
    # rank raises (the syntonic comma it un-tempers leaves) without any blur. Pin the materialization.
    await user.open("/")
    await user.should_not_see(marker="cell:mapping:2:0")       # meantone is rank 2: no third row yet
    _click_glyph(user, "gen_plus")                             # open the green draft row
    await user.should_see(marker="cell:mapping:2:0")
    assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes  # the draft reads green
    for p, v in zip(range(3), ("0", "0", "1")):                # ⟨0 0 1] — the prime-5 generator, independent
        _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
    _commit(user, "cell:mapping:2:2")                          # blur -> on_mapping_change(False) materializes the draft row
    await user.should_see(marker="cell:mapping:2:0")
    assert "rtt-pending" not in _cell_child(user, "cell:mapping:2:0")._classes  # the draft MATERIALIZED -> a real row
    await user.should_not_see(marker="comma_minus:0")          # rank 3 now: nothing tempered, the comma is gone


async def test_a_comma_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_comma_change(preview=True): the comma basis is the mapping's dual. A focused keystroke arms
    # the would-be change but does NOT commit — the mapped list (a comma-derived quantity) still reads
    # the pre-edit value until blur. (The comma row is present independent of the temperament boxes.)
    await user.open("/")
    assert _cell_text(user, "cell:mapped:1:6") == "4"
    cell = _cell_child(user, "cell:comma:0:0")                 # the syntonic comma's prime-2 exponent (4)
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("8")                                        # a preview keystroke, NOT a commit
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # still the pre-edit mapped value — no commit yet
    UserInteraction(user, {cell}, None).trigger("blur")        # blur is the commit: (8 -4 1) is a proper basis
    await user.should_see(marker="cell:comma:0:0")
    assert _cell_child(user, "cell:comma:0:0").value == "8"    # the typed component committed on blur


async def test_an_improper_comma_commit_toasts_and_reverts_the_cells(user: User) -> None:
    # on_comma_change commit arm with an improper comma BASIS: a comma whose dual mapping can't reach
    # every prime — (0 0 1) tempers out prime 5 alone, leaving a mapping that never reaches it — is not
    # a proper temperament, so committing toasts _INVALID_TEMPERAMENT and reverts to the syntonic comma.
    await user.open("/")
    for p, v in zip(range(3), ("0", "0", "1")):                # (0 0 1): from_comma_basis.mapping not proper
        _cell_child(user, f"cell:comma:{p}:0").set_value(v)
    _commit(user, "cell:comma:2:0")
    await user.should_see(web_app._INVALID_TEMPERAMENT)        # the negative toast
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["4", "-4", "1"]  # reverted to syntonic


async def test_an_improper_comma_preview_rings_nothing_and_does_not_toast(user: User) -> None:
    # the comma preview twin of the improper-mapping preview: an improper in-progress comma previewed
    # (focused keystroke, no blur) rings NOTHING and does NOT toast — only the commit toasts.
    await user.open("/")
    _cell_child(user, "cell:comma:0:0").set_value("0")         # drive toward the improper (0 0 1)
    _cell_child(user, "cell:comma:1:0").set_value("0")
    cell = _cell_child(user, "cell:comma:2:0")
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("1")                                        # the basis is now improper, but only previewed
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")
    assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapped:1:6")
    assert _cell_text(user, "cell:mapped:1:6") == "4"          # the document is untouched (no commit)


async def test_a_comma_draft_commit_materializes_a_new_comma_column(user: User) -> None:
    # on_comma_change DRAFT branch: opening a green draft comma column and typing a valid independent
    # comma into it materializes it into a real column the instant the vector completes (rank drops),
    # with no blur. Pin the draft head turning into a committed second comma carrying its own minus.
    await user.open("/")
    _click_glyph(user, "comma_plus")                           # open the draft comma column
    await user.should_see(marker="cell:comma:0:1")
    assert "rtt-pending" in _cell_child(user, "cell:comma:0:1")._classes  # the draft reads green
    for p, v in zip(range(3), ("7", "0", "-3")):               # the diesis 128/125 = (7 0 -3), independent
        _cell_child(user, f"cell:comma:{p}:1").set_value(v)
    _commit(user, "cell:comma:2:1")                            # blur -> on_comma_change(False) materializes the draft column
    await user.should_see(marker="comma_minus:1")              # the draft MATERIALIZED -> a real 2nd comma
    assert "rtt-pending" not in _cell_child(user, "cell:comma:0:1")._classes


async def test_an_invalid_unchanged_basis_reverts_silently(user: User) -> None:
    # on_unchanged_change INVALID arm is the silent variant: a U column that can't form valid ratios
    # (a zero vector raises inside service.comma_ratios, caught) reverts WITHOUT a toast — no
    # ui.notify fires. Pin the silence: the tuning is unchanged and the user-fixture sees no error.
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:1")
    before = _cell_child(user, "tuning:gen:1").value           # the default 1/4-comma fifth
    for p, v in zip(range(3), ("0", "0", "0")):                # a zero column -> comma_ratios raises
        _cell_child(user, f"cell:unchanged:{p}:1").set_value(v)
    _commit(user, "cell:unchanged:2:1")
    await user.should_see(marker="tuning:gen:1")
    assert _cell_child(user, "tuning:gen:1").value == before   # silently reverted — the tuning never moved
    # the silence is the point: no toast text reached the page (a toast would be visible to should_see)
    await user.should_not_see("Not a valid")


async def test_an_unchanged_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_unchanged_change(preview=True): a focused keystroke arms the would-be projection but does NOT
    # retune until blur. on_unchanged_change has NO draft branch (skip draft) — only the plain
    # preview/commit/invalid arms exist.
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:1")
    before = _cell_child(user, "tuning:gen:1").value
    cell = _cell_child(user, "cell:unchanged:2:1")
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("-1")                                       # toward holding 6/5; a preview keystroke only
    assert _cell_child(user, "tuning:gen:1").value == before   # not retuned — no commit on the keystroke


async def test_an_interest_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_interest_change(preview=True): any integer vector is accepted (no validity check), but a
    # focused keystroke only ARMS the candidate (set_interest_vectors would run on commit) — it does
    # NOT commit. Commit one interest interval first, then preview editing it and pin no state change.
    await user.open("/")
    _click_glyph(user, "interest_plus")                        # start a draft
    for p, v in zip(range(3), ("-1", "1", "0")):               # 3/2 = (-1 1 0)
        _cell_child(user, f"cell:interest:{p}:0").set_value(v)
    _commit(user, "cell:interest:2:0")                         # blur materializes the draft into a real column
    await user.should_see(marker="interest:0")
    assert _ratio_value(user, "interest:0") == "3/2"           # committed
    cell = _cell_child(user, "cell:interest:0:0")
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("-2")                                       # a preview keystroke toward 5/4 = (-2 0 1)
    assert _ratio_value(user, "interest:0") == "3/2"           # the committed interval is unchanged — no commit


async def test_any_integer_interest_vector_is_accepted_on_commit(user: User) -> None:
    # on_interest_change has NO validity check (unlike mapping/comma): committing ANY integer vector
    # is accepted, never toasts, never reverts. Pin an arbitrary vector landing as-is — even one that
    # would be an invalid comma/mapping (it isn't one; an interest interval is just a vector).
    await user.open("/")
    _click_glyph(user, "interest_plus")
    for p, v in zip(range(3), ("5", "-3", "2")):               # an arbitrary integer vector, no validity gate
        _cell_child(user, f"cell:interest:{p}:0").set_value(v)
    _commit(user, "cell:interest:2:0")                         # blur -> on_interest_change(False) commits the arbitrary vector
    await user.should_see(marker="interest:0")
    assert [_cell_child(user, f"cell:interest:{p}:0").value for p in range(3)] == ["5", "-3", "2"]  # accepted as-is


async def test_an_interest_draft_commit_materializes_a_new_interest_column(user: User) -> None:
    # on_interest_change DRAFT branch: filling the green draft column commits it into a real interval
    # of interest the moment the vector completes (set_pending_interest materializes it), no blur.
    await user.open("/")
    await user.should_not_see(marker="interest:0")             # no intervals of interest by default
    _click_glyph(user, "interest_plus")
    await user.should_see(marker="cell:interest:0:0")
    assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes  # the draft reads green
    for p, v in zip(range(3), ("-1", "1", "0")):               # 3/2
        _cell_child(user, f"cell:interest:{p}:0").set_value(v)
    _commit(user, "cell:interest:2:0")                         # blur -> on_interest_change(False) materializes the draft column
    await user.should_see(marker="interest:0")                 # the draft MATERIALIZED -> a committed column
    assert "rtt-pending" not in _cell_child(user, "cell:interest:0:0")._classes


async def test_a_held_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_held_change(preview=True): like interest, no validity check; a focused keystroke arms the
    # candidate (set_held_vectors would run on commit) but does NOT retune. Commit a held interval,
    # then preview editing it: the held-constrained tuning must NOT move on the keystroke.
    await user.open("/")
    _toggle(user, "optimization")                              # show the held column
    _click_glyph(user, "held_plus")
    for p, v in zip(range(3), ("-1", "1", "0")):               # hold 3/2 -> the fifth goes pure
        _cell_child(user, f"cell:held:{p}:0").set_value(v)
    _commit(user, "cell:held:2:0")                             # blur materializes the draft held interval
    await user.should_see(marker="held:0")
    assert _cell_child(user, "tuning:gen:1").value == "701.955"  # retuned to hold 3/2 (pure fifth)
    cell = _cell_child(user, "cell:held:0:0")
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("-2")                                       # a preview keystroke toward 5/4 = (-2 0 1)
    assert _cell_child(user, "tuning:gen:1").value == "701.955"  # the tuning is unchanged — no commit


async def test_a_held_draft_commit_materializes_a_new_held_column(user: User) -> None:
    # on_held_change DRAFT branch: filling the green held draft commits it into a real held interval
    # the moment the vector completes (set_pending_held materializes it), no blur.
    await user.open("/")
    _toggle(user, "optimization")
    _click_glyph(user, "held_plus")
    await user.should_see(marker="cell:held:0:0")
    assert "rtt-pending" in _cell_child(user, "cell:held:0:0")._classes
    for p, v in zip(range(3), ("-1", "1", "0")):               # 3/2
        _cell_child(user, f"cell:held:{p}:0").set_value(v)
    _commit(user, "cell:held:2:0")                             # blur -> on_held_change(False) materializes the draft column
    await user.should_see(marker="held:0")                     # the draft MATERIALIZED -> a committed held interval
    assert "rtt-pending" not in _cell_child(user, "cell:held:0:0")._classes


async def test_a_target_keystroke_preview_does_not_commit_until_blur(user: User) -> None:
    # on_target_cells_change(preview=True): note its cell-id order is REVERSED vs the others —
    # cell:vec:targets:{token}:{prime} (token then prime), not cell:{group}:{prime}:{token}. A focused
    # keystroke through that id shape arms the candidate but does NOT commit the override.
    await user.open("/")
    assert _cell_child(user, "cell:vec:targets:0:0").value == "1"  # the first target 2/1 = (1 0 0): prime-2 entry
    cell = _cell_child(user, "cell:vec:targets:0:0")               # NB token (0) BEFORE prime (0)
    UserInteraction(user, {cell}, None).trigger("focus")
    cell.set_value("2")                                           # a preview keystroke (would override to 4/1)
    # no commit on the keystroke: a sibling target cell still shows the un-overridden default set
    assert _cell_child(user, "cell:vec:targets:1:1").value == "1"  # the second target 3/1's prime-3 entry, unmoved
    UserInteraction(user, {cell}, None).trigger("blur")           # blur is the commit: the override lands
    await user.should_see(marker="cell:vec:targets:0:0")
    assert _cell_child(user, "cell:vec:targets:0:0").value == "2"  # the typed override component committed on blur


async def test_a_target_cell_edit_commits_through_the_reversed_id_shape(user: User) -> None:
    # the commit arm through on_target_cells_change's REVERSED id (cell:vec:targets:{token}:{prime}):
    # overriding a component freezes the set as an explicit override that survives the render. Pin the
    # edit landing through that id order — the axis flip the consolidation must preserve.
    await user.open("/")
    cell = _cell_child(user, "cell:vec:targets:0:1")              # token 0, PRIME 1 (the 2/1 target's prime-3 entry)
    cell.set_value("1")                                           # override the first target to (1 1 0) = 6/1
    _commit(user, "cell:vec:targets:0:1")
    await user.should_see(marker="cell:vec:targets:0:1")
    assert _cell_child(user, "cell:vec:targets:0:1").value == "1"  # the override held through the reversed-id commit


async def test_a_target_draft_commit_materializes_a_new_target_column(user: User) -> None:
    # on_target_cells_change DRAFT branch: filling the green target draft (riding index k past the
    # defaults) commits it into a real target the moment the vector completes (set_pending_target), no
    # blur. Pin the materialization through the reversed cell:vec:targets:{token}:{prime} id.
    k = len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, Editor().state.domain_basis))
    await user.open("/")
    _click_glyph(user, "target_plus")
    await user.should_see(marker=f"cell:vec:targets:{k}:0")
    assert "rtt-pending" in _cell_child(user, f"cell:vec:targets:{k}:0")._classes
    for p, v in zip(range(3), ("-1", "1", "0")):                 # 3/2 = (-1 1 0)
        _cell_child(user, f"cell:vec:targets:{k}:{p}").set_value(v)
    _commit(user, f"cell:vec:targets:{k}:2")                   # blur -> on_target_cells_change(False) materializes the draft
    await user.should_see(marker=f"target:{k}")                  # the draft MATERIALIZED -> a real target column
    assert "rtt-pending" not in _cell_child(user, f"cell:vec:targets:{k}:0")._classes


async def test_an_interest_draft_keystroke_preview_does_not_materialize_early(user: User) -> None:
    # the interest/held/target DRAFT-preview arm ARMS a candidate (set_pending_* would run on commit)
    # but an INCOMPLETE draft previews nothing landing: a partial green draft, previewed cell by cell,
    # must NOT materialize until the vector is complete. Pin that a half-filled draft stays pending.
    await user.open("/")
    _click_glyph(user, "interest_plus")
    await user.should_see(marker="cell:interest:0:0")
    first = _cell_child(user, "cell:interest:0:0")
    UserInteraction(user, {first}, None).trigger("focus")
    first.set_value("-1")                                        # one component typed (preview), draft incomplete
    assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes  # STILL a green draft — nothing committed
    await user.should_not_see(marker="interest:0")              # no real interval-of-interest materialized yet


async def test_a_mapping_draft_keystroke_preview_rings_nothing_from_the_value(user: User) -> None:
    # the mapping/comma DRAFT-preview arm is value-INDEPENDENT: the rank-change preview (doomed reds,
    # survivor ambers) is the builder's, painted the instant the green draft opens — so a per-keystroke
    # preview into the draft cells rings NOTHING extra (it calls _edit_candidate(None)). Pin that the
    # builder-driven reds the draft already shows are unchanged by typing into it, and nothing commits.
    await user.open("/")
    _click_glyph(user, "gen_plus")                              # open the draft mapping row -> builder reds the comma
    await user.should_see(marker="cell:mapping:2:0")
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")  # the builder-driven red (draft opened)
    first = _cell_child(user, "cell:mapping:2:0")
    UserInteraction(user, {first}, None).trigger("focus")
    first.set_value("0")                                        # a draft keystroke -> _edit_candidate(None), rings nothing
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")  # the builder red persists, unchanged
    assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes  # the draft is still green — no commit


async def test_the_mapping_matrix_is_inert_when_temperament_boxes_are_off(user: User) -> None:
    # the GUARD only on_mapping_change carries: it returns early when settings["temperament_boxes"] is
    # off (no editable matrix when the boxes are hidden). With the boxes off the matrix cells are not
    # rendered at all, so the handler can never edit — pin both halves: the editable mapping cells
    # vanish, and turning the boxes back on restores meantone (the document was never mutated).
    await user.open("/")
    assert user.find(marker="cell:mapping:0:0").elements        # the editable matrix is shown by default
    assert _cell_text(user, "cell:mapped:1:6") == "4"
    user.find(kind=ui.checkbox, content="temperament boxes").click()  # turn the boxes OFF
    await user.should_not_see(marker="cell:mapping:0:0")        # no editable matrix -> on_mapping_change is inert
    user.find(kind=ui.checkbox, content="temperament boxes").click()  # back ON
    await user.should_see(marker="cell:mapping:0:0")
    assert _cell_text(user, "cell:mapped:1:6") == "4"           # the mapping was never touched while hidden


async def test_an_unfocused_grid_rings_no_cells(user: User) -> None:
    # with no cell being edited there is no baseline, so a plain edit (here via the mapped list's
    # source cell, then read back) leaves nothing ringed — the highlight is strictly an editing aid
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")  # edit without focusing first
    await user.should_see(marker="cell:mapped:1:6")
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")


async def test_wheeling_a_generator_tuning_rings_the_cells_it_moves(user: User) -> None:
    # hovering the generator-tuning cell arms a baseline; each wheel notch (a real, committed nudge)
    # then rings the OTHER cells whose value it moves — the tempered tunings / retunings — so the user
    # sees the ripple while scrolling. The scrolled cell itself is the source and is never rung;
    # leaving the cell clears the rings (the committed nudge stays).
    await user.open("/")
    cell = set(user.find(marker="tuning:gen:0").elements)
    UserInteraction(user, cell, None).trigger("mouseenter")                     # arm the baseline
    UserInteraction(user, cell, None).trigger("wheel.prevent", {"deltaY": -1})  # one notch up -> nudge + render
    await user.should_see(marker="retune:target:0")
    assert "rtt-preview-change" in _wrap_classes(user, "retune:target:0")       # a moved cell rings
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:gen:0")      # ...not the scrolled cell
    UserInteraction(user, cell, None).trigger("mouseleave")                     # leaving clears the rings
    assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:0")


async def test_hovering_a_generator_tuning_sign_previews_reversing_it(user: User) -> None:
    # the +/- the user means "in the generator tuning map" is the clickable SIGN on each tuned
    # generator size (the + of +1197). Hovering it previews reversing that generator — ringing the
    # cells the flip would change: its mapping row and the derived rows — without committing.
    await user.open("/")
    sign = set(user.find(marker="gensign:1").elements)            # the sign on generator 1's tuning
    UserInteraction(user, sign, None).trigger("mouseenter")
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")  # the mapping row it'd flip rings
    UserInteraction(user, sign, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")  # cleared on mouse-out


async def test_hovering_a_temperament_option_previews_loading_it(user: User) -> None:
    # hovering a temperament in the OPEN dropdown previews loading it: it reflows the would-be grid and
    # rings the cells its comma basis would change. A divider header / leaving the option (detail -1)
    # reverts. The option slot dispatches a native `opthover` CustomEvent at the cell WRAP carrying the
    # option's INDEX in `detail` (the popup is teleported, so a slot $emit can't reach the select); the
    # wrap's handler maps the index back to the temperament key. Here we drive that wrap event directly.
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")                                  # the temperament chooser is presets-gated
    await user.should_see(marker="preset:temperament")
    wrap = set(user.find(marker="preset:temperament").elements)    # the cell wrap holds the opthover listener
    idx = list(presets.temperament_options()).index("5:Porcupine")  # the slot dispatches the option index
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})  # hover porcupine (default is meantone)
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")  # the mapping it'd load rings
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})   # leave the option
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")


async def test_hovering_a_tuning_scheme_option_previews_reselecting(user: User) -> None:
    # the tuning-scheme chooser gets the same option-hover preview as the temperament chooser, through
    # the shared _arm_option_hover hook: hovering a scheme rings the cells reselecting it would move —
    # here the damage weights, which the weight slope (minimax-U → minimax-S) re-derives — and leaving
    # clears them. Amber only: a re-solve moves values without reflowing the grid.
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")                                   # the tuning chooser is presets-gated
    _toggle(user, "weighting")                                 # >1 scheme variant (S/U/C) + the weight row
    await user.should_see(marker="preset:tuning")
    wrap = set(user.find(marker="preset:tuning").elements)
    idx = list(presets.tuning_scheme_options(False, False, True)).index("minimax-S")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})  # hover the simplicity variant
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")   # a re-weighted target rings amber
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})   # leave the option
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


async def test_hovering_a_prescaler_option_previews_reselecting(user: User) -> None:
    # the predefined-prescalers chooser previews its options too: under a non-unity weight slope the
    # prescaler defines the complexity that the weights derive from, so hovering a different prescaler
    # rings the re-weighted targets. (Under unity weight the prescaler doesn't reach the weights and
    # the prescaling tile is hidden, so a non-unity slope is set first.)
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")
    _toggle(user, "weighting")
    _toggle(user, "alt. complexity")                           # >1 prescaler option
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # make the prescaler reach the weights
    await user.should_see(marker="preset:prescaler")
    wrap = set(user.find(marker="preset:prescaler").elements)
    idx = list(presets.prescaler_options(True)).index("identity")  # hover a prescaler other than log-prime
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


async def test_hovering_a_complexity_option_previews_reselecting(user: User) -> None:
    # the predefined-complexities chooser (box 𝒄) — a control_select, not a preset — previews its
    # options through the same hook: under a non-unity slope the complexity measure drives the weights,
    # so hovering a different one rings the re-weighted targets. The hovered DISPLAY name maps back to
    # its internal key in _candidate_apply, mirroring the on-select commit.
    await user.open("/")
    _toggle(user, "presets")
    _toggle(user, "weighting")
    _toggle(user, "alt. complexity")
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # make the complexity reach the weights
    await user.should_see(marker="control:complexity")
    wrap = set(user.find(marker="control:complexity").elements)
    idx = list(service.COMPLEXITY_DISPLAYS).index("sopfr")     # hover a measure other than the live lp
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


async def test_hovering_a_weight_slope_option_previews_reselecting(user: User) -> None:
    # the box-𝒘 weight-slope chooser previews its options: the slope is exactly what scales each
    # target's weight, so hovering a different slope rings the re-weighted targets.
    await user.open("/")
    _toggle(user, "weighting")                                # the slope chooser shows with weighting
    await user.should_see(marker="control:slope")
    wrap = set(user.find(marker="control:slope").elements)
    idx = list(service.WEIGHT_SLOPES).index("simplicity-weight")  # default is unity-weight
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


async def test_hovering_a_locked_weight_slope_shows_no_preview(user: User) -> None:
    # all-interval locks the weight slope (simplicity-weighted by construction), greying the chooser. A
    # disabled / locked chooser must not preview — on_chooser_hover skips it on `sel.enabled`, so
    # hovering its options rings nothing even though the slope branch would otherwise re-weight.
    await user.open("/")
    _toggle(user, "weighting")
    _toggle(user, "all-interval")                                 # reveal the all-interval checkbox
    _cell_child(user, "control:all_interval").set_value(True)     # all-interval -> the slope chooser locks
    await user.should_see(marker="control:slope")
    wrap = set(user.find(marker="control:slope").elements)
    idx = list(service.WEIGHT_SLOPES).index("complexity-weight")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")  # locked: no preview


async def test_hovering_the_form_canonical_option_previews_canonicalizing(user: User) -> None:
    # the mapping/comma-basis <choose form> control previews canonicalizing IN PLACE: hovering
    # "canonical" rings the mapping cells it would re-store (the default mapping is not canonical), and
    # leaving clears them. Amber only — the cells change value where they sit, no reflow.
    await user.open("/")
    _toggle(user, "form controls")
    await user.should_see(marker="formchooser:mapping")
    wrap = set(user.find(marker="formchooser:mapping").elements)
    # options are {"": "choose form", "canonical": "canonical"}, so index 1 is the canonical entry
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": 1})
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:2")  # a re-stored mapping cell rings
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:2")


def test_option_hover_delegation_cancels_the_settle_timer_on_pointerdown() -> None:
    # the dropdown option-hover preview DEBOUNCES: hovering an option arms a 90 ms setTimeout that then
    # fires `opthover` (a server re-solve + ring). If that timer were left to fire AFTER the user clicks
    # an option, it would re-ring the change preview once the popup has already closed and the commit's
    # render + popup-hide have cleared the rings — a preview highlight STRANDED on screen (the reported
    # "highlight doesn't go away after the action" bug, in its dropdown form). The fix cancels the pending
    # timer on pointerdown (the commit press), rather than leaning on a popup-removal `mouseout` to do it
    # (a removed element under the cursor does not fire mouseout reliably across browsers). Guard the
    # wiring structurally: a capture-phase pointerdown listener that clearTimeout(timer)s.
    js = "".join(web_app._OPTION_HOVER_DELEGATION.split())  # whitespace-insensitive
    assert "addEventListener('pointerdown'" in js, "the delegation must cancel its timer on a press"
    assert "clearTimeout(timer);" in js and ";},true)" in js, \
        "pointerdown must clearTimeout(timer) in the capture phase"
    # ...and the SAME press must reset the (chooser, option) dedupe. A popup that closes under the
    # pointer fires no mouseout for the hovered option, so without this reset lastCid/lastIdx would
    # survive into the NEXT popup session and swallow a re-hover of the same option — reopening a
    # small dropdown and pointing at the option you want would preview nothing, reading as a dead
    # chooser (the real-browser bug the in-process opthover tests can't see).
    assert "lastCid=null;lastIdx=null;},true)" in js, \
        "pointerdown must reset the dedupe so each popup session's first hover fires"


async def test_hovering_a_target_family_reddens_the_rows_it_drops(user: User) -> None:
    # the TILT/OLD family chooser gets the same option-hover preview through the shared _arm_option_hover
    # hook (it rides the (num, sel) target tuple). Hovering a family previews switching to it: the target
    # set re-derives in place, so the rows the hovered family DROPS ring red and survivors that move ring
    # amber — no reflow (the chooser keeps its value, like the other amber-only choosers). From the
    # 5-limit default (6-TILT) hovering OLD reddens the targets OLD doesn't include; leaving clears it.
    from rtt.app import presets
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")
    wrap = set(user.find(marker="preset:target").elements)         # the cell wrap holds the opthover listener
    idx = list(presets.TARGET_SETS).index("OLD")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # hover OLD over the live TILT
    assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:1")    # a dropped target row → red
    await user.should_see(marker="retune:target:1")                          # ...still on screen (not reflowed)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})    # leave the option
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:1")


async def test_hovering_a_same_count_target_family_rings_the_moved_rows_amber(user: User) -> None:
    # when the hovered family keeps the SAME number of targets but different intervals (no net rows
    # dropped), the preview rings the rows whose value moves amber, in place, and keeps the chooser's own
    # value steady (no reflow, like the other amber-only choosers). From a committed 5-TILT, hovering
    # 5-OLD (both 7 targets, different intervals) rings the moved rows amber; leaving clears them.
    from rtt.app import presets
    await _enable(user, "presets")
    await user.should_see(marker="preset:target")
    num, _sel = _target_preset(user)
    num.set_value("5")                                                       # commit 5-TILT (default is 6)
    await user.should_see(marker="retune:target:1")
    wrap = set(user.find(marker="preset:target").elements)
    idx = list(presets.TARGET_SETS).index("OLD")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # hover 5-OLD (same count)
    assert "rtt-preview-change" in _wrap_classes(user, "retune:target:1")    # a moved row rings amber
    assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:1")  # nothing net-dropped → no red
    _num, sel = _target_preset(user)
    assert sel.value == "TILT"                                               # chooser held steady, not flipped
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})    # leave the option
    assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:1")


async def test_hovering_the_generator_minus_previews_the_dual_rank_change(user: User) -> None:
    # gen_minus drops the LAST generator — a rank change, so it previews the comma↔mapping DUAL: the
    # dropped generator row reds (held in place, no reflow of the mapping band), every comma
    # recombines (amber), and the born comma ghosts green to the right of the basis. Leaving clears
    # all three. (The bus-stub twin of the per-row map_minus; both route through the dual preview.)
    await user.open("/")
    btn = set(user.find(marker="gen_minus").elements)               # drop the last generator (row 1)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-remove" in _wrap_classes(user, "tuning:gen:1")      # the dropped generator's row → red
    assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:0")
    await user.should_see(marker="tuning:gen:1")                           # ...still on screen (no reflow of the row)
    assert "rtt-preview-change" in _wrap_classes(user, "cell:comma:0:0")    # the surviving comma recombines → amber
    await user.should_see(marker="cell:comma:0:1")                         # the born comma ghosts in...
    assert "rtt-pending" in _wrap_classes(user, "cell:comma:0:1")          # ...green
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:gen:1")  # all cleared on mouse-out
    await user.should_not_see(marker="cell:comma:0:1")


async def test_hovering_a_column_minus_reddens_the_removed_column(user: User) -> None:
    # the user's case: hovering a column − (here the domain − that drops the top prime) reddens the
    # column it removes — the prime label and its cells go away on the click — while the cells whose
    # value the re-solve recomputes ring amber. Confirms the preview reaches the column controls, not
    # just the generator rows, and that what DISAPPEARS lights up (a plain changed-cell diff couldn't).
    await user.open("/")
    btn = set(user.find(marker="minus").elements)                  # drop the highest prime (5)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-remove" in _wrap_classes(user, "prime:2")          # the dropped prime → red
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:prime:1")   # a surviving prime's tuning → amber
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "prime:2")


async def test_clicking_a_per_element_domain_minus_removes_that_element(user: User) -> None:
    # the bug: with the nonstandard-domain box on the domain − had vanished — no element was
    # removable. Now every element carries its own −. Clicking the one on the MIDDLE element (the 3
    # of 2.3.5) drops it, shrinking the domain to 2.5 (d: 3 → 2) — proving the per-element − is not
    # confined to the last element. End-to-end: the − glyph → _build_element_minus →
    # editor.remove_domain_element, then a live re-render.
    await _enable(user, "nonstandard domain")
    await user.should_see(marker="element_minus:0")          # a − on EVERY element now (was none on any)
    await user.should_see(marker="element_minus:2")
    await user.should_see(marker="prime:2")                  # 2.3.5: three domain elements
    _click_glyph(user, "element_minus:1")                    # drop the middle element (the 3)
    await user.should_not_see(marker="prime:2")              # d fell to 2 — the third column is gone
    await user.should_not_see(marker="element_minus:2")      # ...and so is its −


async def test_clicking_the_mapping_plus_opens_a_green_draft_row_to_fill_in(user: User) -> None:
    # the mapping + (add a generator) mirrors the interval-list +'s: instead of silently un-tempering
    # a comma, it opens a blank GREEN draft ROW the user types a new generator into, committing once
    # the row appended to M is a proper temperament. (Like a draft column, the cursor also drops into
    # its first matrix cell — the same add_interval focus path; there is no hover-preview, as the
    # column +'s have none.)
    await user.open("/")  # meantone, r=2 n=1
    await user.should_not_see(marker="cell:mapping:2:0")          # no draft row yet
    _click_glyph(user, "gen_plus")                               # open the draft row
    await user.should_see(marker="cell:mapping:2:0")
    await user.should_see(marker="gen:pending")                  # a "?" generator-ratio on the spine
    assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes  # the draft row reads green
    assert _cell_child(user, "cell:mapping:2:0").value == ""                # blank until filled
    # type a new independent generator (prime 5, held just) across the draft row, then commit
    for p, v in zip(range(3), ("0", "0", "1")):
        _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
    _commit(user, "cell:mapping:2:2")                            # blur commits the completed row
    await user.should_see(marker="cell:mapping:2:0")             # a real committed 3rd generator now
    assert "rtt-pending" not in _cell_child(user, "cell:mapping:2:0")._classes  # committed: no longer green
    assert [_cell_child(user, f"cell:mapping:2:{p}").value for p in range(3)] == ["0", "0", "1"]


async def test_hovering_a_temperament_of_a_different_dimensionality_reflows_the_grid(user: User) -> None:
    # the hover REFLOWS the would-be grid, so a temperament with a different d shows its new columns —
    # not just rings on cells that already exist. From the 5-limit default, hovering a 7-limit
    # temperament makes the prime-7 column appear; leaving reverts to the 5-limit grid.
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")
    await user.should_see(marker="preset:temperament")
    await user.should_not_see(marker="prime:3")              # 5-limit default (d=3): no prime-7 column
    wrap = set(user.find(marker="preset:temperament").elements)
    seven = next(k for k in presets.temperament_options() if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS)
    idx = list(presets.temperament_options()).index(seven)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})  # hover a 7-limit temperament
    await user.should_see(marker="prime:3")                  # reflowed: the would-be grid's new prime-7 column
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})   # leave
    await user.should_not_see(marker="prime:3")              # reverted to the 5-limit grid


async def test_hovering_a_lower_limit_temperament_keeps_the_dropped_column_red(user: User) -> None:
    # the counterpart to the reflow test: a hover that DROPS a prime/comma/generator must NOT reflow the
    # doomed cells away (that would just delete them mid-preview). Instead the grid holds its current
    # shape so the column/row the hover would remove stays on screen and turns RED — exactly what the
    # +/- remove preview does, and what the user asked for: see what a hover deletes — while the
    # surviving cells whose value changes ring amber. From a committed 7-limit rank-2 temperament,
    # hovering a 5-limit one reddens the dropped prime-7 column and leaves it on screen; leaving clears it.
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")
    await user.should_see(marker="preset:temperament")
    seven = next(k for k in presets.temperament_options()
                 if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS
                 and len(presets.TEMPERAMENT_COMMAS[k]) == 2)   # rank 2 over d=4 (n=2): a clean limit drop
    _cell_child(user, "preset:temperament").set_value(seven)    # commit it — the prime-7 column appears
    await user.should_see(marker="prime:3")
    wrap = set(user.find(marker="preset:temperament").elements)
    five = next(k for k in presets.temperament_options()
                if k.startswith("5:") and k in presets.TEMPERAMENT_COMMAS)
    idx = list(presets.temperament_options()).index(five)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # hover a 5-limit temperament
    assert "rtt-preview-remove" in _wrap_classes(user, "prime:3")   # the dropped prime-7 column → red
    await user.should_see(marker="prime:3")                          # ...still on screen (NOT reflowed away)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})    # leave the option
    assert "rtt-preview-remove" not in _wrap_classes(user, "prime:3")  # cleared on mouse-out


async def test_hovering_the_replace_diminuator_checkbox_previews_its_reweighting(user: User) -> None:
    # the box-𝐋 "replace diminuator" checkbox swaps the complexity's size factor (lp ↔ lils). Like the
    # +/- buttons it previews on hover: entering it rings the cells its click would re-weight, leaving
    # clears them, and the click still commits on its own. Under a simplicity-weighted scheme the
    # complexity drives the weights, so the change ripples to the weight/complexity columns.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()       # reveal the weighting region (slope chooser)
    user.find(kind=ui.checkbox, content="alt. complexity").click()  # ...and the size-factor checkbox
    _cell_child(user, "control:slope").set_value("simplicity-weight")  # complexity now drives the weights
    await user.should_see(marker="control:diminuator")
    btn = set(user.find(marker="control:diminuator").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:2")   # the re-weighted column rings amber
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:2")  # cleared on mouse-out


async def test_hovering_the_all_interval_checkbox_previews_collapsing_to_the_primes(user: User) -> None:
    # the target-controls "all-interval" checkbox collapses the finite target list to the primes, so its
    # hover is genuinely structural: the dropped target ratios still on screen ring RED (what the click
    # removes) and the re-weighted survivors ring amber. Leaving clears both, and the click still commits.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()     # the weight columns + the entry's parent
    user.find(kind=ui.checkbox, content="all-interval").click()  # reveal the target-controls checkbox
    await user.should_see(marker="control:all_interval")
    btn = set(user.find(marker="control:all_interval").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-remove" in _wrap_classes(user, "target:2")     # a dropped non-prime target → red
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")  # a survivor's re-weight → amber
    await user.should_see(marker="target:2")                          # ...still on screen (no reflow)
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "target:2")
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


async def test_hovering_undo_rings_what_reverting_the_last_edit_changes(user: User) -> None:
    # the undo button reverts the last edit; hovering it previews that revert — ringing exactly the
    # cells one undo step would move — without committing. Make an edit so there is something to undo.
    # (reverting the mapping edit also retunes back to the old optimum; tuning:target:1 moves either way)
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")          # edit the mapping (an undoable step)
    _commit(user, "cell:mapping:1:2")                            # commit on blur (typing only previews now)
    await user.should_see(marker="tuning:target:1")
    btn = set(user.find(marker="undo").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")   # reverting the edit rings it
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")  # cleared on mouse-out


async def test_hovering_redo_rings_what_redoing_the_undone_edit_changes(user: User) -> None:
    # the redo button re-applies the last undone edit; hovering it previews that, ringing the cells redo
    # would move, without committing. Edit then undo, so a redo step is waiting.
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")          # edit (an undoable step)
    _commit(user, "cell:mapping:1:2")                            # commit on blur (typing only previews now)
    user.find(marker="undo").click()                             # undo it -> a redo step is now available
    await user.should_see(marker="tuning:target:1")
    btn = set(user.find(marker="redo").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")   # redoing re-applies the edit
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")  # cleared on mouse-out


async def test_hovering_reset_rings_everything_snapping_back_to_defaults(user: User) -> None:
    # the reset button restores the whole document to the as-shipped defaults; hovering it previews that,
    # ringing every cell the snap-back moves, without committing. An edit makes reset have something to do.
    await user.open("/")
    _cell_child(user, "cell:mapping:1:2").set_value("7")          # diverge from the defaults
    _commit(user, "cell:mapping:1:2")                            # commit on blur (typing only previews now)
    await user.should_see(marker="tuning:target:1")
    btn = set(user.find(marker="reset").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")   # the reverted edit rings
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")  # cleared on mouse-out


async def test_a_disabled_history_button_shows_no_preview(user: User) -> None:
    # at the history root nothing has been edited, so undo is disabled (greyed) — hovering it must show no
    # preview, matching its inert state. (reset is likewise disabled with no changes, redo at the tip.)
    await user.open("/")
    btn = set(user.find(marker="undo").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:4")  # nothing rings...
    assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:target:4")  # ...neither colour
    UserInteraction(user, btn, None).trigger("mouseleave")


# --- the preview clears once the change is APPLIED, not only on mouse-out ---
# The hover/edit-preview tests above all clear via mouse-out (mouseleave / opthover -1 / blur). These
# cover the other way a gesture ends: the user COMMITS (Enter, an unrelated render, a chooser select).
# A regression here is exactly the reported bug — "preview highlighting persists after the change has
# been applied." The rings are a pure function of (document, active gesture), recomputed by every
# render/paint, and commits structurally end the hover-family gestures (render ends any such gesture
# it didn't initiate) — so a stranded ring is unreachable by construction; these tests lock that.

async def test_relabeling_a_domain_element_clears_the_edit_preview_on_commit(user: User) -> None:
    # a chapter-9 domain basis element commits its relabel on blur (Enter routes through blur too), and
    # the edit-preview must end there: the moved cells must not stay ringed after the relabel is applied.
    # Relabel element 1 of the (2 3 5) basis to 7: just:prime:1 (its prime-column just value) moves and
    # survives. The live ring shows while typing, then clears the moment the relabel commits.
    await user.open("/")
    _toggle(user, "nonstandard domain")          # makes the domain basis elements editable (prime:i inputs)
    await user.should_see(marker="prime:1")
    inp = _cell_child(user, "prime:1")
    UserInteraction(user, {inp}, None).trigger("focus")   # snapshot the edit-preview baseline
    inp.set_value("7")                                    # a valid independent relabel -> the live preview rings
    assert "rtt-preview-change" in _wrap_classes(user, "just:prime:1")     # the moved cell rings while editing
    UserInteraction(user, {inp}, None).trigger("blur")                     # APPLY (Enter does this via blur)
    await user.should_see(marker="just:prime:1")          # the moved cell survived the relabel (still on screen)
    assert _cell_child(user, "prime:1").value == "7"       # the relabel committed
    assert "rtt-preview-change" not in _wrap_classes(user, "just:prime:1")  # ...and the ring cleared on commit


async def test_relabeling_a_domain_element_across_a_kind_change_clears_on_blur(user: User) -> None:
    # the hard case the same-kind test above misses: a relabel that crosses the element's KIND — an
    # integer prime (elementcell) → a fraction (elementratio), e.g. 3 → 9/7 — makes the commit's render
    # REBUILD the prime:1 cell. The rebuilt input is a new element, so the old input's blur listener
    # (which ends the edit-preview) is destroyed before it fires, and render re-rings the moved cell
    # against the stale focus baseline. render now detects that the focused cell is being rebuilt and
    # ends the preview itself, so the amber clears on commit instead of lingering until a later blur lands
    # on another cell. (basis (2 3 5); 9/7 = 3²/7 is independent of {2,5}; just:prime:1 moves and survives.)
    # (Enter commits via blur too — see make_cell — so blur is the one commit gesture to exercise.)
    await user.open("/")
    _toggle(user, "nonstandard domain")
    await user.should_see(marker="prime:1")
    inp = _cell_child(user, "prime:1")
    UserInteraction(user, {inp}, None).trigger("focus")
    inp.set_value("9/7")                                  # int → fraction: a kind change that rebuilds the cell
    assert "rtt-preview-change" in _wrap_classes(user, "just:prime:1")    # the live preview rings while editing
    UserInteraction(user, {inp}, None).trigger("blur")    # APPLY (the rebuild destroys the old input)
    await user.should_see(marker="just:prime:1")          # the moved cell survived the rebuild (still on screen)
    assert _ratio_value(user, "prime:1") == "9/7"     # the relabel committed
    assert "rtt-preview-change" not in _wrap_classes(user, "just:prime:1"), \
        "the kind-change relabel left the amber ring stuck after commit"


async def test_committing_a_ratio_clears_the_edit_preview(user: User) -> None:
    # the editable quantities-row ratios (comma / target / held / interest) commit on blur (Enter routes
    # through blur too), and the edit-preview must end there. Retype the syntonic comma 80/81 as the
    # chromatic semitone 25/24 = (-3 -1 2) and commit: the comma's interval-vector cells move and survive,
    # and must not stay ringed once the change has been applied.
    await user.open("/")
    await user.should_see(marker="comma:0")
    inp = _cell_child(user, "comma:0")
    UserInteraction(user, {inp}, None).trigger("focus")
    inp.set_value("25/24")
    UserInteraction(user, {inp}, None).trigger("blur")                     # APPLY (Enter does this via blur)
    await user.should_see(marker="cell:comma:0:0")
    assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]  # committed
    for p in range(3):                                     # the surviving moved vector cells carry no ring
        assert "rtt-preview-change" not in _wrap_classes(user, f"cell:comma:{p}:0")


async def test_an_unrelated_render_does_not_strand_a_control_hovers_red_ring(user: User) -> None:
    # a − hover's preview must not outlive a foreign render. gen_minus' rank-removal preview is
    # view-state threaded into the build (rank_remove), not a gesture — but render() clears it on any
    # render that isn't the hover's own (a Show toggle, a commit), the view-state twin of ending a
    # foreign hover gesture. So the red is stripped, never orphaned, even if the reflow removed the
    # button from under the cursor. Hover the generator − (reddens the doomed generator), toggle
    # "counts", and the red is gone from the surviving cell — and stays gone after mouse-out.
    await user.open("/")
    btn = set(user.find(marker="gen_minus").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")
    assert "rtt-preview-remove" in _wrap_classes(user, "tuning:gen:1")     # armed: the doomed generator → red
    _toggle(user, "counts")                                                # an UNRELATED render (doc unchanged)
    await user.should_see(marker="tuning:gen:1")                          # the reddened cell survives the render
    assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:gen:1")  # ...its red was stripped, not orphaned
    UserInteraction(user, btn, None).trigger("mouseleave")
    assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:gen:1")  # still clear after mouse-out


async def test_selecting_a_temperament_clears_a_prior_shrink_hovers_red(user: User) -> None:
    # a shrinking-temperament hover reddens the column it would drop, in place (no reflow). Committing a
    # DIFFERENT temperament that KEEPS that column on screen must clear the red — the commit's render
    # reconciles it away rather than leaving it stranded. Commit a 7-limit rank-2 temperament so prime:3
    # (the prime-7 column) exists, hover a 5-limit one (reddens prime:3), then select another 7-limit
    # that keeps prime:3: the red is gone once the new temperament is applied.
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")
    await user.should_see(marker="preset:temperament")
    sevens = [k for k in presets.temperament_options()
              if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS
              and len(presets.TEMPERAMENT_COMMAS[k]) == 2]   # rank 2 over d=4: a clean limit-drop hover
    _cell_child(user, "preset:temperament").set_value(sevens[0])   # commit it — the prime-7 column appears
    await user.should_see(marker="prime:3")
    wrap = set(user.find(marker="preset:temperament").elements)
    five = next(k for k in presets.temperament_options()
                if k.startswith("5:") and k in presets.TEMPERAMENT_COMMAS)
    idx = list(presets.temperament_options()).index(five)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # hover a 5-limit (shrink)
    assert "rtt-preview-remove" in _wrap_classes(user, "prime:3")            # armed: the dropped prime-7 column → red
    other7 = next(k for k in sevens if k != sevens[0])
    _cell_child(user, "preset:temperament").set_value(other7)               # APPLY a different 7-limit (keeps prime:3)
    await user.should_see(marker="prime:3")                                  # the column survived the commit
    assert "rtt-preview-remove" not in _wrap_classes(user, "prime:3")        # ...and the stale red was cleared


async def test_completing_a_held_interval_draft_clears_the_rings_without_blur(user: User) -> None:
    # the reported bug, in its submit-a-held-interval form: a draft column COMMITS the moment its
    # typed vector completes — no blur fires (the focused vector cell keeps its id across the
    # commit), so nothing external ends the edit gesture. The change is APPLIED, so its rings must
    # go away immediately: the commit rebases the gesture on the new grid instead of leaving the
    # commit's render ringing everything the new column moved (stranded until a click elsewhere).
    # Completing the vector via a wheel notch is the commit path with no blur anywhere near it.
    await user.open("/")
    _toggle(user, "optimization")                    # show the held column
    _click_glyph(user, "held_plus")                  # start a blank green draft
    await user.should_see(marker="cell:held:0:0")
    inp = _cell_child(user, "cell:held:0:0")
    UserInteraction(user, {inp}, None).trigger("focus")          # the edit gesture rides the vector cell
    _cell_child(user, "cell:held:1:0").set_value("1")            # fill the rest of 3/2 = (-1 1 0)
    _cell_child(user, "cell:held:2:0").set_value("0")
    wrap = set(user.find(marker="cell:held:0:0").elements)
    UserInteraction(user, wrap, None).trigger("wheel", {"deltaY": 100})  # one notch down: blank → -1 → COMMITS
    await user.should_see(marker="held:0")                       # the draft materialized (no blur fired)
    assert _ratio_value(user, "held:0") == "3/2"
    for p in range(3):                                           # the committed column carries no ring
        assert "rtt-preview-change" not in _wrap_classes(user, f"cell:held:{p}:0"), \
            "the held interval commit left its rings stranded (no blur ever fires on this path)"
    assert "rtt-preview-change" not in _wrap_classes(user, "held:0")


async def test_clicking_reset_after_hovering_it_clears_the_preview(user: User) -> None:
    # the reported bug, in its reset form: hovering the reset button rings the cells restoring the
    # defaults would move; clicking it APPLIES — and the mouse never leaves the button, so the clear
    # cannot ride a mouseleave. The commit itself (act ends the hover gesture; its render repaints
    # from the empty gesture) must strip the rings.
    await user.open("/")
    _cell_child(user, "tuning:gen:1").set_value("700.000")   # an edit, so reset has something to restore
    await user.should_see(marker="reset")
    btn = set(user.find(marker="reset").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")   # hover: the hand-tuned cell would move back
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:gen:1")
    user.find(marker="reset").click()                        # APPLY (mouse still over the button)
    await user.should_see(marker="tuning:gen:1")
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:gen:1")   # cleared on the commit
    assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:gen:1")


async def test_selecting_an_established_projection_clears_the_chooser_preview(user: User) -> None:
    # the reported bug, in its established-projection form: hovering a projection option rings the
    # cells re-forming P/G to it would move; SELECTING it applies the change, and the rings must not
    # survive the commit (no opthover -1 need ever arrive — the commit's render ends the gesture).
    await user.open("/")
    _toggle(user, "presets")
    user.find(kind=ui.checkbox, content="projection").click()
    await user.should_see(marker="preset:projection")
    sel = _cell_child(user, "preset:projection")
    wrap = set(user.find(marker="preset:projection").elements)
    idx = list(sel.options).index("1/3-comma")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # hover: the genmap would re-solve
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:gen:1")
    sel.set_value("1/3-comma")                                               # APPLY (commit via the select)
    await user.should_see(marker="preset:projection")
    assert _cell_child(user, "tuning:gen:1").value == "694.786"              # the pick committed
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:gen:1"), \
        "the projection pick left its hover rings stranded after the commit"


async def test_a_stale_opthover_after_popup_hide_is_dropped(user: User) -> None:
    # the documented client race: the option-hover delegation debounces 90 ms, so a settle-timer
    # armed just before a click can fire AFTER the popup closed — re-arming a preview with nothing
    # left to clear it. The server now gates arms on the popup's state: an opthover landing after
    # this chooser's popup-hide (and before a new popup-show) is a stale fire and is dropped. A
    # fresh popup-show reopens the gate. (Choosers that never report popup state — these tests
    # elsewhere — stay allowed: absent means untracked, not closed.)
    from rtt.app import presets
    await user.open("/")
    _toggle(user, "presets")
    _toggle(user, "weighting")                                 # >1 tuning-scheme option (S/U/C)
    await user.should_see(marker="preset:tuning")
    sel = _cell_child(user, "preset:tuning")
    wrap = set(user.find(marker="preset:tuning").elements)
    idx = list(presets.tuning_scheme_options(False, False, True)).index("minimax-S")
    # NiceGUI stores .on("popup-show"/"popup-hide") listeners under camelCased types (its own
    # Select registers the same pair internally), and trigger() matches the stored type exactly.
    UserInteraction(user, {sel}, None).trigger("popupShow")                  # the popup opens
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # a real hover previews
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
    UserInteraction(user, {sel}, None).trigger("popupHide")                  # the popup closed (a pick/Escape)
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")  # the close ended the preview
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})   # the stale settle-timer fire
    assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1"), \
        "a stale opthover after popup-hide re-armed the preview (the stranded-ring race)"
    UserInteraction(user, {sel}, None).trigger("popupShow")                  # a genuine reopen
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")    # ...previews again


async def test_a_control_hover_preserves_an_open_draft(user: User) -> None:
    # a +/- hover previews by applying its op to an editor snapshot and reverting — and that revert
    # must carry the editor's transients: the pending draft column lives OUTSIDE the undoable
    # document, so a restore that drops it silently destroys the user's half-built draft on a mere
    # hover. Open a comma draft, hover the prime − (its hypothetical shrink would also doom the
    # draft — it reds, fine), leave, then force an unrelated render: the green draft must survive.
    await user.open("/")
    _click_glyph(user, "comma_plus")                 # start a blank green comma draft
    await user.should_see(marker="comma:pending")
    UserInteraction(user, {_cell_child(user, "comma:pending")}, None).trigger("blur")  # leave the draft cell
    btn = set(user.find(marker="minus").elements)
    UserInteraction(user, btn, None).trigger("mouseenter")    # the hover's hypothetical runs + reverts
    UserInteraction(user, btn, None).trigger("mouseleave")
    _toggle(user, "counts")                                   # any unrelated render re-reads editor state
    await user.should_see(marker="comma:pending")             # the draft survived the hover
    assert "rtt-pending" in _wrap_classes(user, "comma:pending")   # ...still the green draft head
    await user.should_see(marker="cell:comma:0:1")            # its draft vector column survived too


async def test_gensign_hover_hands_the_wheel_preview_back(user: User) -> None:
    # the clickable sign lives INSIDE the generator-tuning cell, so pointing at it stacks two
    # gestures: the cell's wheel hover (already armed) and the sign's flip hover. The sign hover
    # takes over while it lasts, and leaving it hands the wheel gesture back — so a notch after the
    # sign detour still rings the ripple against the wheel's baseline.
    # (generator 0, whose notch test_wheeling_a_generator_tuning_rings_... proves moves
    # retune:target:0; its flip preview rings cell:mapping:0:0, the 1 → −1 entry)
    await user.open("/")
    cell = set(user.find(marker="tuning:gen:0").elements)
    UserInteraction(user, cell, None).trigger("mouseenter")        # arm the wheel gesture
    sign = set(user.find(marker="gensign:0").elements)
    UserInteraction(user, sign, None).trigger("mouseenter")        # the in-cell sign hover takes over
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")  # the flip preview rings
    UserInteraction(user, sign, None).trigger("mouseleave")        # ...and hands the wheel back
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")
    UserInteraction(user, cell, None).trigger("wheel.prevent", {"deltaY": -1})  # a notch: nudge + render
    await user.should_see(marker="retune:target:0")
    assert "rtt-preview-change" in _wrap_classes(user, "retune:target:0"), \
        "the sign-hover detour lost the wheel gesture — the notch rang nothing"
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:gen:0")   # the scrolled cell never rings
    UserInteraction(user, cell, None).trigger("mouseleave")
    assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:0")


async def test_hovering_a_nonstandard_approach_option_previews_setting_it(user: User) -> None:
    # the chapter-9 nonstandard-domain-approach radio appears once the domain carries a nonprime element.
    # Hovering one of its square options previews reading the temperament that way — ringing the cells the
    # re-analysis moves — without committing the choice. Each option is its own hover target (mouseenter),
    # the whole radio its mouse-out; here we drive those events directly. The tuning is scheme-driven
    # (optimization always invisibly on), so the displayed tuning re-solves under the hovered approach.
    await user.open("/")
    _toggle(user, "plain text values")                            # reveal the editable mapping EBK dual
    _cell_child(user, "ptext:mapping:primes").set_value("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # a nonprime domain
    await user.should_see(marker="approach")                      # ...so the approach radio shows
    prime_opt = set(user.find(marker="approach-prime-based").elements)
    UserInteraction(user, prime_opt, None).trigger("mouseenter")                  # hover "prime-based"
    assert "rtt-preview-change" in _wrap_classes(user, "tuning:prime:0")   # the prime-based retune rings
    UserInteraction(user, set(user.find(marker="approach").elements), None).trigger("mouseleave")  # leave
    assert "rtt-preview-change" not in _wrap_classes(user, "tuning:prime:0")  # cleared on mouse-out


# --- tier 4: robustness — render-pipeline guards & invalid-input handlers (audit findings) ---
#
# These exercise the page's *failure* paths, which the in-process User sim can drive directly. Note
# the render tests run the app from a freshly re-imported module (render_main.py evicts rtt.*), so the
# live page's module is sys.modules["rtt.app.app"], NOT the test-module's top-level `web_app` alias —
# tests that reach into the running app's internals must use _live().

def _live():
    """The module object the live page actually runs from (render_main re-imports rtt.app.app per
    fixture, so the test's top-level `web_app` is a stale earlier copy)."""
    return sys.modules["rtt.app.app"]


async def test_a_mid_render_exception_restores_the_build_guard_so_handlers_stay_live(
        user: User, monkeypatch) -> None:
    # render() sets building[0]=True for its declarative pass, and EVERY commit/preview handler guards
    # on `if building[0]: return`. Without a finally restoring the flag, one mid-render exception leaves
    # building[0] stuck True and silently bricks every handler until an unguarded render heals it. Force
    # a real mid-render crash (a one-shot boom inside the cell loop, reached via a fold toggle whose
    # handler has no building[0] guard), then confirm a guarded mapping commit STILL lands — proof the
    # finally restored building[0] to False.
    await user.open("/")
    live = _live()
    caught = []
    # swallow + record the render exception so it doesn't ERROR-log (which would fail the user fixture)
    monkeypatch.setattr(core.app, "handle_exception", lambda e: caught.append(e))
    orig = live._Reconciler.update_cell
    fired = {"n": 0}

    def boom(self, cb):
        if fired["n"] == 0:
            fired["n"] = 1
            raise RuntimeError("mid-render boom")
        return orig(self, cb)

    monkeypatch.setattr(live._Reconciler, "update_cell", boom)
    user.find(marker="toggle:row:tuning").click()   # a fold toggle re-renders; render raises once
    assert caught and isinstance(caught[0], RuntimeError)   # the render really did blow up mid-pass
    monkeypatch.setattr(live._Reconciler, "update_cell", orig)   # a clean renderer again
    # the page must still be live: a guarded mapping commit reaches the document and persists
    _cell_child(user, "cell:mapping:1:2").set_value("7")   # the fifth's prime-5 entry: 4 -> 7
    _commit(user, "cell:mapping:1:2")
    assert "7" in live._MEMORY_STORE[live._STORE_KEY]["mapping_ebk"]   # NOT swallowed by a stuck guard


async def test_a_corrupt_persisted_field_keeps_the_saved_document_and_warns(
        user: User, caplog) -> None:
    # index() falls back to defaults when editor.load(stored) raises; render() must NOT then overwrite
    # the stored blob with those defaults — that would silently wipe every other still-valid field the
    # user had. Build a real doc, corrupt ONE field, refresh: the stored bytes survive and a notice is
    # surfaced (rather than a silent reset). The app deliberately ERROR-logs the load failure (so the
    # reset is visible in the server log); that log is EXPECTED here, so suppress just that logger for
    # the refresh rather than letting the user fixture treat it as an unexpected error.
    await user.open("/")
    live = _live()
    _cell_child(user, "cell:mapping:1:2").set_value("5")   # the fifth's prime-5 entry: 4 -> 5
    _commit(user, "cell:mapping:1:2")
    stored = live._MEMORY_STORE[live._STORE_KEY]
    assert "5" in stored["mapping_ebk"]   # the user's edit persisted
    corrupt = copy.deepcopy(stored)
    corrupt["held_vectors"] = [["x", 0, 0]]   # one malformed field -> load() raises on the int() parse
    live._MEMORY_STORE[live._STORE_KEY] = corrupt
    with caplog.at_level(logging.CRITICAL, logger="rtt.app.app"):
        await user.open("/")   # refresh: load fails -> defaults shown, but the stored blob must be kept
    after = live._MEMORY_STORE[live._STORE_KEY]
    assert "5" in after["mapping_ebk"]   # the user's bytes are NOT wiped to defaults
    assert after["held_vectors"] == [["x", 0, 0]]   # the exact stored blob is preserved for recovery
    assert user.notify.contains("Your saved data is kept")   # ...and the silent reset is surfaced


async def test_a_zero_prescaler_diagonal_entry_is_rejected_not_committed(user: User) -> None:
    # a 0 (or negative / non-finite) prescaler 𝐿 DIAGONAL entry can't be a complexity scale: under the
    # all-interval simplicity weighting it makes a weight infinite and crashes the solve inside render(),
    # and the bad value is committed so every later render re-crashes. on_prescaler_change must reject it
    # at the edit seam — toast + revert, state untouched — like the ratio / mapping handlers.
    await user.open("/")
    user.find(kind=ui.checkbox, content="weighting").click()
    user.find(kind=ui.checkbox, content="all-interval").click()
    _cell_child(user, "control:all_interval").set_value(True)         # all-interval: simplicity weighting
    user.find(kind=ui.checkbox, content="alt. complexity").click()    # make the prescaler square editable
    await user.should_see(marker="cell:prescaling:primes:0:0")        # an editable DIAGONAL (i==j) entry
    before = _cell_child(user, "cell:prescaling:primes:0:0").value
    _cell_child(user, "cell:prescaling:primes:0:0").set_value("0")    # -> on_prescaler_change rejects it
    assert _cell_child(user, "cell:prescaling:primes:0:0").value == before   # reverted, never committed
    assert user.notify.contains("positive, finite number")           # ...with a toast explaining why


async def test_an_invalid_unchanged_basis_cell_reverts_with_a_toast(user: User) -> None:
    # on_unchanged_change's docstring promised a revert it never performed: a non-integer / garbage U
    # cell hit an early `return` with no render, leaving the typed garbage in the box (the UI left
    # lying). It must now toast + revert (render refills the live basis), like the ratio/mapping handlers.
    await _enable(user, "projection")
    await user.should_see(marker="cell:unchanged:0:0")
    before = _cell_child(user, "cell:unchanged:0:0").value
    _cell_child(user, "cell:unchanged:0:0").set_value("zz")   # unparseable -> not a whole number
    _commit(user, "cell:unchanged:0:0")                        # blur commits (preview=False)
    assert _cell_child(user, "cell:unchanged:0:0").value == before   # reverted: no garbage retained
    assert _cell_child(user, "cell:unchanged:0:0").value != "zz"
    assert user.notify.contains("valid unchanged-interval basis")    # ...with a toast explaining why


# --- per-sub-row ET picker / per-sub-column comma picker (curated build-up) -------------


async def test_subpickers_build_and_derive_their_value_from_state(user: User) -> None:
    await _enable(user, "presets")
    et0 = _cell_child(user, "etpick:0")
    cp0 = _cell_child(user, "commapick:0")
    assert isinstance(et0, ui.select) and isinstance(cp0, ui.select)
    # default meantone: its canonical rows aren't single ETs, so the ET picker shows the "-" prompt;
    # its comma (4 -4 1) IS the syntonic comma (up to sign), so the comma picker matches it
    assert et0.value is None
    assert cp0.value == "81/80"


async def test_picking_two_ets_builds_the_temperament_and_syncs_the_chooser(user: User) -> None:
    await _enable(user, "presets")
    _cell_child(user, "etpick:0").set_value("12")
    _cell_child(user, "etpick:1").set_value("19")
    # 12 & 19 merge to meantone: each row reads back its picked ET (stored verbatim)...
    assert _cell_child(user, "etpick:0").value == "12"
    assert _cell_child(user, "etpick:1").value == "19"
    # ...and the whole-temperament chooser recognizes the result, staying in sync
    assert _cell_child(user, "preset:temperament").value == "5:Meantone"


async def test_picking_a_dependent_et_is_rejected_and_reverts(user: User) -> None:
    await _enable(user, "presets")
    _cell_child(user, "etpick:0").set_value("12")
    _cell_child(user, "etpick:1").set_value("19")
    _cell_child(user, "etpick:1").set_value("12")  # same as row 0 -> dependent, can't combine
    assert _cell_child(user, "etpick:1").value == "19"  # rejected; reverts to the last valid pick


async def test_picking_a_comma_replaces_the_column_and_syncs(user: User) -> None:
    await _enable(user, "presets")
    _cell_child(user, "commapick:0").set_value("128/125")  # swap the syntonic comma for the diesis
    # the column re-derives to the picked comma, and the temperament chooser follows (augmented)
    assert _cell_child(user, "commapick:0").value == "128/125"
    assert _cell_child(user, "preset:temperament").value == "5:Augmented"


async def test_a_draft_comma_picker_adds_the_chosen_comma(user: User) -> None:
    await _enable(user, "presets")
    await user.should_see(marker="cell:mapping:1:0")   # meantone is rank 2 (two mapping rows)
    _click_glyph(user, "comma_plus")                   # + opens a green comma draft column
    await user.should_see(marker="commapick:draft")    # the draft column has its own picker
    _cell_child(user, "commapick:draft").set_value("128/125")  # pick the diesis -> fills + commits it
    # a second, independent comma was added: nullity rises, the rank drops to 1 (the 2nd row is gone)
    await user.should_not_see(marker="cell:mapping:1:0")
    await user.should_not_see(marker="commapick:draft")   # the draft committed and closed


async def test_a_draft_et_picker_adds_a_generator(user: User) -> None:
    await _enable(user, "presets")
    _click_glyph(user, "map_plus")                     # + opens a green mapping-row draft (un-temper)
    await user.should_see(marker="etpick:draft")       # the draft row has its own ET picker
    _cell_child(user, "etpick:draft").set_value("22")  # 22-ET is independent of meantone -> commits
    await user.should_see(marker="cell:mapping:2:0")   # a third generator row was added (rank rose)
    await user.should_not_see(marker="etpick:draft")   # the draft committed and closed


async def test_hovering_an_et_picker_option_previews_replacing_the_row(user: User) -> None:
    # hovering an ET in a committed row's picker previews replacing that row with its val — the would-be
    # mapping reflows and the changed cells ring amber, reverting on leave (like the temperament chooser).
    await _enable(user, "presets")
    et0 = _cell_child(user, "etpick:0")
    wrap = set(user.find(marker="etpick:0").elements)
    idx = list(et0.options).index("12")                                   # the slot dispatches the option index
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})  # hover 12-ET (row 0 is ⟨1 1 0])
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")   # 1 → 12 rings
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})    # leave the option
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")


async def test_hovering_a_comma_picker_option_previews_replacing_the_column(user: User) -> None:
    await _enable(user, "presets")
    cp0 = _cell_child(user, "commapick:0")
    wrap = set(user.find(marker="commapick:0").elements)
    idx = list(cp0.options).index("128/125")                               # hover the diesis (augmented)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")  # the mapping it'd load rings
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")


async def test_hovering_a_draft_comma_picker_populates_the_green_column(user: User) -> None:
    # hovering an option in a DRAFT picker fills the green draft with that comma's values (128/125 =
    # vector (7, 0, -3)), reverting to blank on leave — so you see what you're about to add.
    await _enable(user, "presets")
    _click_glyph(user, "comma_plus")
    await user.should_see(marker="commapick:draft")
    dp = _cell_child(user, "commapick:draft")
    wrap = set(user.find(marker="commapick:draft").elements)
    idx = list(dp.options).index("128/125")
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
    assert _cell_child(user, "cell:comma:0:1").value == "7"   # the draft column filled (prime-2 exponent)
    UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
    assert _cell_child(user, "cell:comma:0:1").value == ""    # reverted to the blank draft

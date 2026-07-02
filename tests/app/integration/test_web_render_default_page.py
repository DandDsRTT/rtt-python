import asyncio
import copy
import logging
import re
import sys
from fractions import Fraction
from types import SimpleNamespace
import nicegui.ui as ui
import pytest
from nicegui import core
from nicegui.element_filter import ElementFilter
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from rtt.app import app as web_app
from rtt.app import rendering as web_rendering
from rtt.app import _editing_tuning, page_assets, service, spreadsheet, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.editor import Editor
from _render_support import _op_classes, _wrap, _part_classes, _row_classes, _cell_child, _generator_tuning_face, _ratio_face, _renders_inside, _px, _DEFAULT_HTML_CELLS, _live_page, _live_assets


class TestDefaultPage:
    def test_default_page_renders_without_error(self, default_page: User) -> None:
        assert default_page.find(content="quantities").elements
        assert default_page.find(content="tuning").elements

    def test_share_button_renders_in_the_corner_bank(self, default_page: User) -> None:
        assert default_page.find(marker="share").elements

    def test_tour_button_renders_in_the_corner_bank(self, default_page: User) -> None:
        assert default_page.find(marker="tour").elements

    def test_grid_pane_publishes_its_base_size_for_the_scrollbar_fit(self, default_page: User) -> None:
        pane = next(iter(default_page.find(marker="gridpane").elements))
        base_width, base_height = pane._props.get("data-base-w"), pane._props.get("data-base-h")
        fit_width = pane._props.get("data-fit-w")
        assert base_width is not None and base_height is not None and fit_width is not None
        assert float(base_width) == float(pane._style["width"].rstrip("px"))
        assert float(base_height) == float(pane._style["height"].rstrip("px"))
        assert 0 < float(fit_width) <= float(base_width), "fit-w is the gridlines' own width — base-w minus the last column title's right overhang — so it # never exceeds base-w; a horizontal scrollbar is owed only when the pane is capped below it"

    def test_value_cells_carry_data_value_for_the_mapping_demo_overlay(self, default_page: User) -> None:
        cell = next(iter(default_page.find(marker="cell:mapping:1:2").elements))
        assert cell._props.get("data-value") == "4", (
            "mapping_demo.js reads each value cell's number from data-value (not the rendered face); the "
            "mapping matrix's prime-5 fifth entry is 4, so its wrap must publish it"
        )

    def test_grid_pane_exposes_the_grid_role_for_assistive_tech(self, default_page: User) -> None:
        pane = next(iter(default_page.find(marker="gridpane").elements))
        assert pane._props.get("role") == "grid"
        assert pane._props.get("aria-label") == "RTT spreadsheet"

    def test_value_cells_expose_a_gridcell_role_and_aria_label(self, default_page: User) -> None:
        cell = next(iter(default_page.find(marker="cell:mapping:1:2").elements))
        assert cell._props.get("role") == "gridcell"
        label = cell._props.get("aria-label")
        assert label and "mapping" in label

    def test_headers_and_row_labels_expose_header_roles(self, default_page: User) -> None:
        header = next(iter(default_page.find(marker="header:primes").elements))
        assert header._props.get("role") == "columnheader"
        row_label = next(iter(default_page.find(marker="label:mapping").elements))
        assert row_label._props.get("role") == "rowheader"

    def test_interval_ratios_carry_reduce_and_reciprocate_buttons(self, default_page: User) -> None:
        assert default_page.find(marker="target:0:reduce").elements
        assert default_page.find(marker="target:0:reciprocate").elements
        assert default_page.find(marker="comma:0:reduce").elements
        assert default_page.find(marker="comma:0:reciprocate").elements
        assert "rtt-operation-disabled" not in _op_classes(default_page, "target:0:reduce")
        assert "rtt-operation-disabled" in _op_classes(default_page, "target:2:reduce")
        assert "rtt-operation-disabled" not in _op_classes(default_page, "target:0:reciprocate")
        assert "rtt-operation-disabled" not in _op_classes(default_page, "target:2:reciprocate")

    def test_interval_columns_render_draggable_reorder_grips(self, default_page: User) -> None:
        assert default_page.find(marker="grip:targets:0").elements, "the target list shows by default, so its reorder grip renders with no setup: a draggable # ⠿ over each column (also the drop target). Drive the builder and confirm it's a drag source"
        grip = next(iter(default_page.find(marker="grip:targets:0").elements))
        assert grip._props.get("draggable")

    def test_settings_and_controls_carry_hover_tooltips(self, default_page: User) -> None:
        tips = [element.text for element in default_page.client.elements.values() if isinstance(element, Tooltip)]
        assert any("name caption" in t for t in tips)
        mapping = next(iter(default_page.find(marker="cell:mapping:0:0").elements))
        assert "approximate this prime" in mapping._props.get("data-zoomhelp", "")

    def test_hover_tooltips_wait_before_appearing(self, default_page: User) -> None:
        tips = [element for element in default_page.client.elements.values() if isinstance(element, Tooltip)]
        assert tips
        assert all(int(element._props.get("delay", 0)) >= 500 for element in tips)

    def test_every_hover_tooltip_hides_instantly_so_a_reflow_cannot_strand_it(self, default_page: User) -> None:
        tips = [element for element in default_page.client.elements.values() if isinstance(element, Tooltip)]
        assert tips
        assert all(int(element._props.get("transition-duration", 300)) == 0 for element in tips)

    def test_every_gridded_value_cell_is_zoomable(self, default_page: User) -> None:
        assert "rtt-zoomable" in _wrap(default_page, "tuning:prime:0")._classes, "hovering ANY gridded value pops the zoom magnifier (zoom.js clones the cell, scaled): the cell # wraps carry .rtt-zoomable for the engine to find them. Both a read-only value (the octave's # 1200.000 tuning) and an editable one (a mapping entry) get it — the magnifier is for every value, # not just the read-only ones. Structural cells (a row/column header) never become zoomable"
        assert "rtt-zoomable" in _wrap(default_page, "cell:mapping:0:0")._classes
        assert "rtt-zoomable" in _wrap(default_page, "quantities_generator:0")._classes

    def test_structural_cells_are_not_zoomable(self, default_page: User) -> None:
        for element in default_page.client.elements.values():
            classes = getattr(element, "_classes", [])
            if "rtt-zoomable" in classes:
                assert not any(c in classes for c in
                               ("rtt-column-header", "rtt-row-label", "rtt-symbol", "rtt-box-title"))

    def test_value_cell_help_folds_into_the_zoom_magnifier(self, default_page: User) -> None:
        mapping = _wrap(default_page, "cell:mapping:0:0")
        assert mapping._props.get("data-zoomhelp", "").startswith("How many of this generator")
        assert not any(isinstance(c, Tooltip) for c in mapping.default_slot.children)

    def test_the_guide_chapter_slider_gates_the_panel_at_the_first_run_chapter(self, default_page: User) -> None:
        slider = next(iter(default_page.find(marker="chapterslider").elements))
        assert slider.value == show_settings.CHAPTER_DEFAULT, (
            "a genuinely-new browser opens at the default chapter")
        for key in ("counts", "interest", "interval_ratios", "tuning_tiles", "optimization"):
            assert "rtt-chapter-hidden" not in _row_classes(default_page, key), key
        for key in ("app_units", "projection",
                    "generator_detempering", "identity_objects"):
            assert "rtt-chapter-hidden" in _row_classes(default_page, key), (
                f"{key} reveals after chapter {show_settings.CHAPTER_DEFAULT}, so its row is collapsed at first run")
        with pytest.raises(AssertionError):
            default_page.find(marker="showrow:nonstandard_domain")
        assert "rtt-chap-invisible" not in _part_classes(default_page, "gridded_values"), "the dummy tile's parts are gated the space-preserving way: an early layer shows, a ch5 one is # invisible-but-in-place (visibility:hidden, NOT display:none)"
        assert "rtt-chap-invisible" in _part_classes(default_page, "tile_units")
        assert "rtt-chap-invisible" not in next(iter(default_page.find(marker="audiobank").elements))._classes, "the audio bank now lives in the frozen audio-settings box, so it is never chapter-gated invisible"
        def _box(key):
            return next(iter(default_page.find(marker=f"showbox:{key}").elements))
        assert "disable" in _box("app_units")._props
        assert "disable" not in _box("counts")._props
        assert "rtt-chapter-hidden" not in _row_classes(default_page, "basic")
        assert "rtt-chapter-hidden" in _row_classes(default_page, "other"), (
            "'other' reveals only beyond the guide, so its expander collapses at first run")
        reading = next(iter(default_page.find(marker="chapterreading").elements))
        assert reading.text == "4: Exploring temperaments"

    def test_guide_settings_box_holds_a_dd_default_terminology_radio(self, default_page: User) -> None:
        assert next(iter(default_page.find(marker="guidesettingstitle").elements)).text == "guide settings"
        dd_opt = next(iter(default_page.find(marker="terminologyradio:dd").elements))
        assert "rtt-range-option-on" in dd_opt._classes

    def test_positive_generator_tuning_cell_shows_an_explicit_plus_sign(self, default_page: User) -> None:
        sign_lbl, _, _ = _generator_tuning_face(default_page, "tuning:generator:1")
        assert sign_lbl.text == "+"

    def test_editable_generator_tuning_cell_renders_a_stacked_cents_face(self, default_page: User) -> None:
        value = _cell_child(default_page, "tuning:generator:1").value
        _sign, whole_in, frac_in = _generator_tuning_face(default_page, "tuning:generator:1")
        assert "." not in whole_in.value
        assert frac_in.value and "." not in frac_in.value
        assert f"{whole_in.value}.{frac_in.value}" == value

    def test_editable_ratio_cell_renders_a_stacked_fraction_face(self, default_page: User) -> None:
        assert isinstance(_cell_child(default_page, "comma:0"), ui.input), "the editable numerator box, not a static label"
        num, denominator = _ratio_face(default_page, "comma:0")
        assert (num.value, denominator.value) == ("80", "81")

    def test_a_disabled_toggle_greys_its_box_and_its_example_together(self, default_page: User) -> None:
        def box(key):
            return next(iter(default_page.find(marker=f"showbox:{key}").elements))
        def example_greyed(key):
            return "rtt-ex-disabled" in next(iter(default_page.find(marker=f"showexample:{key}").elements))._classes
        assert "disable" in box("generator_detempering")._props and example_greyed("generator_detempering")

    def test_audio_bank_is_always_live_with_a_leading_mute(self, default_page: User) -> None:
        assert "rtt-bank-off" not in next(iter(default_page.find(marker="audiobank").elements))._classes, "the waveform / play-mode / hold / 1-1 bank lives in the frozen audio-settings box and is now # ALWAYS live — mute (its leading control) is the on/off gate, so there is no audio Show toggle # and no greyed bank. All five controls render, mute first"
        for control in ("mute", "wave", "mode", "hold", "root"):
            assert default_page.find(marker=f"audio_control:{control}").elements

    @pytest.mark.parametrize("cell, region", [
        ("header:generators", "columnheadinner"),
        ("toggle:column:targets", "columnheadinner"),
        ("label:tuning", "rowband"),
        ("toggle:row:tuning", "rowband"),
        ("toggle:all", "corner"),
    ])
    def test_each_title_renders_into_its_frozen_region(self, default_page: User, cell: str, region: str) -> None:
        assert _renders_inside(default_page, cell, region)

    @pytest.mark.parametrize("cell, region", [
        ("plus", "columnheadinner"),
        ("minus", "columnheadinner"),
        ("generator_plus", "columnheadinner"),
        ("target_plus", "columnheadinner"),
        ("map_plus", "rowband"),
        ("map_minus:0", "rowband"),
    ])
    def test_branch_controls_render_into_their_frozen_region(self, default_page: User, cell: str, region: str) -> None:
        assert _renders_inside(default_page, cell, region), "the always-shown + and the hover − now ride the frozen branch bands with their gridlines # (column controls in the column strip, mapping/basis controls in the row band), so they # stay put while the value tiles scroll under them. The renderer routes each cell to its # pane by its POSITION — which band its top-left falls in — not a hand-kept kind list (which # couldn't anyway: the column + and the basis + share the kind 'plus' but freeze in different # bands)"

    def test_body_cells_render_on_the_board_under_no_frozen_region(self, default_page: User) -> None:
        assert _renders_inside(default_page, "cell:mapping:0:0", "board")
        for region in ("columnheadinner", "rowband", "corner"):
            assert not _renders_inside(default_page, "cell:mapping:0:0", region)

    def test_settings_frozen_header_plus_chrome_bar_matches_the_grid_column_strip_height(self, default_page: User) -> None:
        frozen = next(iter(default_page.find(marker="showfrozen").elements))
        columnhead = next(iter(default_page.find(marker="columnhead").elements))
        assert frozen._style.get("height")
        assert _px(frozen, "height") == _px(columnhead, "height") - page_assets._CHROME_H

    def test_grid_pane_hugs_the_grid_with_a_margin_all_round(self, default_page: User) -> None:
        layout = Editor().layout()
        pane = next(iter(default_page.find(marker="gridpane").elements))
        board = next(iter(default_page.find(marker="board").elements))
        columnhead = next(iter(default_page.find(marker="columnhead").elements))
        assert _px(board, "width") == layout.width
        assert layout.right_overhang > 0
        assert _px(pane, "width") == _px(board, "width") + layout.right_overhang + 24
        assert _px(pane, "height") == _px(board, "height") + _px(columnhead, "height") + 24

    def test_settings_body_caps_below_the_window_so_it_doesnt_scroll_when_it_fits(self, default_page: User) -> None:
        scroll = next(iter(default_page.find(marker="showscroll").elements))
        columnhead = next(iter(default_page.find(marker="columnhead").elements))
        fy = _px(columnhead, "height")
        assert scroll._style.get("max-height") == f"calc(100dvh - {page_assets._PAD + fy}px)"

    @pytest.mark.parametrize("cell_id", _DEFAULT_HTML_CELLS)
    def test_default_view_html_cell_renders_non_blank_content(self, default_page: User, cell_id: str) -> None:
        assert default_page.find(marker=cell_id).elements
        assert getattr(_cell_child(default_page, cell_id), "content", ""), \
            f"{cell_id} rendered with empty html content — did render() drop its kind's branch?"


class TestFirstVisitGate:
    async def test_a_fresh_load_is_a_first_visit(self, user: User) -> None:
        await user.open("/")
        _, page = _live_page()
        assert page.first_visit is True, (
            "a fresh browser with nothing stored is the visit the tour autostarts for, so its grid is "
            "gated until the tour's opening chapter settles")

    async def test_a_shared_link_load_is_not_a_first_visit(self, user: User) -> None:
        token = _live_assets()._encode_state(Editor().serialize())
        await user.open(f"/?{_live_assets()._STATE_PARAM}={token}")
        _, page = _live_page()
        assert page.first_visit is False, "a shared-link load is not a fresh first visit — no gate"

    async def test_a_stored_chapter_makes_it_not_a_first_visit(self, user: User) -> None:
        await user.open("/")
        _live_assets()._doc_store()[_live_assets()._CHAPTER_KEY] = show_settings.CHAPTER_DEFAULT
        await user.open("/")
        _, page = _live_page()
        assert page.first_visit is False, (
            "a returning visitor who already has a chosen chapter is past the tour — no gate")


class TestDefaultPageGuideLinks:
    def test_value_cell_in_a_guided_tile_offers_the_guide_hovercard(self, default_page: User) -> None:
        mapping = _wrap(default_page, "cell:mapping:0:0")
        assert "rtt-guide-link" in mapping._classes, "a computed value cell in a guided tile also carries the deep-dive guide hover-card (the terse zoom caption never held a clickable link), so a learner hovering the NUMBER — not just the tile caption — has a path into the guide"
        assert mapping._props.get("data-guide-url", "").startswith("https://")
        assert "Mappings" in mapping._props.get("data-guide-loc", "")
        assert mapping._props.get("data-guide-text", "")

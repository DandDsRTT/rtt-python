from __future__ import annotations

import logging

from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_buttons import _ReconButtons
from rtt.app._recon_choosers import _ReconChoosers
from rtt.app._recon_display import _ReconDisplayCells
from rtt.app._recon_drag import _ReconDrag
from rtt.app._recon_value import _ReconValueCells
from rtt.app.editor import Editor
from rtt.app.page_assets import (
    _CELLUNIT_MAX_FONT,
    _EBK_SVG_KINDS,
    _INT_WHEEL_JS,
    _STACKED_EXIT_JS,
    _WHEEL_STEPS,
    VALUE_KINDS,
    _KindHandlers,
)
from rtt.app.render_html import (
    _bold_units,
    _cents_parts,
    _units_font,
)

_log = logging.getLogger(__name__)


class _Reconciler:
    def __init__(self, editor: Editor, gestures=None) -> None:
        self._editor = editor
        # the gesture state machine is OWNED by the GestureController; the reconciler only
        # READS the live gesture (to honour a chooser/temperament preview hold while updating a
        # cell). It borrows it through this narrow back-reference rather than owning the state.
        self._gestures = gestures
        self._cb = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self._init_handles()
        self._init_render_caches()
        self.cell_kinds: dict[str, _KindHandlers] = {}
        self._value = _ReconValueCells(self)
        self._display = _ReconDisplayCells(self)
        self._choose = _ReconChoosers(self)
        self._buttons = _ReconButtons(self)
        self._drag = _ReconDrag(self)
        self._register_display_kinds()
        self._register_value_kinds()
        self._register_label_kinds()
        self._register_control_kinds()
        self._register_button_kinds()

    @property
    def _cur_gesture(self):
        return self._gestures.gesture if self._gestures is not None else None

    def _init_handles(self) -> None:
        self.els: dict = {}
        self.inputs: dict = {}
        self.den_inputs: dict = {}
        self.frac_edits: dict = {}
        self.ratio_ops: dict = {}
        self.labels: dict = {}
        self.fracs: dict = {}
        self.ratio_faces: dict = {}
        self.stacked_faces: dict = {}
        self.stacked_w: dict = {}
        self.gensign_faces: dict = {}
        self.htmls: dict = {}
        self.ebk_sizes: dict = {}
        self.chart_keys: dict = {}
        self.range_keys: dict = {}
        self.exprs: dict = {}
        self.expr_state: dict = {}
        self.kinds: dict = {}
        self.selects: dict = {}  # preset cell id -> its q-select
        self.checks: dict = {}  # control_check cell id -> its q-checkbox (the box-𝐋 "replace diminuator")
        self.ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
        self.rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
        self.scheme_buttons: dict = {}  # back-to-scheme button cell id -> its ui.button (for the idle grey)
        self.mean_damage_tips: dict = {}  # mean damage SYMBOL cell id -> its ui.tooltip (the value cell folds its
        # help into the zoom magnifier as data-zoomhelp; the symbol — not a value cell — keeps a swappable tooltip)
        self.target_limit_tip = (
            None  # the target chooser's ui.tooltip (text swaps to an invalid-limit message)
        )
        self.captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
        self.caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
        self.math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
        self.math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
        self.fold_state: dict = {}  # fold-toggle cell id -> last state token (unfold_more/less), to swap its SVG on change
        self.cell_units: dict = {}  # value cell id -> the ui.html holding its per-cell unit (the units toggle)
        self.cell_unit_text: dict = {}  # ...and its last unit string, to rewrite on a units toggle / value change
        self.popup_state: dict = {}

    def _init_render_caches(self) -> None:
        # Change-guard caches: the last applied (geometry string / content signature / ring state) per
        # entity, so render() reapplies an element's style/content/rings ONLY when it actually changed
        # — most cells are untouched between renders, so the reconcile skips them instead of re-running
        # the per-cell work over the whole page on every interaction.
        self.styled: dict = {}  # entity id -> last applied position/size style string
        self.content_sig: dict = {}  # cell id -> last (content fields, w, h, audio) it was updated for
        self.ring_sig: dict = {}  # cell id -> last (in-amber, in-red) ring state it was painted for
        # The single source of truth for every per-id handle dict, so drop() clears an entity from ALL
        # of them. Forgetting one leaks handles to a deleted element (checks was historically omitted —
        # the box-𝐋 diminuator checkbox); a NEW per-id handle dict MUST be added here.
        self._handle_dicts = (
            self.els,
            self.inputs,
            self.den_inputs,
            self.frac_edits,
            self.ratio_ops,
            self.labels,
            self.fracs,
            self.ratio_faces,
            self.stacked_faces,
            self.stacked_w,
            self.gensign_faces,
            self.htmls,
            self.ebk_sizes,
            self.chart_keys,
            self.range_keys,
            self.exprs,
            self.expr_state,
            self.kinds,
            self.selects,
            self.checks,
            self.ptext_inputs,
            self.rangeopts,
            self.scheme_buttons,
            self.mean_damage_tips,
            self.captions,
            self.caption_html,
            self.math_cells,
            self.math_rendered,
            self.fold_state,
            self.cell_units,
            self.cell_unit_text,
            self.styled,
            self.content_sig,
            self.ring_sig,
        )

    def _register_display_kinds(self) -> None:
        for _ebk_kind in _EBK_SVG_KINDS:
            self.cell_kinds[_ebk_kind] = _KindHandlers(self._display._build_svgfill, self._display._update_ebk)
        self.cell_kinds["chart"] = _KindHandlers(self._display._build_svgfill, self._display._update_chart)
        self.cell_kinds["rangechart"] = _KindHandlers(self._display._build_svgfill, self._display._update_rangechart)

        self.cell_kinds["count"] = _KindHandlers(self._display._build_count, self._display._update_mathcell)
        self.cell_kinds["symbol"] = _KindHandlers(self._display._build_symbol, self._display._update_mathcell)
        self.cell_kinds["matlabel"] = _KindHandlers(self._display._build_matlabel, self._display._update_mathcell)
        self.cell_kinds["units"] = _KindHandlers(self._display._build_units, self._display._update_mathcell)
        self.cell_kinds["caption"] = _KindHandlers(self._display._build_caption, self._display._update_caption)

        self.cell_kinds["ptextpending"] = _KindHandlers(
            self._display._build_ptextpending, self._display._update_ptextpending
        )
        self.cell_kinds["mathexpr"] = _KindHandlers(self._display._build_mathexpr, self._display._update_mathexpr)

    def _register_value_kinds(self) -> None:
        _gridvalue = _KindHandlers(self._value._build_gridvalue, self._value._update_gridvalue)
        for _gv_kind in (
            "mapping",
            "commacell",
            "unchangedcell",
            "interestcell",
            "heldcell",
            "targetcell",
            "formcell",
        ):
            self.cell_kinds[_gv_kind] = _gridvalue
        self.cell_kinds["prescalercell"] = _KindHandlers(
            self._value._build_prescalercell, self._value._update_prescalercell
        )
        self.cell_kinds["weightcell"] = _KindHandlers(
            self._value._build_weightcell, self._value._update_weightcell
        )
        self.cell_kinds["powerinput"] = _KindHandlers(
            self._value._build_powerinput, self._value._update_powerinput
        )
        self.cell_kinds["powerdisplay"] = _KindHandlers(
            self._value._build_powerdisplay, self._value._update_powerdisplay
        )
        self.cell_kinds["gentuningcell"] = _KindHandlers(
            self._value._build_gentuningcell, self._value._update_gentuningcell
        )

        self.cell_kinds["ptextedit"] = _KindHandlers(self._value._build_ptextedit, self._value._update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(self._value._build_genratio, self._value._update_ratio)
        self.cell_kinds["ratiocell"] = _gridvalue
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(self._value._build_commaratio, self._value._update_ratio)
        self.cell_kinds["tuningvalue"] = _KindHandlers(
            self._value._build_tuning_value, self._value._update_tuning_value
        )

    def _register_label_kinds(self) -> None:
        _value_builder = self._value._label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(
            self._value._label_builder("rtt-colheader"), self._value._update_label
        )
        self.cell_kinds["rowlabel"] = _KindHandlers(
            self._value._label_builder("rtt-rowlabel"), self._value._update_label
        )
        self.cell_kinds["ptext"] = _KindHandlers(
            self._value._label_builder("rtt-ptext"), self._value._update_ptext
        )
        self.cell_kinds["transpose"] = _KindHandlers(
            self._value._label_builder("rtt-transpose"), self._value._update_label
        )
        self.cell_kinds["boxtitle"] = _KindHandlers(self._value._label_builder("rtt-boxtitle"), None)

    def _register_control_kinds(self) -> None:
        self.cell_kinds["rangemode"] = _KindHandlers(self._choose._build_rangemode, self._choose._update_rangemode)
        self.cell_kinds["scheme_button"] = _KindHandlers(
            self._choose._build_scheme_button, self._choose._update_scheme_button
        )
        self.cell_kinds["rowtoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["coltoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["tiletoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["alltoggle"] = _KindHandlers(self._choose._build_alltoggle, self._choose._update_foldtoggle)

        self.cell_kinds["preset"] = _KindHandlers(self._choose._build_preset, self._choose._update_preset)
        self.cell_kinds["etpick"] = _KindHandlers(self._choose._build_etpick, self._choose._update_subpick)
        self.cell_kinds["commapick"] = _KindHandlers(self._choose._build_commapick, self._choose._update_subpick)
        self.cell_kinds["control_select"] = _KindHandlers(
            self._choose._build_control_select, self._choose._update_control_select
        )
        self.cell_kinds["control_check"] = _KindHandlers(
            self._choose._build_control_check, self._choose._update_control_check
        )
        self.cell_kinds["formchooser"] = _KindHandlers(
            self._choose._build_formchooser, self._choose._update_formchooser
        )

    def _register_button_kinds(self) -> None:
        self.cell_kinds["minus"] = _KindHandlers(self._buttons._build_minus)
        self.cell_kinds["plus"] = _KindHandlers(self._buttons._build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(self._buttons._build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(self._buttons._build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(self._buttons._build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(self._buttons._build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(self._drag._build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(self._drag._build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(self._buttons._build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(self._buttons._build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(self._buttons._build_comma_plus)
        self.cell_kinds["element_plus"] = _KindHandlers(self._buttons._build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(self._buttons._build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._buttons._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._buttons._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._buttons._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._buttons._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._buttons._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._buttons._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._buttons._build_colgrip)

    def drop(self, eid: str) -> None:
        self.els[eid].delete()
        for d in self._handle_dicts:
            d.pop(eid, None)

    def _attach_guide_link(self, wrap, gh: tooltips.GuideHelp, tile: str) -> None:
        # the hover-card (a body-level div built by _GUIDE_JS) reads these and renders a card that
        # stays open while hovered, so its "Read in the Guide" link is actually clickable — a Quasar
        # tooltip can't be (it hides the moment the cursor leaves the cell toward it). data-guide-tile
        # ties a tile's name + symbol cells into ONE hover zone so the card doesn't jump (the link
        # doesn't run away) when the cursor crosses from one to the other.
        wrap.classes("rtt-guide-link")
        wrap._props["data-guide-text"] = gh.text
        wrap._props["data-guide-tile"] = tile
        if gh.url:
            wrap._props["data-guide-loc"] = gh.location
            wrap._props["data-guide-url"] = gh.url

    def make_cell(self, cb: spreadsheet.CellBox) -> None:
        # build a cell's element in the active parent (the caller opens the freeze container),
        # register it + its kind (and audio key) so render() can place and reconcile it after.
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            self.cell_kinds[cb.kind].build(cb, wrap)
            if cb.audio is not None:
                self._tag_audio(wrap, cb)
        # Hover affordances. A gridded VALUE cell (VALUE_KINDS) becomes .rtt-zoomable — hovering it
        # pops the zoom magnifier (a client-side clone, _ZOOM_JS), and its own hover help (if any —
        # the editable cells' "type to edit…", the mean damage / dual(𝑞) explanations) folds INTO that
        # magnifier as data-zoomhelp rather than a separate tooltip, so value cells carry exactly one
        # hover popup. Every other control keeps its plain help tooltip. All wording still lives in
        # rtt.app.tooltips; a NEW kind must be classified there (READONLY_KINDS or a help entry) or
        # test_web_tooltips' completeness sweep fails. The mark/data-eid ride the wrap, so the magnifier
        # (which clones the wrap) and any tooltip hang off it too.
        self._attach_hover_help(wrap, cb)
        self.els[cb.id] = wrap
        self.kinds[cb.id] = cb.kind
        self._wire_cell_input(wrap, cb)

    def _attach_hover_help(self, wrap, cb: spreadsheet.CellBox) -> None:
        help_text = tooltips.control_help(cb.kind, cb.id)
        if cb.kind in VALUE_KINDS:
            wrap.classes("rtt-zoomable")
            if help_text:
                wrap._props["data-zoomhelp"] = help_text
        elif help_text:
            if cb.id in tooltips.MEAN_DAMAGE_IDS:
                with wrap:
                    self.mean_damage_tips[cb.id] = ui.tooltip(help_text)
            elif cb.id == "preset:target":
                with wrap:
                    self.target_limit_tip = ui.tooltip(help_text)
            else:
                wrap.tooltip(help_text)
        if cb.kind in ("symbol", "caption"):
            gh = tooltips.tile_guide_help_for_cell(cb.id)
            if gh is not None:
                self._attach_guide_link(wrap, gh, cb.id.split(":", 1)[1])

    def _wire_cell_input(self, wrap, cb: spreadsheet.CellBox) -> None:
        if cb.kind.endswith(("plus", "minus")):
            wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
        edit_input = self.inputs.get(cb.id) or self.ptext_inputs.get(cb.id)
        if edit_input is not None:
            den = self.den_inputs.get(cb.id)
            guard = _STACKED_EXIT_JS if den is not None else None
            for fld in (edit_input, den) if den is not None else (edit_input,):
                fld.on(
                    "focus", lambda _=None, cid=cb.id: self._cb.on_cell_focus(cid), js_handler=guard
                )
                fld.on(
                    "blur", lambda _=None, cid=cb.id: self._cb.on_cell_blur(cid), js_handler=guard
                )
                fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
        if cb.kind in _WHEEL_STEPS:
            wrap.on(
                "wheel",
                lambda e, cid=cb.id: self._cb.on_value_wheel(cid, e.args.get("deltaY")),
                args=["deltaY"],
                js_handler=_INT_WHEEL_JS,
            )

    def update_cell(self, cb: spreadsheet.CellBox) -> None:
        handlers = self.cell_kinds[cb.kind]
        if handlers.update is not None:
            handlers.update(cb)
        if cb.unit:
            if cb.id not in self.cell_units:
                with self.els[cb.id]:
                    self.cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                self.els[cb.id].classes(add="rtt-cell-united")
            if self.cell_unit_text.get(cb.id) != (cb.unit, cb.w):
                self.cell_units[cb.id].set_content(_bold_units(cb.unit))
                self.cell_units[cb.id].style(
                    f"font-size:{_units_font(cb.unit, cb.w, _CELLUNIT_MAX_FONT):.2f}px"
                )
                self.cell_unit_text[cb.id] = (cb.unit, cb.w)
        elif cb.id in self.cell_units:
            self.cell_units[cb.id].delete()
            self.cell_units.pop(cb.id, None)
            self.cell_unit_text.pop(cb.id, None)
            self.els[cb.id].classes(remove="rtt-cell-united")
        if cb.audio is not None:
            self._tag_audio(self.els[cb.id], cb)

    def _tag_audio(self, el, cb: spreadsheet.CellBox) -> None:
        tile, idx, cents = cb.audio
        el.classes(add="rtt-spk").props(
            f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"'
        )

    def cell_value(self, cid: str) -> str:
        num = str(self.inputs[cid].value).strip()
        if not num:
            return ""
        if num == "?":
            return "?/?"
        if "/" in num:
            return num
        den = str(self.den_inputs[cid].value).strip() if cid in self.den_inputs else ""
        return num if den in ("", "1", "?") else f"{num}/{den}"

    def decimal_value(self, cid: str) -> str:
        whole = str(self.inputs[cid].value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = str(self.den_inputs[cid].value).strip().lstrip(".") if cid in self.den_inputs else ""
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.inputs[cid].value = whole
        if cid in self.den_inputs:
            self.den_inputs[cid].value = frac

    def _target_preset_values(self):
        if self._editor.target_override is not None or service.is_all_interval(
            self._editor.tuning_scheme
        ):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:
            limit = service.default_target_limit(family, self._editor.state.domain_basis)
        return limit, family

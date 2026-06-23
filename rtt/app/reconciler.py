from __future__ import annotations

import logging
from typing import ClassVar

from nicegui import ui

from rtt.app import (
    presets,
    service,
    spreadsheet,
    spreadsheet_text,
    tooltips,
)
from rtt.app.editor import Editor
from rtt.app.marks import (
    ebk_svg,
)
from rtt.app.render_html import (
    _FOLD_GLYPH,
    _bar_chart,
    _bold_units,
    _cents_parts,
    _control_svg,
    _digit_fit_font,
    _gentuning_parts,
    _limit_text,
    _math_html,
    _mathexpr_html,
    _power_parts,
    _ptext_font,
    _range_chart,
    _ratio_font,
    _ratio_parts,
    _select_props,
    _underline_html,
    _units_font,
    _units_html,
)


from rtt.app.page_assets import (
    _KindHandlers,
    _SUBPICK_POPUP_W,
    _CELL_FONT,
    _GENSIGN_W,
    _STACKED_MAIN_FONT,
    _WHEEL_STEPS,
    _INT_WHEEL_JS,
    _GridValueSpec,
    _GRIDVALUE_SPECS,
    _vgroup_key,
    _STACKED_EXIT_JS,
    _GROUP_EXIT_JS,
    _UNITS_MAX_FONT,
    _CELLUNIT_MAX_FONT,
    _MATLABEL_FONT,
    _MATLABEL_MIN_FONT,
    _EBK_SVG_KINDS,
    _EBK_SQUARE,
    _TRANSPOSE_MARK,
    VALUE_KINDS,
    _GroupedSelect,
    _set_offlist_prompt,
    _projection_prompt,
    _formchooser_options,
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
            self.cell_kinds[_ebk_kind] = _KindHandlers(self._build_svgfill, self._update_ebk)
        self.cell_kinds["chart"] = _KindHandlers(self._build_svgfill, self._update_chart)
        self.cell_kinds["rangechart"] = _KindHandlers(self._build_svgfill, self._update_rangechart)

        self.cell_kinds["count"] = _KindHandlers(self._build_count, self._update_mathcell)
        self.cell_kinds["symbol"] = _KindHandlers(self._build_symbol, self._update_mathcell)
        self.cell_kinds["matlabel"] = _KindHandlers(self._build_matlabel, self._update_mathcell)
        self.cell_kinds["units"] = _KindHandlers(self._build_units, self._update_mathcell)
        self.cell_kinds["caption"] = _KindHandlers(self._build_caption, self._update_caption)

        self.cell_kinds["ptextpending"] = _KindHandlers(
            self._build_ptextpending, self._update_ptextpending
        )
        self.cell_kinds["mathexpr"] = _KindHandlers(self._build_mathexpr, self._update_mathexpr)

    def _register_value_kinds(self) -> None:
        _gridvalue = _KindHandlers(self._build_gridvalue, self._update_gridvalue)
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
            self._build_prescalercell, self._update_prescalercell
        )
        self.cell_kinds["weightcell"] = _KindHandlers(
            self._build_weightcell, self._update_weightcell
        )
        self.cell_kinds["powerinput"] = _KindHandlers(
            self._build_powerinput, self._update_powerinput
        )
        self.cell_kinds["powerdisplay"] = _KindHandlers(
            self._build_powerdisplay, self._update_powerdisplay
        )
        self.cell_kinds["gentuningcell"] = _KindHandlers(
            self._build_gentuningcell, self._update_gentuningcell
        )

        self.cell_kinds["ptextedit"] = _KindHandlers(self._build_ptextedit, self._update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(self._build_genratio, self._update_ratio)
        self.cell_kinds["ratiocell"] = _gridvalue
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(self._build_commaratio, self._update_ratio)
        self.cell_kinds["tuningvalue"] = _KindHandlers(
            self._build_tuning_value, self._update_tuning_value
        )

    def _register_label_kinds(self) -> None:
        _value_builder = self._label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(
            self._label_builder("rtt-colheader"), self._update_label
        )
        self.cell_kinds["rowlabel"] = _KindHandlers(
            self._label_builder("rtt-rowlabel"), self._update_label
        )
        self.cell_kinds["ptext"] = _KindHandlers(
            self._label_builder("rtt-ptext"), self._update_ptext
        )
        self.cell_kinds["transpose"] = _KindHandlers(
            self._label_builder("rtt-transpose"), self._update_label
        )
        self.cell_kinds["boxtitle"] = _KindHandlers(self._label_builder("rtt-boxtitle"), None)

    def _register_control_kinds(self) -> None:
        self.cell_kinds["rangemode"] = _KindHandlers(self._build_rangemode, self._update_rangemode)
        self.cell_kinds["scheme_button"] = _KindHandlers(
            self._build_scheme_button, self._update_scheme_button
        )
        self.cell_kinds["rowtoggle"] = _KindHandlers(
            self._build_foldtoggle, self._update_foldtoggle
        )
        self.cell_kinds["coltoggle"] = _KindHandlers(
            self._build_foldtoggle, self._update_foldtoggle
        )
        self.cell_kinds["tiletoggle"] = _KindHandlers(
            self._build_foldtoggle, self._update_foldtoggle
        )
        self.cell_kinds["alltoggle"] = _KindHandlers(self._build_alltoggle, self._update_foldtoggle)

        self.cell_kinds["preset"] = _KindHandlers(self._build_preset, self._update_preset)
        self.cell_kinds["etpick"] = _KindHandlers(self._build_etpick, self._update_subpick)
        self.cell_kinds["commapick"] = _KindHandlers(self._build_commapick, self._update_subpick)
        self.cell_kinds["control_select"] = _KindHandlers(
            self._build_control_select, self._update_control_select
        )
        self.cell_kinds["control_check"] = _KindHandlers(
            self._build_control_check, self._update_control_check
        )
        self.cell_kinds["formchooser"] = _KindHandlers(
            self._build_formchooser, self._update_formchooser
        )

    def _register_button_kinds(self) -> None:
        self.cell_kinds["minus"] = _KindHandlers(self._build_minus)
        self.cell_kinds["plus"] = _KindHandlers(self._build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(self._build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(self._build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(self._build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(self._build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(self._build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(self._build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(self._build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(self._build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(self._build_comma_plus)
        self.cell_kinds["element_plus"] = _KindHandlers(self._build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(self._build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._build_colgrip)

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

    def _put_stacked_face(self, cid: str, cls: str, main: str, sub: str, width: float) -> None:
        with ui.element("div").classes(cls):
            m = ui.label(main).classes("rtt-stacked-main")
            s = ui.label(sub).classes("rtt-stacked-sub")
        self.stacked_faces[cid] = (m, s)
        self.stacked_w[cid] = width
        self._size_stacked_main(m, main, sub, width)

    def _size_stacked_main(self, main_label, main: str, sub: str, width: float) -> None:
        solo = not sub
        main_label.classes(
            add="rtt-stacked-solo" if solo else "", remove="" if solo else "rtt-stacked-solo"
        )
        size = (
            _digit_fit_font(len(main), width, float(_CELL_FONT))
            if solo
            else float(_STACKED_MAIN_FONT)
        )
        main_label.style(f"font-size:{size:.2f}px")

    def _sync_stacked_face(self, cid: str, main: str, sub: str) -> None:
        m, s = self.stacked_faces[cid]
        m.set_text(main)
        s.set_text(sub)
        self._size_stacked_main(m, main, sub, self.stacked_w[cid])

    def set_cents_face(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self._sync_stacked_face(cid, whole, f".{frac}" if frac else "")

    def cents_face(self, cb: spreadsheet.CellBox, cls: str) -> None:
        whole, frac = _cents_parts(cb.text)
        self._put_stacked_face(cb.id, cls, whole, f".{frac}" if frac else "", cb.w)

    def _ratio(self, cb: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
        face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
        self.ratio_faces[cb.id] = face
        with face:
            self._ratio_body(cb, approx)

    def _ratio_body(self, cb: spreadsheet.CellBox, approx: bool) -> None:
        parts = _ratio_parts(cb.text)
        if parts and not all(p.lstrip("-").isdigit() for p in parts):
            parts = None
        whole = bool(parts) and parts[1] == "1"
        if approx and parts:
            ui.label("~").classes("rtt-approx")
        if parts:
            with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
                num = ui.label(parts[0]).classes("rtt-frac-num")
                den = ui.label(parts[1]).classes("rtt-frac-den")
            self.fracs[cb.id] = (num, den)
            self._fit_ratio(cb.id, parts[0], parts[1], cb.w, whole)
        else:
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value")

    def _fit_ratio(self, cid: str, num: str, den: str, width: float, whole: bool = False) -> None:
        size = (
            _digit_fit_font(len(num), width, float(_CELL_FONT))
            if whole
            else _ratio_font(num, den, width)
        )
        font = f"font-size:{size:.2f}px"
        self.fracs[cid][0].style(font)
        self.fracs[cid][1].style(font)

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

    def _build_svgfill(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.htmls[cb.id] = ui.html("").classes("rtt-svgfill")

    def _update_ebk(self, cb: spreadsheet.CellBox) -> None:
        if self.ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
            self.htmls[cb.id].set_content(ebk_svg(cb))
            self.ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)

    def _update_chart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
        if self.chart_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(
                _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
            )
            self.chart_keys[cb.id] = key

    def _update_rangechart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
        if self.range_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(
                _range_chart(cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
            )
            self.range_keys[cb.id] = key

    def _build_count(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.math_cells[cb.id] = ui.html("").classes("rtt-count")

    def _build_symbol(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-symbol-cell")
        cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
        self.math_cells[cb.id] = ui.html("").classes(cls)

    @staticmethod
    def _matlabel_classes(text: str) -> str:
        return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"

    def _build_matlabel(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-matlabel-cell")
        self.math_cells[cb.id] = ui.html("").classes(self._matlabel_classes(cb.text))

    def _build_units(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-units-cell")
        self.math_cells[cb.id] = ui.html("").classes("rtt-units")

    def _update_mathcell(self, cb: spreadsheet.CellBox) -> None:
        if cb.kind == "units":
            html = _units_html(cb.text)
            if self.math_rendered.get(cb.id) != (html, cb.w):
                self.math_cells[cb.id].set_content(html)
                self.math_cells[cb.id].style(
                    f"font-size:{_units_font(cb.text, cb.w, _UNITS_MAX_FONT):.2f}px"
                )
                self.math_rendered[cb.id] = (html, cb.w)
            return
        html = _math_html(cb.text)
        font = None
        if cb.kind == "matlabel" and ":col:" in cb.id and "‖" not in cb.text and " " not in cb.text:
            w = spreadsheet_text._min_width_for_lines(cb.text, 1, _MATLABEL_FONT)
            if w > cb.w - 2:
                font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cb.w - 2) / w)
        if self.math_rendered.get(cb.id) != (html, font):
            self.math_cells[cb.id].set_content(html)
            if font is not None:
                self.math_cells[cb.id].style(f"font-size:{font:.2f}px")
            self.math_rendered[cb.id] = (html, font)
            if cb.kind == "matlabel":
                self.math_cells[cb.id].classes(replace=self._matlabel_classes(cb.text))
            if cb.id == "optimization:mean_damage:symbol":
                wide = "‖" in cb.text
                self.math_cells[cb.id].classes(
                    replace="rtt-symbol rtt-opt-1line rtt-opt-wide"
                    if wide
                    else "rtt-symbol rtt-opt-1line"
                )

    def _build_caption(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-caption-cell")
        one_line = cb.id.startswith("optimization:") and cb.id != "optimization:mean_damage:caption"
        cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
        if cb.align == "left":
            cls += " rtt-caption-left"
        self.captions[cb.id] = ui.html("").classes(cls)

    def _update_caption(self, cb: spreadsheet.CellBox) -> None:
        html = _underline_html(cb.text, cb.underlines)
        if self.caption_html.get(cb.id) != html:
            self.captions[cb.id].set_content(html)
            self.caption_html[cb.id] = html
        self.captions[cb.id].classes(
            add="rtt-caption-disabled" if cb.disabled else "",
            remove="" if cb.disabled else "rtt-caption-disabled",
        )

    def _build_ptextpending(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.htmls[cb.id] = ui.html("").classes("rtt-ptextpending")

    def _update_ptextpending(self, cb: spreadsheet.CellBox) -> None:
        ed = self._editor
        off = not ed.settings.get("ebk", True)

        def squared(prefix, draft, suffix, vector_based):
            if not off:
                return prefix, draft, suffix
            return (
                prefix.translate(_EBK_SQUARE),
                draft.translate(_EBK_SQUARE),
                suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""),
            )

        if cb.id == "ptext:mapping:primes":
            committed = service.simple_matrix_to_ebk(cb.text, False) if off else cb.text
            prefix, draft, suffix = squared(
                *service.mapping_pending_text(committed, ed.pending_mapping_row), False
            )
            self.htmls[cb.id].set_content(
                f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}"
            )
            self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            return
        if cb.id == "ptext:vectors:targets":
            targets = ed.target_override or service.target_interval_set(
                ed.target_spec, ed.state.domain_basis
            )
            committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
            pending = ed.pending_target
        else:
            committed, pending = ed.state.comma_basis, ed.pending_comma
        prefix, draft, suffix = squared(*service.vector_list_pending_text(committed, pending), True)
        self.htmls[cb.id].set_content(f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
        self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")

    def _build_mathexpr(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.exprs[cb.id] = ui.html("").classes("rtt-mathexpr")

    def _update_mathexpr(self, cb: spreadsheet.CellBox) -> None:
        if self.expr_state.get(cb.id) != (cb.text, cb.w):
            self.exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
            self.expr_state[cb.id] = (cb.text, cb.w)

    def _build_gridvalue(self, cb: spreadsheet.CellBox, wrap) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        commit, preview = self._gridvalue_handlers(cb, spec)
        if spec.ratio_allowed:
            self._build_fraction(cb, wrap, commit, preview)
        else:
            wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cb)}"')
            inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
            inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
            self.inputs[cb.id] = inp
        self._arm_gridvalue(wrap, cb, spec)

    def _build_fraction(self, cb: spreadsheet.CellBox, wrap, commit, preview) -> None:
        # the editable stacked fraction: a numerator input over a bar over a denominator input, edited
        # IN PLACE (no overlay face, no diagonal slash). The two are SEPARATE fields — Tab moves
        # num->den, the bar isn't selectable — and the cell collapses to the big-integer view when the
        # denominator is blank/1 ("/" in integer view splits it open again). _FRACTION_JS drives the
        # live int<->ratio switch client-side; make_cell gates focus/blur (it also wires the den) so
        # the commit fires only when focus leaves the WHOLE cell. The white box + black outline rides
        # the WRAP (one box around two inputs), not each input's own Quasar control.
        wrap.classes("rtt-cell-input rtt-fraccell")
        box = ui.element("div").classes("rtt-frac-edit")
        with box:
            num = (
                ui.input(on_change=preview)
                .props("dense borderless")
                .classes("rtt-cellinput rtt-frac-num-in")
            )
            ui.element("div").classes("rtt-frac-bar")
            den = (
                ui.input(on_change=preview)
                .props("dense borderless")
                .classes("rtt-cellinput rtt-frac-den-in")
            )
        num.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        den.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.inputs[cb.id] = num
        self.den_inputs[cb.id] = den
        self.frac_edits[cb.id] = box
        self._arm_ratio_ops(cb, wrap)

    def _arm_ratio_ops(self, cb: spreadsheet.CellBox, wrap) -> None:
        # the equave-reduce + reciprocate buttons flanking the bar of an editable interval ratio —
        # any editable interval ratiocell (commas / targets / held / intervals of interest) AND the
        # editable domain basis elements (nonstandard-domain box on: elementcell / elementratio). NOT
        # the read-only derived faces (the ~generator ratios, a non-projection unchanged column, the
        # standard read-only domain primes), which carry no value to edit in place. Each reveals on
        # hover, hides while the cell is edited, and reads disabled when its op is a no-op: an interval
        # already inside [1, equave) can't reduce, a unison can't reciprocate. They commit through
        # transform_interval, one undo step.
        if (
            cb.kind not in ("ratiocell", "elementcell", "elementratio")
            or cb.pending
            or cb.id.split(":", 1)[0] not in ("comma", "target", "held", "interest", "prime")
        ):
            return
        wrap.classes("rtt-ratioed")
        with wrap:
            reduce_btn = (
                ui.html(_control_svg("reduce"))
                .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-reduce")
                .mark(f"{cb.id}:reduce")
                .tooltip(tooltips.RATIO_REDUCE_HELP)
            )
            recip_btn = (
                ui.html(_control_svg("reciprocate"))
                .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-recip")
                .mark(f"{cb.id}:reciprocate")
                .tooltip(tooltips.RATIO_RECIPROCATE_HELP)
            )
        reduce_btn.on("click", lambda _=None, cid=cb.id: self._cb.transform_interval(cid, "reduce"))
        recip_btn.on(
            "click", lambda _=None, cid=cb.id: self._cb.transform_interval(cid, "reciprocate")
        )
        self.ratio_ops[cb.id] = (reduce_btn, recip_btn)
        self._sync_ratio_ops(cb.id, cb.text)

    def _sync_ratio_ops(self, cid: str, text: str) -> None:
        ops = self.ratio_ops.get(cid)
        if ops is None:
            return
        availability = service.interval_op_availability(text, self._editor.state.domain_basis)
        for btn, enabled in zip(ops, availability, strict=False):
            btn.classes(
                add="" if enabled else "rtt-op-disabled",
                remove="rtt-op-disabled" if enabled else "",
            )

    def _gridvalue_handlers(self, cb: spreadsheet.CellBox, spec: _GridValueSpec):
        fn = getattr(self._cb, spec.commit)
        if spec.cid_arg:

            def commit(_=None, cid=cb.id):
                return fn(cid)

            pv = getattr(self._cb, spec.preview) if spec.preview else None
            preview = (lambda _e=None, cid=cb.id: pv(cid)) if pv else None
        else:

            def commit(_=None):
                return fn()

            preview = (lambda _e=None: fn(preview=True)) if spec.preview else None
        return commit, preview

    def _arm_gridvalue(self, wrap, cb: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
        if spec.arm is None:
            return
        if spec.arm[0] == "row":
            self._arm_row_target(wrap, cb.gen)
        else:
            self._arm_col_target(wrap, spec.arm[1], cb.comma)

    def _update_gridvalue(self, cb: spreadsheet.CellBox) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        text = self._gridvalue_text(cb)
        if spec.ratio_allowed:
            self._update_fraction(cb, text)
        else:
            self.inputs[cb.id].value = text
        if spec.pending:
            target = self.els[cb.id] if spec.ratio_allowed else self.inputs[cb.id]
            target.classes(
                add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
            )

    def _update_fraction(self, cb: spreadsheet.CellBox, text: str) -> None:
        num, den = _ratio_parts(text) or (text, "")
        ratio = den not in ("", "1")
        self.inputs[cb.id].value = num
        self.den_inputs[cb.id].value = den if ratio else ""
        self.frac_edits[cb.id].props(f"data-fracmode={'ratio' if ratio else 'int'}")
        self._fit_fraction(cb.id, num, den, cb.w, ratio)
        self._sync_ratio_ops(cb.id, text)

    def _fit_fraction(self, cid: str, num: str, den: str, width: float, ratio: bool) -> None:
        size = (
            _ratio_font(num, den, width)
            if ratio
            else _digit_fit_font(len(num), width, float(_CELL_FONT))
        )
        style = f"font-size:{size:.2f}px"
        self.inputs[cid].style(style)
        self.den_inputs[cid].style(style)

    def _gridvalue_text(self, cb: spreadsheet.CellBox) -> str:
        if cb.pending and cb.kind in ("commacell", "mapping"):
            draft = (
                self._editor.pending_comma
                if cb.kind == "commacell"
                else self._editor.pending_mapping_row
            )
            v = draft[cb.prime] if draft is not None else None
            return "" if v is None else str(v)
        return "" if cb.blank else cb.text

    def _build_decimal(self, cb: spreadsheet.CellBox, wrap, commit, *, gen_index=None) -> None:
        wrap.classes("rtt-cell-input rtt-deccell")
        box = ui.element("div").classes("rtt-dec-edit")
        with box:
            with ui.element("div").classes("rtt-dec-main"):
                if gen_index is not None:
                    s = (
                        ui.label("")
                        .classes("rtt-gensign")
                        .mark(f"gensign:{gen_index}")
                        .on(
                            "click",
                            lambda _=None, i=gen_index: self._cb.act(
                                lambda: self._editor.flip_generator(i)
                            ),
                        )
                    )
                    self._preview_control(s, lambda gi=gen_index: self._editor.flip_generator(gi))
                    self.gensign_faces[cb.id] = s
                whole = (
                    ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-whole-in")
                )
            with ui.element("div").classes("rtt-dec-sub"):
                ui.label(".").classes("rtt-dec-dot")
                frac = ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-frac-in")
        whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.inputs[cb.id] = whole
        self.den_inputs[cb.id] = frac
        self.frac_edits[cb.id] = box

    def _update_decimal(self, cb: spreadsheet.CellBox, text: str, *, signed=False) -> None:
        if signed:
            sign, whole, frac = _gentuning_parts(text)
            if cb.id in self.gensign_faces:
                self.gensign_faces[cb.id].set_text(sign)
        else:
            whole, frac = _cents_parts(text)
        self.inputs[cb.id].value = whole
        self.den_inputs[cb.id].value = frac
        self.frac_edits[cb.id].props(f"data-decmode={'dec' if frac else 'int'}")
        fit_w = cb.w - _GENSIGN_W if signed else cb.w
        self.frac_edits[cb.id].style(
            f"--dec-whole-font:{_digit_fit_font(len(whole), fit_w, float(_CELL_FONT)):.2f}px"
        )

    def _build_prescalercell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda _e=None, cid=cb.id: self._cb.on_prescaler_change(cid))

    def _update_prescalercell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_weightcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda _e=None, cid=cb.id: self._cb.on_weight_change(cid))

    def _update_weightcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_powerinput(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = (
            ui.input(on_change=lambda _e, cid=cb.id: self._cb.on_power_change(cid))
            .props("dense borderless")
            .classes("rtt-cellinput")
        )
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerinput(self, cb: spreadsheet.CellBox) -> None:
        self.inputs[cb.id].value = cb.text
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_powerdisplay(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerdisplay(self, cb: spreadsheet.CellBox) -> None:
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_gentuningcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        i = int(cb.id.rsplit(":", 1)[1])
        self._build_decimal(
            cb, wrap, lambda _e=None, cid=cb.id: self._cb.on_gentuning_change(cid), gen_index=i
        )
        wrap.on(
            "wheel.prevent",
            lambda e, cid=cb.id: self._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
            args=["deltaY"],
        )
        wrap.on("mouseenter", lambda _=None, cid=cb.id: self._cb.gentuning_hover(cid))
        wrap.on("mouseleave", lambda _=None, cid=cb.id: self._cb.gentuning_unhover(cid))

    def _update_gentuningcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, "" if cb.blank else cb.text, signed=True)

    def _build_ptextedit(self, cb: spreadsheet.CellBox, _wrap) -> None:
        if cb.id.startswith("ptext:projection:"):
            inp = ui.input(value=cb.text).props("dense borderless").classes("rtt-ptextedit")
            inp.on(
                "blur",
                lambda _e=None, cid=cb.id: self._cb.on_ptext_edit(
                    cid, self.ptext_inputs[cid].value
                ),
            )
        else:
            inp = (
                ui.input(
                    value=cb.text,
                    on_change=lambda e, cid=cb.id: self._cb.on_ptext_edit(cid, e.value),
                )
                .props("dense borderless")
                .classes("rtt-ptextedit")
            )
        self.ptext_inputs[cb.id] = inp

    def _update_ptextedit(self, cb: spreadsheet.CellBox) -> None:
        self.ptext_inputs[cb.id].value = cb.text
        self.ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    def _build_genratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=True)

    def _build_commaratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=False)

    def _build_ratio_face(self, cb: spreadsheet.CellBox, wrap, approx: bool) -> None:
        if cb.pending:
            wrap.classes(add="rtt-pending")
        if cb.pending and cb.text in ("?", "?/?", ""):
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value rtt-pending-q")
        else:
            self._ratio(cb, approx=approx)

    def _update_ratio(self, cb: spreadsheet.CellBox) -> None:
        self.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )
        face = self.ratio_faces.get(cb.id)
        if face is None:
            return
        face.clear()
        self.fracs.pop(cb.id, None)
        self.labels.pop(cb.id, None)
        with face:
            self._ratio_body(cb, approx=(cb.kind == "genratio"))

    def _build_tuning_value(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.cents_face(cb, "rtt-tuning-value")

    def _update_tuning_value(self, cb: spreadsheet.CellBox) -> None:
        self.set_cents_face(cb.id, cb.text)
        self.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )

    def _label_builder(self, cls: str):
        def build(cb, _wrap):
            self.labels[cb.id] = ui.label(cb.text).classes(cls)

        return build

    def _update_label(self, cb: spreadsheet.CellBox) -> None:
        self.labels[cb.id].set_text(cb.text)
        self.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )

    def _update_ptext(self, cb: spreadsheet.CellBox) -> None:
        self.labels[cb.id].set_text(cb.text)
        self.labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    def _build_rangemode(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-rangemode")
        opts = {}
        for mode in ("monotone", "tradeoff"):
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")
                ui.label(mode).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, m=mode: self._cb.on_range_mode(m))
            opts[mode] = opt
        self.rangeopts[cb.id] = opts

    def _update_rangemode(self, cb: spreadsheet.CellBox) -> None:
        for mode, opt in self.rangeopts[cb.id].items():
            (
                opt.classes(add="rtt-rangeopt-on")
                if mode == cb.text
                else opt.classes(remove="rtt-rangeopt-on")
            )

    def _build_scheme_button(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.scheme_buttons[cb.id] = (
            ui.button(
                cb.text, on_click=lambda: self._cb.act(self._editor.back_to_scheme), color=None
            )
            .props("unelevated dense no-caps")
            .classes("rtt-scheme-btn")
        )

    def _update_scheme_button(self, cb: spreadsheet.CellBox) -> None:
        btn = self.scheme_buttons[cb.id]
        (
            btn.classes(add="rtt-scheme-btn-idle")
            if not self._editor.manual_tuning
            else btn.classes(remove="rtt-scheme-btn-idle")
        )

    def _build_foldtoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        item = cb.id.split("toggle:", 1)[1]
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
            "rtt-glyph rtt-toggle"
        )
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None, it=item: self._cb.on_toggle(it))

    def _build_alltoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
            "rtt-glyph rtt-toggle"
        )
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None: self._cb.on_toggle_all())

    def _update_foldtoggle(self, cb: spreadsheet.CellBox) -> None:
        if self.fold_state.get(cb.id) != cb.text:
            self.htmls[cb.id].set_content(_control_svg(_FOLD_GLYPH[cb.text]))
            self.fold_state[cb.id] = cb.text

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

    def _arm_option_hover(self, sel, wrap, cid: str) -> None:
        sel.add_slot(
            "option",
            f"""
            <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cid}">
                <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
            </q-item>
        """,
        )
        wrap.on("opthover", lambda e: self._cb.on_chooser_hover(cid, e.args), args=["detail"])
        sel.on("popup-show", lambda _=None: self._cb.on_popup(cid, True))
        sel.on("popup-hide", lambda _=None: self._cb.on_popup(cid, False))

    def _build_preset(self, cb: spreadsheet.CellBox, wrap) -> None:
        name = cb.id.split(":")[1]
        if name == "target":
            self._build_preset_target(cb, wrap)
        elif name == "temperament":
            self._build_preset_temperament(cb, wrap)
        else:
            options, value, prompt = self._scheme_options(cb, name)
            self._build_scheme_select(cb, wrap, options, value, prompt)

    def _build_preset_target(self, cb: spreadsheet.CellBox, wrap) -> None:
        limit, family = self._target_preset_values()
        with ui.element("div").classes("rtt-preset-target"):
            num = (
                ui.input(value=_limit_text(limit), on_change=lambda _e: self._cb.on_target_change())
                .props(
                    'dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300'
                )
                .classes("rtt-preset-num")
            )
            # make the limit input CONTROLLED (ui.input defaults loopback off, leaving the box
            # uncontrolled during typing). Off, the server can't overwrite what was typed, so a
            # rejected non-number couldn't be reverted nor a value reddened-in-place. On, the
            # server's value always wins — debounce keeps the echo to once-per-settled-entry.
            self._wire_target_limit(num, cb)
            sel = (
                ui.select(
                    list(presets.TARGET_SETS),
                    value=family,
                    on_change=lambda _e: self._cb.on_target_change(),
                )
                .props(_select_props(cb.w - 30))
                .classes("rtt-preset")
            )
        _set_offlist_prompt(sel, family)
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = (num, sel)

    def _wire_target_limit(self, num, cb: spreadsheet.CellBox) -> None:
        num.LOOPBACK = True
        num._props["loopback"] = True
        num.on(
            "wheel",
            lambda e: self._cb.on_target_limit_wheel(e.args.get("deltaY")),
            args=["deltaY"],
            js_handler=_INT_WHEEL_JS,
        )
        num.on("focus", lambda _=None: self._cb.on_cell_focus(cb.id))
        num.on("blur", lambda _=None, cid=cb.id: self._cb.on_cell_blur(cid))
        # Enter commits the typed limit. The field is debounce=300 + loopback-controlled, so its
        # value only settles to the server (firing the on_change commit) after a typing pause or
        # on blur — pressing Enter alone did nothing (the reported "Enter doesn't submit the
        # TILT/OLD number, only blur"). Blur the input on Enter: Quasar flushes the debounced
        # value at once (committing via on_change) and the native blur runs on_cell_blur. Pure
        # client-side, so it also works when the debounce hasn't yet elapsed.
        num.on("keydown.enter", js_handler="(e) => e.target.blur()")
        # ...and previews each keystroke LIVE the way a wheel notch does, reddening the rows the
        # typed limit would drop before the debounced commit reflows them away. on_change is the
        # debounced model-value (the commit); this must fire at once on each keystroke instead.
        # NOT the DOM `input` event: a Quasar QInput doesn't forward native `input` to a NiceGUI
        # `.on()` listener (it never reaches the socket — verified), so an `.on("input")` preview
        # silently never ran. `keyup` DOES fire on the QInput; and since NiceGUI's `args=` only
        # filters TOP-LEVEL event keys (it can't pull the nested `target.value`), mirror the
        # wheel's js_handler trick and emit the live DOM text ourselves — `e.args` is then the
        # typed string (the loopback-debounced model value lags a keystroke, so read the event).
        num.on(
            "keyup",
            lambda e: self._cb.on_target_limit_preview(e.args),
            js_handler="(e) => emit(e.target.value)",
        )

    def _build_preset_temperament(self, cb: spreadsheet.CellBox, wrap) -> None:
        value = presets.identify(self._editor.state)
        sel = (
            _GroupedSelect(
                presets.temperament_options(),
                value=value,
                is_divider=presets.is_divider,
                on_change=lambda e: self._cb.on_preset(cb.id, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        _set_offlist_prompt(sel, value)
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _scheme_options(self, cb: spreadsheet.CellBox, name: str) -> tuple[list, object, str]:
        if name == "prescaler":
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            return options, (value if value in options else None), "-"
        if name == "projection":
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            return options, (value if value in options else None), _projection_prompt(cb.id)
        options = presets.tuning_scheme_options(
            service.is_all_interval(self._editor.tuning_scheme),
            self._editor.settings["alt_complexity"],
            self._editor.settings["weighting"],
        )
        scheme = self._editor.displayed_tuning_scheme_name
        return options, (scheme if scheme in options else None), "-"

    def _build_scheme_select(self, cb, wrap, options, value, prompt) -> None:
        sel = (
            ui.select(options, value=value, on_change=lambda e: self._cb.on_preset(cb.id, e.value))
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        _set_offlist_prompt(sel, value, prompt)
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _chooser_reflow_hold(self, cid: str) -> bool:
        # True while a generic chooser hover's REFLOW preview is re-rendering the grid for THIS
        # chooser: the hovered chooser's q-select value + open popup must stay steady across that
        # re-render (re-setting a q-select's value / options would disrupt or close its open popup),
        # so the cell's update is skipped while it holds. Held by chooser GROUP, not exact id: a
        # preset and its copy (preset:tuning ⟷ preset:tuning:gens, preset:projection ⟷
        # preset:projection:gens — one selection shown in two tiles) must move together, else the
        # non-hovered twin would flip to the hypothetical value while the hovered one stays put, so
        # the two faces would disagree mid-preview. The group is the cid's first two ":"-segments
        # (the copy adds a 3rd), so the base + every copy share it. The generic-chooser analogue of
        # the temperament guard below, which groups its own copies via the "preset:temperament" prefix.
        g = self._cur_gesture
        if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
            return False

        def group(c):
            return ":".join(c.split(":")[:2])

        return group(cid) == group(g.source)

    def _update_preset(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        if cb.id.startswith("preset:temperament"):
            g = self._cur_gesture
            if g is not None and g.kind == "temp" and g.reflowed:
                return
            value = presets.identify(self._editor.state)
            self.selects[cb.id].value = value
            _set_offlist_prompt(self.selects[cb.id], value)
        elif cb.id == "preset:target":
            num, sel = self.selects[cb.id]
            limit, family = self._target_preset_values()
            num.value = _limit_text(limit)
            sel.value = family
            _set_offlist_prompt(sel, family)
            num.set_enabled(not cb.disabled)
            sel.set_enabled(not cb.disabled)
            self._sync_target_limit_error(num, family, limit)
        elif cb.id == "preset:prescaler":
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value)
            self.selects[cb.id].set_enabled(not cb.disabled)
        elif cb.id.startswith("preset:projection"):
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value, prompt=_projection_prompt(cb.id))
            self.selects[cb.id].set_enabled(not cb.disabled)
        else:
            name = self._editor.displayed_tuning_scheme_name
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme),
                self._editor.settings["alt_complexity"],
                self._editor.settings["weighting"],
            )
            scheme = name if name in options else None
            self.selects[cb.id].set_options(options, value=scheme)
            _set_offlist_prompt(self.selects[cb.id], scheme)
            self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_subpick(self, cb, wrap, options, value):
        sel = (
            ui.select(
                options,
                value=value if value in options else None,
                on_change=lambda e, cid=cb.id: self._cb.on_subpick(cid, e.value),
            )
            .props(_select_props(_SUBPICK_POPUP_W))
            .classes("rtt-preset rtt-subpick")
        )
        _set_offlist_prompt(sel, value if value in options else None)
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _build_etpick(self, cb, wrap):
        db = self._editor.state.domain_basis
        value = None if cb.pending else presets.identify_et(self._editor.state.mapping[cb.gen], db)
        self._build_subpick(cb, wrap, presets.et_options(db), value)

    def _build_commapick(self, cb, wrap):
        db = self._editor.state.domain_basis
        value = (
            None
            if cb.pending
            else presets.identify_comma(self._editor.state.comma_basis[cb.comma], db)
        )
        self._build_subpick(cb, wrap, presets.comma_options(db), value)

    def _update_subpick(self, cb):
        g = self._cur_gesture
        if g is not None and g.kind == "temp" and g.reflowed:
            return
        sel = self.selects.get(cb.id)
        if not isinstance(sel, ui.select):
            return
        db = self._editor.state.domain_basis
        if cb.id.startswith("etpick:"):
            options = presets.et_options(db)
            if cb.pending or cb.gen >= len(self._editor.state.mapping):
                value = None
            else:
                value = presets.identify_et(self._editor.state.mapping[cb.gen], db)
        else:
            options = presets.comma_options(db)
            if cb.pending or cb.comma >= len(self._editor.state.comma_basis):
                value = None
            else:
                value = presets.identify_comma(self._editor.state.comma_basis[cb.comma], db)
        value = value if value in options else None
        sel.set_options(options, value=value)
        _set_offlist_prompt(sel, value)

    def _sync_target_limit_error(self, num, family, limit) -> None:
        problem = service.target_limit_problem(family, limit)
        num.classes(
            add="rtt-limit-error" if problem else "", remove="" if problem else "rtt-limit-error"
        )
        if self.target_limit_tip is not None:
            self.target_limit_tip.set_text(
                tooltips.target_limit_help(problem)
                if problem
                else tooltips.control_help("preset", "preset:target")
            )
            self.target_limit_tip.classes(
                add="rtt-tip-error" if problem else "", remove="" if problem else "rtt-tip-error"
            )

    def _build_control_select(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = (
            ui.select(
                list(cb.values),
                value=cb.text or None,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _update_control_select(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.selects[cb.id].set_options(list(cb.values), value=cb.text or None)
        self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_control_check(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.checks[cb.id] = (
            ui.checkbox(
                cb.text,
                value=cb.checked,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value),
            )
            .props("dense")
            .classes("rtt-control-check")
        )
        apply = self._control_check_preview(cb)
        if apply is not None:
            self._preview_control(wrap, apply)

    def _control_check_preview(self, cb: spreadsheet.CellBox):
        if cb.id == "control:diminuator":
            return lambda: self._editor.set_diminuator_replaced(
                not service.diminuator_replaced(self._editor.tuning_scheme)
            )
        if cb.id == "control:all_interval":
            return lambda: self._editor.set_all_interval(
                not service.is_all_interval(self._editor.tuning_scheme)
            )
        return None

    def _update_control_check(self, cb: spreadsheet.CellBox) -> None:
        self.checks[cb.id].value = cb.checked

    def _build_formchooser(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = (
            ui.select(
                _formchooser_options(cb.id),
                value=cb.text or "",
                on_change=lambda e, c=cb.id: self._cb.on_form_choose(c, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _update_formchooser(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.selects[cb.id].set_options(_formchooser_options(cb.id), value=cb.text or "")

    def _preview_control(self, el, apply) -> None:
        el.on("mouseenter", lambda _=None: self._cb.control_hover(apply))
        el.on("mouseleave", lambda _=None: self._cb.control_unhover())

    def _preview_rank_remove(self, el, axis: str, idx: int) -> None:
        el.on("mouseenter", lambda _=None: self._cb.rank_remove_hover(axis, idx))
        el.on("mouseleave", lambda _=None: self._cb.rank_remove_unhover())

    def _build_minus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click", lambda _=None: self._cb.act(self._editor.shrink)
        )
        self._preview_control(wrap, self._editor.shrink)

    def _build_plus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn").on(
            "click", lambda _=None: self._cb.act(self._editor.expand)
        )
        self._preview_control(wrap, self._editor.expand)

    def _build_gen_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click",
            lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)),
        )
        self._preview_rank_remove(wrap, "row", cb.gen)

    def _build_gen_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping")
        )

    def _build_map_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        if cb.pending:
            ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
                "click", lambda _=None: self._cb.act(self._editor.cancel_pending_mapping_row)
            )
            return
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
            "click",
            lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)),
        )
        self._preview_rank_remove(wrap, "row", cb.gen)

    def _build_map_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping")
        )

    def _build_map_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
        # HTML5 drag-to-combine, built EXACTLY like the working column-reorder grip (_build_colgrip):
        # the grip is BOTH the drag SOURCE and a drop TARGET, with a per-element dragover preventDefault
        # marking it a valid drop target. This is the proven path — drop one row's GRIP onto another's
        # to add it in. (A Quasar INPUT cell is not a reliable native drop target; reorder hit the same
        # wall and drops grip-to-grip too. The mapping cells are ALSO armed via _arm_row_target so
        # hovering the row itself previews/accepts where the browser allows it, but the grip always
        # works.) dragstart records the source row + effectAllowed='copy'/setData (copy cursor; Firefox
        # drag-start); dragenter previews; drop commits; dragend clears. src==idx (own row) is a no-op.
        # NOTE: no js dragstart — exactly like reorder. We do NOT set effectAllowed (leaving it the
        # default 'uninitialized', which permits ALL drops incl. copy). Setting effectAllowed='copy'
        # here previously LEFT IT 'none' and blocked every drop — the merge regression. dropEffect on
        # dragover still requests the + (copy) cursor, allowed under 'uninitialized'.
        wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, idx=cb.gen: self._begin_row_drag(idx))
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, idx=cb.gen: self._preview_row_drop(idx))
        wrap.on("dragend", lambda _=None: self._end_row_drag())
        wrap.on("drop.prevent", lambda _=None, idx=cb.gen: self._drop_on_row(idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_row_target(self, wrap, gen: int) -> None:
        # the mapping row is the drop target for a dragged generator row: dragover keeps every cell a
        # droppable copy surface (preventDefault makes a drop land here; dropEffect='copy' gives the +
        # cursor), dragenter previews dropping the dragged row INTO this row, drop commits it. The py
        # preview/drop are no-ops unless a row drag is actually in flight (_row_drag set), so a
        # non-combine drag — or a row over its own cells — passing over a cell changes nothing.
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, idx=gen: self._preview_row_drop(idx))
        wrap.on("drop.prevent", lambda _=None, idx=gen: self._drop_on_row(idx))

    def _begin_row_drag(self, idx: int) -> None:
        self._row_drag = idx
        self._cb.combine_begin()

    def _end_row_drag(self) -> None:
        self._row_drag = None
        self._cb.combine_end()

    def _preview_row_drop(self, idx: int) -> None:
        src = self._row_drag
        valid = src is not None and src != idx
        apply = (lambda: self._editor.add_mapping_row_to(src, idx)) if valid else None
        target = (
            (lambda cb: cb.kind == "mapping" and getattr(cb, "gen", None) == idx) if valid else None
        )
        self._cb.combine_preview(apply, target)

    def _drop_on_row(self, idx: int) -> None:
        src = self._row_drag
        self._row_drag = None
        if src is not None and src != idx:
            self._cb.combine_commit(lambda: self._editor.add_mapping_row_to(src, idx))
        else:
            self._cb.combine_end()

    _INTERVAL_COMBINE: ClassVar[dict[str, str]] = {
        "comma": "add_comma_to",
        "target": "add_target_to",
        "held": "add_held_to",
        "interest": "add_interest_to",
    }

    def _build_int_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
        group = cb.id.split(":")[1]
        wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, g=group, idx=cb.comma: self._begin_col_drag(g, idx))
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on(
            "dragenter.prevent",
            lambda _=None, g=group, idx=cb.comma: self._preview_int_drop(g, idx),
        )
        wrap.on("dragend", lambda _=None: self._end_col_drag())
        wrap.on(
            "drop.prevent", lambda _=None, g=group, idx=cb.comma: self._drop_on_interval(g, idx)
        )
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_col_target(self, wrap, group: str, idx: int) -> None:
        wrap.on(
            "dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}"
        )
        wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: self._preview_int_drop(g, i))
        wrap.on("drop.prevent", lambda _=None, g=group, i=idx: self._drop_on_interval(g, i))

    def _int_combine(self, group: str, idx: int):
        if self._col_drag is None:
            return None
        src_group, src = self._col_drag
        if src_group != group or src == idx:
            return None
        combine = getattr(self._editor, self._INTERVAL_COMBINE[group])
        return lambda: combine(src, idx)

    def _begin_col_drag(self, group: str, idx: int) -> None:
        self._col_drag = (group, idx)
        self._cb.combine_begin()

    def _end_col_drag(self) -> None:
        self._col_drag = None
        self._cb.combine_end()

    _GROUP_CELL_KIND: ClassVar[dict[str, str]] = {
        "comma": "commacell",
        "target": "targetcell",
        "held": "heldcell",
        "interest": "interestcell",
    }

    def _preview_int_drop(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        kind = self._GROUP_CELL_KIND[group]
        target = (
            (lambda cb: cb.kind == kind and getattr(cb, "comma", None) == idx)
            if apply is not None
            else None
        )
        self._cb.combine_preview(apply, target)

    def _drop_on_interval(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        self._col_drag = None
        if apply is not None:
            self._cb.combine_commit(apply)
        else:
            self._cb.combine_end()

    def _build_basis_minus(self, _cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v").on(
            "click", lambda _=None: self._cb.act(self._editor.shrink)
        )
        self._preview_control(wrap, self._editor.shrink)

    def _build_comma_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb,
            wrap,
            self._editor.cancel_pending_comma,
            self._editor.remove_comma,
            rank_axis="comma",
        )

    def _build_comma_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-comma").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_comma, "comma")
        )

    def _build_element_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-element").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_element, "element")
        )

    def _build_element_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        action = (
            self._editor.remove_element
            if cb.id.endswith(":pending")
            else (lambda idx=cb.prime: self._editor.remove_domain_element(idx))
        )
        btn = "rtt-minus-btn-v" if ":basis" in cb.id else "rtt-minus-btn"
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes(f"rtt-glyph {btn}").on(
            "click", lambda _=None: self._cb.act(action)
        )
        self._preview_control(wrap, action)

    def _build_list_minus(
        self, cb: spreadsheet.CellBox, wrap, cancel, remove, rank_axis: str | None = None
    ) -> None:
        pending = cb.id.endswith(":pending")
        action = cancel if pending else (lambda idx=cb.comma: remove(idx))
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn").on(
            "click", lambda _=None: self._cb.act(action)
        )
        if rank_axis is not None and not pending:
            self._preview_rank_remove(wrap, rank_axis, cb.comma)
        else:
            self._preview_control(wrap, action)

    def _build_interest_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb, wrap, self._editor.cancel_pending_interest, self._editor.remove_interest
        )

    def _build_interest_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-interest").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_interest, "interest")
        )

    def _build_held_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_held, self._editor.remove_held)

    def _build_held_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-held").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_held, "held")
        )

    def _build_target_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(
            cb, wrap, self._editor.cancel_pending_target, self._editor.remove_target
        )

    def _build_target_plus(self, _cb: spreadsheet.CellBox, _wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-target").on(
            "click", lambda _=None: self._cb.add_interval(self._editor.add_target, "target")
        )

    def _build_colgrip(self, cb: spreadsheet.CellBox, wrap) -> None:
        # drag one column's grip onto another to MOVE/reorder it; the per-list "grip:{list}:add" zone
        # is drop-only — the append / into-empty-list target on the stub gridline, so dropping into a
        # list is always "drop on the gridline" (no separate header/+ target). Mirrors the proven
        # drag-to-combine handle EXACTLY (which the user confirmed works), so it relies on no global
        # drag.js / dragging-class: a grip is BOTH source AND drop target, with a per-element dragover
        # preventDefault (client-side, so it doesn't round-trip per move) marking it a valid target.
        # The dragged column's (list, idx) is held server-side from dragstart through drop.
        _, lst, tail = cb.id.split(":")
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")
        if tail == "add":
            wrap.classes("rtt-colgrip rtt-coldrop")
            wrap.on(
                "dragenter.prevent", lambda _=None, which=lst: self._cb.on_drag_enter(which, None)
            )
            wrap.on("drop.prevent", lambda _=None, which=lst: self._cb.on_drop(which, None))
            return
        idx = cb.comma
        wrap.classes("rtt-drag-handle rtt-colgrip").props("draggable=true")
        wrap.on("dragstart", lambda _=None, which=lst, i=idx: self._cb.on_drag_start(which, i))
        wrap.on(
            "dragenter.prevent", lambda _=None, which=lst, i=idx: self._cb.on_drag_enter(which, i)
        )
        wrap.on("dragend", lambda _=None: self._cb.on_drag_end())
        wrap.on("drop.prevent", lambda _=None, which=lst, i=idx: self._cb.on_drop(which, i))
        ui.icon("drag_indicator").classes("rtt-grip")



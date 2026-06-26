from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Protocol, cast, runtime_checkable

from nicegui import ui

from rtt.app import _recon_buttons as buttons
from rtt.app import _recon_choosers as choosers
from rtt.app import _recon_display as display
from rtt.app import _recon_drag as drag
from rtt.app import _recon_value as value
from rtt.app import (
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_handles import EMPTY as _EMPTY_HANDLES
from rtt.app._recon_handles import EMPTY_ENTITY as _EMPTY_ENTITY
from rtt.app._recon_handles import CellHandles, EntityHandles
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

_Cb = Callable[..., object]


@runtime_checkable
class ReconcilerCallbacks(Protocol):
    act: _Cb
    add_interval: _Cb
    on_preset: _Cb
    on_subpick: _Cb
    on_form_choose: _Cb
    on_target_change: _Cb
    on_control_select: _Cb
    on_range_mode: _Cb
    on_toggle: _Cb
    on_toggle_all: _Cb

    on_power_change: _Cb
    on_gentuning_change: _Cb
    on_gentuning_wheel: _Cb
    on_value_wheel: _Cb
    on_target_limit_wheel: _Cb
    on_target_limit_preview: _Cb
    on_prescaler_change: _Cb
    on_weight_change: _Cb
    on_ptext_edit: _Cb

    on_mapping_change: _Cb
    on_form_change: _Cb
    on_comma_change: _Cb
    on_unchanged_change: _Cb
    on_interest_change: _Cb
    on_held_change: _Cb
    on_target_cells_change: _Cb
    on_ratio_change: _Cb
    on_element_change: _Cb
    on_element_preview: _Cb
    transform_interval: _Cb

    on_cell_focus: _Cb
    on_cell_blur: _Cb
    combine_begin: _Cb
    combine_preview: _Cb
    combine_commit: _Cb
    combine_end: _Cb
    control_hover: _Cb
    control_unhover: _Cb
    rank_remove_hover: _Cb
    rank_remove_unhover: _Cb
    on_chooser_hover: _Cb
    on_popup: _Cb
    gentuning_hover: _Cb
    gentuning_unhover: _Cb
    on_drag_start: _Cb
    on_drag_enter: _Cb
    on_drag_end: _Cb
    on_drop: _Cb


def required_callback_names() -> frozenset[str]:
    return frozenset(ReconcilerCallbacks.__annotations__)


def _marked_providers(sources: tuple[object, ...], name: str) -> list[_Cb]:
    return [
        method
        for source in sources
        if getattr((method := getattr(source, name, None)), "_rtt_cb", False)
    ]


def _raise_on_binding_problems(unbound: list[str], duplicated: list[str]) -> None:
    problems = []
    if unbound:
        problems.append(f"unbound (renamed or missing @cb_method): {sorted(unbound)}")
    if duplicated:
        problems.append(f"bound on multiple sources: {sorted(duplicated)}")
    if problems:
        raise RuntimeError("reconciler callbacks " + "; ".join(problems))


def bind_callbacks(*sources: object) -> ReconcilerCallbacks:
    bound: dict[str, _Cb] = {}
    unbound: list[str] = []
    duplicated: list[str] = []
    for name in required_callback_names():
        providers = _marked_providers(sources, name)
        if not providers:
            unbound.append(name)
        elif len(providers) > 1:
            duplicated.append(name)
        else:
            bound[name] = providers[0]
    _raise_on_binding_problems(unbound, duplicated)
    return cast("ReconcilerCallbacks", SimpleNamespace(**bound))


class _Reconciler:
    def __init__(self, editor: Editor, gestures=None) -> None:
        self._editor = editor
        self._gestures = gestures
        self._cb: ReconcilerCallbacks | None = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self.pretransform = False
        self._init_handles()
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
        self.cells: dict[str, CellHandles] = {}
        self.entities: dict[str, EntityHandles] = {}
        self.target_limit_tip = None

    def _register_display_kinds(self) -> None:
        for _ebk_kind in _EBK_SVG_KINDS:
            self.cell_kinds[_ebk_kind] = _KindHandlers(display.build_svgfill, display.update_ebk)
        self.cell_kinds["chart"] = _KindHandlers(display.build_svgfill, display.update_chart)
        self.cell_kinds["rangechart"] = _KindHandlers(
            display.build_svgfill, display.update_rangechart
        )

        self.cell_kinds["count"] = _KindHandlers(display.build_count, display.update_mathcell)
        self.cell_kinds["symbol"] = _KindHandlers(display.build_symbol, display.update_mathcell)
        self.cell_kinds["matlabel"] = _KindHandlers(display.build_matlabel, display.update_mathcell)
        self.cell_kinds["units"] = _KindHandlers(display.build_units, display.update_mathcell)
        self.cell_kinds["caption"] = _KindHandlers(display.build_caption, display.update_caption)

        self.cell_kinds["ptextpending"] = _KindHandlers(
            display.build_ptextpending, display.update_ptextpending
        )
        self.cell_kinds["mathexpr"] = _KindHandlers(display.build_mathexpr, display.update_mathexpr)

    def _register_value_kinds(self) -> None:
        _gridvalue = _KindHandlers(value.build_gridvalue, value.update_gridvalue)
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
            value.build_prescalercell, value.update_prescalercell
        )
        self.cell_kinds["weightcell"] = _KindHandlers(
            value.build_weightcell, value.update_weightcell
        )
        self.cell_kinds["powerinput"] = _KindHandlers(
            value.build_powerinput, value.update_powerinput
        )
        self.cell_kinds["powerdisplay"] = _KindHandlers(
            value.build_powerdisplay, value.update_powerdisplay
        )
        self.cell_kinds["gentuningcell"] = _KindHandlers(
            value.build_gentuningcell, value.update_gentuningcell
        )

        self.cell_kinds["ptextedit"] = _KindHandlers(value.build_ptextedit, value.update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(value.build_genratio, value.update_ratio)
        self.cell_kinds["ratiocell"] = _gridvalue
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(value.build_commaratio, value.update_ratio)
        self.cell_kinds["tuningvalue"] = _KindHandlers(
            value.build_tuning_value, value.update_tuning_value
        )

    def _register_label_kinds(self) -> None:
        _value_builder = value.label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, value.update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, value.update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, value.update_label)
        self.cell_kinds["colheader"] = _KindHandlers(
            value.label_builder("rtt-colheader"), value.update_label
        )
        self.cell_kinds["rowlabel"] = _KindHandlers(
            value.label_builder("rtt-rowlabel"), value.update_label
        )
        self.cell_kinds["ptext"] = _KindHandlers(
            value.label_builder("rtt-ptext"), value.update_ptext
        )
        self.cell_kinds["transpose"] = _KindHandlers(
            value.label_builder("rtt-transpose"), value.update_label
        )
        self.cell_kinds["boxtitle"] = _KindHandlers(value.label_builder("rtt-boxtitle"), None)

    def _register_control_kinds(self) -> None:
        self.cell_kinds["rangemode"] = _KindHandlers(
            choosers.build_rangemode, choosers.update_rangemode
        )
        self.cell_kinds["scheme_button"] = _KindHandlers(
            choosers.build_scheme_button, choosers.update_scheme_button
        )
        self.cell_kinds["rowtoggle"] = _KindHandlers(
            choosers.build_foldtoggle, choosers.update_foldtoggle
        )
        self.cell_kinds["coltoggle"] = _KindHandlers(
            choosers.build_foldtoggle, choosers.update_foldtoggle
        )
        self.cell_kinds["tiletoggle"] = _KindHandlers(
            choosers.build_foldtoggle, choosers.update_foldtoggle
        )
        self.cell_kinds["alltoggle"] = _KindHandlers(
            choosers.build_alltoggle, choosers.update_foldtoggle
        )

        self.cell_kinds["preset"] = _KindHandlers(choosers.build_preset, choosers.update_preset)
        self.cell_kinds["etpick"] = _KindHandlers(choosers.build_etpick, choosers.update_subpick)
        self.cell_kinds["commapick"] = _KindHandlers(
            choosers.build_commapick, choosers.update_subpick
        )
        self.cell_kinds["control_select"] = _KindHandlers(
            choosers.build_control_select, choosers.update_control_select
        )
        self.cell_kinds["control_check"] = _KindHandlers(
            choosers.build_control_check, choosers.update_control_check
        )
        self.cell_kinds["formchooser"] = _KindHandlers(
            choosers.build_formchooser, choosers.update_formchooser
        )

    def _register_button_kinds(self) -> None:
        self.cell_kinds["minus"] = _KindHandlers(buttons.build_minus)
        self.cell_kinds["plus"] = _KindHandlers(buttons.build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(buttons.build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(buttons.build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(buttons.build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(buttons.build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(drag.build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(drag.build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(buttons.build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(buttons.build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(buttons.build_comma_plus)
        self.cell_kinds["element_plus"] = _KindHandlers(buttons.build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(buttons.build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(buttons.build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(buttons.build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(buttons.build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(buttons.build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(buttons.build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(buttons.build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(buttons.build_colgrip)

    def drop(self, eid: str) -> None:
        self.entities[eid].el.delete()
        self.cells.pop(eid, None)
        self.entities.pop(eid, None)

    def _attach_guide_link(self, wrap, gh: tooltips.GuideHelp, tile: str, text: str) -> None:
        # Quasar: a ui.tooltip hides the moment the cursor leaves the cell toward it, so its link can't
        # be clicked; these data-attrs feed a custom body-level hover-card (_GUIDE_JS) that stays open.
        wrap.classes("rtt-guide-link")
        wrap._props["data-guide-text"] = text
        wrap._props["data-guide-tile"] = tile
        if gh.url:
            wrap._props["data-guide-loc"] = gh.location
            wrap._props["data-guide-url"] = gh.url

    def make_cell(self, cb: spreadsheet.CellBox) -> None:
        self.cells[cb.id] = CellHandles()
        self.entities[cb.id] = EntityHandles()
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            self.cell_kinds[cb.kind].build(self, cb, wrap)
            if cb.audio is not None:
                self._tag_audio(wrap, cb)
        self._attach_hover_help(wrap, cb)
        self.entities[cb.id].el = wrap
        self.cells[cb.id].kind = cb.kind
        self._wire_cell_input(wrap, cb)

    def _attach_hover_help(self, wrap, cb: spreadsheet.CellBox) -> None:
        plain = tooltips.control_help(cb.kind, cb.id)
        relabeled = tooltips.control_help(cb.kind, cb.id, pretransform=True)
        help_text = relabeled if self.pretransform else plain
        if cb.kind in VALUE_KINDS:
            wrap.classes("rtt-zoomable")
            if help_text:
                wrap._props["data-zoomhelp"] = help_text
        elif help_text:
            if cb.id in tooltips.MEAN_DAMAGE_IDS:
                with wrap:
                    self.cells[cb.id].mean_damage_tip = ui.tooltip(help_text)
            elif cb.id == "preset:target":
                with wrap:
                    self.target_limit_tip = ui.tooltip(help_text)
            elif plain != relabeled:
                with wrap:
                    self.cells[cb.id].help_tip = (ui.tooltip(help_text), plain, relabeled)
            else:
                wrap.tooltip(help_text)
        if cb.kind in ("symbol", "caption"):
            gh = tooltips.tile_guide_help_for_cell(cb.id)
            if gh is not None:
                gh_pt = tooltips.tile_guide_help_for_cell(cb.id, pretransform=True)
                text = gh_pt.text if self.pretransform else gh.text
                self._attach_guide_link(wrap, gh, cb.id.split(":", 1)[1], text)
                if gh.text != gh_pt.text:
                    self.cells[cb.id].guide_help_text = (gh.text, gh_pt.text)

    def _wire_cell_input(self, wrap, cb: spreadsheet.CellBox) -> None:
        if cb.kind.endswith(("plus", "minus")):
            wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
        edit_input = self.cells[cb.id].value.input or self.cells[cb.id].value.ptext_input
        if edit_input is not None:
            den = self.cells[cb.id].value.den_input
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
            handlers.update(self, cb)
        if cb.unit:
            if self.cells[cb.id].cell_unit is None:
                with self.entities[cb.id].el:
                    self.cells[cb.id].cell_unit = ui.html("").classes("rtt-cellunit")
                self.entities[cb.id].el.classes(add="rtt-cell-united")
            if self.cells[cb.id].cell_unit_text != (cb.unit, cb.w):
                self.cells[cb.id].cell_unit.set_content(_bold_units(cb.unit))
                self.cells[cb.id].cell_unit.style(
                    f"font-size:{_units_font(cb.unit, cb.w, _CELLUNIT_MAX_FONT):.2f}px"
                )
                self.cells[cb.id].cell_unit_text = (cb.unit, cb.w)
        elif self.cells[cb.id].cell_unit is not None:
            self.cells[cb.id].cell_unit.delete()
            self.cells[cb.id].cell_unit = None
            self.cells[cb.id].cell_unit_text = None
            self.entities[cb.id].el.classes(remove="rtt-cell-united")
        if cb.audio is not None:
            self._tag_audio(self.entities[cb.id].el, cb)

    def _tag_audio(self, el, cb: spreadsheet.CellBox) -> None:
        tile, idx, cents = cb.audio
        el.classes(add="rtt-spk").props(
            f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"'
        )

    def handles(self, cid: str) -> CellHandles:
        return self.cells.get(cid, _EMPTY_HANDLES)

    def entity(self, eid: str) -> EntityHandles:
        return self.entities.get(eid, _EMPTY_ENTITY)

    def cell_value(self, cid: str) -> str:
        num = str(self.cells[cid].value.input.value).strip()
        if not num:
            return ""
        if num == "?":
            return "?/?"
        if "/" in num:
            return num
        den = (
            str(self.cells[cid].value.den_input.value).strip()
            if self.cells[cid].value.den_input
            else ""
        )
        return num if den in ("", "1", "?") else f"{num}/{den}"

    def decimal_value(self, cid: str) -> str:
        whole = str(self.cells[cid].value.input.value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = (
            str(self.cells[cid].value.den_input.value).strip().lstrip(".")
            if self.cells[cid].value.den_input
            else ""
        )
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.cells[cid].value.input.value = whole
        if self.cells[cid].value.den_input:
            self.cells[cid].value.den_input.value = frac

    def _target_preset_values(self):
        if self._editor.target_override is not None or service.is_all_interval(
            self._editor.tuning_scheme
        ):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:
            state = self._editor.state
            limit = service.default_target_limit(family, state.domain_basis)
        return limit, family

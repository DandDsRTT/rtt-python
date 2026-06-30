from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Protocol, cast, runtime_checkable

from nicegui import ui

from rtt.app import _recon_cells, _recon_kinds, spreadsheet
from rtt.app._recon_handles import EMPTY as _EMPTY_HANDLES
from rtt.app._recon_handles import EMPTY_ENTITY as _EMPTY_ENTITY
from rtt.app._recon_handles import CellHandles, EntityHandles
from rtt.app.editor import Editor
from rtt.app.page_assets import (
    _CELLUNIT_MAX_FONT,
    _KindHandlers,
)
from rtt.app.render_html import (
    _bold_units,
    _cents_parts,
    _units_font,
)

_log = logging.getLogger(__name__)

_Cb = Callable[..., object]


_DEMO_VALUE_KINDS = frozenset(
    {
        "mapping",
        "mapped",
        "vector",
        "targetcell",
        "heldcell",
        "commacell",
        "interestcell",
        "unchangedcell",
    }
)


def _stamp_value(wrap, cell_box: spreadsheet.CellBox) -> None:
    if cell_box.kind in _DEMO_VALUE_KINDS:
        wrap.props(f'data-value="{cell_box.text}"')


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
    on_plain_text_edit: _Cb

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
        self._cell_box: ReconcilerCallbacks | None = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self.pretransform = False
        self.cells: dict[str, CellHandles] = {}
        self.entities: dict[str, EntityHandles] = {}
        self.target_limit_tip = None
        self.cell_kinds: dict[str, _KindHandlers] = {}
        _recon_kinds.register_display_kinds(self.cell_kinds)
        _recon_kinds.register_value_kinds(self.cell_kinds)
        _recon_kinds.register_label_kinds(self.cell_kinds)
        _recon_kinds.register_control_kinds(self.cell_kinds)
        _recon_kinds.register_button_kinds(self.cell_kinds)

    @property
    def _cur_gesture(self):
        return _recon_cells.cur_gesture(self._gestures)

    def drop(self, element_id: str) -> None:
        self.entities[element_id].element.delete()
        self.cells.pop(element_id, None)
        self.entities.pop(element_id, None)

    def make_cell(self, cell_box: spreadsheet.CellBox) -> None:
        self.cells[cell_box.id] = CellHandles()
        self.entities[cell_box.id] = EntityHandles()
        wrap = (
            ui.element("div")
            .classes("rtt-cell")
            .props(f'data-eid="{cell_box.id}"')
            .mark(cell_box.id)
        )
        with wrap:
            self.cell_kinds[cell_box.kind].build(self, cell_box, wrap)
            if cell_box.audio is not None:
                _recon_cells.tag_audio(wrap, cell_box)
        _recon_cells.attach_hover_help(self, wrap, cell_box)
        self.entities[cell_box.id].element = wrap
        self.cells[cell_box.id].kind = cell_box.kind
        _stamp_value(wrap, cell_box)
        _recon_cells.wire_cell_input(self, wrap, cell_box)

    def update_cell(self, cell_box: spreadsheet.CellBox) -> None:
        handlers = self.cell_kinds[cell_box.kind]
        if handlers.update is not None:
            handlers.update(self, cell_box)
        if cell_box.unit:
            if self.cells[cell_box.id].cell_unit is None:
                with self.entities[cell_box.id].element:
                    self.cells[cell_box.id].cell_unit = ui.html("").classes("rtt-cellunit")
                self.entities[cell_box.id].element.classes(add="rtt-cell-united")
            if self.cells[cell_box.id].cell_unit_text != (cell_box.unit, cell_box.width):
                self.cells[cell_box.id].cell_unit.set_content(_bold_units(cell_box.unit))
                self.cells[cell_box.id].cell_unit.style(
                    f"font-size:{_units_font(cell_box.unit, cell_box.width, _CELLUNIT_MAX_FONT):.2f}px"
                )
                self.cells[cell_box.id].cell_unit_text = (cell_box.unit, cell_box.width)
        elif self.cells[cell_box.id].cell_unit is not None:
            self.cells[cell_box.id].cell_unit.delete()
            self.cells[cell_box.id].cell_unit = None
            self.cells[cell_box.id].cell_unit_text = None
            self.entities[cell_box.id].element.classes(remove="rtt-cell-united")
        if cell_box.audio is not None:
            _recon_cells.tag_audio(self.entities[cell_box.id].element, cell_box)
        _stamp_value(self.entities[cell_box.id].element, cell_box)

    def handles(self, cell_id: str) -> CellHandles:
        return self.cells.get(cell_id, _EMPTY_HANDLES)

    def entity(self, element_id: str) -> EntityHandles:
        return self.entities.get(element_id, _EMPTY_ENTITY)

    def cell_value(self, cell_id: str) -> str:
        num = str(self.cells[cell_id].value.input.value).strip()
        if not num:
            return ""
        if num == "?":
            return "?/?"
        if "/" in num:
            return num
        den = (
            str(self.cells[cell_id].value.den_input.value).strip()
            if self.cells[cell_id].value.den_input
            else ""
        )
        return num if den in ("", "1", "?") else f"{num}/{den}"

    def decimal_value(self, cell_id: str) -> str:
        whole = str(self.cells[cell_id].value.input.value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = (
            str(self.cells[cell_id].value.den_input.value).strip().lstrip(".")
            if self.cells[cell_id].value.den_input
            else ""
        )
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cell_id: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.cells[cell_id].value.input.value = whole
        if self.cells[cell_id].value.den_input:
            self.cells[cell_id].value.den_input.value = frac

    def _target_preset_values(self):
        return _recon_cells.target_preset_values(self._editor)

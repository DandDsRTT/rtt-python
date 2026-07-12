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
        "target_cell",
        "held_cell",
        "comma_cell",
        "interest_cell",
        "unchanged_cell",
    }
)


_ROLE_BY_KIND = {"column_header": "columnheader", "row_label": "rowheader"}


def _cell_role(cell: spreadsheet.Cell) -> str | None:
    if cell.in_grid:
        return "gridcell"
    return _ROLE_BY_KIND.get(cell.kind)


def _stamp_value(wrap, cell: spreadsheet.Cell) -> None:
    if cell.kind in _DEMO_VALUE_KINDS:
        wrap.props(f'data-value="{cell.text}"')
    if cell.matrix:
        wrap.props(f'data-mx="{cell.matrix}" data-mxo="{cell.matrix_orient}"')
    if cell.aria:
        wrap.props(f'aria-label="{cell.aria.replace(chr(34), chr(39))}"')


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
    on_generator_tuning_change: _Cb
    on_generator_tuning_wheel: _Cb
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
    on_chooser_hover: _Cb
    on_popup: _Cb
    generator_tuning_hover: _Cb
    generator_tuning_unhover: _Cb
    on_drag_start: _Cb
    on_drag_enter: _Cb
    on_drag_end: _Cb
    on_drop: _Cb
    on_band_drag_start: _Cb
    on_band_drag_end: _Cb
    on_band_drop: _Cb


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
        self._callbacks: ReconcilerCallbacks | None = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self._element_drag: tuple[str, int] | None = None
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

    def build_cell(self, cell: spreadsheet.Cell) -> None:
        self.cells[cell.id] = CellHandles()
        self.entities[cell.id] = EntityHandles()
        wrap = (
            ui.element("div")
            .classes("rtt-cell" + (" rtt-gridval" if cell.in_grid else ""))
            .props(f'data-eid="{cell.id}"')
            .mark(cell.id)
        )
        role = _cell_role(cell)
        if role:
            wrap.props(f'role="{role}"')
        with wrap:
            self.cell_kinds[cell.kind].build(self, cell, wrap)
            if cell.audio is not None:
                _recon_cells.tag_audio(wrap, cell)
        _recon_cells.attach_hover_help(self, wrap, cell)
        self.entities[cell.id].element = wrap
        self.cells[cell.id].kind = cell.kind
        _stamp_value(wrap, cell)
        _recon_cells.wire_cell_input(self, wrap, cell)

    def update_cell(self, cell: spreadsheet.Cell) -> None:
        handlers = self.cell_kinds[cell.kind]
        if handlers.update is not None:
            handlers.update(self, cell)
        if cell.unit:
            if self.cells[cell.id].cell_unit is None:
                with self.entities[cell.id].element:
                    self.cells[cell.id].cell_unit = ui.html("").classes("rtt-cell-unit")
                self.entities[cell.id].element.classes(add="rtt-cell-united")
            if self.cells[cell.id].cell_unit_text != (cell.unit, cell.width):
                self.cells[cell.id].cell_unit.set_content(_bold_units(cell.unit))
                self.cells[cell.id].cell_unit.style(
                    f"font-size:{_units_font(cell.unit, cell.width, _CELLUNIT_MAX_FONT):.2f}px"
                )
                self.cells[cell.id].cell_unit_text = (cell.unit, cell.width)
        elif self.cells[cell.id].cell_unit is not None:
            self.cells[cell.id].cell_unit.delete()
            self.cells[cell.id].cell_unit = None
            self.cells[cell.id].cell_unit_text = None
            self.entities[cell.id].element.classes(remove="rtt-cell-united")
        if cell.audio is not None:
            _recon_cells.tag_audio(self.entities[cell.id].element, cell)
        _stamp_value(self.entities[cell.id].element, cell)

    def handles(self, cell_id: str) -> CellHandles:
        return self.cells.get(cell_id, _EMPTY_HANDLES)

    def entity(self, element_id: str) -> EntityHandles:
        return self.entities.get(element_id, _EMPTY_ENTITY)

    def cell_value(self, cell_id: str) -> str:
        numerator = str(self.cells[cell_id].value.input.value).strip()
        if not numerator:
            return ""
        if numerator == "?":
            return "?/?"
        if "/" in numerator:
            return numerator
        denominator = (
            str(self.cells[cell_id].value.denominator_input.value).strip()
            if self.cells[cell_id].value.denominator_input
            else ""
        )
        return numerator if denominator in ("", "1", "?") else f"{numerator}/{denominator}"

    def decimal_value(self, cell_id: str) -> str:
        whole = str(self.cells[cell_id].value.input.value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = (
            str(self.cells[cell_id].value.denominator_input.value).strip().lstrip(".")
            if self.cells[cell_id].value.denominator_input
            else ""
        )
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cell_id: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.cells[cell_id].value.input.value = whole
        if self.cells[cell_id].value.denominator_input:
            self.cells[cell_id].value.denominator_input.value = frac

    def _target_preset_values(self):
        return _recon_cells.target_preset_values(self._editor)

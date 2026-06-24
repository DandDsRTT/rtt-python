from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EntityHandles:
    el: object = None
    styled: object = None
    ring_sig: object = None


@dataclass
class ValueHandles:
    input: object = None
    den_input: object = None
    frac_edit: object = None
    ratio_op: object = None
    label: object = None
    frac: object = None
    ratio_face: object = None
    stacked_face: object = None
    stacked_w: object = None
    gensign_face: object = None
    ptext_input: object = None


@dataclass
class DisplayHandles:
    html: object = None
    ebk_size: object = None
    chart_key: object = None
    range_key: object = None
    expr: object = None
    expr_state: object = None
    caption: object = None
    caption_html: object = None
    math_cell: object = None
    math_rendered: object = None


@dataclass
class ChooserHandles:
    select: object = None
    check: object = None
    rangeopts: dict = field(default_factory=dict)
    scheme_button: object = None
    fold_state: object = None


@dataclass
class CellHandles:
    value: ValueHandles = field(default_factory=ValueHandles)
    display: DisplayHandles = field(default_factory=DisplayHandles)
    chooser: ChooserHandles = field(default_factory=ChooserHandles)
    kind: object = None
    content_sig: object = None
    cell_unit: object = None
    cell_unit_text: object = None
    popup_state: object = None
    mean_damage_tip: object = None
    help_tip: object = None
    guide_help_text: object = None


def _reject_write(self, name, value):
    raise AttributeError(
        f"read-only handle sentinel ({name!r} assignment): rec.handles(id)/rec.entity(id) returned it "
        "because the id is not live — route writes through rec.cells[id] / rec.entities[id]"
    )


def _read_only(cls):
    return type(f"_ReadOnly{cls.__name__}", (cls,), {"__setattr__": _reject_write})


_RO = {c: _read_only(c) for c in (CellHandles, ValueHandles, DisplayHandles, ChooserHandles, EntityHandles)}


def _frozen_cell() -> CellHandles:
    sentinel = CellHandles()
    sentinel.value.__class__ = _RO[ValueHandles]
    sentinel.display.__class__ = _RO[DisplayHandles]
    sentinel.chooser.__class__ = _RO[ChooserHandles]
    sentinel.__class__ = _RO[CellHandles]
    return sentinel


def _frozen_entity() -> EntityHandles:
    sentinel = EntityHandles()
    sentinel.__class__ = _RO[EntityHandles]
    return sentinel


EMPTY = _frozen_cell()
EMPTY_ENTITY = _frozen_entity()

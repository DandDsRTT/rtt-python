from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CellHandles:
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
    html: object = None
    ebk_size: object = None
    chart_key: object = None
    range_key: object = None
    expr: object = None
    expr_state: object = None
    kind: object = None
    select: object = None
    check: object = None
    ptext_input: object = None
    rangeopts: dict = field(default_factory=dict)
    scheme_button: object = None
    mean_damage_tip: object = None
    caption: object = None
    caption_html: object = None
    math_cell: object = None
    math_rendered: object = None
    fold_state: object = None
    cell_unit: object = None
    cell_unit_text: object = None
    popup_state: object = None
    content_sig: object = None
    help_tip: object = None
    guide_help_text: object = None


class _ReadOnlyCellHandles(CellHandles):
    def __setattr__(self, name, value):
        raise AttributeError(
            f"the empty-cell handle sentinel is read-only ({name!r} assignment): rec.handles(id) "
            "returned it because the cell id is not live — route writes through rec.cells[id]"
        )


def _empty_sentinel() -> CellHandles:
    sentinel = CellHandles()
    sentinel.__class__ = _ReadOnlyCellHandles
    return sentinel


EMPTY = _empty_sentinel()

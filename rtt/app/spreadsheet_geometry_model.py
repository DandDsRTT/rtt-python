from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Geometry:
    total_w: float
    total_h: float
    node_x: float
    node_edge: float
    header_y: float
    col_node_y: float
    branch_top_y: float
    fanout_y: float
    FAN: float
    size_factor: float
    size_rows: int
    prescale_rows: int
    all_interval_simplicity_weight: bool

    col_x: Mapping[str, float]
    col_w: Mapping[str, float]
    content_w: Mapping[str, float]
    content_x: Mapping[str, float]
    open_col_w: Mapping[str, float]
    col_collapsible: Mapping[str, bool]
    col_header: Mapping[str, str]
    present_caption_rows: frozenset
    matlabel_primes_w: float
    matlabel_ssprimes_w: float
    matlabel_other_w: Mapping[str, float]
    row_handle_w: float
    etpick_w: float
    primes_x: float | None
    commas_x: float | None
    targets_x: float | None
    interest_x: float | None
    held_x: float | None
    detempering_x: float | None
    canongens_x: float | None
    ssgens_x: float | None
    ssprimes_x: float | None

    rows: Mapping
    row_cpick: Mapping[str, float]
    row_plus_y: Mapping[str, float]

    group_elem: Mapping[str, str]
    group_left: Mapping[str, Callable[[int], float]]
    group_n: Mapping[str, int]
    group_ratio: Mapping[str, Callable[[int], object]]
    plus_stub_x: Mapping[str, float]

    tiles: tuple
    declared_tiles: frozenset
    ptext_strings: Mapping

    gtm_chart: bool
    gtm_extra: float
    lbox_ctrl: bool
    lbox_extra: float
    cbox_ctrl: bool
    cbox_extra: float
    opt_ctrl: bool
    opt_extra: float
    opt_cap_lines: int
    show_approach: bool
    approach_extra: float
    slope_ctrl: bool
    slope_extra: float
    slope_locked: bool
    mean_damage_caption: str


GEOMETRY_FIELDS = tuple(f.name for f in fields(Geometry))


def freeze_geometry(draft) -> Geometry:
    return Geometry(**{name: getattr(draft, name) for name in GEOMETRY_FIELDS})


class _GeometryAccess:
    pass


for _field in GEOMETRY_FIELDS:
    setattr(
        _GeometryAccess, _field, property(lambda self, _name=_field: getattr(self.geometry, _name))
    )
del _field

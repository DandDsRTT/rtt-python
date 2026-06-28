from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Geometry:
    total_w: float = 0.0
    total_h: float = 0.0
    node_x: float = 0.0
    node_edge: float = 0.0
    header_y: float = 0.0
    col_node_y: float = 0.0
    branch_top_y: float = 0.0
    fanout_y: float = 0.0
    FAN: float = 0.0
    size_factor: float = 0.0
    size_rows: int = 0
    prescale_rows: int = 0
    all_interval_simplicity_weight: bool = False

    col_x: Mapping[str, float] = field(default_factory=dict)
    col_w: Mapping[str, float] = field(default_factory=dict)
    content_w: Mapping[str, float] = field(default_factory=dict)
    content_x: Mapping[str, float] = field(default_factory=dict)
    open_col_w: Mapping[str, float] = field(default_factory=dict)
    col_collapsible: Mapping[str, bool] = field(default_factory=dict)
    col_header: Mapping[str, str] = field(default_factory=dict)
    present_caption_rows: frozenset = frozenset()
    matlabel_primes_w: float = 0.0
    matlabel_superspace_primes_w: float = 0.0
    matlabel_other_w: Mapping[str, float] = field(default_factory=dict)
    row_handle_w: float = 0.0
    etpick_w: float = 0.0
    primes_x: float | None = None
    commas_x: float | None = None
    targets_x: float | None = None
    interest_x: float | None = None
    held_x: float | None = None
    detempering_x: float | None = None
    canongens_x: float | None = None
    superspace_generators_x: float | None = None
    superspace_primes_x: float | None = None

    rows: Mapping = field(default_factory=dict)
    row_plus_y: Mapping[str, float] = field(default_factory=dict)

    group_elem: Mapping[str, str] = field(default_factory=dict)
    group_left: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    group_n: Mapping[str, int] = field(default_factory=dict)
    group_ratio: Mapping[str, tuple] = field(default_factory=dict)
    plus_stub_x: Mapping[str, float] = field(default_factory=dict)

    tiles: tuple = ()
    declared_tiles: frozenset = frozenset()
    plain_text_strings: Mapping = field(default_factory=dict)

    gtm_chart: bool = False
    gtm_extra: float = 0.0
    lbox_ctrl: bool = False
    lbox_extra: float = 0.0
    cbox_ctrl: bool = False
    cbox_extra: float = 0.0
    opt_ctrl: bool = False
    opt_extra: float = 0.0
    opt_cap_lines: int = 0
    show_approach: bool = False
    approach_extra: float = 0.0
    slope_ctrl: bool = False
    slope_extra: float = 0.0
    slope_locked: bool = False
    mean_damage_caption: str = ""

    superspace_tuning_map: object = None

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Line:
    id: str
    orientation: Literal["v", "h"]
    position: float
    start: float
    length: float
    dotted: bool = False


@dataclass(frozen=True)
class Block:
    id: str
    x: float
    y: float
    width: float
    height: float
    tint: str = ""
    boxed: bool = False


@dataclass(frozen=True)
class CellBox:
    id: str
    x: float
    y: float
    width: float
    height: float
    kind: str
    text: str = ""
    gen: int = -1
    prime: int = -1
    comma: int = -1
    underlines: tuple[tuple[int, int], ...] = ()
    values: tuple[float, ...] = ()
    ranges: tuple[tuple[float, float], ...] = ()
    indicator: float | None = None
    indicator_label: str = ""
    column_gap: float = 0
    pending: bool = False
    preview_remove: bool = False
    preview_change: bool = False
    checked: bool = False
    blank: bool = False
    unit: str = ""
    align: str = ""
    disabled: bool = False
    audio: tuple | None = None
    decimals: bool = True


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    cells: tuple[CellBox, ...]
    freeze_x: float
    freeze_y: float
    right_overhang: float = 0.0
    identities: dict | None = None
    approach_box: tuple | None = None
    pretransform: bool = False

"""Coordinate-space entities for the temperament grid.

The layout (:mod:`rtt.web.spreadsheet`) produces these positioned entities with
*stable, semantic ids* so the reconciling renderer can keep them across state
changes and animate add/remove/move:

* :class:`Line` — one entity per coordinate axis (``v:prime:2``, ``h:mapping:0``), a
  continuous line, not per-cell segments.
* :class:`Block` — an #e0e0e0 panel rectangle (``block:mapping`` ...).
* :class:`CellBox` — an input / label / button / caption (``cell:mapping:0:1``,
  ``prime:2``, ``header:primes`` ...).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    id: str
    orientation: str  # "v" | "h"
    pos: float  # cross-axis position (x for v, y for h)
    start: float  # along-axis start (y for v, x for h)
    length: float
    dotted: bool = False  # a folded row/column converges to one rule; dot it so the
    # collapsed band reads as a dotted placeholder for its hidden content


@dataclass(frozen=True)
class Block:
    id: str
    x: float
    y: float
    w: float
    h: float
    tint: str = ""  # colour-group name for a colorization wash ("tuning"); "" for a plain grey tile
    boxed: bool = False  # render a thin-bordered box (the nested tuning-ranges box) rather than a plain tile


@dataclass(frozen=True)
class CellBox:
    id: str
    x: float
    y: float
    w: float
    h: float
    kind: str
    text: str = ""
    gen: int = -1
    prime: int = -1
    comma: int = -1
    underlines: tuple[tuple[int, int], ...] = ()  # (start, len) spans of text to underline (mnemonics)
    values: tuple[float, ...] = ()  # per-column data for a "chart" cell's bars
    ranges: tuple[tuple[float, float], ...] = ()  # per-generator (low, high) for a "rangechart" cell's I-beams
    indicator: float | None = None  # a "chart" cell's horizontal indicator level (the optimization
    # objective ⟪𝐝⟫ₚ on the damage chart), drawn as a line across the plot when set
    indicator_label: str = ""  # the subscript on that indicator's ⟪𝐝⟫ label — the scheme's Lp
    # power (∞ / 2 / 1) — so the renderer can letter the line-breaking label
    pending: bool = False  # a not-yet-valid comma draft cell — rendered blank and red-outlined
    alert: bool = False  # a value that violates a constraint (a held interval the current tuning
    # does not hold just): the renderer paints the whole cell red until the constraint is restored
    checked: bool = False  # a "control_check" checkbox's state (the box-𝐋 "replace diminuator")
    blank: bool = False  # a value cell kept (its box/brackets stay) but emptied of its
    # number -- how "quantities" off shows the bare gridded structure
    unit: str = ""  # the cell's per-value unit (e.g. "g₁/p₁"), shown small beneath the value
    # when the general `units` toggle is on -- the tile's unit with its variables indexed
    align: str = ""  # horizontal text alignment for a caption (default centred; "left" left-justifies
    # it under the control it labels, like a preset chooser's "predefined prescalers" label)
    disabled: bool = False  # a "control_select" rendered greyed and non-interactive: the box-𝒘
    # weight-slope chooser in all-interval mode, locked to its forced simplicity-weight value


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    cells: tuple[CellBox, ...]
    freeze_x: float  # left edge of the first value tile: the row titles/toggles AND the row
    # branching (trunks, left buses, the ± controls) freeze left of here against horizontal scroll
    freeze_y: float  # top edge of the first value tile: the column titles/toggles AND the column
    # branching (trunks, fan-out buses, the ± controls) freeze above here against vertical scroll
    right_overhang: float = 0.0  # how far the widest column title spills past `width` (titles render
    # unwrapped and centred on their gridline, so the narrow last column's long title reaches beyond
    # the grid's right edge); the renderer widens the grey pane by this so the title isn't clipped

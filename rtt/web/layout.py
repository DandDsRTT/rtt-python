"""Coordinate-space entities for the temperament grid.

The layout (:mod:`rtt.web.spreadsheet`) produces these positioned entities with
*stable, semantic ids* so the reconciling renderer can keep them across state
changes and animate add/remove/move:

* :class:`Line` — one entity per coordinate axis (``v:prime:2``, ``h:gen:0``), a
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


@dataclass(frozen=True)
class Block:
    id: str
    x: float
    y: float
    w: float
    h: float
    tint: str = ""  # colour-group name for a colorization wash ("tuning"); "" for a plain grey tile


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
    pending: bool = False  # a not-yet-valid comma draft cell — rendered blank and red-outlined
    blank: bool = False  # a value cell kept (its box/brackets stay) but emptied of its
    # number -- how "quantities" off shows the bare gridded structure


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    cells: tuple[CellBox, ...]

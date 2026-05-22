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


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    cells: tuple[CellBox, ...]

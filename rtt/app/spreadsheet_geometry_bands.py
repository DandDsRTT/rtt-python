from __future__ import annotations

from rtt.app.grid_tables import FRAMED_ROWS
from rtt.app.spreadsheet_constants import (
    FOOT_HEIGHT,
    FRAME_GAP,
    FRAME_HEIGHT,
    FRAME_OVERHANG,
    ROW_HEIGHT,
    V_SPLIT_GAP,
    VAL_BRACKET_HEIGHT,
)


def map_top(geometry, i: int) -> float:
    return geometry.rows["mapping"].y + i * ROW_HEIGHT


def projection_top(geometry, i: int) -> float:
    return geometry.rows["projection"].y + i * ROW_HEIGHT


def canonical_top(geometry, i: int) -> float:
    return geometry.rows["canonical"].y + i * ROW_HEIGHT


def vector_top(geometry, p: int) -> float:
    return geometry.rows["vectors"].y + p * ROW_HEIGHT


def superspace_vector_top(geometry, p: int) -> float:
    return geometry.rows["superspace_vectors"].y + p * ROW_HEIGHT


def superspace_map_top(geometry, i: int) -> float:
    return geometry.rows["superspace_mapping"].y + i * ROW_HEIGHT


def superspace_projection_top(geometry, i: int) -> float:
    return geometry.rows["superspace_projection"].y + i * ROW_HEIGHT


def prescale_size_gap(geometry) -> float:
    return V_SPLIT_GAP if geometry.size_rows else 0


def subrow_top(geometry, row_key: str, i: int) -> float:
    gap = (
        prescale_size_gap(geometry)
        if (row_key == "prescaling" and i >= geometry.prescale_rows)
        else 0
    )
    return geometry.rows[row_key].y + i * ROW_HEIGHT + gap


def comma_picker_band_y(geometry, row_key: str) -> float:
    row = geometry.rows[row_key]
    return row.y + row.height + row.frame


def plain_text_band_y(geometry, row_key: str) -> float:
    row = geometry.rows[row_key]
    return row.y + row.height + row.frame + row.comma_picker + row.symbol + row.text + row.units


def frame_top_y(geometry, row_key: str) -> float:
    return geometry.rows[row_key].y - FRAME_HEIGHT - FRAME_GAP


def frame_foot_y(geometry, row_key: str) -> float:
    return geometry.rows[row_key].y + geometry.rows[row_key].height + FRAME_GAP


def separator_span(resolved, geometry, row_key: str):
    if row_key not in FRAMED_ROWS:
        return geometry.rows[row_key].y + (ROW_HEIGHT - VAL_BRACKET_HEIGHT) / 2, VAL_BRACKET_HEIGHT
    if not resolved.flags.ebk:
        return geometry.rows[row_key].y, geometry.rows[row_key].height
    y = frame_top_y(geometry, row_key) - FRAME_OVERHANG
    return y, frame_foot_y(geometry, row_key) + FOOT_HEIGHT + FRAME_OVERHANG - y

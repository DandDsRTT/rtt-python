from __future__ import annotations

from rtt.app.spreadsheet_constants import FRAME_GAP, FRAME_H, ROW_H


def map_top(geometry, i: int) -> float:
    return geometry.rows["mapping"].y + i * ROW_H


def proj_top(geometry, i: int) -> float:
    return geometry.rows["projection"].y + i * ROW_H


def canon_top(geometry, i: int) -> float:
    return geometry.rows["canon"].y + i * ROW_H


def vec_top(geometry, p: int) -> float:
    return geometry.rows["vectors"].y + p * ROW_H


def ss_vec_top(geometry, p: int) -> float:
    return geometry.rows["ss_vectors"].y + p * ROW_H


def ss_map_top(geometry, i: int) -> float:
    return geometry.rows["ss_mapping"].y + i * ROW_H


def ss_proj_top(geometry, i: int) -> float:
    return geometry.rows["ss_projection"].y + i * ROW_H


def cpick_band_y(geometry, rkey: str) -> float:
    row = geometry.rows[rkey]
    return row.y + row.h + row.frame


def ptext_band_y(geometry, rkey: str) -> float:
    row = geometry.rows[rkey]
    return row.y + row.h + row.frame + geometry.row_cpick[rkey] + row.sym + row.cap + row.units


def frame_top_y(geometry, rkey: str) -> float:
    return geometry.rows[rkey].y - FRAME_H - FRAME_GAP


def frame_brace_y(geometry, rkey: str) -> float:
    return geometry.rows[rkey].y + geometry.rows[rkey].h + FRAME_GAP

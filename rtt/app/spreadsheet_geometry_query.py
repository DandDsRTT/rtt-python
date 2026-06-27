from __future__ import annotations

from rtt.app.grid_tables import (
    EDITABLE_PTEXT,
    FORM_CHOOSERS,
    FORM_SUBSCRIPT_GENS,
    FORM_SUBSCRIPT_ROWS,
    FRAMED_ROWS,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    UNITS,
)
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BOX_INNER,
    BRACE_H,
    BRACKET_W,
    CAPTION_LINE,
    COL_W,
    CTRL_LABEL_GAP,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    INTERVAL_COL_GAP,
    PAD,
    PRESET_H,
    PRESET_W,
    PTEXT_EDIT_H,
    PTEXT_H,
    ROW_H,
    SCHEME_BTN_SQ,
    TARGET_PRESET_W,
    V_SPLIT_GAP,
    VAL_BRACKET_H,
)
from rtt.app.spreadsheet_text import _sub, _subscript_coord, pending_token


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


def prescale_size_gap(geometry) -> float:
    return V_SPLIT_GAP if geometry.size_rows else 0


def subrow_top(geometry, rkey: str, i: int) -> float:
    gap = (
        prescale_size_gap(geometry) if (rkey == "prescaling" and i >= geometry.prescale_rows) else 0
    )
    return geometry.rows[rkey].y + i * ROW_H + gap


def cpick_band_y(geometry, rkey: str) -> float:
    row = geometry.rows[rkey]
    return row.y + row.h + row.frame


def ptext_band_y(geometry, rkey: str) -> float:
    row = geometry.rows[rkey]
    return row.y + row.h + row.frame + row.cpick + row.sym + row.cap + row.units


def frame_top_y(geometry, rkey: str) -> float:
    return geometry.rows[rkey].y - FRAME_H - FRAME_GAP


def frame_brace_y(geometry, rkey: str) -> float:
    return geometry.rows[rkey].y + geometry.rows[rkey].h + FRAME_GAP


def separator_span(resolved, geometry, rkey: str):
    if rkey not in FRAMED_ROWS:
        return geometry.rows[rkey].y + (ROW_H - VAL_BRACKET_H) / 2, VAL_BRACKET_H
    if not resolved.flags.ebk:
        return geometry.rows[rkey].y, geometry.rows[rkey].h
    y = frame_top_y(geometry, rkey) - FRAME_OVERHANG
    return y, frame_brace_y(geometry, rkey) + BRACE_H + FRAME_OVERHANG - y


def matlabel_gutter_w(geometry, group_key: str) -> float:
    if group_key == "primes":
        return geometry.matlabel_primes_w
    if group_key == "ssprimes":
        return geometry.matlabel_ssprimes_w
    return geometry.matlabel_other_w.get(group_key, 0)


def handle_gutter_w(geometry, group_key: str) -> float:
    return geometry.row_handle_w if group_key == "primes" else 0


def etpick_left_pad(geometry, group_key: str) -> float:
    if group_key != "primes" or not geometry.etpick_w:
        return 0
    return max(
        0,
        geometry.etpick_w
        - handle_gutter_w(geometry, group_key)
        - matlabel_gutter_w(geometry, group_key),
    )


def outer_gutter_w(geometry, group_key: str) -> float:
    return (
        etpick_left_pad(geometry, group_key)
        + handle_gutter_w(geometry, group_key)
        + matlabel_gutter_w(geometry, group_key)
    )


def content_box(geometry, key: str):
    return geometry.content_x[key], geometry.content_w[key]


def tile_box(geometry, key: str):
    return geometry.col_x[key], geometry.col_w[key]


def tile_span_box(geometry, rkey: str, ckey: str):
    if (rkey, ckey) == ("counts", "gens") and "canongens" in geometry.col_x:
        x = geometry.col_x["canongens"]
        return x, geometry.col_x["gens"] + geometry.col_w["gens"] - x
    return tile_box(geometry, ckey)


def matrix_span(geometry, resolved, group_key: str):
    x, w = content_box(geometry, group_key)
    mx = outer_gutter_w(geometry, group_key)
    x, w = x + mx, w - 2 * mx
    if group_key == "commas" and resolved.unchanged.empty_comma_w:
        x, w = x + resolved.unchanged.empty_comma_w, w - resolved.unchanged.empty_comma_w
    return x, w


def prime_left(geometry, p: int) -> float:
    return geometry.primes_x + outer_gutter_w(geometry, "primes") + BRACKET_W + p * COL_W


def comma_left(geometry, resolved, c: int) -> float:
    gap = V_SPLIT_GAP if (resolved.unchanged.shown and 0 < resolved.dims.nc_shown <= c) else 0
    return geometry.commas_x + BRACKET_W + resolved.unchanged.empty_comma_w + c * COL_W + gap


def comma_value_pos(resolved, i: int) -> int:
    return i if i < resolved.dims.nc else i + (resolved.dims.nc_shown - resolved.dims.nc)


def interval_col_gap(ckey: str) -> float:
    if ckey in ("targets", "held"):
        return INTERVAL_COL_GAP
    if ckey == "interest":
        return INTERVAL_COL_GAP / 2
    return 0


def interval_list_w(n: int, ckey: str) -> float:
    return 2 * BRACKET_W + n * COL_W + max(n - 1, 0) * interval_col_gap(ckey)


def target_left(geometry, j: int) -> float:
    return geometry.targets_x + BRACKET_W + j * (COL_W + interval_col_gap("targets"))


def interest_left(geometry, i: int) -> float:
    return geometry.interest_x + BRACKET_W + i * (COL_W + interval_col_gap("interest"))


def held_left(geometry, i: int) -> float:
    return geometry.held_x + BRACKET_W + i * (COL_W + interval_col_gap("held"))


def detempering_left(geometry, i: int) -> float:
    return geometry.detempering_x + BRACKET_W + i * COL_W


def gen_left(geometry, g: int) -> float:
    return geometry.content_x["gens"] + outer_gutter_w(geometry, "gens") + BRACKET_W + g * COL_W


def canongen_left(geometry, g: int) -> float:
    return geometry.canongens_x + outer_gutter_w(geometry, "canongens") + BRACKET_W + g * COL_W


def ss_gen_left(geometry, g: int) -> float:
    return geometry.ssgens_x + BRACKET_W + g * COL_W


def ss_prime_left(geometry, p: int) -> float:
    return geometry.ssprimes_x + outer_gutter_w(geometry, "ssprimes") + BRACKET_W + p * COL_W


def sub_axis_x(geometry, ckey: str, i: int) -> float:
    return geometry.group_left[ckey][i] + COL_W / 2


def col_plus_x(geometry, resolved, ckey: str) -> float:
    n = geometry.group_n[ckey]
    if n == 0:
        mx, mw = matrix_span(geometry, resolved, ckey)
        return mx + mw / 2
    if ckey == "commas" and resolved.unchanged.shown:
        if resolved.dims.nc_shown == 0:
            return geometry.commas_x + BRACKET_W + resolved.unchanged.empty_comma_w / 2
        return comma_left(geometry, resolved, resolved.dims.nc_shown - 1) + COL_W + V_SPLIT_GAP / 2
    return sub_axis_x(geometry, ckey, n - 1) + COL_W + interval_col_gap(ckey)


def col_open(geometry, collapsed, key: str) -> bool:
    return key in geometry.col_x and f"col:{key}" not in collapsed


def row_open(geometry, collapsed, key: str) -> bool:
    return key in geometry.rows and f"row:{key}" not in collapsed


def tile_open(geometry, collapsed, rkey: str, ckey: str) -> bool:
    return (
        (rkey, ckey) in geometry.declared_tiles
        and row_open(geometry, collapsed, rkey)
        and col_open(geometry, collapsed, ckey)
        and f"tile:{rkey}:{ckey}" not in collapsed
    )


def col_token(resolved, group: str, i: int):
    if group == "commas" and i >= resolved.dims.nc:
        return f"u{i - resolved.dims.nc}"
    pairs = resolved.col_ids.get(group)
    return i if pairs is None else pairs[i][0]


def pending_col_token(resolved, group: str):
    return pending_token([tok for tok, _ in resolved.col_ids[group]])


def pending_draft_idx(resolved, group: str):
    return {
        "commas": (resolved.scalars.comma_draft or None, resolved.dims.nc),
        "targets": (resolved.targets.pending, resolved.dims.k),
        "held": (resolved.held.pending, resolved.dims.nh),
        "interest": (resolved.interest.pending, resolved.dims.mi),
    }.get(group)


def tile_unit(resolved, rkey: str, ckey: str) -> str:
    base = UNITS.get((rkey, ckey))
    if base is None:
        return ""
    if rkey == "complexity":
        return base.replace("(C)", resolved.scalars.complexity_unit)
    if rkey == "weight":
        return resolved.scalars.weight_unit
    if rkey == "damage":
        return resolved.scalars.damage_unit
    return base


def cell_unit(resolved, rkey: str, ckey: str, *, gen=None, prime=None, elem=None) -> str:
    if not resolved.flags.cell_units:
        return ""
    u = tile_unit(resolved, rkey, ckey)
    superspace = rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")
    if gen is not None:
        if superspace:
            u = u.replace(f"g{SUBSCRIPT_L}", f"g{SUBSCRIPT_L}{_sub(gen + 1)}")
        elif f"g{SUBSCRIPT_C}" in u:
            gc = f"g{SUBSCRIPT_C}"
            u = _subscript_coord(u.replace(gc, "\x00"), "g", f"g{_sub(gen + 1)}").replace(
                "\x00", f"{gc}{_sub(gen + 1)}"
            )
        else:
            u = _subscript_coord(u, "g", f"g{_sub(gen + 1)}")
    if prime is not None:
        coord = "p" if superspace else resolved.labels.domain_label
        u = _subscript_coord(u, "p", f"{coord}{_sub(prime + 1)}")
    if elem is not None:
        u = _subscript_coord(
            u, resolved.labels.domain_label, f"{resolved.labels.domain_label}{_sub(elem + 1)}"
        )
    return u


def row_fans(geometry, key: str) -> bool:
    return geometry.rows[key].nsub > 1 or key in geometry.row_plus_y


def plus_shows(geometry, resolved, collapsed, state, ckey: str) -> bool:
    if ckey in ("interest", "held"):
        return col_open(geometry, collapsed, ckey) and (
            row_open(geometry, collapsed, "quantities") or row_open(geometry, collapsed, "vectors")
        )
    if ckey == "targets":
        return (
            tile_open(geometry, collapsed, "quantities", "targets")
            or tile_open(geometry, collapsed, "vectors", "targets")
        ) and not resolved.scalars.all_interval
    if ckey == "gens":
        return tile_open(geometry, collapsed, "quantities", "gens") and state.n > 0
    if ckey == "primes":
        return tile_open(geometry, collapsed, "quantities", "primes") and (
            resolved.flags.nonstandard_domain or resolved.scalars.standard_domain
        )
    if ckey == "commas":
        return tile_open(geometry, collapsed, "quantities", "commas") or tile_open(
            geometry, collapsed, "vectors", "commas"
        )
    return tile_open(geometry, collapsed, "quantities", ckey) or tile_open(
        geometry, collapsed, "vectors", ckey
    )


def form_subscripted(resolved, glyph: str, rkey: str, ckey: str) -> str:
    if (
        glyph
        and resolved.flags.form_subscript
        and (rkey in FORM_SUBSCRIPT_ROWS or (rkey, ckey) in FORM_SUBSCRIPT_GENS)
    ):
        return glyph[:1] + SUBSCRIPT_C + glyph[1:]
    return glyph


def projection_superspace_tail(resolved) -> str:
    return f" = G{SUBSCRIPT_L}→ₛ𝑀ₛ→{SUBSCRIPT_L}" if resolved.flags.superspace else ""


def weight_simplicity_header(resolved, i: int) -> str:
    symbol = f"w{_sub(i + 1)}"
    if not resolved.flags.equivalences:
        return symbol
    return f"{symbol} = c{_sub(i + 1)}⁻¹"


def control_dims(geometry, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):
    dropdown_w = max(40, min(geometry.col_w[ckey] - 2 * BOX_INNER, cap_w))
    label_h = CAPTION_LINE if label else 0
    box_h = 2 * BOX_INNER + PRESET_H + label_h
    box_h += (SCHEME_BTN_SQ + CTRL_LABEL_GAP) if scheme_btn else 0
    if form_label is not None:
        box_h += BAND_GAP + PRESET_H + (CAPTION_LINE if form_label else 0)
    return dropdown_w, label_h, box_h


def preset_cap(name: str):
    return TARGET_PRESET_W if name == "target" else PRESET_W


def preset_form_label(resolved, name: str, rkey: str, ckey: str):
    embeds = (
        name == "temperament"
        and resolved.flags.form_controls
        and any(rk == rkey and ck == ckey for _n, rk, ck, _l in FORM_CHOOSERS)
    )
    return "form" if embeds else None


def ptext_editable(resolved, rkey: str, ckey: str) -> bool:
    if rkey == "prescaling":
        return (rkey, ckey) == ("prescaling", "ssprimes" if resolved.flags.superspace else "primes")
    if rkey == "tuning" and resolved.flags.superspace_generators:
        return ckey == "ssgens"
    return (rkey, ckey) in EDITABLE_PTEXT


def ptext_height(resolved, rkey: str, ckey: str):
    return PTEXT_EDIT_H if ptext_editable(resolved, rkey, ckey) else PTEXT_H


def panel_rect(geometry, collapsed, rkey: str, ckey: str):
    tile_c = f"tile:{rkey}:{ckey}" in collapsed
    col_c = f"col:{ckey}" in collapsed or tile_c
    row_c = f"row:{rkey}" in collapsed or tile_c
    cx, cw = tile_span_box(geometry, rkey, ckey)
    ch, cy = geometry.rows[rkey].tile_h, geometry.rows[rkey].tile_top
    w, px = (0, 0) if col_c else (cw, PAD)
    h, py = (0, 0) if row_c else (ch, PAD)
    bx = cx + cw / 2 if col_c else cx
    by = cy + ch / 2 if row_c else cy
    return bx - px, by - py, w + 2 * px, h + 2 * py

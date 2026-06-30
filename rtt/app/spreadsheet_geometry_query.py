from __future__ import annotations

from rtt.app.grid_tables import (
    EDITABLE_PLAIN_TEXT,
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
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    INTERVAL_COL_GAP,
    PAD,
    PLAIN_TEXT_EDIT_H,
    PLAIN_TEXT_H,
    PRESET_H,
    PRESET_W,
    ROW_H,
    SCHEME_BUTTON_SQ,
    TARGET_PRESET_W,
    V_SPLIT_GAP,
    VAL_BRACKET_H,
)
from rtt.app.spreadsheet_text import _sub, _subscript_coord, pending_token


def map_top(geometry, i: int) -> float:
    return geometry.rows["mapping"].y + i * ROW_H


def projection_top(geometry, i: int) -> float:
    return geometry.rows["projection"].y + i * ROW_H


def canon_top(geometry, i: int) -> float:
    return geometry.rows["canon"].y + i * ROW_H


def vector_top(geometry, p: int) -> float:
    return geometry.rows["vectors"].y + p * ROW_H


def superspace_vector_top(geometry, p: int) -> float:
    return geometry.rows["superspace_vectors"].y + p * ROW_H


def superspace_map_top(geometry, i: int) -> float:
    return geometry.rows["superspace_mapping"].y + i * ROW_H


def superspace_projection_top(geometry, i: int) -> float:
    return geometry.rows["superspace_projection"].y + i * ROW_H


def prescale_size_gap(geometry) -> float:
    return V_SPLIT_GAP if geometry.size_rows else 0


def subrow_top(geometry, row_key: str, i: int) -> float:
    gap = (
        prescale_size_gap(geometry)
        if (row_key == "prescaling" and i >= geometry.prescale_rows)
        else 0
    )
    return geometry.rows[row_key].y + i * ROW_H + gap


def comma_picker_band_y(geometry, row_key: str) -> float:
    row = geometry.rows[row_key]
    return row.y + row.height + row.frame


def plain_text_band_y(geometry, row_key: str) -> float:
    row = geometry.rows[row_key]
    return row.y + row.height + row.frame + row.comma_picker + row.symbol + row.caption + row.units


def frame_top_y(geometry, row_key: str) -> float:
    return geometry.rows[row_key].y - FRAME_H - FRAME_GAP


def frame_brace_y(geometry, row_key: str) -> float:
    return geometry.rows[row_key].y + geometry.rows[row_key].height + FRAME_GAP


def separator_span(resolved, geometry, row_key: str):
    if row_key not in FRAMED_ROWS:
        return geometry.rows[row_key].y + (ROW_H - VAL_BRACKET_H) / 2, VAL_BRACKET_H
    if not resolved.flags.ebk:
        return geometry.rows[row_key].y, geometry.rows[row_key].height
    y = frame_top_y(geometry, row_key) - FRAME_OVERHANG
    return y, frame_brace_y(geometry, row_key) + BRACE_H + FRAME_OVERHANG - y


def matlabel_gutter_w(geometry, group_key: str) -> float:
    if group_key == "primes":
        return geometry.matlabel_primes_w
    if group_key == "superspace_primes":
        return geometry.matlabel_superspace_primes_w
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


def tile_span_box(geometry, row_key: str, column_key: str):
    if (row_key, column_key) == ("counts", "gens") and "canongens" in geometry.col_x:
        x = geometry.col_x["canongens"]
        return x, geometry.col_x["gens"] + geometry.col_w["gens"] - x
    return tile_box(geometry, column_key)


def matrix_span(geometry, resolved, group_key: str):
    x, width = content_box(geometry, group_key)
    matrix_x = outer_gutter_w(geometry, group_key)
    x, width = x + matrix_x, width - 2 * matrix_x
    if group_key == "commas" and resolved.unchanged.empty_comma_w:
        x, width = x + resolved.unchanged.empty_comma_w, width - resolved.unchanged.empty_comma_w
    return x, width


def prime_left(geometry, p: int) -> float:
    return geometry.primes_x + outer_gutter_w(geometry, "primes") + BRACKET_W + p * COL_W


def comma_left(geometry, resolved, c: int) -> float:
    gap = (
        V_SPLIT_GAP
        if (resolved.unchanged.shown and 0 < resolved.dims.comma_count_shown <= c)
        else 0
    )
    return geometry.commas_x + BRACKET_W + resolved.unchanged.empty_comma_w + c * COL_W + gap


def comma_value_pos(resolved, i: int) -> int:
    return (
        i
        if i < resolved.dims.comma_count
        else i + (resolved.dims.comma_count_shown - resolved.dims.comma_count)
    )


def interval_col_gap(column_key: str) -> float:
    if column_key in ("targets", "held"):
        return INTERVAL_COL_GAP
    if column_key == "interest":
        return INTERVAL_COL_GAP / 2
    return 0


def interval_list_w(n: int, column_key: str) -> float:
    return 2 * BRACKET_W + n * COL_W + max(n - 1, 0) * interval_col_gap(column_key)


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


def superspace_gen_left(geometry, g: int) -> float:
    return geometry.superspace_generators_x + BRACKET_W + g * COL_W


def superspace_prime_left(geometry, p: int) -> float:
    return (
        geometry.superspace_primes_x
        + outer_gutter_w(geometry, "superspace_primes")
        + BRACKET_W
        + p * COL_W
    )


def sub_axis_x(geometry, column_key: str, i: int) -> float:
    return geometry.group_left[column_key][i] + COL_W / 2


def col_plus_x(geometry, resolved, column_key: str) -> float:
    n = geometry.group_n[column_key]
    if n == 0:
        matrix_x, matrix_width = matrix_span(geometry, resolved, column_key)
        return matrix_x + matrix_width / 2
    if column_key == "commas" and resolved.unchanged.shown:
        if resolved.dims.comma_count_shown == 0:
            return geometry.commas_x + BRACKET_W + resolved.unchanged.empty_comma_w / 2
        return (
            comma_left(geometry, resolved, resolved.dims.comma_count_shown - 1)
            + COL_W
            + V_SPLIT_GAP / 2
        )
    return sub_axis_x(geometry, column_key, n - 1) + COL_W + interval_col_gap(column_key)


def col_open(geometry, collapsed, key: str) -> bool:
    return key in geometry.col_x and f"col:{key}" not in collapsed


def row_open(geometry, collapsed, key: str) -> bool:
    return key in geometry.rows and f"row:{key}" not in collapsed


def tile_open(geometry, collapsed, row_key: str, column_key: str) -> bool:
    return (
        (row_key, column_key) in geometry.declared_tiles
        and row_open(geometry, collapsed, row_key)
        and col_open(geometry, collapsed, column_key)
        and f"tile:{row_key}:{column_key}" not in collapsed
    )


def col_token(resolved, group: str, i: int):
    if group == "commas" and i >= resolved.dims.comma_count:
        return f"u{i - resolved.dims.comma_count}"
    pairs = resolved.col_ids.get(group)
    return i if pairs is None else pairs[i][0]


def pending_col_token(resolved, group: str):
    return pending_token([token for token, _ in resolved.col_ids[group]])


def pending_draft_idx(resolved, group: str):
    return {
        "commas": (resolved.scalars.comma_draft or None, resolved.dims.comma_count),
        "targets": (resolved.targets.pending, resolved.dims.target_count),
        "held": (resolved.held.pending, resolved.dims.held_count),
        "interest": (resolved.interest.pending, resolved.dims.interest_count),
    }.get(group)


def tile_unit(resolved, row_key: str, column_key: str) -> str:
    base = UNITS.get((row_key, column_key))
    if base is None:
        return ""
    if row_key == "complexity":
        return base.replace("(C)", resolved.scalars.complexity_unit)
    if row_key == "weight":
        return resolved.scalars.weight_unit
    if row_key == "damage":
        return resolved.scalars.damage_unit
    return base


def cell_unit(resolved, row_key: str, column_key: str, *, gen=None, prime=None, elem=None) -> str:
    if not resolved.flags.cell_units:
        return ""
    u = tile_unit(resolved, row_key, column_key)
    superspace = row_key.startswith("superspace_") or column_key in (
        "superspace_generators",
        "superspace_primes",
    )
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
    return geometry.rows[key].num_subrows > 1 or key in geometry.row_plus_y


def plus_shows(geometry, resolved, collapsed, state, column_key: str) -> bool:
    if column_key in ("interest", "held"):
        return col_open(geometry, collapsed, column_key) and (
            row_open(geometry, collapsed, "quantities") or row_open(geometry, collapsed, "vectors")
        )
    if column_key == "targets":
        return (
            tile_open(geometry, collapsed, "quantities", "targets")
            or tile_open(geometry, collapsed, "vectors", "targets")
        ) and not resolved.scalars.all_interval
    if column_key == "gens":
        return tile_open(geometry, collapsed, "quantities", "gens") and state.nullity > 0
    if column_key == "primes":
        return tile_open(geometry, collapsed, "quantities", "primes") and (
            resolved.flags.nonstandard_domain or resolved.scalars.standard_domain
        )
    if column_key == "commas":
        return tile_open(geometry, collapsed, "quantities", "commas") or tile_open(
            geometry, collapsed, "vectors", "commas"
        )
    return tile_open(geometry, collapsed, "quantities", column_key) or tile_open(
        geometry, collapsed, "vectors", column_key
    )


def form_subscripted(resolved, glyph: str, row_key: str, column_key: str) -> str:
    if (
        glyph
        and resolved.flags.form_subscript
        and (row_key in FORM_SUBSCRIPT_ROWS or (row_key, column_key) in FORM_SUBSCRIPT_GENS)
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


def control_dims(
    geometry, column_key: str, cap_w, label, scheme_button: bool = False, form_label=None
):
    dropdown_w = max(40, min(geometry.col_w[column_key] - 2 * BOX_INNER, cap_w))
    label_h = CAPTION_LINE if label else 0
    box_h = 2 * BOX_INNER + PRESET_H + label_h
    box_h += (SCHEME_BUTTON_SQ + BOX_INNER) if scheme_button else 0
    if form_label is not None:
        box_h += BAND_GAP + PRESET_H + (CAPTION_LINE if form_label else 0)
    return dropdown_w, label_h, box_h


def preset_cap(name: str):
    return TARGET_PRESET_W if name == "target" else PRESET_W


def preset_form_label(resolved, name: str, row_key: str, column_key: str):
    embeds = (
        name == "temperament"
        and resolved.flags.form_controls
        and any(rk == row_key and ck == column_key for _n, rk, ck, _l in FORM_CHOOSERS)
    )
    return "form" if embeds else None


def plain_text_editable(resolved, row_key: str, column_key: str) -> bool:
    if row_key == "prescaling":
        return (row_key, column_key) == (
            "prescaling",
            "superspace_primes" if resolved.flags.superspace else "primes",
        )
    if row_key == "tuning" and resolved.flags.superspace_generators:
        return column_key == "superspace_generators"
    return (row_key, column_key) in EDITABLE_PLAIN_TEXT


def plain_text_height(resolved, row_key: str, column_key: str):
    return PLAIN_TEXT_EDIT_H if plain_text_editable(resolved, row_key, column_key) else PLAIN_TEXT_H


def panel_rect(geometry, collapsed, row_key: str, column_key: str):
    tile_c = f"tile:{row_key}:{column_key}" in collapsed
    col_c = f"col:{column_key}" in collapsed or tile_c
    row_c = f"row:{row_key}" in collapsed or tile_c
    tile_x, tile_width = tile_span_box(geometry, row_key, column_key)
    tile_height, tile_y = geometry.rows[row_key].tile_h, geometry.rows[row_key].tile_top
    width, padding_x = (0, 0) if col_c else (tile_width, PAD)
    height, padding_y = (0, 0) if row_c else (tile_height, PAD)
    box_x = tile_x + tile_width / 2 if col_c else tile_x
    box_y = tile_y + tile_height / 2 if row_c else tile_y
    return box_x - padding_x, box_y - padding_y, width + 2 * padding_x, height + 2 * padding_y

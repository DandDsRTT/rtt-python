from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    BANDS,
    COUNTS_TILES,
    DETEMPERING_COUNTS_TILES,
    EDITABLE_PLAIN_TEXT_ROWS,
    EQUIVALENCES,
    FORM_CHOOSERS,
    FORM_EQUIVALENCES,
    OPTIMIZATION_COUNTS_TILES,
    PRESET_COPIES,
    PRESETS,
    SUPERSPACE_COUNTS_TILES,
    SUPERSPACE_TILES,
    SYMBOLS,
    TILES,
    UNITS_TILES,
)
from rtt.app.spreadsheet_constants import (
    BOX_INNER,
    BOX_OUTER,
    BRACKET_WIDTH,
    CAPTION_LINE,
    CBOX_NODROP_WIDTH,
    CBOX_WIDTH,
    COLUMN_WIDTH,
    LBOX_DIM_WIDTH,
    MAX_CAPTION_LINES,
    OPT_BOX_MIN_WIDTH,
    PBOX_WIDTH,
    PLAIN_TEXT_EDIT_HEIGHT,
    PLAIN_TEXT_HEIGHT,
    PRESET_WIDTH,
    SCHEME_CTRL_WIDTH,
    SYMBOL_FONT,
    TBOX_WIDTH,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_text import (
    _min_width_for_lines,
    _wrap_lines,
)


def declare_interval_column_tiles(resolved):
    interest_tiles = ()
    if resolved.dimensions.interest_count_shown:
        interest_tiles += (
            ("block:vector:interest", "vectors", "interest"),
            ("block:interest", "quantities", "interest"),
            ("block:imapped", "mapping", "interest"),
            ("block:tuning:interest", "tuning", "interest"),
            ("block:just:interest", "just", "interest"),
            ("block:retune:interest", "retune", "interest"),
            ("block:urow:interest", "units", "interest"),
            ("block:prescaling:interest", "prescaling", "interest"),
            ("block:complexity:interest", "complexity", "interest"),
        )
    held_tiles = ()
    if resolved.dimensions.held_count_shown:
        held_tiles += (
            ("block:held", "quantities", "held"),
            ("block:vector:held", "vectors", "held"),
            ("block:hmapped", "mapping", "held"),
            ("block:tuning:held", "tuning", "held"),
            ("block:just:held", "just", "held"),
            ("block:retune:held", "retune", "held"),
            ("block:urow:held", "units", "held"),
            ("block:prescaling:held", "prescaling", "held"),
            ("block:complexity:held", "complexity", "held"),
        )
    detempering_tiles = (
        ("block:detempering", "quantities", "detempering"),
        ("block:vector:detempering", "vectors", "detempering"),
        ("block:mapped_detempering", "mapping", "detempering"),
        ("block:tuning:detempering", "tuning", "detempering"),
        ("block:just:detempering", "just", "detempering"),
        ("block:retune:detempering", "retune", "detempering"),
        ("block:prescaling:detempering", "prescaling", "detempering"),
        ("block:complexity:detempering", "complexity", "detempering"),
        ("block:urow:detempering", "units", "detempering"),
    ) if resolved.flags.generator_detempering else ()
    return interest_tiles, held_tiles, detempering_tiles


def declare_tiles(resolved, context, interest_tiles, held_tiles, detempering_tiles):
    tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
             + SUPERSPACE_COUNTS_TILES
             + TILES + UNITS_TILES + SUPERSPACE_TILES
             + interest_tiles + held_tiles + detempering_tiles + _projection_col_tiles(resolved)
             + _superspace_projection_col_tiles(resolved) + _canon_col_tiles(resolved))
    declared_tiles = {(row_key, column_key) for _bid, row_key, column_key in tiles}
    return tiles, _prune_declared_tiles(declared_tiles, resolved, context)


def _projection_col_tiles(resolved):
    if not resolved.flags.projection:
        return ()
    tiles = (
        ("block:projection:quantities", "projection", "quantities"),
        ("block:projection:units", "projection", "units"),
    )
    if resolved.flags.generator_detempering:
        tiles += (("block:projection:detempering", "projection", "detempering"),)
    if resolved.scalars.targets_editable:
        tiles += (("block:projection:targets", "projection", "targets"),)
    if resolved.dimensions.held_count_shown:
        tiles += (("block:projection:held", "projection", "held"),)
    if resolved.dimensions.interest_count_shown:
        tiles += (("block:projection:interest", "projection", "interest"),)
    if resolved.flags.superspace:
        tiles += (
            ("block:projection:superspace_generators", "projection", "superspace_generators"),
            ("block:projection:superspace_primes", "projection", "superspace_primes"),
        )
    return tiles


def _superspace_projection_col_tiles(resolved):
    if not resolved.flags.superspace_projection:
        return ()
    tiles = (
        ("block:superspace_projection:superspace_generators", "superspace_projection", "superspace_generators"),
        ("block:superspace_projection:primes", "superspace_projection", "primes"),
    )
    if resolved.unchanged.shown:
        tiles += (("block:superspace_projection:commas", "superspace_projection", "commas"),)
    if resolved.flags.generator_detempering:
        tiles += (("block:superspace_projection:detempering", "superspace_projection", "detempering"),)
    if resolved.scalars.targets_editable:
        tiles += (("block:superspace_projection:targets", "superspace_projection", "targets"),)
    if resolved.dimensions.held_count_shown:
        tiles += (("block:superspace_projection:held", "superspace_projection", "held"),)
    if resolved.dimensions.interest_count_shown:
        tiles += (("block:superspace_projection:interest", "superspace_projection", "interest"),)
    return tiles


def _canon_col_tiles(resolved):
    if not resolved.flags.canon:
        return ()
    tiles = (("block:canon_comma", "canon", "commas"),)
    if resolved.flags.generator_detempering:
        tiles += (("block:canon_detempering", "canon", "detempering"),)
    if resolved.scalars.targets_editable:
        tiles += (("block:canon_mapped", "canon", "targets"),)
    if resolved.dimensions.held_count_shown:
        tiles += (("block:canon_held", "canon", "held"),)
    if resolved.dimensions.interest_count_shown:
        tiles += (("block:canon_interest", "canon", "interest"),)
    return tiles


def _prune_declared_tiles(declared_tiles, resolved, context):
    if service.is_all_interval(context.tuning_scheme):
        declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                           ("tuning", "targets"), ("just", "targets"), ("retune", "targets"),
                           ("superspace_vectors", "targets"), ("superspace_mapping", "targets")}
    if not resolved.flags.identity_objects:
        declared_tiles -= {("vectors", "primes"), ("mapping", "gens"),
                                ("mapping", "detempering"), ("canon", "canongens"),
                                ("superspace_vectors", "superspace_primes"), ("superspace_mapping", "superspace_generators")}
    if not resolved.dimensions.held_count_shown:
        declared_tiles -= {("superspace_vectors", "held"), ("superspace_mapping", "held")}
    if not resolved.dimensions.interest_count_shown:
        declared_tiles -= {("superspace_vectors", "interest"), ("superspace_mapping", "interest")}
    return declared_tiles


def init_superspace_tuning(resolved, context):
    if not resolved.flags.superspace:
        return None
    superspace_override = context.superspace_generator_tuning if resolved.flags.superspace_generators else None
    return service.superspace_tuning(context.state, context.tuning_scheme, context.nonprime_approach,
                                     generator_override=superspace_override)


def caption_floor(geometry, resolved, key: str):
    if not resolved.flags.names:
        return 0
    return max((_min_width_for_lines(resolved.labels.captions[(rk, key)], MAX_CAPTION_LINES)
                for rk in geometry.present_caption_rows
                if (rk, key) in resolved.labels.captions and (rk, key) in geometry.declared_tiles), default=0)


def symbol_floor(geometry, resolved, key: str):
    if not (resolved.flags.symbols or resolved.flags.equivalences):
        return 0
    floor = 0
    for (row_key, column_key), glyph in SYMBOLS.items():
        if column_key != key or (row_key, column_key) not in geometry.declared_tiles:
            continue
        equiv = ""
        if resolved.flags.equivalences:
            equiv = EQUIVALENCES.get((row_key, column_key), "")
            if resolved.flags.form_subscript and (row_key, column_key) in FORM_EQUIVALENCES:
                equiv = FORM_EQUIVALENCES[(row_key, column_key)]
            if (row_key, column_key) == ("projection", "primes"):
                equiv += query.projection_superspace_tail(resolved)
        sub_glyph = query.form_subscripted(resolved, glyph, row_key, column_key)
        floor = max(floor, _min_width_for_lines(sub_glyph + equiv, 1, SYMBOL_FONT))
    return floor


def control_floor(resolved, context, key: str):
    floor = 0
    if key == ("superspace_primes" if resolved.flags.superspace else "primes") and resolved.flags.lbox_show:
        floor = PBOX_WIDTH if resolved.flags.presets else LBOX_DIM_WIDTH + 2 * BOX_INNER
    if key == "targets" and resolved.flags.cbox_show:
        cbox_width = CBOX_WIDTH if resolved.flags.presets else CBOX_NODROP_WIDTH
        floor = max(floor, cbox_width + 2 * BOX_INNER)
    if key == "targets" and resolved.flags.presets and context.settings["all_interval"]:
        floor = max(floor, TBOX_WIDTH)
    if (key == "targets" and resolved.flags.optimization and "row:damage" not in context.collapsed
            and "tile:damage:targets" not in context.collapsed):
        floor = max(floor, OPT_BOX_MIN_WIDTH)
    labels = ([lbl for _n, resolved, c, lbl in PRESETS + PRESET_COPIES if c == key and lbl] if resolved.flags.presets else [])
    labels += [lbl for _n, resolved, c, lbl in FORM_CHOOSERS if c == key and lbl] if resolved.flags.form_controls else []
    if labels:
        floor = max(floor, BOX_OUTER + BOX_INNER + 6 + max(_min_width_for_lines(lbl, 1) for lbl in labels))
    if key in ("primes", "gens") and context.settings["projection"]:
        floor = max(floor, 2 * BOX_OUTER + SCHEME_CTRL_WIDTH)
    return floor


def commas_band_width(resolved, nc_count: int):
    nv = nc_count + resolved.dimensions.unchanged_count
    split = V_SPLIT_GAP if (resolved.unchanged.shown and nc_count > 0) else 0
    empty = (_min_width_for_lines("nullity", 1)
             if (resolved.unchanged.shown and nc_count == 0) else 0)
    return 2 * BRACKET_WIDTH + nv * COLUMN_WIDTH + split + empty


def _caption_wrap_w(geometry, resolved, context, column_key: str):
    if column_key == "commas" and resolved.ghosts.comma:
        resting = commas_band_width(resolved, resolved.dimensions.comma_count + (1 if resolved.commas.pending is not None else 0))
        return max(resting, caption_floor(geometry, resolved, column_key),
                   control_floor(resolved, context, column_key), symbol_floor(geometry, resolved, column_key))
    return geometry.open_column_width[column_key]


def caption_band(geometry, resolved, context, key: str, folded: bool):
    if not (resolved.flags.names and key in BANDS["caption"].rows and not folded):
        return 0
    lines = [_wrap_lines(resolved.labels.captions[(key, c)], _caption_wrap_w(geometry, resolved, context, c)) for c in geometry.column_x
             if (key, c) in resolved.labels.captions and (key, c) in geometry.declared_tiles]
    if key == "counts" and resolved.unchanged.shown and "commas" in geometry.column_x:
        lines.append(_wrap_lines("unchanged interval count", resolved.dimensions.unchanged_count * COLUMN_WIDTH))
        lines.append(_wrap_lines("nullity", resolved.dimensions.comma_count * COLUMN_WIDTH + resolved.unchanged.empty_comma_width))
    return max(lines, default=1) * CAPTION_LINE


def plain_text_band(geometry, key: str, folded: bool):
    if folded or not any(rk == key for rk, _ck in geometry.plain_text_strings):
        return 0
    return PLAIN_TEXT_EDIT_HEIGHT if key in EDITABLE_PLAIN_TEXT_ROWS else PLAIN_TEXT_HEIGHT


def control_region_band_height(content_height):
    return 2 * BOX_OUTER + 2 * BOX_INNER + content_height


def _control_band_h(geometry, column_key: str, cap_width, label, scheme_button: bool = False, form_label=None):
    return 2 * BOX_OUTER + query.control_dims(geometry, column_key, cap_width, label, scheme_button, form_label)[2]


def preset_band_height(geometry, resolved, key: str):
    return max((_control_band_h(geometry, column_key, query.preset_cap(name), label, scheme_button=(name == "projection"),
                               form_label=query.preset_form_label(resolved, name, rk, column_key))
                for name, rk, column_key, label in PRESETS + PRESET_COPIES
                if rk == key and column_key in geometry.column_width), default=0)


def formchooser_band_height(geometry, key: str):
    return max((_control_band_h(geometry, column_key, PRESET_WIDTH, label)
                for name, rk, column_key, label in FORM_CHOOSERS if rk == key and column_key in geometry.column_width), default=0)

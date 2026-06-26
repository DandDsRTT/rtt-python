from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    BANDS,
    COUNTS_TILES,
    DETEMPERING_COUNTS_TILES,
    EDITABLE_PTEXT_ROWS,
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
    BRACKET_W,
    CAPTION_LINE,
    CBOX_NODROP_W,
    CBOX_W,
    COL_W,
    LBOX_DIM_W,
    MAX_CAPTION_LINES,
    OPT_BOX_MIN_W,
    PBOX_W,
    PRESET_W,
    PTEXT_EDIT_H,
    PTEXT_H,
    SCHEME_CTRL_W,
    SYMBOL_FONT,
    TBOX_W,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_text import (
    _min_width_for_lines,
    _wrap_lines,
)


def declare_interval_column_tiles(resolved):
    _r = resolved
    interest_tiles = ()
    if _r.dims.mi_shown:
        interest_tiles += (
            ("block:vec:interest", "vectors", "interest"),
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
    if _r.dims.nh_shown:
        held_tiles += (
            ("block:held", "quantities", "held"),
            ("block:vec:held", "vectors", "held"),
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
        ("block:vec:detempering", "vectors", "detempering"),
        ("block:mapped_detempering", "mapping", "detempering"),
        ("block:tuning:detempering", "tuning", "detempering"),
        ("block:just:detempering", "just", "detempering"),
        ("block:retune:detempering", "retune", "detempering"),
        ("block:prescaling:detempering", "prescaling", "detempering"),
        ("block:complexity:detempering", "complexity", "detempering"),
        ("block:urow:detempering", "units", "detempering"),
    ) if _r.flags.detempering else ()
    return interest_tiles, held_tiles, detempering_tiles


def declare_tiles(resolved, ctx, interest_tiles, held_tiles, detempering_tiles):
    tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
             + SUPERSPACE_COUNTS_TILES
             + TILES + UNITS_TILES + SUPERSPACE_TILES
             + interest_tiles + held_tiles + detempering_tiles + _projection_col_tiles(resolved)
             + _ss_projection_col_tiles(resolved) + _canon_col_tiles(resolved))
    declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in tiles}
    return tiles, _prune_declared_tiles(declared_tiles, resolved, ctx)


def _projection_col_tiles(resolved):
    _r = resolved
    if not _r.flags.projection:
        return ()
    tiles = (
        ("block:proj:quantities", "projection", "quantities"),
        ("block:proj:units", "projection", "units"),
    )
    if _r.flags.detempering:
        tiles += (("block:proj:detempering", "projection", "detempering"),)
    if _r.scalars.targets_editable:
        tiles += (("block:proj:targets", "projection", "targets"),)
    if _r.dims.nh_shown:
        tiles += (("block:proj:held", "projection", "held"),)
    if _r.dims.mi_shown:
        tiles += (("block:proj:interest", "projection", "interest"),)
    if _r.flags.superspace:
        tiles += (
            ("block:proj:ssgens", "projection", "ssgens"),
            ("block:proj:ssprimes", "projection", "ssprimes"),
        )
    return tiles


def _ss_projection_col_tiles(resolved):
    _r = resolved
    if not _r.flags.ss_projection:
        return ()
    tiles = (
        ("block:ssproj:ssgens", "ss_projection", "ssgens"),
        ("block:ssproj:primes", "ss_projection", "primes"),
    )
    if _r.unchanged.shown:
        tiles += (("block:ssproj:commas", "ss_projection", "commas"),)
    if _r.flags.detempering:
        tiles += (("block:ssproj:detempering", "ss_projection", "detempering"),)
    if _r.scalars.targets_editable:
        tiles += (("block:ssproj:targets", "ss_projection", "targets"),)
    if _r.dims.nh_shown:
        tiles += (("block:ssproj:held", "ss_projection", "held"),)
    if _r.dims.mi_shown:
        tiles += (("block:ssproj:interest", "ss_projection", "interest"),)
    return tiles


def _canon_col_tiles(resolved):
    _r = resolved
    if not _r.flags.canon:
        return ()
    tiles = (("block:canon_comma", "canon", "commas"),)
    if _r.flags.detempering:
        tiles += (("block:canon_detempering", "canon", "detempering"),)
    if _r.scalars.targets_editable:
        tiles += (("block:canon_mapped", "canon", "targets"),)
    if _r.dims.nh_shown:
        tiles += (("block:canon_held", "canon", "held"),)
    if _r.dims.mi_shown:
        tiles += (("block:canon_interest", "canon", "interest"),)
    return tiles


def _prune_declared_tiles(declared_tiles, resolved, ctx):
    _r = resolved
    if service.is_all_interval(ctx.tuning_scheme):
        declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                           ("tuning", "targets"), ("just", "targets"), ("retune", "targets"),
                           ("ss_vectors", "targets"), ("ss_mapping", "targets")}
    if not _r.flags.identity_objects:
        declared_tiles -= {("vectors", "primes"), ("mapping", "gens"),
                                ("mapping", "detempering"), ("canon", "canongens"),
                                ("ss_vectors", "ssprimes"), ("ss_mapping", "ssgens")}
    if not _r.dims.nh_shown:
        declared_tiles -= {("ss_vectors", "held"), ("ss_mapping", "held")}
    if not _r.dims.mi_shown:
        declared_tiles -= {("ss_vectors", "interest"), ("ss_mapping", "interest")}
    return declared_tiles


def init_superspace_tuning(resolved, ctx):
    if not resolved.flags.superspace:
        return None
    ss_override = ctx.superspace_generator_tuning if resolved.flags.superspace_generators else None
    return service.superspace_tuning(ctx.state, ctx.tuning_scheme, ctx.nonprime_approach,
                                     generator_override=ss_override)


def caption_floor(geometry, resolved, key: str):
    if not resolved.flags.captions:
        return 0
    return max((_min_width_for_lines(resolved.labels.captions[(rk, key)], MAX_CAPTION_LINES)
                for rk in geometry.present_caption_rows
                if (rk, key) in resolved.labels.captions and (rk, key) in geometry.declared_tiles), default=0)


def symbol_floor(geometry, resolved, key: str):
    if not (resolved.flags.symbols or resolved.flags.equiv):
        return 0
    floor = 0
    for (rkey, ckey), glyph in SYMBOLS.items():
        if ckey != key or (rkey, ckey) not in geometry.declared_tiles:
            continue
        equiv = ""
        if resolved.flags.equiv:
            equiv = EQUIVALENCES.get((rkey, ckey), "")
            if resolved.flags.form_subscript and (rkey, ckey) in FORM_EQUIVALENCES:
                equiv = FORM_EQUIVALENCES[(rkey, ckey)]
            if (rkey, ckey) == ("projection", "primes"):
                equiv += query.projection_superspace_tail(resolved)
        sub_glyph = query.form_subscripted(resolved, glyph, rkey, ckey)
        floor = max(floor, _min_width_for_lines(sub_glyph + equiv, 1, SYMBOL_FONT))
    return floor


def control_floor(resolved, ctx, key: str):
    floor = 0
    if key == ("ssprimes" if resolved.flags.superspace else "primes") and resolved.flags.lbox_show:
        floor = PBOX_W if resolved.flags.presets else LBOX_DIM_W + 2 * BOX_INNER
    if key == "targets" and resolved.flags.cbox_show:
        cbox_w = CBOX_W if resolved.flags.presets else CBOX_NODROP_W
        floor = max(floor, cbox_w + 2 * BOX_INNER)
    if key == "targets" and resolved.flags.presets and ctx.settings["all_interval"]:
        floor = max(floor, TBOX_W)
    if (key == "targets" and resolved.flags.optimization and "row:damage" not in ctx.collapsed
            and "tile:damage:targets" not in ctx.collapsed):
        floor = max(floor, OPT_BOX_MIN_W)
    labels = ([lbl for _n, _r, c, lbl in PRESETS + PRESET_COPIES if c == key and lbl] if resolved.flags.presets else [])
    labels += [lbl for _n, _r, c, lbl in FORM_CHOOSERS if c == key and lbl] if resolved.flags.form_controls else []
    if labels:
        floor = max(floor, BOX_OUTER + BOX_INNER + 6 + max(_min_width_for_lines(lbl, 1) for lbl in labels))
    if key in ("primes", "gens") and ctx.settings["projection"]:
        floor = max(floor, 2 * BOX_OUTER + SCHEME_CTRL_W)
    return floor


def commas_band_w(resolved, nc_count: int):
    nv = nc_count + resolved.dims.nu
    split = V_SPLIT_GAP if (resolved.unchanged.shown and nc_count > 0) else 0
    empty = (_min_width_for_lines("nullity", 1)
             if (resolved.unchanged.shown and nc_count == 0) else 0)
    return 2 * BRACKET_W + nv * COL_W + split + empty


def _caption_wrap_w(geometry, resolved, ctx, ckey: str):
    if ckey == "commas" and resolved.ghosts.comma:
        resting = commas_band_w(resolved, resolved.dims.nc + (1 if resolved.commas.pending is not None else 0))
        return max(resting, caption_floor(geometry, resolved, ckey),
                   control_floor(resolved, ctx, ckey), symbol_floor(geometry, resolved, ckey))
    return geometry.open_col_w[ckey]


def caption_band(geometry, resolved, ctx, key: str, folded: bool):
    if not (resolved.flags.captions and key in BANDS["caption"].rows and not folded):
        return 0
    lines = [_wrap_lines(resolved.labels.captions[(key, c)], _caption_wrap_w(geometry, resolved, ctx, c)) for c in geometry.col_x
             if (key, c) in resolved.labels.captions and (key, c) in geometry.declared_tiles]
    if key == "counts" and resolved.unchanged.shown and "commas" in geometry.col_x:
        lines.append(_wrap_lines("unchanged interval count", resolved.dims.nu * COL_W))
        lines.append(_wrap_lines("nullity", resolved.dims.nc * COL_W + resolved.unchanged.empty_comma_w))
    return max(lines, default=1) * CAPTION_LINE


def ptext_band(geometry, key: str, folded: bool):
    if folded or not any(rk == key for rk, _ck in geometry.ptext_strings):
        return 0
    return PTEXT_EDIT_H if key in EDITABLE_PTEXT_ROWS else PTEXT_H


def control_region_band_h(content_h):
    return 2 * BOX_OUTER + 2 * BOX_INNER + content_h


def _control_band_h(geometry, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):
    return 2 * BOX_OUTER + query.control_dims(geometry, ckey, cap_w, label, scheme_btn, form_label)[2]


def preset_band_h(geometry, resolved, key: str):
    return max((_control_band_h(geometry, ckey, query.preset_cap(name), label, scheme_btn=(name == "projection"),
                               form_label=query.preset_form_label(resolved, name, rk, ckey))
                for name, rk, ckey, label in PRESETS + PRESET_COPIES
                if rk == key and ckey in geometry.col_w), default=0)


def formchooser_band_h(geometry, key: str):
    return max((_control_band_h(geometry, ckey, PRESET_W, label)
                for name, rk, ckey, label in FORM_CHOOSERS if rk == key and ckey in geometry.col_w), default=0)

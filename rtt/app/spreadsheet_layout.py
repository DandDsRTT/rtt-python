from __future__ import annotations

from dataclasses import replace

from rtt.app import service, terminology
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    BANDS,
)
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BAND_GAP,
    BOX_INNER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    BRACE_H,
    BRACKET_W,
    CAPTION_LINE,
    CHART_GAP,
    CHART_H,
    COL_W,
    COMMAPICK_GAP,
    ETPICK_GAP,
    ETPICK_W,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    GAP,
    GRIP_BAND,
    HEADER_H,
    LABEL_W,
    MATLABEL_H,
    MATLABEL_PAD,
    MATLABEL_W,
    MATLABEL_W_SS,
    MATLABEL_W_SSPRIMES,
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_T,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    PAD,
    PRESET_H,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    ROW_HANDLE_GAP,
    ROW_HANDLE_W,
    SCHEME_BTN_SQ,
    STRIP,
    TITLE_MARGIN,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_geometry import (
    caption_band,
    caption_floor,
    commas_band_w,
    control_floor,
    control_region_band_h,
    declare_interval_column_tiles,
    declare_tiles,
    formchooser_band_h,
    init_superspace_tuning,
    preset_band_h,
    ptext_band,
    symbol_floor,
)
from rtt.app.spreadsheet_geometry_model import Geometry
from rtt.app.spreadsheet_models import RowBand
from rtt.app.spreadsheet_text import _title_w, _wrap_lines


def compute_geometry(resolved, context):
    interest_tiles, held_tiles, detempering_tiles = declare_interval_column_tiles(resolved)
    tiles, declared_tiles = declare_tiles(resolved, context, interest_tiles, held_tiles, detempering_tiles)
    geometry = Geometry(ss_tun=init_superspace_tuning(resolved, context),
                        tiles=tiles, declared_tiles=declared_tiles)
    geometry, col_bands, content_x0 = _define_col_bands(geometry, resolved, context, LABEL_W)
    geometry, row_bands = _define_row_bands(geometry, resolved)
    geometry = _layout_columns(geometry, resolved, context, col_bands, content_x0)
    geometry, tile_extra = _resolve_tile_extras(geometry, resolved, context)
    geometry, rows_top_y = _init_row_geometry(geometry, HEADER_H)
    geometry = _resolve_ptext_strings(geometry, resolved, context)
    geometry = _layout_rows(geometry, resolved, context, row_bands, tile_extra, rows_top_y)
    return _init_group_geometry(geometry, resolved, context)


def _resolve_col_headers(resolved):
    domain_title = ("domain basis\nelements"
                    if service.domain_has_nonprimes(resolved.dims.elements)
                    else "domain\nprimes")
    col_header = {"quantities": "interval ratios", "units": "units",
                  "canongens": "canonical\ngenerators", "gens": "generators",
                  "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                  "primes": domain_title, "detempering": "generator\ndetempering",
                  "commas": "commas",
                  "held": "held\nintervals", "targets": "target\nintervals",
                  "interest": "other intervals\nof interest"}
    if resolved.unchanged.shown:
        col_header["commas"] = "unrotated\nvector list"
    return col_header


def _matlabel_other_w(geometry, resolved):
    _label_row_present = {"mapping": resolved.flags.temperament_tiles, "vectors": resolved.flags.interval_vectors,
                          "canon": resolved.flags.canon, "projection": resolved.flags.projection,
                          "prescaling": resolved.flags.prescaling_shown, "ss_mapping": resolved.flags.superspace,
                          "ss_vectors": resolved.flags.superspace, "ss_projection": resolved.flags.ss_projection}
    other = {}
    if resolved.flags.header_symbols:
        for (rk, ck) in resolved.labels.row_labels:
            if ck not in ("primes", "ssprimes") and _label_row_present.get(rk) and (rk, ck) in geometry.declared_tiles:
                other[ck] = MATLABEL_W
    return other


def _define_col_bands(geometry, resolved, context, label_w):
    size_factor = service.complexity_size_factor(context.tuning_scheme)
    geometry = replace(
        geometry,
        col_header=_resolve_col_headers(resolved),
        matlabel_primes_w=((MATLABEL_W_SS if resolved.flags.superspace else MATLABEL_W)
                           if (resolved.flags.header_symbols and resolved.flags.temperament_tiles) else 0),
        matlabel_ssprimes_w=MATLABEL_W_SSPRIMES if (resolved.flags.header_symbols and resolved.flags.superspace) else 0,
        matlabel_other_w=_matlabel_other_w(geometry, resolved),
        row_handle_w=(ROW_HANDLE_W + ROW_HANDLE_GAP) if (
            context.settings.get("drag_to_combine") and resolved.flags.temperament_tiles and resolved.dims.r > 1) else 0,
        etpick_w=(ETPICK_W + ETPICK_GAP) if (resolved.flags.presets and resolved.flags.temperament_tiles) else 0,
        size_factor=size_factor,
        size_rows=1 if size_factor else 0,
        prescale_rows=resolved.dims.dL if resolved.flags.superspace else resolved.dims.d,
        all_interval_simplicity_weight=resolved.scalars.all_interval and (
            bool(size_factor) or resolved.scalars.prescaler_is_matrix),
        node_x=label_w + GAP,
        node_edge=label_w + GAP + TOGGLE,
    )
    return geometry, _col_bands(geometry, resolved, context), label_w + GAP + TOGGLE + GAP


def _col_bands(geometry, resolved, context):
    return (
        ("quantities", COL_W, resolved.flags.interval_ratios, True),
        ("units", COL_W, resolved.flags.domain_units, True),
        ("canongens", 2 * BRACKET_W + resolved.dims.rc * COL_W + 2 * query.matlabel_gutter_w(geometry, "canongens"), resolved.flags.canon, True),
        ("gens", 2 * BRACKET_W + resolved.dims.r * COL_W + 2 * query.matlabel_gutter_w(geometry, "gens"), resolved.flags.temperament_tiles, True),
        ("ssgens", 2 * BRACKET_W + resolved.dims.rL * COL_W, resolved.flags.superspace, True),
        ("ssprimes", 2 * BRACKET_W + resolved.dims.dL * COL_W + 2 * geometry.matlabel_ssprimes_w, resolved.flags.superspace, True),
        ("primes", 2 * BRACKET_W + resolved.dims.d_shown * COL_W + 2 * query.outer_gutter_w(geometry, "primes"), resolved.flags.temperament_tiles, True),
        ("detempering", 2 * BRACKET_W + resolved.dims.r * COL_W, resolved.flags.generator_detempering, True),
        ("commas", commas_band_w(resolved, resolved.dims.nc_shown), resolved.flags.temperament_tiles, True),
        ("held", query.interval_list_w(resolved.dims.nh_shown, "held"), resolved.flags.optimization, True),
        ("targets", query.interval_list_w(resolved.dims.k_shown, "targets"), resolved.flags.tuning_tiles and context.targets_in_use, True),
        ("interest", query.interval_list_w(resolved.dims.mi_shown, "interest"), resolved.flags.interest, True),
    )


def _define_row_bands(geometry, resolved):
    row_bands = (
        ("counts", ROW_H, resolved.flags.counts, True, "counts"),
        ("quantities", ROW_H, resolved.flags.interval_ratios, True, "interval\nratios"),
        ("units", ROW_H, resolved.flags.domain_units, True, "units"),
        ("scaling_factors", ROW_H, resolved.unchanged.shown, True, "scaling factors"),
        ("vectors", resolved.dims.d * ROW_H, resolved.flags.interval_vectors, True, "interval vectors"),
        ("canon", resolved.dims.rc * ROW_H, resolved.flags.canon, True, "canonical mapping"),
        ("mapping", resolved.dims.r_shown * ROW_H, resolved.flags.temperament_tiles, True, "mapping"),
        ("ss_vectors", resolved.dims.dL * ROW_H, resolved.flags.superspace, True, "superspace\ninterval vectors"),
        ("ss_mapping", resolved.dims.rL * ROW_H, resolved.flags.superspace, True, "superspace\nmapping"),
        ("ss_projection", resolved.dims.dL * ROW_H, resolved.flags.ss_projection, True, "superspace\nprojection"),
        ("projection", resolved.dims.d * ROW_H, resolved.flags.projection, True, "projection"),
        ("tuning", ROW_H, resolved.flags.tuning_tiles, True, "tuning"),
        ("just", ROW_H, resolved.flags.tuning_tiles, True, "just tuning"),
        ("retune", ROW_H, resolved.flags.tuning_tiles, True, "retuning"),
        ("prescaling", (geometry.prescale_rows + geometry.size_rows) * ROW_H + query.prescale_size_gap(geometry), resolved.flags.prescaling_shown, True, "complexity prescaling"),
        ("complexity", ROW_H, resolved.flags.complexity_shown, True, "complexity"),
        ("weight", ROW_H, resolved.flags.weighting, True, "weight"),
        ("damage", ROW_H, resolved.flags.tuning_tiles, True, "damage"),
    )
    row_bands = tuple(
        (key, h, present, collapsible, terminology.substitute(label, resolved.flags.terminology_mode))
        for key, h, present, collapsible, label in row_bands
    )
    present_caption_rows = frozenset(
        key for key, _h, present, _c, _l in row_bands if present and key in BANDS["caption"].rows)
    return replace(geometry, present_caption_rows=present_caption_rows), row_bands


def _layout_columns(geometry, resolved, context, col_bands, content_x0) -> Geometry:
    col_x, col_w, content_w, col_collapsible, open_col_w = {}, {}, {}, {}, {}
    x = content_x0
    first_present = True
    prev_title_oh = None
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        collapsed_col = f"col:{key}" in context.collapsed
        hug_w = max(natural, caption_floor(geometry, resolved, key), control_floor(resolved, context, key), symbol_floor(geometry, resolved, key))
        if first_present:
            hug_w = max(hug_w, _title_w(geometry.col_header[key]) - 2 * PAD)
            first_present = False
        open_col_w[key] = hug_w
        if collapsed_col:
            col_w[key] = content_w[key] = min(hug_w, _title_w(geometry.col_header[key]))
        else:
            content_w[key] = natural
            col_w[key] = hug_w
        col_collapsible[key] = collapsible
        half_oh = _title_w(geometry.col_header[key]) / 2 - col_w[key] / 2
        if prev_title_oh is not None:
            x += max(GAP, TITLE_MARGIN + prev_title_oh + half_oh)
        col_x[key] = x
        x += col_w[key]
        prev_title_oh = half_oh
    content_x = {key: col_x[key] + (col_w[key] - content_w[key]) / 2 for key in col_x}
    return replace(
        geometry, col_x=col_x, col_w=col_w, content_w=content_w, col_collapsible=col_collapsible,
        open_col_w=open_col_w, total_w=x + GAP, content_x=content_x,
        primes_x=content_x.get("primes"), commas_x=content_x.get("commas"),
        targets_x=content_x.get("targets"), interest_x=content_x.get("interest"),
        held_x=content_x.get("held"), detempering_x=content_x.get("detempering"),
        canongens_x=content_x.get("canongens"), ssgens_x=content_x.get("ssgens"),
        ssprimes_x=content_x.get("ssprimes"))


def _init_row_geometry(geometry, header_h):
    branch_top_y = header_h + (GAP - TOGGLE) / 2 + TOGGLE
    geometry = replace(geometry, header_y=0, col_node_y=header_h + (GAP - TOGGLE) / 2,
                       branch_top_y=branch_top_y, FAN=(GAP - PAD) / 2)
    return geometry, branch_top_y + GAP + GRIP_BAND


def _layout_rows(geometry, resolved, context, row_bands, tile_extra, rows_top_y) -> Geometry:
    show_charts = resolved.flags.charts
    rows: dict[str, RowBand] = {}
    y = rows_top_y
    for key, natural, present, collapsible, label in row_bands:
        if not present:
            continue
        band = _compute_row_band(geometry, resolved, context, key, natural, collapsible, label, tile_extra, show_charts, y)
        rows[key] = band
        y += band.tile_h + GAP
    return replace(geometry, rows=rows, total_h=y,
                   fanout_y=geometry.branch_top_y + geometry.FAN)


def _row_interval_handle(geometry, resolved, context, key, folded):
    return (key == "vectors" and not folded and context.settings.get("drag_to_combine")
            and ((resolved.dims.nc >= 2 and query.col_open(geometry, context.collapsed, "commas"))
                 or (resolved.dims.k >= 2 and not resolved.scalars.all_interval and query.col_open(geometry, context.collapsed, "targets"))
                 or (resolved.dims.nh >= 2 and query.col_open(geometry, context.collapsed, "held"))
                 or (resolved.dims.mi >= 2 and query.col_open(geometry, context.collapsed, "interest"))))


def _compute_row_band(geometry, resolved, context, key, natural, collapsible, label, tile_extra, show_charts, y):
    folded = f"row:{key}" in context.collapsed
    framed = key in BANDS["frame"].rows and not folded
    has_matlabel = (resolved.flags.header_symbols and key in BANDS["col_label"].rows and not folded)
    toggle_band = TOGGLE + 2 * TOGGLE_INSET - PAD
    interval_handle = _row_interval_handle(geometry, resolved, context, key, folded)
    handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if interval_handle else 0
    base_head = 0 if folded else max(toggle_band, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else toggle_band)
    head = base_head + handle_band
    top_frame = (FRAME_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    bot_frame = (BRACE_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    charted = show_charts and key in BANDS["chart"].rows and not folded and natural == ROW_H
    chart_band = (CHART_H + CHART_GAP) if charted else 0
    caption = caption_band(geometry, resolved, context, key, folded)
    symbol = BANDS["symbol"].height if ((resolved.flags.symbols or resolved.flags.equivalences)
                                     and key in BANDS["symbol"].rows and not folded) else 0
    units = BANDS["units"].height if (resolved.flags.units and key in BANDS["units"].rows and not folded) else 0
    preset = preset_band_h(geometry, resolved, key) if (((resolved.flags.presets and key in BANDS["preset"].rows)
                                     or (context.settings["all_interval"] and key == "vectors"))
                                    and not folded) else 0
    scheme_button = (control_region_band_h(SCHEME_BTN_SQ)
                 if (key == "projection" and context.settings["projection"] and not resolved.flags.presets and not folded) else 0)
    form_controls = (formchooser_band_h(geometry, key)
                if (resolved.flags.form_controls and not resolved.flags.presets
                    and key in BANDS["form_chooser"].rows and not folded) else 0)
    comma_picker = (COMMAPICK_GAP + ROW_H) if (key == "vectors" and resolved.flags.presets
                                       and query.col_open(geometry, context.collapsed, "commas")
                                       and (resolved.dims.nc > 0 or resolved.commas.pending is not None) and not folded) else 0
    ptext = ptext_band(geometry, key, folded)
    symbol += BAND_GAP if symbol else 0
    caption += BAND_GAP if caption else 0
    units += BAND_GAP if units else 0
    ptext += BAND_GAP if ptext else 0
    row_h = STRIP if folded else natural
    chart_top = (y + head + top_frame) if charted else None
    interval_handle_top = (y + (handle_band - ROW_HANDLE_W) // 2) if interval_handle else None
    matrix_label_top = (y + handle_band + (base_head - MATLABEL_H) // 2) if has_matlabel else None
    trailing_band = symbol + caption + units + preset + ptext + form_controls + scheme_button + comma_picker + tile_extra.get(key, 0)
    foot = 0 if (folded or trailing_band) else toggle_band
    tile_h = (head + top_frame + chart_band + row_h + bot_frame + comma_picker + symbol + caption + units
              + preset + ptext + form_controls + scheme_button + tile_extra.get(key, 0) + foot)
    return RowBand(
        y=y + head + top_frame + chart_band, h=row_h, label=label, collapsible=collapsible,
        tile_h=tile_h, tile_top=y, frame=bot_frame, symbol=symbol, caption=caption, units=units, ptext=ptext,
        preset=preset, scheme_button=scheme_button, num_subrows=round(natural / ROW_H), comma_picker=comma_picker,
        chart_top=chart_top, interval_handle_top=interval_handle_top, matrix_label_top=matrix_label_top)


def _group_geometry_fields(geometry, resolved):
    group_n = {"gens": resolved.dims.r, "primes": resolved.dims.d_shown, "commas": resolved.dims.nv_shown,
               "targets": resolved.dims.k_shown,
               "interest": resolved.dims.mi_shown, "held": resolved.dims.nh_shown, "detempering": resolved.dims.r,
               "canongens": resolved.dims.rc, "ssgens": resolved.dims.rL, "ssprimes": resolved.dims.dL}
    content_x = geometry.content_x
    left_fn = {"gens": lambda i: query.gen_left(geometry, i),
               "primes": lambda i: query.prime_left(geometry, i),
               "commas": lambda i: query.comma_left(geometry, resolved, i),
               "targets": lambda i: query.target_left(geometry, i),
               "interest": lambda i: query.interest_left(geometry, i),
               "held": lambda i: query.held_left(geometry, i),
               "detempering": lambda i: query.detempering_left(geometry, i),
               "canongens": lambda i: query.canongen_left(geometry, i),
               "ssgens": lambda i: query.ss_gen_left(geometry, i),
               "ssprimes": lambda i: query.ss_prime_left(geometry, i)}
    return {
        "group_elem": {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                       "interest": "interest", "held": "held", "detempering": "detempering",
                       "canongens": "cangen", "ssgens": "ssgen", "ssprimes": "ssprime"},
        "group_n": group_n,
        "group_left": {g: tuple(fn(i) for i in range(group_n[g])) if g in content_x else ()
                       for g, fn in left_fn.items()},
        "group_ratio": {
            "primes": tuple(service.element_ratio(e) for e in resolved.dims.elements),
            "commas": tuple(resolved.commas.ratios[:resolved.dims.nc]) + tuple(resolved.unchanged.ratios),
            "targets": tuple(resolved.targets.ratios),
            "interest": tuple(resolved.interest.ratios),
            "held": tuple(resolved.held.ratios),
            "detempering": tuple(resolved.scalars.gens),
            "ssprimes": tuple(service.element_ratio(e) for e in resolved.dims.superspace_primes),
        }}


def _init_group_geometry(geometry, resolved, context) -> Geometry:
    geometry = replace(geometry, **_group_geometry_fields(geometry, resolved))
    plus_stub_x = {column_key: query.col_plus_x(geometry, resolved, column_key)
                   for column_key in ("gens", "primes", "commas", "targets", "interest", "held")
                   if query.plus_shows(geometry, resolved, context.collapsed, context.state, column_key)}
    row_plus_y = {}
    if query.tile_open(geometry, context.collapsed, "vectors", "quantities") and (resolved.flags.nonstandard_domain or resolved.scalars.standard_domain):
        row_plus_y["vectors"] = query.vec_top(geometry, resolved.dims.d_shown) + ROW_H / 2
    if query.tile_open(geometry, context.collapsed, "mapping", "quantities") and context.state.n > 0:
        row_plus_y["mapping"] = query.map_top(geometry, resolved.dims.r_shown) + ROW_H / 2
    return replace(geometry, plus_stub_x=plus_stub_x, row_plus_y=row_plus_y)


def _resolve_tile_extras(geometry, resolved, context):
    gtm_chart = (resolved.flags.tuning_ranges and resolved.flags.tuning_tiles and "row:tuning" not in context.collapsed
                 and query.col_open(geometry, context.collapsed, "gens") and "tile:tuning:gens" not in context.collapsed)
    gtm_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if gtm_chart else 0
    lbox_ctrl = resolved.flags.lbox_show and query.col_open(geometry, context.collapsed, "ssprimes" if resolved.flags.superspace else "primes") and not resolved.flags.presets
    lbox_extra = (RANGE_GAP + control_region_band_h(PRESET_H + CAPTION_LINE)) if lbox_ctrl else 0
    cbox_ctrl = resolved.flags.cbox_show and query.col_open(geometry, context.collapsed, "targets")
    cbox_extra = (RANGE_GAP + control_region_band_h(ROW_H + resolved.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)) if cbox_ctrl else 0
    opt_ctrl = (resolved.flags.optimization and "row:damage" not in context.collapsed
                and query.col_open(geometry, context.collapsed, "targets") and "tile:damage:targets" not in context.collapsed)
    mean_damage_caption = "retuning magnitude" if resolved.scalars.all_interval else "power mean"
    if context.tuning_optimized:
        mean_damage_caption = f"minimized {mean_damage_caption}"
    opt_cap_lines = _wrap_lines(mean_damage_caption, OPT_MEAN_DAMAGE_W) if opt_ctrl else 1
    opt_extra = ((RANGE_GAP + OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + ROW_H + resolved.scalars.ctrl_symbol_h
                  + opt_cap_lines * CAPTION_LINE + OPT_PAD_B) if opt_ctrl else 0)
    show_approach = (service.domain_has_nonprimes(resolved.dims.elements)
                     and "row:damage" not in context.collapsed and query.col_open(geometry, context.collapsed, "targets")
                     and "tile:damage:targets" not in context.collapsed)
    approach_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if show_approach else 0
    slope_ctrl = (resolved.flags.weighting
                  and "row:weight" not in context.collapsed
                  and query.col_open(geometry, context.collapsed, "targets") and "tile:weight:targets" not in context.collapsed)
    slope_locked = slope_ctrl and (service.is_all_interval(context.tuning_scheme)
                                   or resolved.scalars.custom_weights_active)
    slope_extra = (RANGE_GAP + control_region_band_h(PRESET_H + CAPTION_LINE)) if slope_ctrl else 0
    geometry = replace(
        geometry, gtm_chart=gtm_chart, gtm_extra=gtm_extra, lbox_ctrl=lbox_ctrl, lbox_extra=lbox_extra,
        cbox_ctrl=cbox_ctrl, cbox_extra=cbox_extra, opt_ctrl=opt_ctrl, opt_extra=opt_extra,
        opt_cap_lines=opt_cap_lines, show_approach=show_approach, approach_extra=approach_extra,
        slope_ctrl=slope_ctrl, slope_extra=slope_extra, slope_locked=slope_locked,
        mean_damage_caption=mean_damage_caption)
    return geometry, {
        "tuning": gtm_extra,
        "prescaling": lbox_extra,
        "complexity": cbox_extra,
        "weight": slope_extra,
        "damage": opt_extra + approach_extra,
    }


def _resolve_ptext_strings(geometry, resolved, context) -> Geometry:
    ptext_strings = (service.plain_text_values(context.state, context.tuning_scheme, context.target_spec,
                                               held=resolved.held.vectors, interest=resolved.interest.vectors,
                                               generator_tuning=context.generator_tuning,
                                               target_override=context.target_override,
                                               nonprime_approach=context.nonprime_approach,
                                               superspace=resolved.flags.superspace,
                                               superspace_generator_override=(
                                                   context.superspace_generator_tuning
                                                   if resolved.flags.superspace_generators else None),
                                               consolidate_v=resolved.unchanged.shown,
                                               held_basis_ratios=context.held_basis_ratios,
                                               decimals=resolved.flags.decimals,
                                               custom_prescaler=context.custom_prescaler,
                                               derived=service.DerivedQuantities(
                                                   targets=resolved.targets.ratios, tun=resolved.tuning.tun,
                                                   target_weights=resolved.tuning.target_weights,
                                                   target_sizes=resolved.targets.sizes,
                                                   comma_sizes=resolved.commas.sizes,
                                                   superspace_tun=(geometry.ss_tun
                                                                   if resolved.flags.superspace else None)))
                     if resolved.flags.plain_text_values else {})
    if not resolved.flags.ebk:
        ptext_strings = {k: service.ebk_to_simple_matrix(v) for k, v in ptext_strings.items()}
    return replace(geometry, ptext_strings=ptext_strings)

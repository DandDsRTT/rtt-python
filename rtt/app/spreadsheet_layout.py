from __future__ import annotations

from types import SimpleNamespace

from rtt.app import service
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
    OPTION_BOX_PX,
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
from rtt.app.spreadsheet_geometry_model import freeze_geometry
from rtt.app.spreadsheet_models import RowBand
from rtt.app.spreadsheet_text import _title_w, _wrap_lines


def compute_geometry(resolved, ctx):
    draft = SimpleNamespace()
    init_superspace_tuning(draft, resolved, ctx)
    interest_tiles, held_tiles, detempering_tiles = declare_interval_column_tiles(resolved)
    declare_tiles(draft, resolved, ctx, interest_tiles, held_tiles, detempering_tiles)
    col_bands, content_x0 = _define_col_bands(draft, resolved, ctx, LABEL_W)
    row_bands = _define_row_bands(draft, resolved)
    _layout_columns(draft, resolved, ctx, col_bands, content_x0)
    tile_extra = _resolve_tile_extras(draft, resolved, ctx)
    rows_top_y = _init_row_geometry(draft, HEADER_H)
    _resolve_ptext_strings(draft, resolved, ctx)
    _layout_rows(draft, resolved, ctx, row_bands, tile_extra, rows_top_y)
    _init_group_geometry(draft, resolved, ctx)
    return freeze_geometry(draft)


def _resolve_col_headers(draft, resolved) -> None:
    _r = resolved
    domain_title = ("domain basis\nelements"
                    if service.domain_has_nonprimes(_r.dims.elements)
                    else "domain\nprimes")
    draft.col_header = {"quantities": "interval ratios", "units": "units",
                  "canongens": "canonical\ngenerators", "gens": "generators",
                  "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                  "primes": domain_title, "detempering": "generator\ndetempering",
                  "commas": "commas",
                  "held": "held\nintervals", "targets": "target\nintervals",
                  "interest": "other intervals\nof interest"}
    if _r.unchanged.shown:
        draft.col_header["commas"] = "unrotated\nvector list"


def _define_col_bands(draft, resolved, ctx, label_w):
    _r = resolved
    _resolve_col_headers(draft, resolved)
    draft.matlabel_primes_w = ((MATLABEL_W_SS if _r.flags.superspace else MATLABEL_W)
                              if (_r.flags.header_symbols and _r.flags.temp) else 0)
    draft.matlabel_ssprimes_w = MATLABEL_W_SSPRIMES if (_r.flags.header_symbols and _r.flags.superspace) else 0
    _label_row_present = {"mapping": _r.flags.temp, "vectors": _r.flags.interval_vectors,
                          "canon": _r.flags.canon, "projection": _r.flags.projection,
                          "prescaling": _r.flags.prescaling_shown, "ss_mapping": _r.flags.superspace,
                          "ss_vectors": _r.flags.superspace, "ss_projection": _r.flags.ss_projection}
    draft.matlabel_other_w = {}
    if _r.flags.header_symbols:
        for (rk, ck) in _r.labels.row_labels:
            if ck not in ("primes", "ssprimes") and _label_row_present.get(rk) and (rk, ck) in draft.declared_tiles:
                draft.matlabel_other_w[ck] = MATLABEL_W
    draft.row_handle_w = (ROW_HANDLE_W + ROW_HANDLE_GAP) if (
        ctx.settings.get("drag_to_combine") and _r.flags.temp and _r.dims.r > 1) else 0
    draft.etpick_w = (ETPICK_W + ETPICK_GAP) if (_r.flags.presets and _r.flags.temp) else 0
    draft.size_factor = service.complexity_size_factor(ctx.tuning_scheme)
    draft.size_rows = 1 if draft.size_factor else 0
    draft.prescale_rows = _r.dims.dL if _r.flags.superspace else _r.dims.d
    draft.all_interval_simplicity_weight = _r.scalars.all_interval and (
        bool(draft.size_factor) or _r.scalars.prescaler_is_matrix)
    col_bands = (
        ("quantities", COL_W, _r.flags.interval_ratios, True),
        ("units", COL_W, _r.flags.domain_units, True),
        ("canongens", 2 * BRACKET_W + _r.dims.rc * COL_W + 2 * query.matlabel_gutter_w(draft, "canongens"), _r.flags.canon, True),
        ("gens", 2 * BRACKET_W + _r.dims.r * COL_W + 2 * query.matlabel_gutter_w(draft, "gens"), _r.flags.temp, True),
        ("ssgens", 2 * BRACKET_W + _r.dims.rL * COL_W, _r.flags.superspace, True),
        ("ssprimes", 2 * BRACKET_W + _r.dims.dL * COL_W + 2 * draft.matlabel_ssprimes_w, _r.flags.superspace, True),
        ("primes", 2 * BRACKET_W + _r.dims.d_shown * COL_W + 2 * query.outer_gutter_w(draft, "primes"), _r.flags.temp, True),
        ("detempering", 2 * BRACKET_W + _r.dims.r * COL_W, _r.flags.detempering, True),
        ("commas", commas_band_w(resolved, _r.dims.nc_shown), _r.flags.temp, True),
        ("held", 2 * BRACKET_W + _r.dims.nh_shown * COL_W, _r.flags.optimization, True),
        ("targets", 2 * BRACKET_W + _r.dims.k_shown * COL_W, _r.flags.tuning and ctx.targets_in_use, True),
        ("interest", 2 * BRACKET_W + _r.dims.mi_shown * COL_W, _r.flags.interest, True),
    )
    draft.node_x = label_w + GAP
    draft.node_edge = draft.node_x + TOGGLE
    content_x0 = draft.node_x + TOGGLE + GAP
    return col_bands, content_x0


def _define_row_bands(draft, resolved):
    _r = resolved
    row_bands = (
        ("counts", ROW_H, _r.flags.counts, True, "counts"),
        ("quantities", ROW_H, _r.flags.interval_ratios, True, "interval\nratios"),
        ("units", ROW_H, _r.flags.domain_units, True, "units"),
        ("scaling_factors", ROW_H, _r.unchanged.shown, True, "scaling factors"),
        ("vectors", _r.dims.d * ROW_H, _r.flags.interval_vectors, True, "interval vectors"),
        ("canon", _r.dims.rc * ROW_H, _r.flags.canon, True, "canonical mapping"),
        ("mapping", _r.dims.r_shown * ROW_H, _r.flags.temp, True, "mapping"),
        ("ss_vectors", _r.dims.dL * ROW_H, _r.flags.superspace, True, "superspace\ninterval vectors"),
        ("ss_mapping", _r.dims.rL * ROW_H, _r.flags.superspace, True, "superspace\nmapping"),
        ("ss_projection", _r.dims.dL * ROW_H, _r.flags.ss_projection, True, "superspace\nprojection"),
        ("projection", _r.dims.d * ROW_H, _r.flags.projection, True, "projection"),
        ("tuning", ROW_H, _r.flags.tuning, True, "tuning"),
        ("just", ROW_H, _r.flags.tuning, True, "just tuning"),
        ("retune", ROW_H, _r.flags.tuning, True, "retuning"),
        ("prescaling", (draft.prescale_rows + draft.size_rows) * ROW_H, _r.flags.prescaling_shown, True, "complexity prescaling"),
        ("complexity", ROW_H, _r.flags.complexity_shown, True, "complexity"),
        ("weight", ROW_H, _r.flags.weighting, True, "weight"),
        ("damage", ROW_H, _r.flags.tuning, True, "damage"),
    )
    draft.present_caption_rows = frozenset(
        key for key, _h, present, _c, _l in row_bands if present and key in BANDS["caption"].rows)
    return row_bands


def _layout_columns(draft, resolved, ctx, col_bands, content_x0) -> None:
    draft.col_x, draft.col_w, draft.content_w, draft.col_collapsible, draft.open_col_w = {}, {}, {}, {}, {}
    x = content_x0
    first_present = True
    prev_title_oh = None
    for key, natural, present, collapsible in col_bands:
        if not present:
            continue
        collapsed_col = f"col:{key}" in ctx.collapsed
        hug_w = max(natural, caption_floor(draft, resolved, key), control_floor(resolved, ctx, key), symbol_floor(draft, resolved, key))
        if first_present:
            hug_w = max(hug_w, _title_w(draft.col_header[key]) - 2 * PAD)
            first_present = False
        draft.open_col_w[key] = hug_w
        if collapsed_col:
            draft.col_w[key] = draft.content_w[key] = min(hug_w, _title_w(draft.col_header[key]))
        else:
            draft.content_w[key] = natural
            draft.col_w[key] = hug_w
        draft.col_collapsible[key] = collapsible
        half_oh = _title_w(draft.col_header[key]) / 2 - draft.col_w[key] / 2
        if prev_title_oh is not None:
            x += max(GAP, TITLE_MARGIN + prev_title_oh + half_oh)
        draft.col_x[key] = x
        x += draft.col_w[key]
        prev_title_oh = half_oh
    draft.total_w = x + GAP

    draft.content_x = {key: draft.col_x[key] + (draft.col_w[key] - draft.content_w[key]) / 2 for key in draft.col_x}

    draft.primes_x = draft.content_x.get("primes")
    draft.commas_x = draft.content_x.get("commas")
    draft.targets_x = draft.content_x.get("targets")
    draft.interest_x = draft.content_x.get("interest")
    draft.held_x = draft.content_x.get("held")
    draft.detempering_x = draft.content_x.get("detempering")
    draft.canongens_x = draft.content_x.get("canongens")
    draft.ssgens_x = draft.content_x.get("ssgens")
    draft.ssprimes_x = draft.content_x.get("ssprimes")


def _init_row_geometry(draft, header_h):
    draft.header_y = 0
    draft.col_node_y = header_h + (GAP - TOGGLE) / 2
    draft.branch_top_y = draft.col_node_y + TOGGLE
    rows_top_y = draft.branch_top_y + GAP + GRIP_BAND
    draft.FAN = (GAP - PAD) / 2

    draft.rows: dict[str, RowBand] = {}
    draft.row_cpick = {}
    return rows_top_y


def _layout_rows(draft, resolved, ctx, row_bands, tile_extra, rows_top_y) -> None:
    show_charts = resolved.flags.charts
    y = rows_top_y
    for key, natural, present, collapsible, label in row_bands:
        if not present:
            continue
        band = _compute_row_band(draft, resolved, ctx, key, natural, collapsible, label, tile_extra, show_charts, y)
        draft.rows[key] = band
        y += band.tile_h + GAP
    draft.total_h = y

    draft.fanout_y = draft.branch_top_y + draft.FAN


def _row_int_handle(draft, resolved, ctx, key, folded):
    _r = resolved
    return (key == "vectors" and not folded and ctx.settings.get("drag_to_combine")
            and ((_r.dims.nc >= 2 and query.col_open(draft, ctx.collapsed, "commas"))
                 or (_r.dims.k >= 2 and not _r.scalars.all_interval and query.col_open(draft, ctx.collapsed, "targets"))
                 or (_r.dims.nh >= 2 and query.col_open(draft, ctx.collapsed, "held"))
                 or (_r.dims.mi >= 2 and query.col_open(draft, ctx.collapsed, "interest"))))


def _compute_row_band(draft, resolved, ctx, key, natural, collapsible, label, tile_extra, show_charts, y) -> RowBand:
    _r = resolved
    folded = f"row:{key}" in ctx.collapsed
    framed = key in BANDS["frame"].rows and not folded
    has_matlabel = (_r.flags.header_symbols and key in BANDS["col_label"].rows and not folded)
    head_default = TOGGLE + 2 * TOGGLE_INSET - PAD
    int_handle = _row_int_handle(draft, resolved, ctx, key, folded)
    handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if int_handle else 0
    base_head = 0 if folded else max(head_default, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else head_default)
    head = base_head + handle_band
    top_frame = (FRAME_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    bot_frame = (BRACE_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    charted = show_charts and key in BANDS["chart"].rows and not folded and natural == ROW_H
    chart_band = (CHART_H + CHART_GAP) if charted else 0
    cap = caption_band(draft, resolved, ctx, key, folded)
    sym = BANDS["symbol"].height if ((_r.flags.symbols or _r.flags.equiv)
                                     and key in BANDS["symbol"].rows and not folded) else 0
    uni = BANDS["units"].height if (_r.flags.units and key in BANDS["units"].rows and not folded) else 0
    pre = preset_band_h(draft, resolved, key) if (((_r.flags.presets and key in BANDS["preset"].rows)
                                     or (ctx.settings["all_interval"] and key == "vectors"))
                                    and not folded) else 0
    schemebtn = (control_region_band_h(SCHEME_BTN_SQ)
                 if (key == "projection" and ctx.settings["projection"] and not _r.flags.presets and not folded) else 0)
    formctrl = (formchooser_band_h(draft, key)
                if (_r.flags.form_controls and not _r.flags.presets
                    and key in BANDS["form_chooser"].rows and not folded) else 0)
    cpick = (COMMAPICK_GAP + ROW_H) if (key == "vectors" and _r.flags.presets
                                       and query.col_open(draft, ctx.collapsed, "commas")
                                       and (_r.dims.nc > 0 or _r.commas.pending is not None) and not folded) else 0
    ptext = ptext_band(draft, key, folded)
    sym += BAND_GAP if sym else 0
    cap += BAND_GAP if cap else 0
    uni += BAND_GAP if uni else 0
    ptext += BAND_GAP if ptext else 0
    row_h = STRIP if folded else natural
    chart_top = (y + head + top_frame) if charted else None
    int_handle_top = (y + (handle_band - ROW_HANDLE_W) // 2) if int_handle else None
    matlabel_top = (y + handle_band + (base_head - MATLABEL_H) // 2) if has_matlabel else None
    draft.row_cpick[key] = cpick
    tile_h = (head + top_frame + chart_band + row_h + bot_frame + cpick + sym + cap + uni
              + pre + ptext + formctrl + schemebtn + tile_extra.get(key, 0))
    return RowBand(
        y=y + head + top_frame + chart_band, h=row_h, label=label, collapsible=collapsible,
        tile_h=tile_h, tile_top=y, frame=bot_frame, sym=sym, cap=cap, units=uni, ptext=ptext,
        pre=pre, schemebtn=schemebtn, nsub=round(natural / ROW_H),
        chart_top=chart_top, int_handle_top=int_handle_top, matlabel_top=matlabel_top)


def _init_group_geometry(draft, resolved, ctx) -> None:
    _r = resolved
    draft.group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                  "interest": "interest", "held": "held", "detempering": "detempering",
                  "canongens": "cangen", "ssgens": "ssgen", "ssprimes": "ssprime"}
    group_n = {"gens": _r.dims.r, "primes": _r.dims.d_shown, "commas": _r.dims.nv_shown,
               "targets": _r.dims.k_shown,
               "interest": _r.dims.mi_shown, "held": _r.dims.nh_shown, "detempering": _r.dims.r,
               "canongens": _r.dims.rc, "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}
    draft.group_n = group_n
    content_x = draft.content_x
    left_fn = {"gens": lambda i: query.gen_left(draft, i),
               "primes": lambda i: query.prime_left(draft, i),
               "commas": lambda i: query.comma_left(draft, resolved, i),
               "targets": lambda i: query.target_left(draft, i),
               "interest": lambda i: query.interest_left(draft, i),
               "held": lambda i: query.held_left(draft, i),
               "detempering": lambda i: query.detempering_left(draft, i),
               "canongens": lambda i: query.canongen_left(draft, i),
               "ssgens": lambda i: query.ss_gen_left(draft, i),
               "ssprimes": lambda i: query.ss_prime_left(draft, i)}
    draft.group_left = {g: tuple(fn(i) for i in range(group_n[g])) if g in content_x else ()
                                for g, fn in left_fn.items()}
    draft.group_ratio = {
        "primes": tuple(service.element_ratio(e) for e in _r.dims.elements),
        "commas": tuple(_r.commas.ratios[:_r.dims.nc]) + tuple(_r.unchanged.ratios),
        "targets": tuple(_r.targets.ratios),
        "interest": tuple(_r.interest.ratios),
        "held": tuple(_r.held.ratios),
        "detempering": tuple(_r.scalars.gens),
        "ssprimes": tuple(service.element_ratio(e) for e in _r.dims.superspace_primes),
    }

    draft.plus_stub_x = {ckey: query.col_plus_x(draft, resolved, ckey)
                   for ckey in ("gens", "primes", "commas", "targets", "interest", "held")
                   if query.plus_shows(draft, resolved, ctx.collapsed, ctx.state, ckey)}

    draft.row_plus_y = {}
    if query.tile_open(draft, ctx.collapsed, "vectors", "quantities") and (_r.flags.nonstandard_domain or _r.scalars.standard_domain):
        draft.row_plus_y["vectors"] = query.vec_top(draft, _r.dims.d_shown) + ROW_H / 2
    if query.tile_open(draft, ctx.collapsed, "mapping", "quantities") and ctx.state.n > 0:
        draft.row_plus_y["mapping"] = query.map_top(draft, _r.dims.r_shown) + ROW_H / 2


def _resolve_tile_extras(draft, resolved, ctx):
    _r = resolved
    draft.gtm_chart = (_r.flags.ranges and _r.flags.tuning and "row:tuning" not in ctx.collapsed
                 and query.col_open(draft, ctx.collapsed, "gens") and "tile:tuning:gens" not in ctx.collapsed)
    draft.gtm_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if draft.gtm_chart else 0
    draft.lbox_ctrl = _r.flags.lbox_show and query.col_open(draft, ctx.collapsed, "ssprimes" if _r.flags.superspace else "primes") and not _r.flags.presets
    draft.lbox_extra = (RANGE_GAP + control_region_band_h(OPTION_BOX_PX + CAPTION_LINE)) if draft.lbox_ctrl else 0
    draft.cbox_ctrl = _r.flags.cbox_show and query.col_open(draft, ctx.collapsed, "targets")
    draft.cbox_extra = (RANGE_GAP + control_region_band_h(ROW_H + _r.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)) if draft.cbox_ctrl else 0
    draft.opt_ctrl = (_r.flags.optimization and "row:damage" not in ctx.collapsed
                and query.col_open(draft, ctx.collapsed, "targets") and "tile:damage:targets" not in ctx.collapsed)
    draft.mean_damage_caption = "retuning magnitude" if _r.scalars.all_interval else "power mean"
    if ctx.tuning_optimized:
        draft.mean_damage_caption = f"minimized {draft.mean_damage_caption}"
    draft.opt_cap_lines = _wrap_lines(draft.mean_damage_caption, OPT_MEAN_DAMAGE_W) if draft.opt_ctrl else 1
    draft.opt_extra = ((RANGE_GAP + OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + ROW_H + _r.scalars.ctrl_symbol_h
                  + draft.opt_cap_lines * CAPTION_LINE + OPT_PAD_B) if draft.opt_ctrl else 0)
    draft.show_approach = (service.domain_has_nonprimes(_r.dims.elements)
                      and "row:damage" not in ctx.collapsed and query.col_open(draft, ctx.collapsed, "targets")
                      and "tile:damage:targets" not in ctx.collapsed)
    draft.approach_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if draft.show_approach else 0
    draft.slope_ctrl = (_r.flags.weighting
                  and "row:weight" not in ctx.collapsed
                  and query.col_open(draft, ctx.collapsed, "targets") and "tile:weight:targets" not in ctx.collapsed)
    draft.slope_locked = draft.slope_ctrl and (service.is_all_interval(ctx.tuning_scheme)
                                             or _r.scalars.custom_weights_active)
    draft.slope_extra = (RANGE_GAP + control_region_band_h(PRESET_H + CAPTION_LINE)) if draft.slope_ctrl else 0
    return {
        "tuning": draft.gtm_extra,
        "prescaling": draft.lbox_extra,
        "complexity": draft.cbox_extra,
        "weight": draft.slope_extra,
        "damage": draft.opt_extra + draft.approach_extra,
    }


def _resolve_ptext_strings(draft, resolved, ctx) -> None:
    _r = resolved
    draft.ptext_strings = (service.plain_text_values(ctx.state, ctx.tuning_scheme, ctx.target_spec,
                                               held=_r.held.vectors, interest=_r.interest.vectors,
                                               generator_tuning=ctx.generator_tuning,
                                               target_override=ctx.target_override,
                                               nonprime_approach=ctx.nonprime_approach,
                                               superspace=_r.flags.superspace,
                                               superspace_generator_override=(
                                                   ctx.superspace_generator_tuning
                                                   if _r.flags.superspace_generators else None),
                                               consolidate_v=_r.unchanged.shown,
                                               held_basis_ratios=ctx.held_basis_ratios,
                                               decimals=_r.flags.decimals,
                                               custom_prescaler=ctx.custom_prescaler,
                                               derived=service.DerivedQuantities(
                                                   targets=_r.targets.ratios, tun=_r.tuning.tun,
                                                   target_weights=_r.tuning.target_weights,
                                                   target_sizes=_r.targets.sizes,
                                                   comma_sizes=_r.commas.sizes,
                                                   superspace_tun=(draft.ss_tun
                                                                   if _r.flags.superspace else None)))
                     if _r.flags.ptext else {})
    if not _r.flags.ebk:
        draft.ptext_strings = {k: service.ebk_to_simple_matrix(v) for k, v in draft.ptext_strings.items()}

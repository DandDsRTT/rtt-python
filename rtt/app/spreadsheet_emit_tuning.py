from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import BANDS, SUB_CLOSE, SUB_OPEN
from rtt.app.layout import Block, CellBox
from rtt.app.spreadsheet_closed_form import (
    _closed_form,
    _ss_closed_form,
    closed_form_operand,
)
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BOX_INNER,
    BOX_OUTER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    BRACKET_W,
    CAPTION_LINE,
    CBOX_DROP_W,
    CBOX_SLOT_W,
    CHART_H,
    COL_W,
    OPT_COL_GAP,
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_L,
    OPT_PAD_R,
    OPT_PAD_T,
    OPT_POW_CAP_W,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    PRESET_H,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    SYMBOL_H,
)
from rtt.app.spreadsheet_emit_model import EmitResult, voice
from rtt.app.spreadsheet_emit_prescaling import emit_prescaling_band
from rtt.app.spreadsheet_text import (
    _format_power,
    _math_expr,
    _power_mean,
    emit_option_check,
)


def emit_tuning(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    region_boxes: list = []
    chart_tiles: list = []
    chart_indicators: dict = {}
    _emit_tuning_rows(cells, chart_tiles, resolved, geometry, ctx)
    cells.extend(emit_prescaling_band(resolved, geometry, ctx).cells)
    _emit_lbox_control(cells, region_boxes, resolved, geometry, ctx)
    _emit_cbox_controls(cells, region_boxes, resolved, geometry, ctx)
    _emit_complexity_row(cells, chart_tiles, resolved, geometry, ctx)
    _emit_weight_row(cells, region_boxes, chart_tiles, resolved, geometry, ctx)
    _emit_damage_row(cells, chart_tiles, chart_indicators, resolved, geometry, ctx)
    _emit_charts(cells, chart_tiles, chart_indicators, geometry, ctx)
    gtm_box = _emit_tuning_ranges_box(cells, resolved, geometry, ctx)
    opt_box = _emit_optimization_box(cells, resolved, geometry, ctx)
    approach_frame, approach_box = _emit_approach_box(cells, geometry)
    return EmitResult(cells=tuple(cells), region_boxes=tuple(region_boxes),
                      extra={"gtm_box": gtm_box, "opt_box": opt_box,
                             "approach_frame": approach_frame, "approach_box": approach_box})


def tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, group, values, editable_kind=None) -> None:
    _r = resolved
    if not query.tile_open(geometry, ctx.collapsed, key, group):
        return
    values = tuple(values)
    if key in BANDS["chart"].rows:
        chart_tiles.append((key, group, values))
    y = geometry.rows[key].y
    is_gen_group = group in ("gens", "ssgens")
    is_prime_group = group in ("primes", "ssprimes")
    for i, v in enumerate(values):
        cid = f"{key}:{geometry.group_elem[group]}:{query.col_token(_r, group, i)}"
        x = geometry.group_left[group][query.comma_value_pos(_r, i) if group == "commas" else i]
        u = query.cell_unit(_r, key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
        operand = closed_form_operand(_r, geometry, ctx, key, group, i, v) if _r.flags.math else None
        if operand is not None:
            cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=u))
        else:
            cells.append(CellBox(cid, x, y, COL_W, ROW_H, editable_kind or "tuningvalue",
                                 text=service.cents(v, _r.flags.decimals), unit=u))
        if key in ("tuning", "just"):
            voice(cells, f"{key}:{group}", i, v)
    pending_idx = query.pending_draft_idx(_r, group)
    if pending_idx is not None and pending_idx[0] is not None:
        text = ""
        if _r.ghosts.comma and group == "commas":
            gsize = {"tuning": 0.0, "just": _r.ghosts.comma_just, "retune": -_r.ghosts.comma_just,
                     "complexity": _r.ghosts.comma_complexity}.get(key)
            if gsize is not None:
                text = service.cents(gsize, _r.flags.decimals)
        cells.append(CellBox(f"{key}:{geometry.group_elem[group]}:draft", geometry.group_left[group][pending_idx[1]],
                             y, COL_W, ROW_H, "tuningvalue", text=text, pending=True))


def chart(cells, geometry, ctx, rkey, ckey, values, indicator=None, indicator_label="") -> None:
    values = tuple(values)
    if values and rkey in geometry.rows and geometry.rows[rkey].chart_top is not None and query.tile_open(geometry, ctx.collapsed, rkey, ckey):
        x = geometry.group_left[ckey][0] - BRACKET_W
        gap = query.interval_col_gap(ckey)
        width = 2 * BRACKET_W + len(values) * COL_W + max(len(values) - 1, 0) * gap
        cells.append(CellBox(f"chart:{rkey}:{ckey}", x, geometry.rows[rkey].chart_top,
                             width, CHART_H, "chart", values=values, col_gap=gap,
                             indicator=indicator, indicator_label=indicator_label))


def _emit_tuning_rows(cells, chart_tiles, resolved, geometry, ctx) -> None:
    _emit_tuning_prime_rows(cells, chart_tiles, resolved, geometry, ctx)
    _emit_tuning_gen_row(cells, resolved, geometry, ctx)
    _emit_tuning_canongen_row(cells, resolved, geometry, ctx)
    _emit_tuning_superspace_rows(cells, chart_tiles, resolved, geometry, ctx)
    _emit_tuning_detempering_rows(cells, chart_tiles, resolved, geometry, ctx)


def _emit_tuning_prime_rows(cells, chart_tiles, resolved, geometry, ctx) -> None:
    _r = resolved
    tuning_data = {
        "tuning": (_r.tuning.tun.tuning_map, _r.tuning.comma_sizes.tempered + _r.unchanged.sizes.tempered, _r.tuning.target_sizes.tempered, _r.tuning.interest_sizes.tempered, _r.tuning.held_sizes.tempered),
        "just": (_r.tuning.tun.just_map, _r.tuning.comma_sizes.just + _r.unchanged.sizes.just, _r.tuning.target_sizes.just, _r.tuning.interest_sizes.just, _r.tuning.held_sizes.just),
        "retune": (_r.tuning.tun.retuning_map, _r.tuning.comma_sizes.errors + _r.unchanged.sizes.errors, _r.tuning.target_sizes.errors, _r.tuning.interest_sizes.errors, _r.tuning.held_sizes.errors),
    }
    for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
        if query.row_open(geometry, ctx.collapsed, key):
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "primes", prime_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "commas", comma_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "targets", target_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "interest", interest_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "held", held_vals)


def _emit_tuning_gen_row(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if not (query.row_open(geometry, ctx.collapsed, "tuning") and query.tile_open(geometry, ctx.collapsed, "tuning", "gens")):
        return
    gen_kind = "tuningvalue" if _r.flags.superspace_generators else "gentuningcell"
    for i, v in enumerate(_r.tuning.tun.generator_map):
        operand = None
        if _r.flags.math and not _r.flags.superspace_generators:
            closed_form = _closed_form(resolved, ctx)
            operand = closed_form.generator_operand(i, v) if closed_form is not None else None
        if operand is not None:
            cells.append(CellBox(f"tuning:gen:{query.col_token(_r, 'gens', i)}", geometry.group_left["gens"][i], geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=query.cell_unit(_r, "tuning", "gens", gen=i)))
        else:
            cells.append(CellBox(f"tuning:gen:{query.col_token(_r, 'gens', i)}", geometry.group_left["gens"][i], geometry.rows["tuning"].y, COL_W, ROW_H,
                                 gen_kind, text=service.cents(v, _r.flags.decimals), gen=i, unit=query.cell_unit(_r, "tuning", "gens", gen=i)))
        voice(cells, "tuning:gens", i, v)


def _emit_tuning_canongen_row(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if not (query.row_open(geometry, ctx.collapsed, "tuning") and query.tile_open(geometry, ctx.collapsed, "tuning", "canongens")):
        return
    gm = _r.tuning.tun.generator_map
    for j in range(_r.dims.rc):
        v = sum(gm[k] * _r.canon.inverse_form_M[k][j] for k in range(_r.dims.r))
        operand = None
        if _r.flags.math:
            closed_form = _closed_form(resolved, ctx)
            if closed_form is not None:
                coefficients = [_r.canon.inverse_form_M[k][j] for k in range(_r.dims.r)]
                operand = closed_form.canonical_generator_operand(coefficients, v)
        if operand is not None:
            cells.append(CellBox(f"tuning:cangen:{j}", query.canongen_left(geometry, j), geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=query.cell_unit(_r, "tuning", "canongens", gen=j)))
        else:
            cells.append(CellBox(f"tuning:cangen:{j}", query.canongen_left(geometry, j), geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "tuningvalue", text=service.cents(v, _r.flags.decimals), gen=j, unit=query.cell_unit(_r, "tuning", "canongens", gen=j)))
        voice(cells, "tuning:canongens", j, v)


def _emit_tuning_superspace_rows(cells, chart_tiles, resolved, geometry, ctx) -> None:
    _r = resolved
    if not (_r.flags.superspace and query.row_open(geometry, ctx.collapsed, "tuning")):
        return
    ss_tun = geometry.ss_tun
    if query.tile_open(geometry, ctx.collapsed, "tuning", "ssgens"):
        _emit_tuning_ssgen_row(cells, chart_tiles, resolved, geometry, ctx, ss_tun)
    tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "tuning", "ssprimes", ss_tun.tuning_map)
    if query.row_open(geometry, ctx.collapsed, "just"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "just", "ssprimes", ss_tun.just_map)
    if query.row_open(geometry, ctx.collapsed, "retune"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "retune", "ssprimes", ss_tun.retuning_map)


def _emit_tuning_ssgen_row(cells, chart_tiles, resolved, geometry, ctx, ss_tun) -> None:
    _r = resolved
    if not _r.flags.superspace_generators:
        tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "tuning", "ssgens", ss_tun.generator_map)
        return
    ss_cf = _ss_closed_form(resolved, ctx) if _r.flags.math else None
    for i, v in enumerate(ss_tun.generator_map):
        operand = ss_cf.generator_operand(i, v) if ss_cf is not None else None
        if operand is not None:
            cells.append(CellBox(f"tuning:ssgen:{i}", geometry.group_left["ssgens"][i], geometry.rows["tuning"].y,
                                 COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals),
                                 unit=query.cell_unit(_r, "tuning", "ssgens", gen=i)))
        else:
            cells.append(CellBox(f"tuning:ssgen:{i}", geometry.group_left["ssgens"][i], geometry.rows["tuning"].y,
                                 COL_W, ROW_H, "gentuningcell", text=service.cents(v, _r.flags.decimals),
                                 unit=query.cell_unit(_r, "tuning", "ssgens", gen=i)))
        voice(cells, "tuning:ssgens", i, v)


def _emit_tuning_detempering_rows(cells, chart_tiles, resolved, geometry, ctx) -> None:
    _r = resolved
    if not _r.flags.detempering:
        return
    for key, values in (("tuning", _r.detempering.sizes.tempered),
                        ("just", _r.detempering.sizes.just),
                        ("retune", _r.detempering.sizes.errors)):
        if query.row_open(geometry, ctx.collapsed, key):
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, key, "detempering", values)


def _emit_lbox_control(cells, region_boxes, resolved, geometry, ctx) -> None:
    _r = resolved
    if geometry.lbox_ctrl:
        box_top = geometry.rows["prescaling"].tile_top + geometry.rows["prescaling"].tile_h - geometry.lbox_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:diminuator", "ssprimes" if _r.flags.superspace else "primes",
                                box_top, PRESET_H + CAPTION_LINE)
        emit_option_check(cells, "diminuator", "replace diminuator",
                          service.diminuator_replaced(ctx.tuning_scheme), bx, by)


def _emit_cbox_controls(cells, region_boxes, resolved, geometry, ctx) -> None:
    _r = resolved
    if not geometry.cbox_ctrl:
        return
    box_top = geometry.rows["complexity"].tile_top + geometry.rows["complexity"].tile_h - geometry.cbox_extra + RANGE_GAP
    tx, cy = control_region(region_boxes, geometry, "block:complexity", "targets", box_top, ROW_H + _r.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)
    sym_y = cy + ROW_H
    cap_y = sym_y + _r.scalars.ctrl_symbol_h
    cap_h = 3 * CAPTION_LINE
    slot_w = CBOX_SLOT_W
    q_slot_x = tx
    if _r.flags.presets:
        drop_w = CBOX_DROP_W
        complexity_key = service.complexity_name_of(ctx.tuning_scheme)
        if _r.labels.realized_prescaler is None:
            complexity_key = "custom"
        complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
        complexity_values = (((*tuple(service.COMPLEXITY_DISPLAYS.values()), "custom"))
                             if _r.flags.alt_complexity else (complexity_text,))
        complexity_locked = _is_sole_option(complexity_values, complexity_text)
        cells.append(CellBox("control:complexity", tx, cy, drop_w, PRESET_H,
                             "control_select", text=complexity_text, values=complexity_values,
                             disabled=complexity_locked))
        cells.append(CellBox("caption:complexity", tx, cy + PRESET_H, drop_w,
                             CAPTION_LINE, "caption", text="predefined complexities",
                             align="left", disabled=complexity_locked))
        q_slot_x = tx + drop_w + OPT_COL_GAP
    q_x = q_slot_x + (slot_w - COL_W) / 2
    q_text = _format_power(service.complexity_norm_power(ctx.tuning_scheme))
    q_kind = "powerinput" if _r.flags.alt_complexity else "powerdisplay"
    cells.append(CellBox("control:q", q_x, cy, COL_W, ROW_H, q_kind, text=q_text))
    if _r.flags.symbols:
        cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_w, SYMBOL_H, "symbol", text="𝑞"))
    cells.append(CellBox("caption:q", q_slot_x, cap_y, slot_w, cap_h, "caption",
                         text="interval complexity norm power"))
    if service.is_all_interval(ctx.tuning_scheme):
        dual_slot_x = q_slot_x + slot_w + OPT_COL_GAP
        dual_x = dual_slot_x + (slot_w - COL_W) / 2
        dual_text = _format_power(service.dual_norm_power(ctx.tuning_scheme))
        cells.append(CellBox("control:dual", dual_x, cy, COL_W, ROW_H, "powerdisplay", text=dual_text))
        if _r.flags.symbols:
            cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_w, SYMBOL_H,
                                 "symbol", text="dual(𝑞)"))
        cells.append(CellBox("caption:dual", dual_slot_x, cap_y, slot_w, cap_h, "caption",
                             text="dual norm power"))


def _emit_complexity_row(cells, chart_tiles, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "complexity"):
        for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
            values = _r.complexities[group] + (_r.unchanged.complexities if group == "commas" else ())
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "complexity", group, values)
        if _r.flags.superspace and query.tile_open(geometry, ctx.collapsed, "complexity", "ssprimes"):
            tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "complexity", "ssprimes",
                             service.superspace_complexity_prescaler(ctx.state, ctx.tuning_scheme))


def _emit_weight_row(cells, region_boxes, chart_tiles, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "weight") and query.tile_open(geometry, ctx.collapsed, "weight", "targets"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "weight", "targets", _r.tuning.target_weights,
                         editable_kind="weightcell" if _r.scalars.custom_weights_active else None)
    if geometry.slope_ctrl:
        box_top = geometry.rows["weight"].tile_top + geometry.rows["weight"].tile_h - geometry.slope_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
        slope_w = geometry.col_w["targets"] - 2 * BOX_INNER
        cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                             "control_select", text=service.weight_slope_of(ctx.tuning_scheme),
                             values=tuple(service.WEIGHT_SLOPES), disabled=geometry.slope_locked))
        cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                             slope_w, CAPTION_LINE, "caption",
                             text="damage weight slope", align="left", disabled=geometry.slope_locked))


def _emit_damage_row(cells, chart_tiles, chart_indicators, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "damage"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, ctx, "damage", "targets", _r.tuning.target_sizes.damage)
        if _r.flags.optimization:
            power = _displayed_mean_damage_power(ctx)
            chart_indicators[("damage", "targets")] = (
                _power_mean(_r.tuning.target_sizes.damage, power), _format_power(power))


def _emit_charts(cells, chart_tiles, chart_indicators, geometry, ctx) -> None:
    for rkey, ckey, values in chart_tiles:
        indicator, label = chart_indicators.get((rkey, ckey), (None, ""))
        chart(cells, geometry, ctx, rkey, ckey, values, indicator=indicator, indicator_label=label)


def _emit_tuning_ranges_box(cells, resolved, geometry, ctx):
    _r = resolved
    gtm_box = None
    if geometry.gtm_chart:
        chosen = _r.tuning.tun.monotone_generator_range if ctx.range_mode == "monotone" else _r.tuning.tun.tradeoff_generator_range
        gx, gw = geometry.col_x["gens"], geometry.col_w["gens"]
        cy = geometry.rows["tuning"].tile_top + geometry.rows["tuning"].tile_h - geometry.gtm_extra + RANGE_GAP
        cells.append(CellBox("rangetitle:tuning:gens", gx, cy + BOX_INNER, gw, BOX_TITLE_H, "boxtitle",
                             text="tuning ranges", align="left"))
        chart_y = cy + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
        cells.append(CellBox("rangechart:tuning:gens", gx, chart_y, gw, RANGE_CHART_H, "rangechart",
                             ranges=tuple(chosen) if chosen is not None else (),
                             values=tuple(_r.tuning.tun.generator_map),
                             decimals=_r.flags.decimals))
        cells.append(CellBox("rangemode:tuning:gens", gx, chart_y + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                             "rangemode", text=ctx.range_mode))
        gtm_box = (gx, cy, gw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)
    return gtm_box


def _emit_optimization_box(cells, resolved, geometry, ctx):
    _r = resolved
    opt_box = None
    if geometry.opt_ctrl:
        ox = geometry.col_x["targets"]
        box_w = geometry.col_w["targets"]
        box_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_h
                   - geometry.opt_extra + RANGE_GAP)
        title_top = box_top + OPT_PAD_T
        content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP
        sym_top = content_top + ROW_H
        cap_top = sym_top + _r.scalars.ctrl_symbol_h
        cap_band = geometry.opt_cap_lines * CAPTION_LINE
        body_h = ROW_H + _r.scalars.ctrl_symbol_h + cap_band + OPT_PAD_B
        mean_damage_x = ox + OPT_PAD_L
        mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2
        pow_slot_x = mean_damage_x + OPT_MEAN_DAMAGE_W + OPT_COL_GAP
        pow_x = pow_slot_x + (OPT_POW_CAP_W - COL_W) / 2
        mean_damage = _power_mean(_r.tuning.target_sizes.damage, _displayed_mean_damage_power(ctx))
        power = _format_power(_displayed_optimization_power(ctx))
        cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                             text="optimization"))
        cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                             text=service.cents(mean_damage, _r.flags.decimals)))
        mean_damage_symbol = (f"⟪𝒓{_r.labels.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                      if _r.scalars.all_interval else "⟪𝐝⟫ₚ")
        if ctx.tuning_optimized:
            mean_damage_symbol = f"min({mean_damage_symbol})"
        if _r.flags.symbols:
            cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPT_MEAN_DAMAGE_W, SYMBOL_H,
                                 "symbol", text=mean_damage_symbol))
        cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, cap_top, OPT_MEAN_DAMAGE_W, cap_band,
                             "caption", text=geometry.mean_damage_caption))
        power_locked = _r.scalars.all_interval or not _r.flags.alt_complexity
        cells.append(CellBox("optimization:power", pow_x, content_top, COL_W, ROW_H,
                             "powerdisplay" if power_locked else "powerinput", text=power))
        if _r.flags.symbols:
            cells.append(CellBox("optimization:power:symbol", pow_x, sym_top, COL_W, SYMBOL_H,
                                 "symbol", text="𝑝"))
        cells.append(CellBox("optimization:power:caption", pow_x + (COL_W - OPT_POW_CAP_W) / 2, cap_top,
                             OPT_POW_CAP_W, CAPTION_LINE, "caption", text="optimization power"))
        opt_box = (ox, box_top, box_w, OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + body_h)
    return opt_box


def _emit_approach_box(cells, geometry):
    approach_frame = None
    approach_box = None
    if geometry.show_approach:
        ax = geometry.col_x["targets"]
        aw = geometry.col_w["targets"]
        box_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_h
                   - geometry.opt_extra - geometry.approach_extra + RANGE_GAP)
        cells.append(CellBox("optimization:approach:title", ax, box_top + BOX_INNER, aw, BOX_TITLE_H, "boxtitle",
                             text="nonstandard domain approach", align="left"))
        radio_top = box_top + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
        approach_box = (ax + OPT_PAD_L, radio_top,
                        aw - OPT_PAD_L - OPT_PAD_R, APPROACH_RADIO_H)
        approach_frame = (ax, box_top, aw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H)
    return approach_frame, approach_box


def control_region(region_boxes, geometry, box_id, ckey, top, content_h):
    box_y = top + BOX_OUTER
    region_boxes.append(Block(box_id, geometry.col_x[ckey], box_y, geometry.col_w[ckey],
                              2 * BOX_INNER + content_h, boxed=True))
    return geometry.col_x[ckey] + BOX_INNER, box_y + BOX_INNER


def _is_sole_option(options, value) -> bool:
    opts = options if isinstance(options, dict) else {o: o for o in options}
    return len(opts) == 1 and value in opts


def _displayed_optimization_power(ctx) -> float:
    if service.is_all_interval(ctx.tuning_scheme):
        return float("inf")
    return service.optimization_power(ctx.tuning_scheme)


def _displayed_mean_damage_power(ctx) -> float:
    if service.is_all_interval(ctx.tuning_scheme):
        return service.dual_norm_power(ctx.tuning_scheme)
    return service.optimization_power(ctx.tuning_scheme)

from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import BANDS, SUB_CLOSE, SUB_OPEN
from rtt.app.layout import Block, CellBox
from rtt.app.spreadsheet_closed_form import (
    _closed_form,
    _superspace_closed_form,
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


def emit_tuning(resolved, geometry, context) -> EmitResult:
    cells: list = []
    region_boxes: list = []
    chart_tiles: list = []
    chart_indicators: dict = {}
    _emit_tuning_rows(cells, chart_tiles, resolved, geometry, context)
    cells.extend(emit_prescaling_band(resolved, geometry, context).cells)
    _emit_lbox_control(cells, region_boxes, resolved, geometry, context)
    _emit_cbox_controls(cells, region_boxes, resolved, geometry, context)
    _emit_complexity_row(cells, chart_tiles, resolved, geometry, context)
    _emit_weight_row(cells, region_boxes, chart_tiles, resolved, geometry, context)
    _emit_damage_row(cells, chart_tiles, chart_indicators, resolved, geometry, context)
    _emit_charts(cells, chart_tiles, chart_indicators, geometry, context)
    gtm_box = _emit_tuning_ranges_box(cells, resolved, geometry, context)
    opt_box = _emit_optimization_box(cells, resolved, geometry, context)
    approach_frame, approach_box = _emit_approach_box(cells, geometry)
    return EmitResult(cells=tuple(cells), region_boxes=tuple(region_boxes),
                      extra={"gtm_box": gtm_box, "opt_box": opt_box,
                             "approach_frame": approach_frame, "approach_box": approach_box})


def tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, group, values, editable_kind=None) -> None:
    if not query.tile_open(geometry, context.collapsed, key, group):
        return
    values = tuple(values)
    if key in BANDS["chart"].rows:
        chart_tiles.append((key, group, values))
    y = geometry.rows[key].y
    is_gen_group = group in ("gens", "superspace_generators")
    is_prime_group = group in ("primes", "superspace_primes")
    for i, v in enumerate(values):
        cell_id = f"{key}:{geometry.group_elem[group]}:{query.col_token(resolved, group, i)}"
        x = geometry.group_left[group][query.comma_value_pos(resolved, i) if group == "commas" else i]
        u = query.cell_unit(resolved, key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
        operand = closed_form_operand(resolved, geometry, context, key, group, i, v) if resolved.flags.math_expressions else None
        if operand is not None:
            cells.append(CellBox(cell_id, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=u))
        else:
            cells.append(CellBox(cell_id, x, y, COL_W, ROW_H, editable_kind or "tuningvalue",
                                 text=service.cents(v, resolved.flags.decimals), unit=u))
        if key in ("tuning", "just"):
            voice(cells, f"{key}:{group}", i, v)
    pending_idx = query.pending_draft_idx(resolved, group)
    if pending_idx is not None and pending_idx[0] is not None:
        text = ""
        if resolved.ghosts.comma and group == "commas":
            gsize = {"tuning": 0.0, "just": resolved.ghosts.comma_just, "retune": -resolved.ghosts.comma_just,
                     "complexity": resolved.ghosts.comma_complexity}.get(key)
            if gsize is not None:
                text = service.cents(gsize, resolved.flags.decimals)
        cells.append(CellBox(f"{key}:{geometry.group_elem[group]}:draft", geometry.group_left[group][pending_idx[1]],
                             y, COL_W, ROW_H, "tuningvalue", text=text, pending=True))


def chart(cells, geometry, context, row_key, column_key, values, indicator=None, indicator_label="") -> None:
    values = tuple(values)
    if values and row_key in geometry.rows and geometry.rows[row_key].chart_top is not None and query.tile_open(geometry, context.collapsed, row_key, column_key):
        x = geometry.group_left[column_key][0] - BRACKET_W
        gap = query.interval_col_gap(column_key)
        width = 2 * BRACKET_W + len(values) * COL_W + max(len(values) - 1, 0) * gap
        cells.append(CellBox(f"chart:{row_key}:{column_key}", x, geometry.rows[row_key].chart_top,
                             width, CHART_H, "chart", values=values, col_gap=gap,
                             indicator=indicator, indicator_label=indicator_label))


def _emit_tuning_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    _emit_tuning_prime_rows(cells, chart_tiles, resolved, geometry, context)
    _emit_tuning_gen_row(cells, resolved, geometry, context)
    _emit_tuning_canongen_row(cells, resolved, geometry, context)
    _emit_tuning_superspace_rows(cells, chart_tiles, resolved, geometry, context)
    _emit_tuning_detempering_rows(cells, chart_tiles, resolved, geometry, context)


def _emit_tuning_prime_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    tuning_data = {
        "tuning": (resolved.tuning.tuning_map.tuning_map, resolved.tuning.comma_sizes.tempered + resolved.unchanged.sizes.tempered, resolved.tuning.target_sizes.tempered, resolved.tuning.interest_sizes.tempered, resolved.tuning.held_sizes.tempered),
        "just": (resolved.tuning.tuning_map.just_map, resolved.tuning.comma_sizes.just + resolved.unchanged.sizes.just, resolved.tuning.target_sizes.just, resolved.tuning.interest_sizes.just, resolved.tuning.held_sizes.just),
        "retune": (resolved.tuning.tuning_map.retuning_map, resolved.tuning.comma_sizes.errors + resolved.unchanged.sizes.errors, resolved.tuning.target_sizes.errors, resolved.tuning.interest_sizes.errors, resolved.tuning.held_sizes.errors),
    }
    for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
        if query.row_open(geometry, context.collapsed, key):
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "primes", prime_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "commas", comma_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "targets", target_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "interest", interest_vals)
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "held", held_vals)


def _emit_tuning_gen_row(cells, resolved, geometry, context) -> None:
    if not (query.row_open(geometry, context.collapsed, "tuning") and query.tile_open(geometry, context.collapsed, "tuning", "gens")):
        return
    gen_kind = "tuningvalue" if resolved.flags.superspace_generators else "gentuningcell"
    for i, v in enumerate(resolved.tuning.tuning_map.generator_map):
        operand = None
        if resolved.flags.math_expressions and not resolved.flags.superspace_generators:
            closed_form = _closed_form(resolved, context)
            operand = closed_form.generator_operand(i, v) if closed_form is not None else None
        if operand is not None:
            cells.append(CellBox(f"tuning:gen:{query.col_token(resolved, 'gens', i)}", geometry.group_left["gens"][i], geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "mathexpr", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "gens", gen=i)))
        else:
            cells.append(CellBox(f"tuning:gen:{query.col_token(resolved, 'gens', i)}", geometry.group_left["gens"][i], geometry.rows["tuning"].y, COL_W, ROW_H,
                                 gen_kind, text=service.cents(v, resolved.flags.decimals), gen=i, unit=query.cell_unit(resolved, "tuning", "gens", gen=i)))
        voice(cells, "tuning:gens", i, v)


def _emit_tuning_canongen_row(cells, resolved, geometry, context) -> None:
    if not (query.row_open(geometry, context.collapsed, "tuning") and query.tile_open(geometry, context.collapsed, "tuning", "canongens")):
        return
    generator_map = resolved.tuning.tuning_map.generator_map
    for j in range(resolved.dims.canonical_rank):
        v = sum(generator_map[k] * resolved.canon.inverse_form_M[k][j] for k in range(resolved.dims.rank))
        operand = None
        if resolved.flags.math_expressions:
            closed_form = _closed_form(resolved, context)
            if closed_form is not None:
                coefficients = [resolved.canon.inverse_form_M[k][j] for k in range(resolved.dims.rank)]
                operand = closed_form.canonical_generator_operand(coefficients, v)
        if operand is not None:
            cells.append(CellBox(f"tuning:cangen:{j}", query.canongen_left(geometry, j), geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "mathexpr", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "canongens", gen=j)))
        else:
            cells.append(CellBox(f"tuning:cangen:{j}", query.canongen_left(geometry, j), geometry.rows["tuning"].y, COL_W, ROW_H,
                                 "tuningvalue", text=service.cents(v, resolved.flags.decimals), gen=j, unit=query.cell_unit(resolved, "tuning", "canongens", gen=j)))
        voice(cells, "tuning:canongens", j, v)


def _emit_tuning_superspace_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    if not (resolved.flags.superspace and query.row_open(geometry, context.collapsed, "tuning")):
        return
    superspace_tuning_map = geometry.superspace_tuning_map
    if query.tile_open(geometry, context.collapsed, "tuning", "superspace_generators"):
        _emit_tuning_superspace_generator_row(cells, chart_tiles, resolved, geometry, context, superspace_tuning_map)
    tuning_value_row(cells, chart_tiles, resolved, geometry, context, "tuning", "superspace_primes", superspace_tuning_map.tuning_map)
    if query.row_open(geometry, context.collapsed, "just"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "just", "superspace_primes", superspace_tuning_map.just_map)
    if query.row_open(geometry, context.collapsed, "retune"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "retune", "superspace_primes", superspace_tuning_map.retuning_map)


def _emit_tuning_superspace_generator_row(cells, chart_tiles, resolved, geometry, context, superspace_tuning_map) -> None:
    if not resolved.flags.superspace_generators:
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "tuning", "superspace_generators", superspace_tuning_map.generator_map)
        return
    superspace_closed_form = _superspace_closed_form(resolved, context) if resolved.flags.math_expressions else None
    for i, v in enumerate(superspace_tuning_map.generator_map):
        operand = superspace_closed_form.generator_operand(i, v) if superspace_closed_form is not None else None
        if operand is not None:
            cells.append(CellBox(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
                                 COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals),
                                 unit=query.cell_unit(resolved, "tuning", "superspace_generators", gen=i)))
        else:
            cells.append(CellBox(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
                                 COL_W, ROW_H, "gentuningcell", text=service.cents(v, resolved.flags.decimals),
                                 unit=query.cell_unit(resolved, "tuning", "superspace_generators", gen=i)))
        voice(cells, "tuning:superspace_generators", i, v)


def _emit_tuning_detempering_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    if not resolved.flags.generator_detempering:
        return
    for key, values in (("tuning", resolved.detempering.sizes.tempered),
                        ("just", resolved.detempering.sizes.just),
                        ("retune", resolved.detempering.sizes.errors)):
        if query.row_open(geometry, context.collapsed, key):
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "detempering", values)


def _emit_lbox_control(cells, region_boxes, resolved, geometry, context) -> None:
    if geometry.lbox_ctrl:
        box_top = geometry.rows["prescaling"].tile_top + geometry.rows["prescaling"].tile_h - geometry.lbox_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:diminuator", "superspace_primes" if resolved.flags.superspace else "primes",
                                box_top, PRESET_H + CAPTION_LINE)
        emit_option_check(cells, "diminuator", "replace diminuator",
                          service.diminuator_replaced(context.tuning_scheme), bx, by)


def _emit_cbox_controls(cells, region_boxes, resolved, geometry, context) -> None:
    if not geometry.cbox_ctrl:
        return
    box_top = geometry.rows["complexity"].tile_top + geometry.rows["complexity"].tile_h - geometry.cbox_extra + RANGE_GAP
    tx, control_y = control_region(region_boxes, geometry, "block:complexity", "targets", box_top, ROW_H + resolved.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)
    sym_y = control_y + ROW_H
    cap_y = sym_y + resolved.scalars.ctrl_symbol_h
    cap_h = 3 * CAPTION_LINE
    slot_w = CBOX_SLOT_W
    q_slot_x = tx
    if resolved.flags.presets:
        drop_w = CBOX_DROP_W
        complexity_key = service.complexity_name_of(context.tuning_scheme)
        if resolved.labels.realized_prescaler is None:
            complexity_key = "custom"
        complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
        complexity_values = (((*tuple(service.COMPLEXITY_DISPLAYS.values()), "custom"))
                             if resolved.flags.alt_complexity else (complexity_text,))
        complexity_locked = _is_sole_option(complexity_values, complexity_text)
        cells.append(CellBox("control:complexity", tx, control_y, drop_w, PRESET_H,
                             "control_select", text=complexity_text, values=complexity_values,
                             disabled=complexity_locked))
        cells.append(CellBox("caption:complexity", tx, control_y + PRESET_H, drop_w,
                             CAPTION_LINE, "caption", text="predefined complexities",
                             align="left", disabled=complexity_locked))
        q_slot_x = tx + drop_w + OPT_COL_GAP
    q_x = q_slot_x + (slot_w - COL_W) / 2
    q_text = _format_power(service.complexity_norm_power(context.tuning_scheme))
    q_kind = "powerinput" if resolved.flags.alt_complexity else "powerdisplay"
    cells.append(CellBox("control:q", q_x, control_y, COL_W, ROW_H, q_kind, text=q_text))
    if resolved.flags.symbols:
        cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_w, SYMBOL_H, "symbol", text="𝑞"))
    cells.append(CellBox("caption:q", q_slot_x, cap_y, slot_w, cap_h, "caption",
                         text="interval complexity norm power"))
    if service.is_all_interval(context.tuning_scheme):
        dual_slot_x = q_slot_x + slot_w + OPT_COL_GAP
        dual_x = dual_slot_x + (slot_w - COL_W) / 2
        dual_text = _format_power(service.dual_norm_power(context.tuning_scheme))
        cells.append(CellBox("control:dual", dual_x, control_y, COL_W, ROW_H, "powerdisplay", text=dual_text))
        if resolved.flags.symbols:
            cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_w, SYMBOL_H,
                                 "symbol", text="dual(𝑞)"))
        cells.append(CellBox("caption:dual", dual_slot_x, cap_y, slot_w, cap_h, "caption",
                             text="dual norm power"))


def _emit_complexity_row(cells, chart_tiles, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "complexity"):
        for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
            values = resolved.complexities[group] + (resolved.unchanged.complexities if group == "commas" else ())
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, "complexity", group, values)
        if resolved.flags.superspace and query.tile_open(geometry, context.collapsed, "complexity", "superspace_primes"):
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, "complexity", "superspace_primes",
                             service.superspace_complexity_prescaler(context.state, context.tuning_scheme))


def _emit_weight_row(cells, region_boxes, chart_tiles, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "weight") and query.tile_open(geometry, context.collapsed, "weight", "targets"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "weight", "targets", resolved.tuning.target_weights,
                         editable_kind="weightcell" if resolved.scalars.custom_weights_active else None)
    if geometry.slope_ctrl:
        box_top = geometry.rows["weight"].tile_top + geometry.rows["weight"].tile_h - geometry.slope_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
        slope_w = geometry.col_w["targets"] - 2 * BOX_INNER
        cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                             "control_select", text=service.weight_slope_of(context.tuning_scheme),
                             values=tuple(service.WEIGHT_SLOPES), disabled=geometry.slope_locked))
        cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                             slope_w, CAPTION_LINE, "caption",
                             text="damage weight slope", align="left", disabled=geometry.slope_locked))


def _emit_damage_row(cells, chart_tiles, chart_indicators, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "damage"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "damage", "targets", resolved.tuning.target_sizes.damage)
        if resolved.flags.optimization:
            power = _displayed_mean_damage_power(context)
            chart_indicators[("damage", "targets")] = (
                _power_mean(resolved.tuning.target_sizes.damage, power), _format_power(power))


def _emit_charts(cells, chart_tiles, chart_indicators, geometry, context) -> None:
    for row_key, column_key, values in chart_tiles:
        indicator, label = chart_indicators.get((row_key, column_key), (None, ""))
        chart(cells, geometry, context, row_key, column_key, values, indicator=indicator, indicator_label=label)


def _emit_tuning_ranges_box(cells, resolved, geometry, context):
    gtm_box = None
    if geometry.gtm_chart:
        chosen = resolved.tuning.tuning_map.monotone_generator_range if context.range_mode == "monotone" else resolved.tuning.tuning_map.tradeoff_generator_range
        gens_x, gens_width = geometry.col_x["gens"], geometry.col_w["gens"]
        control_y = geometry.rows["tuning"].tile_top + geometry.rows["tuning"].tile_h - geometry.gtm_extra + RANGE_GAP
        cells.append(CellBox("rangetitle:tuning:gens", gens_x, control_y + BOX_INNER, gens_width, BOX_TITLE_H, "boxtitle",
                             text="tuning ranges", align="left"))
        chart_y = control_y + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
        cells.append(CellBox("rangechart:tuning:gens", gens_x, chart_y, gens_width, RANGE_CHART_H, "rangechart",
                             ranges=tuple(chosen) if chosen is not None else (),
                             values=tuple(resolved.tuning.tuning_map.generator_map),
                             decimals=resolved.flags.decimals))
        cells.append(CellBox("rangemode:tuning:gens", gens_x, chart_y + RANGE_CHART_H + RANGE_GAP, gens_width, RANGE_MODE_H,
                             "rangemode", text=context.range_mode))
        gtm_box = (gens_x, control_y, gens_width, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)
    return gtm_box


def _emit_optimization_box(cells, resolved, geometry, context):
    opt_box = None
    if geometry.opt_ctrl:
        ox = geometry.col_x["targets"]
        box_w = geometry.col_w["targets"]
        box_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_h
                   - geometry.opt_extra + RANGE_GAP)
        title_top = box_top + OPT_PAD_T
        content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP
        sym_top = content_top + ROW_H
        cap_top = sym_top + resolved.scalars.ctrl_symbol_h
        cap_band = geometry.opt_cap_lines * CAPTION_LINE
        body_h = ROW_H + resolved.scalars.ctrl_symbol_h + cap_band + OPT_PAD_B
        mean_damage_x = ox + OPT_PAD_L
        mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2
        pow_slot_x = mean_damage_x + OPT_MEAN_DAMAGE_W + OPT_COL_GAP
        pow_x = pow_slot_x + (OPT_POW_CAP_W - COL_W) / 2
        mean_damage = _power_mean(resolved.tuning.target_sizes.damage, _displayed_mean_damage_power(context))
        power = _format_power(_displayed_optimization_power(context))
        cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                             text="optimization"))
        cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                             text=service.cents(mean_damage, resolved.flags.decimals)))
        mean_damage_symbol = (f"⟪𝒓{resolved.labels.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                      if resolved.scalars.all_interval else "⟪𝐝⟫ₚ")
        if context.tuning_optimized:
            mean_damage_symbol = f"min({mean_damage_symbol})"
        if resolved.flags.symbols:
            cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPT_MEAN_DAMAGE_W, SYMBOL_H,
                                 "symbol", text=mean_damage_symbol))
        cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, cap_top, OPT_MEAN_DAMAGE_W, cap_band,
                             "caption", text=geometry.mean_damage_caption))
        power_locked = resolved.scalars.all_interval or not resolved.flags.alt_complexity
        cells.append(CellBox("optimization:power", pow_x, content_top, COL_W, ROW_H,
                             "powerdisplay" if power_locked else "powerinput", text=power))
        if resolved.flags.symbols:
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


def control_region(region_boxes, geometry, box_id, column_key, top, content_h):
    box_y = top + BOX_OUTER
    region_boxes.append(Block(box_id, geometry.col_x[column_key], box_y, geometry.col_w[column_key],
                              2 * BOX_INNER + content_h, boxed=True))
    return geometry.col_x[column_key] + BOX_INNER, box_y + BOX_INNER


def _is_sole_option(options, value) -> bool:
    opts = options if isinstance(options, dict) else {o: o for o in options}
    return len(opts) == 1 and value in opts


def _displayed_optimization_power(context) -> float:
    if service.is_all_interval(context.tuning_scheme):
        return float("inf")
    return service.optimization_power(context.tuning_scheme)


def _displayed_mean_damage_power(context) -> float:
    if service.is_all_interval(context.tuning_scheme):
        return service.dual_norm_power(context.tuning_scheme)
    return service.optimization_power(context.tuning_scheme)

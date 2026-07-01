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
    APPROACH_RADIO_HEIGHT,
    BOX_INNER,
    BOX_OUTER,
    BOX_TITLE_GAP,
    BOX_TITLE_HEIGHT,
    BRACKET_WIDTH,
    CAPTION_LINE,
    CHART_HEIGHT,
    COLUMN_WIDTH,
    COMPLEXITY_BOX_DROP_WIDTH,
    COMPLEXITY_BOX_SLOT_WIDTH,
    OPTIMIZATION_COL_GAP,
    OPTIMIZATION_MEAN_DAMAGE_WIDTH,
    OPTIMIZATION_PADDING_B,
    OPTIMIZATION_PADDING_L,
    OPTIMIZATION_PADDING_R,
    OPTIMIZATION_PADDING_T,
    OPTIMIZATION_POWER_CAP_WIDTH,
    OPTIMIZATION_TITLE_GAP,
    OPTIMIZATION_TITLE_HEIGHT,
    PRESET_HEIGHT,
    RANGE_CHART_HEIGHT,
    RANGE_GAP,
    RANGE_MODE_HEIGHT,
    ROW_HEIGHT,
    SYMBOL_HEIGHT,
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
    tuning_ranges_box = _emit_tuning_ranges_box(cells, resolved, geometry, context)
    optimization_box = _emit_optimization_box(cells, resolved, geometry, context)
    approach_frame, approach_box = _emit_approach_box(cells, geometry)
    return EmitResult(cells=tuple(cells), region_boxes=tuple(region_boxes),
                      extra={"tuning_ranges_box": tuning_ranges_box, "optimization_box": optimization_box,
                             "approach_frame": approach_frame, "approach_box": approach_box})


def tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, group, values, editable_kind=None) -> None:
    if not query.tile_open(geometry, context.collapsed, key, group):
        return
    values = tuple(values)
    if key in BANDS["chart"].rows:
        chart_tiles.append((key, group, values))
    y = geometry.rows[key].y
    is_generator_group = group in ("generators", "superspace_generators")
    is_prime_group = group in ("primes", "superspace_primes")
    for i, v in enumerate(values):
        cell_id = f"{key}:{geometry.group_elem[group]}:{query.column_token(resolved, group, i)}"
        x = geometry.group_left[group][query.comma_value_pos(resolved, i) if group == "commas" else i]
        u = query.cell_unit(resolved, key, group, generator=i if is_generator_group else None, prime=i if is_prime_group else None)
        operand = closed_form_operand(resolved, geometry, context, key, group, i, v) if resolved.flags.math_expressions else None
        if operand is not None:
            cells.append(CellBox(cell_id, x, y, COLUMN_WIDTH, ROW_HEIGHT, "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=u))
        else:
            cells.append(CellBox(cell_id, x, y, COLUMN_WIDTH, ROW_HEIGHT, editable_kind or "tuning_value",
                                 text=service.cents(v, resolved.flags.decimals), unit=u))
        if key in ("tuning", "just"):
            voice(cells, f"{key}:{group}", i, v)
    pending_index = query.pending_draft_index(resolved, group)
    if pending_index is not None and pending_index[0] is not None:
        text = ""
        if resolved.ghosts.comma and group == "commas":
            gsize = {"tuning": 0.0, "just": resolved.ghosts.comma_just, "retune": -resolved.ghosts.comma_just,
                     "complexity": resolved.ghosts.comma_complexity}.get(key)
            if gsize is not None:
                text = service.cents(gsize, resolved.flags.decimals)
        cells.append(CellBox(f"{key}:{geometry.group_elem[group]}:draft", geometry.group_left[group][pending_index[1]],
                             y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text=text, pending=True))


def chart(cells, geometry, context, row_key, column_key, values, indicator=None, indicator_label="") -> None:
    values = tuple(values)
    if values and row_key in geometry.rows and geometry.rows[row_key].chart_top is not None and query.tile_open(geometry, context.collapsed, row_key, column_key):
        x = geometry.group_left[column_key][0] - BRACKET_WIDTH
        gap = query.interval_col_gap(column_key)
        width = 2 * BRACKET_WIDTH + len(values) * COLUMN_WIDTH + max(len(values) - 1, 0) * gap
        cells.append(CellBox(f"chart:{row_key}:{column_key}", x, geometry.rows[row_key].chart_top,
                             width, CHART_HEIGHT, "chart", values=values, column_gap=gap,
                             indicator=indicator, indicator_label=indicator_label))


def _emit_tuning_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    _emit_tuning_prime_rows(cells, chart_tiles, resolved, geometry, context)
    _emit_tuning_generator_row(cells, resolved, geometry, context)
    _emit_tuning_canonical_generator_row(cells, resolved, geometry, context)
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


def _emit_tuning_generator_row(cells, resolved, geometry, context) -> None:
    if not (query.row_open(geometry, context.collapsed, "tuning") and query.tile_open(geometry, context.collapsed, "tuning", "generators")):
        return
    generator_kind = "tuning_value" if resolved.flags.superspace_generators else "generator_tuning_cell"
    for i, v in enumerate(resolved.tuning.tuning_map.generator_map):
        operand = None
        if resolved.flags.math_expressions and not resolved.flags.superspace_generators:
            closed_form = _closed_form(resolved, context)
            operand = closed_form.generator_operand(i, v) if closed_form is not None else None
        if operand is not None:
            cells.append(CellBox(f"tuning:generator:{query.column_token(resolved, 'generators', i)}", geometry.group_left["generators"][i], geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "generators", generator=i)))
        else:
            cells.append(CellBox(f"tuning:generator:{query.column_token(resolved, 'generators', i)}", geometry.group_left["generators"][i], geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 generator_kind, text=service.cents(v, resolved.flags.decimals), generator=i, unit=query.cell_unit(resolved, "tuning", "generators", generator=i)))
        voice(cells, "tuning:generators", i, v)


def _emit_tuning_canonical_generator_row(cells, resolved, geometry, context) -> None:
    if not (query.row_open(geometry, context.collapsed, "tuning") and query.tile_open(geometry, context.collapsed, "tuning", "canonical_generators")):
        return
    generator_map = resolved.tuning.tuning_map.generator_map
    for j in range(resolved.dimensions.canonical_rank):
        v = sum(generator_map[k] * resolved.canonical.form_M[k][j] for k in range(resolved.dimensions.rank))
        operand = None
        if resolved.flags.math_expressions:
            closed_form = _closed_form(resolved, context)
            if closed_form is not None:
                coefficients = [resolved.canonical.form_M[k][j] for k in range(resolved.dimensions.rank)]
                operand = closed_form.canonical_generator_operand(coefficients, v)
        if operand is not None:
            cells.append(CellBox(f"tuning:canonical_generator:{j}", query.canonical_generator_left(geometry, j), geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "canonical_generators", generator=j)))
        else:
            cells.append(CellBox(f"tuning:canonical_generator:{j}", query.canonical_generator_left(geometry, j), geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "tuning_value", text=service.cents(v, resolved.flags.decimals), generator=j, unit=query.cell_unit(resolved, "tuning", "canonical_generators", generator=j)))
        voice(cells, "tuning:canonical_generators", j, v)


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
                                 COLUMN_WIDTH, ROW_HEIGHT, "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals),
                                 unit=query.cell_unit(resolved, "tuning", "superspace_generators", generator=i)))
        else:
            cells.append(CellBox(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
                                 COLUMN_WIDTH, ROW_HEIGHT, "generator_tuning_cell", text=service.cents(v, resolved.flags.decimals),
                                 unit=query.cell_unit(resolved, "tuning", "superspace_generators", generator=i)))
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
    if geometry.prescaling_box_control:
        box_top = geometry.rows["prescaling"].tile_top + geometry.rows["prescaling"].tile_height - geometry.prescaling_box_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:diminuator", "superspace_primes" if resolved.flags.superspace else "primes",
                                box_top, PRESET_HEIGHT + CAPTION_LINE)
        emit_option_check(cells, "diminuator", "replace diminuator",
                          service.diminuator_replaced(context.tuning_scheme), bx, by)


def _emit_cbox_controls(cells, region_boxes, resolved, geometry, context) -> None:
    if not geometry.complexity_box_control:
        return
    box_top = geometry.rows["complexity"].tile_top + geometry.rows["complexity"].tile_height - geometry.complexity_box_extra + RANGE_GAP
    tx, control_y = control_region(region_boxes, geometry, "block:complexity", "targets", box_top, ROW_HEIGHT + resolved.scalars.control_symbol_height + 3 * CAPTION_LINE)
    sym_y = control_y + ROW_HEIGHT
    caption_y = sym_y + resolved.scalars.control_symbol_height
    caption_height = 3 * CAPTION_LINE
    slot_width = COMPLEXITY_BOX_SLOT_WIDTH
    q_slot_x = tx
    if resolved.flags.presets:
        drop_width = COMPLEXITY_BOX_DROP_WIDTH
        complexity_key = service.complexity_name_of(context.tuning_scheme)
        if resolved.labels.realized_prescaler is None:
            complexity_key = "custom"
        complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
        complexity_values = (((*tuple(service.COMPLEXITY_DISPLAYS.values()), "custom"))
                             if resolved.flags.alt_complexity else (complexity_text,))
        complexity_locked = _is_sole_option(complexity_values, complexity_text)
        cells.append(CellBox("control:complexity", tx, control_y, drop_width, PRESET_HEIGHT,
                             "control_select", text=complexity_text, values=complexity_values,
                             disabled=complexity_locked))
        cells.append(CellBox("caption:complexity", tx, control_y + PRESET_HEIGHT, drop_width,
                             CAPTION_LINE, "caption", text="predefined complexities",
                             align="left", disabled=complexity_locked))
        q_slot_x = tx + drop_width + OPTIMIZATION_COL_GAP
    q_x = q_slot_x + (slot_width - COLUMN_WIDTH) / 2
    q_text = _format_power(service.complexity_norm_power(context.tuning_scheme))
    q_kind = "power_input" if resolved.flags.alt_complexity else "power_display"
    cells.append(CellBox("control:q", q_x, control_y, COLUMN_WIDTH, ROW_HEIGHT, q_kind, text=q_text))
    if resolved.flags.symbols:
        cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_width, SYMBOL_HEIGHT, "symbol", text="𝑞"))
    cells.append(CellBox("caption:q", q_slot_x, caption_y, slot_width, caption_height, "caption",
                         text="interval complexity norm power"))
    if service.is_all_interval(context.tuning_scheme):
        dual_slot_x = q_slot_x + slot_width + OPTIMIZATION_COL_GAP
        dual_x = dual_slot_x + (slot_width - COLUMN_WIDTH) / 2
        dual_text = _format_power(service.dual_norm_power(context.tuning_scheme))
        cells.append(CellBox("control:dual", dual_x, control_y, COLUMN_WIDTH, ROW_HEIGHT, "power_display", text=dual_text))
        if resolved.flags.symbols:
            cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_width, SYMBOL_HEIGHT,
                                 "symbol", text="dual(𝑞)"))
        cells.append(CellBox("caption:dual", dual_slot_x, caption_y, slot_width, caption_height, "caption",
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
                         editable_kind="weight_cell" if resolved.scalars.custom_weights_active else None)
    if geometry.slope_control:
        box_top = geometry.rows["weight"].tile_top + geometry.rows["weight"].tile_height - geometry.slope_extra + RANGE_GAP
        bx, by = control_region(region_boxes, geometry, "block:slope", "targets", box_top, PRESET_HEIGHT + CAPTION_LINE)
        slope_width = geometry.column_width["targets"] - 2 * BOX_INNER
        cells.append(CellBox("control:slope", bx, by, slope_width, PRESET_HEIGHT,
                             "control_select", text=service.weight_slope_of(context.tuning_scheme),
                             values=tuple(service.WEIGHT_SLOPES), disabled=geometry.slope_locked))
        cells.append(CellBox("caption:slope", bx, by + PRESET_HEIGHT,
                             slope_width, CAPTION_LINE, "caption",
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
    tuning_ranges_box = None
    if geometry.tuning_ranges_chart:
        chosen = resolved.tuning.tuning_map.monotone_generator_range if context.range_mode == "monotone" else resolved.tuning.tuning_map.tradeoff_generator_range
        generators_x, generators_width = geometry.column_x["generators"], geometry.column_width["generators"]
        control_y = geometry.rows["tuning"].tile_top + geometry.rows["tuning"].tile_height - geometry.tuning_ranges_extra + RANGE_GAP
        cells.append(CellBox("rangetitle:tuning:generators", generators_x, control_y + BOX_INNER, generators_width, BOX_TITLE_HEIGHT, "box_title",
                             text="tuning ranges", align="left"))
        chart_y = control_y + BOX_INNER + BOX_TITLE_HEIGHT + BOX_TITLE_GAP
        cells.append(CellBox("rangechart:tuning:generators", generators_x, chart_y, generators_width, RANGE_CHART_HEIGHT, "rangechart",
                             ranges=tuple(chosen) if chosen is not None else (),
                             values=tuple(resolved.tuning.tuning_map.generator_map),
                             decimals=resolved.flags.decimals))
        cells.append(CellBox("rangemode:tuning:generators", generators_x, chart_y + RANGE_CHART_HEIGHT + RANGE_GAP, generators_width, RANGE_MODE_HEIGHT,
                             "rangemode", text=context.range_mode))
        tuning_ranges_box = (generators_x, control_y, generators_width, 2 * BOX_INNER + BOX_TITLE_HEIGHT + BOX_TITLE_GAP + RANGE_CHART_HEIGHT + RANGE_GAP + RANGE_MODE_HEIGHT)
    return tuning_ranges_box


def _emit_optimization_box(cells, resolved, geometry, context):
    optimization_box = None
    if geometry.optimization_control:
        ox = geometry.column_x["targets"]
        box_width = geometry.column_width["targets"]
        box_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_height
                   - geometry.optimization_extra + RANGE_GAP)
        title_top = box_top + OPTIMIZATION_PADDING_T
        content_top = title_top + OPTIMIZATION_TITLE_HEIGHT + OPTIMIZATION_TITLE_GAP
        sym_top = content_top + ROW_HEIGHT
        caption_top = sym_top + resolved.scalars.control_symbol_height
        caption_band = geometry.optimization_cap_lines * CAPTION_LINE
        body_height = ROW_HEIGHT + resolved.scalars.control_symbol_height + caption_band + OPTIMIZATION_PADDING_B
        mean_damage_x = ox + OPTIMIZATION_PADDING_L
        mean_damage_val_x = mean_damage_x + (OPTIMIZATION_MEAN_DAMAGE_WIDTH - COLUMN_WIDTH) / 2
        power_slot_x = mean_damage_x + OPTIMIZATION_MEAN_DAMAGE_WIDTH + OPTIMIZATION_COL_GAP
        power_x = power_slot_x + (OPTIMIZATION_POWER_CAP_WIDTH - COLUMN_WIDTH) / 2
        mean_damage = _power_mean(resolved.tuning.target_sizes.damage, _displayed_mean_damage_power(context))
        power = _format_power(_displayed_optimization_power(context))
        cells.append(CellBox("optimization:title", ox, title_top, box_width, OPTIMIZATION_TITLE_HEIGHT, "box_title",
                             text="optimization"))
        cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value",
                             text=service.cents(mean_damage, resolved.flags.decimals)))
        mean_damage_symbol = (f"⟪𝒓{resolved.labels.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                      if resolved.scalars.all_interval else "⟪𝐝⟫ₚ")
        if context.tuning_optimized:
            mean_damage_symbol = f"min({mean_damage_symbol})"
        if resolved.flags.symbols:
            cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPTIMIZATION_MEAN_DAMAGE_WIDTH, SYMBOL_HEIGHT,
                                 "symbol", text=mean_damage_symbol))
        cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, caption_top, OPTIMIZATION_MEAN_DAMAGE_WIDTH, caption_band,
                             "caption", text=geometry.mean_damage_caption))
        power_locked = resolved.scalars.all_interval or not resolved.flags.alt_complexity
        cells.append(CellBox("optimization:power", power_x, content_top, COLUMN_WIDTH, ROW_HEIGHT,
                             "power_display" if power_locked else "power_input", text=power))
        if resolved.flags.symbols:
            cells.append(CellBox("optimization:power:symbol", power_x, sym_top, COLUMN_WIDTH, SYMBOL_HEIGHT,
                                 "symbol", text="𝑝"))
        cells.append(CellBox("optimization:power:caption", power_x + (COLUMN_WIDTH - OPTIMIZATION_POWER_CAP_WIDTH) / 2, caption_top,
                             OPTIMIZATION_POWER_CAP_WIDTH, CAPTION_LINE, "caption", text="optimization power"))
        optimization_box = (ox, box_top, box_width, OPTIMIZATION_PADDING_T + OPTIMIZATION_TITLE_HEIGHT + OPTIMIZATION_TITLE_GAP + body_height)
    return optimization_box


def _emit_approach_box(cells, geometry):
    approach_frame = None
    approach_box = None
    if geometry.show_approach:
        ax = geometry.column_x["targets"]
        aw = geometry.column_width["targets"]
        box_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_height
                   - geometry.optimization_extra - geometry.approach_extra + RANGE_GAP)
        cells.append(CellBox("optimization:approach:title", ax, box_top + BOX_INNER, aw, BOX_TITLE_HEIGHT, "box_title",
                             text="nonstandard domain approach", align="left"))
        radio_top = box_top + BOX_INNER + BOX_TITLE_HEIGHT + BOX_TITLE_GAP
        approach_box = (ax + OPTIMIZATION_PADDING_L, radio_top,
                        aw - OPTIMIZATION_PADDING_L - OPTIMIZATION_PADDING_R, APPROACH_RADIO_HEIGHT)
        approach_frame = (ax, box_top, aw, 2 * BOX_INNER + BOX_TITLE_HEIGHT + BOX_TITLE_GAP + APPROACH_RADIO_HEIGHT)
    return approach_frame, approach_box


def control_region(region_boxes, geometry, box_id, column_key, top, content_height):
    box_y = top + BOX_OUTER
    region_boxes.append(Block(box_id, geometry.column_x[column_key], box_y, geometry.column_width[column_key],
                              2 * BOX_INNER + content_height, boxed=True))
    return geometry.column_x[column_key] + BOX_INNER, box_y + BOX_INNER


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

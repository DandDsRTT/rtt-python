from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import BANDS, SUB_CLOSE, SUB_OPEN
from rtt.app.layout import Block, Cell
from rtt.app.spreadsheet_closed_form import (
    _closed_form,
    _superspace_closed_form,
    closed_form_operand,
)
from rtt.app.spreadsheet_constants import (
    BRACKET_WIDTH,
    CHART_HEIGHT,
    COLUMN_WIDTH,
    COMPLEXITY_PANEL_DROP_WIDTH,
    COMPLEXITY_PANEL_SLOT_WIDTH,
    OPTIMIZATION_COL_GAP,
    OPTIMIZATION_MEAN_DAMAGE_WIDTH,
    OPTIMIZATION_PADDING_B,
    OPTIMIZATION_PADDING_L,
    OPTIMIZATION_PADDING_R,
    OPTIMIZATION_PADDING_T,
    OPTIMIZATION_POWER_CAP_WIDTH,
    OPTIMIZATION_TITLE_GAP,
    OPTIMIZATION_TITLE_HEIGHT,
    PANEL_INNER,
    PANEL_OUTER,
    PANEL_TITLE_GAP,
    PANEL_TITLE_HEIGHT,
    PRESET_HEIGHT,
    RADIO_GAP,
    RADIO_HEIGHT,
    RANGE_CHART_HEIGHT,
    RANGE_GAP,
    RANGE_MODE_HEIGHT,
    ROW_HEIGHT,
    SYMBOL_HEIGHT,
    TEXT_LINE,
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
    region_panels: list = []
    chart_tiles: list = []
    chart_indicators: dict = {}
    _emit_tuning_rows(cells, chart_tiles, resolved, geometry, context)
    cells.extend(emit_prescaling_band(resolved, geometry, context).cells)
    _emit_prescaler_panel_control(cells, region_panels, resolved, geometry, context)
    _emit_complexity_panel_controls(cells, region_panels, resolved, geometry, context)
    _emit_complexity_row(cells, chart_tiles, resolved, geometry, context)
    _emit_weight_row(cells, region_panels, chart_tiles, resolved, geometry, context)
    _emit_damage_row(cells, chart_tiles, chart_indicators, resolved, geometry, context)
    _emit_charts(cells, chart_tiles, chart_indicators, geometry, context)
    tuning_ranges_panel = _emit_tuning_ranges_panel(cells, resolved, geometry, context)
    optimization_panel, merged_approach_panel = _emit_optimization_panel(cells, resolved, geometry, context)
    approach_panel = merged_approach_panel or _emit_approach_panel(region_panels, geometry)
    return EmitResult(cells=tuple(cells), region_panels=tuple(region_panels),
                      extra={"tuning_ranges_panel": tuning_ranges_panel, "optimization_panel": optimization_panel,
                             "approach_panel": approach_panel})


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
            cells.append(Cell(cell_id, x, y, COLUMN_WIDTH, ROW_HEIGHT, "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=u))
        else:
            cells.append(Cell(cell_id, x, y, COLUMN_WIDTH, ROW_HEIGHT, editable_kind or "tuning_value",
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
        cells.append(Cell(f"{key}:{geometry.group_elem[group]}:draft", geometry.group_left[group][pending_index[1]],
                             y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text=text, pending=True))


def chart(cells, geometry, context, row_key, column_key, values, indicator=None, indicator_label="") -> None:
    values = tuple(values)
    if values and row_key in geometry.rows and geometry.rows[row_key].chart_top is not None and query.tile_open(geometry, context.collapsed, row_key, column_key):
        x = geometry.group_left[column_key][0] - BRACKET_WIDTH
        gap = query.interval_col_gap(column_key)
        width = 2 * BRACKET_WIDTH + len(values) * COLUMN_WIDTH + max(len(values) - 1, 0) * gap
        cells.append(Cell(f"chart:{row_key}:{column_key}", x, geometry.rows[row_key].chart_top,
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
            cells.append(Cell(f"tuning:generator:{query.column_token(resolved, 'generators', i)}", geometry.group_left["generators"][i], geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "generators", generator=i)))
        else:
            cells.append(Cell(f"tuning:generator:{query.column_token(resolved, 'generators', i)}", geometry.group_left["generators"][i], geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 generator_kind, text=service.cents(v, resolved.flags.decimals), generator=i, unit=query.cell_unit(resolved, "tuning", "generators", generator=i)))
        voice(cells, "tuning:generators", i, v)
    if resolved.scalars.generator_draft:
        cells.append(Cell("tuning:generator:pending", query.generator_left(geometry, resolved.dimensions.rank), geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=resolved.dimensions.rank, pending=True))


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
            cells.append(Cell(f"tuning:canonical_generator:{j}", query.canonical_generator_left(geometry, j), geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals), unit=query.cell_unit(resolved, "tuning", "canonical_generators", generator=j)))
        else:
            cells.append(Cell(f"tuning:canonical_generator:{j}", query.canonical_generator_left(geometry, j), geometry.rows["tuning"].y, COLUMN_WIDTH, ROW_HEIGHT,
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
            cells.append(Cell(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
                                 COLUMN_WIDTH, ROW_HEIGHT, "math_expression", text=_math_expr(operand, v, resolved.flags.quantities, resolved.flags.decimals),
                                 unit=query.cell_unit(resolved, "tuning", "superspace_generators", generator=i)))
        else:
            cells.append(Cell(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
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


def _emit_prescaler_panel_control(cells, region_panels, resolved, geometry, context) -> None:
    if geometry.prescaling_panel_control:
        panel_top = geometry.rows["prescaling"].tile_top + geometry.rows["prescaling"].tile_height - geometry.prescaling_panel_extra + RANGE_GAP
        bx, by = control_region(region_panels, geometry, "block:diminuator", "superspace_primes" if resolved.flags.superspace else "primes",
                                panel_top, PRESET_HEIGHT + TEXT_LINE)
        emit_option_check(cells, "diminuator", "replace diminuator",
                          service.diminuator_replaced(context.tuning_scheme), bx, by)


def _emit_complexity_panel_controls(cells, region_panels, resolved, geometry, context) -> None:
    if not geometry.complexity_panel_control:
        return
    panel_top = geometry.rows["complexity"].tile_top + geometry.rows["complexity"].tile_height - geometry.complexity_panel_extra + RANGE_GAP
    tx, control_y = control_region(region_panels, geometry, "block:complexity", "targets", panel_top, ROW_HEIGHT + resolved.scalars.control_symbol_height + 3 * TEXT_LINE)
    sym_y = control_y + ROW_HEIGHT
    text_y = sym_y + resolved.scalars.control_symbol_height
    text_height = 3 * TEXT_LINE
    slot_width = COMPLEXITY_PANEL_SLOT_WIDTH
    q_slot_x = tx
    if resolved.flags.presets:
        drop_width = COMPLEXITY_PANEL_DROP_WIDTH
        complexity_key = service.complexity_name_of(context.tuning_scheme)
        if resolved.labels.realized_prescaler is None:
            complexity_key = "custom"
        complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
        complexity_values = (tuple(service.COMPLEXITY_DISPLAYS.values())
                             if resolved.flags.alt_complexity else (complexity_text,))
        complexity_locked = _is_sole_option(complexity_values, complexity_text)
        cells.append(Cell("control:complexity", tx, control_y, drop_width, PRESET_HEIGHT,
                             "control_select", text=complexity_text, values=complexity_values,
                             disabled=complexity_locked))
        cells.append(Cell("label:established-complexities", tx, control_y + PRESET_HEIGHT, drop_width,
                             TEXT_LINE, "label", text="established complexities",
                             align="left", disabled=complexity_locked))
        q_slot_x = tx + drop_width + OPTIMIZATION_COL_GAP
    q_x = q_slot_x + (slot_width - COLUMN_WIDTH) / 2
    q_text = _format_power(service.complexity_norm_power(context.tuning_scheme))
    q_kind = "power_input" if resolved.flags.alt_complexity else "power_display"
    cells.append(Cell("control:q", q_x, control_y, COLUMN_WIDTH, ROW_HEIGHT, q_kind, text=q_text))
    if resolved.flags.symbols:
        cells.append(Cell("symbol:q", q_slot_x, sym_y, slot_width, SYMBOL_HEIGHT, "symbol", text="𝑞"))
    cells.append(Cell("label:q", q_slot_x, text_y, slot_width, text_height, "label",
                         text="interval complexity norm power"))
    if service.is_all_interval(context.tuning_scheme):
        dual_slot_x = q_slot_x + slot_width + OPTIMIZATION_COL_GAP
        dual_x = dual_slot_x + (slot_width - COLUMN_WIDTH) / 2
        dual_text = _format_power(service.dual_norm_power(context.tuning_scheme))
        cells.append(Cell("control:dual", dual_x, control_y, COLUMN_WIDTH, ROW_HEIGHT, "power_display", text=dual_text))
        if resolved.flags.symbols:
            cells.append(Cell("symbol:dual", dual_slot_x, sym_y, slot_width, SYMBOL_HEIGHT,
                                 "symbol", text="dual(𝑞)"))
        cells.append(Cell("label:dual", dual_slot_x, text_y, slot_width, text_height, "label",
                             text="dual norm power"))


def _emit_complexity_row(cells, chart_tiles, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "complexity"):
        for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
            values = resolved.complexities[group] + (resolved.unchanged.complexities if group == "commas" else ())
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, "complexity", group, values)
        if resolved.flags.superspace and query.tile_open(geometry, context.collapsed, "complexity", "superspace_primes"):
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, "complexity", "superspace_primes",
                             service.superspace_complexity_prescaler(context.state, context.tuning_scheme))


def _emit_weight_row(cells, region_panels, chart_tiles, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "weight") and query.tile_open(geometry, context.collapsed, "weight", "targets"):
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "weight", "targets", resolved.tuning.target_weights,
                         editable_kind="weight_cell" if resolved.scalars.custom_weights_active else None)
    if geometry.slope_control:
        panel_top = geometry.rows["weight"].tile_top + geometry.rows["weight"].tile_height - geometry.slope_extra + RANGE_GAP
        bx, by = control_region(region_panels, geometry, "block:slope", "targets", panel_top, geometry.slope_height)
        slope_width = geometry.column_width["targets"] - 2 * PANEL_INNER
        slope_values = tuple(service.WEIGHT_SLOPES)
        if context.settings["custom_weights"]:
            slope_labels = (*(f"{slope} slope" for slope in slope_values), "custom")
            slope_values = (*slope_values, "custom")
            slope_group = "damage weight"
        else:
            slope_labels = slope_values
            slope_group = "damage weight slope"
        slope_selected = "custom" if resolved.scalars.custom_weights_active else service.weight_slope_of(context.tuning_scheme)
        cells.append(Cell("control:slope", bx, by, slope_width, geometry.slope_height,
                             "control_radio", text=slope_selected,
                             values=slope_values, option_labels=slope_labels, label=slope_group,
                             disabled=geometry.slope_locked))


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


def _emit_tuning_ranges_panel(cells, resolved, geometry, context):
    tuning_ranges_panel = None
    if geometry.tuning_ranges_chart:
        generators_x, generators_width = geometry.column_x["generators"], geometry.column_width["generators"]
        control_y = geometry.rows["tuning"].tile_top + geometry.rows["tuning"].tile_height - geometry.tuning_ranges_extra + RANGE_GAP
        cells.append(Cell("rangetitle:tuning:generators", generators_x, control_y + PANEL_INNER, generators_width, PANEL_TITLE_HEIGHT, "panel_title",
                             text="tuning ranges", align="left"))
        y = control_y + PANEL_INNER + PANEL_TITLE_HEIGHT + PANEL_TITLE_GAP
        if geometry.tuning_range_chart:
            chosen = resolved.tuning.tuning_map.monotone_generator_range if context.range_mode == "monotone" else resolved.tuning.tuning_map.tradeoff_generator_range
            cells.append(Cell("rangechart:tuning:generators", generators_x, y, generators_width, RANGE_CHART_HEIGHT, "rangechart",
                                 ranges=tuple(chosen) if chosen is not None else (),
                                 values=tuple(resolved.tuning.tuning_map.generator_map),
                                 decimals=resolved.flags.decimals))
            y += RANGE_CHART_HEIGHT + RANGE_GAP
        if geometry.tuning_range_mode:
            cells.append(Cell("rangemode:tuning:generators", generators_x + PANEL_INNER, y, generators_width - 2 * PANEL_INNER, RANGE_MODE_HEIGHT,
                                 "rangemode", text=context.range_mode))
            y += RANGE_MODE_HEIGHT + RANGE_GAP
        tuning_ranges_panel = (generators_x, control_y, generators_width, (y - RANGE_GAP) - control_y + PANEL_INNER)
    return tuning_ranges_panel


def _emit_optimization_panel(cells, resolved, geometry, context):
    optimization_panel = None
    approach_panel = None
    if geometry.optimization_control:
        ox = geometry.column_x["targets"]
        panel_width = geometry.column_width["targets"]
        panel_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_height
                   - geometry.optimization_extra + RANGE_GAP)
        title_top = panel_top + OPTIMIZATION_PADDING_T
        approach_top = title_top + OPTIMIZATION_TITLE_HEIGHT + OPTIMIZATION_TITLE_GAP
        approach_section = (RADIO_HEIGHT + RADIO_GAP) if geometry.show_approach else 0
        content_top = approach_top + approach_section
        sym_top = content_top + ROW_HEIGHT
        text_top = sym_top + resolved.scalars.control_symbol_height
        text_band = geometry.optimization_cap_lines * TEXT_LINE
        body_height = ROW_HEIGHT + resolved.scalars.control_symbol_height + text_band + approach_section + OPTIMIZATION_PADDING_B
        mean_damage_x = ox + OPTIMIZATION_PADDING_L
        mean_damage_val_x = mean_damage_x + (OPTIMIZATION_MEAN_DAMAGE_WIDTH - COLUMN_WIDTH) / 2
        power_slot_x = mean_damage_x + OPTIMIZATION_MEAN_DAMAGE_WIDTH + OPTIMIZATION_COL_GAP
        power_x = power_slot_x + (OPTIMIZATION_POWER_CAP_WIDTH - COLUMN_WIDTH) / 2
        mean_damage = _power_mean(resolved.tuning.target_sizes.damage, _displayed_mean_damage_power(context))
        power = _format_power(_displayed_optimization_power(context))
        cells.append(Cell("optimization:title", ox, title_top, panel_width, OPTIMIZATION_TITLE_HEIGHT, "panel_title",
                             text="optimization"))
        cells.append(Cell("optimization:mean_damage", mean_damage_val_x, content_top, COLUMN_WIDTH, ROW_HEIGHT, "control_value",
                             text=service.cents(mean_damage, resolved.flags.decimals)))
        mean_damage_symbol = (f"⟪𝒓{resolved.labels.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                      if resolved.scalars.all_interval else "⟪𝐝⟫ₚ")
        if context.tuning_optimized:
            mean_damage_symbol = f"min({mean_damage_symbol})"
        if resolved.flags.symbols:
            cells.append(Cell("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPTIMIZATION_MEAN_DAMAGE_WIDTH, SYMBOL_HEIGHT,
                                 "symbol", text=mean_damage_symbol))
        cells.append(Cell("optimization:mean_damage:label", mean_damage_x, text_top, OPTIMIZATION_MEAN_DAMAGE_WIDTH, text_band,
                             "label", text=geometry.mean_damage_label))
        power_locked = resolved.scalars.all_interval or not resolved.flags.alt_complexity
        cells.append(Cell("optimization:power", power_x, content_top, COLUMN_WIDTH, ROW_HEIGHT,
                             "power_display" if power_locked else "power_input", text=power))
        if resolved.flags.symbols:
            cells.append(Cell("optimization:power:symbol", power_x, sym_top, COLUMN_WIDTH, SYMBOL_HEIGHT,
                                 "symbol", text="𝑝"))
        cells.append(Cell("optimization:power:label", power_x + (COLUMN_WIDTH - OPTIMIZATION_POWER_CAP_WIDTH) / 2, text_top,
                             OPTIMIZATION_POWER_CAP_WIDTH, TEXT_LINE, "label", text="optimization power"))
        if geometry.show_approach:
            radio_x = ox + OPTIMIZATION_PADDING_L
            radio_width = panel_width - OPTIMIZATION_PADDING_L - OPTIMIZATION_PADDING_R
            approach_panel = (radio_x, approach_top, radio_width, RADIO_HEIGHT)
        optimization_panel = (ox, panel_top, panel_width, OPTIMIZATION_PADDING_T + OPTIMIZATION_TITLE_HEIGHT + OPTIMIZATION_TITLE_GAP + body_height)
    return optimization_panel, approach_panel


def _emit_approach_panel(region_panels, geometry):
    if not (geometry.show_approach and not geometry.optimization_control):
        return None
    panel_top = (geometry.rows["damage"].tile_top + geometry.rows["damage"].tile_height
               - geometry.approach_extra + RANGE_GAP)
    bx, by = control_region(region_panels, geometry, "block:approach", "targets", panel_top, RADIO_HEIGHT)
    return (bx, by, geometry.column_width["targets"] - 2 * PANEL_INNER, RADIO_HEIGHT)


def control_region(region_panels, geometry, panel_id, column_key, top, content_height):
    panel_y = top + PANEL_OUTER
    region_panels.append(Block(panel_id, geometry.column_x[column_key], panel_y, geometry.column_width[column_key],
                              2 * PANEL_INNER + content_height, paneled=True))
    return geometry.column_x[column_key] + PANEL_INNER, panel_y + PANEL_INNER


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

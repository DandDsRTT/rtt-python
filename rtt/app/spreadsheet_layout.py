from __future__ import annotations

from dataclasses import replace

from rtt.app import service, terminology
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    BANDS,
)
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BOX_INNER,
    BOX_TITLE_GAP,
    BOX_TITLE_HEIGHT,
    BRACE_HEIGHT,
    BRACKET_WIDTH,
    CAPTION_LINE,
    CHART_GAP,
    CHART_HEIGHT,
    COLUMN_WIDTH,
    COMMAPICK_GAP,
    ETPICK_GAP,
    ETPICK_WIDTH,
    FRAME_GAP,
    FRAME_HEIGHT,
    FRAME_OVERHANG,
    GAP,
    GRIP_BAND,
    HEADER_HEIGHT,
    LABEL_WIDTH,
    MATRIX_LABEL_HEIGHT,
    MATRIX_LABEL_PADDING,
    MATRIX_LABEL_SUPERSPACE_PRIMES_WIDTH,
    MATRIX_LABEL_SUPERSPACE_WIDTH,
    MATRIX_LABEL_WIDTH,
    OPTIMIZATION_MEAN_DAMAGE_WIDTH,
    OPTIMIZATION_PADDING_B,
    OPTIMIZATION_PADDING_T,
    OPTIMIZATION_TITLE_GAP,
    OPTIMIZATION_TITLE_HEIGHT,
    PAD,
    PRESET_HEIGHT,
    RADIO_BOX_GAP,
    RADIO_BOX_HEIGHT,
    RANGE_CHART_HEIGHT,
    RANGE_GAP,
    RANGE_MODE_HEIGHT,
    ROW_HANDLE_GAP,
    ROW_HANDLE_WIDTH,
    ROW_HEIGHT,
    STRIP,
    TITLE_MARGIN,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_geometry import (
    caption_band,
    caption_floor,
    commas_band_width,
    control_floor,
    control_region_band_height,
    count_floor,
    declare_interval_column_tiles,
    declare_tiles,
    init_superspace_tuning,
    plain_text_band,
    preset_band_height,
    symbol_floor,
)
from rtt.app.spreadsheet_geometry_model import Geometry
from rtt.app.spreadsheet_models import RowBand
from rtt.app.spreadsheet_text import _title_w, _wrap_lines


def compute_geometry(resolved, context):
    interest_tiles, held_tiles, detempering_tiles = declare_interval_column_tiles(resolved)
    tiles, declared_tiles = declare_tiles(resolved, context, interest_tiles, held_tiles, detempering_tiles)
    geometry = Geometry(superspace_tuning_map=init_superspace_tuning(resolved, context),
                        tiles=tiles, declared_tiles=declared_tiles)
    geometry, column_bands, content_x0 = _define_col_bands(geometry, resolved, context)
    geometry, row_bands = _define_row_bands(geometry, resolved)
    geometry = _layout_columns(geometry, resolved, context, column_bands, content_x0)
    geometry, tile_extra = _resolve_tile_extras(geometry, resolved, context)
    geometry, rows_top_y = _init_row_geometry(geometry)
    geometry = _resolve_plain_text_strings(geometry, resolved, context)
    geometry = _layout_rows(geometry, resolved, context, row_bands, tile_extra, rows_top_y)
    return _init_group_geometry(geometry, resolved, context)


def _resolve_col_headers(resolved):
    domain_title = ("domain basis\nelements"
                    if service.domain_has_nonprimes(resolved.dimensions.elements)
                    else "domain\nprimes")
    column_header = {"quantities": "interval ratios", "units": "units",
                  "canonical_generators": "canonical\ngenerators", "generators": "generators",
                  "superspace_generators": "superspace\ngenerators", "superspace_primes": "superspace\nprimes",
                  "primes": domain_title, "detempering": "generator\ndetempering",
                  "commas": "commas",
                  "held": "held\nintervals", "targets": "target\nintervals",
                  "interest": "other intervals\nof interest"}
    if resolved.unchanged.shown:
        column_header["commas"] = "unrotated\nvector list"
    return column_header


def _matrix_label_other_w(geometry, resolved):
    _label_row_present = {"mapping": resolved.flags.temperament_tiles, "vectors": resolved.flags.interval_vectors,
                          "canonical": resolved.flags.canonical, "projection": resolved.flags.projection,
                          "prescaling": resolved.flags.prescaling_shown, "superspace_mapping": resolved.flags.superspace,
                          "superspace_vectors": resolved.flags.superspace, "superspace_projection": resolved.flags.superspace_projection}
    other = {}
    if resolved.flags.header_symbols:
        for (rk, ck) in resolved.labels.row_labels:
            if ck not in ("primes", "superspace_primes") and _label_row_present.get(rk) and (rk, ck) in geometry.declared_tiles:
                other[ck] = MATRIX_LABEL_WIDTH
    return other


def _define_col_bands(geometry, resolved, context):
    size_factor = service.complexity_size_factor(context.tuning_scheme)
    geometry = replace(
        geometry,
        column_header=_resolve_col_headers(resolved),
        matrix_label_primes_width=((MATRIX_LABEL_SUPERSPACE_WIDTH if resolved.flags.superspace else MATRIX_LABEL_WIDTH)
                           if (resolved.flags.header_symbols and resolved.flags.temperament_tiles) else 0),
        matrix_label_superspace_primes_width=MATRIX_LABEL_SUPERSPACE_PRIMES_WIDTH if (resolved.flags.header_symbols and resolved.flags.superspace) else 0,
        matrix_label_other_width=_matrix_label_other_w(geometry, resolved),
        row_handle_width=(ROW_HANDLE_WIDTH + ROW_HANDLE_GAP) if (
            context.settings.get("drag_to_combine") and resolved.flags.temperament_tiles and resolved.dimensions.rank > 1) else 0,
        etpick_width=(ETPICK_WIDTH + ETPICK_GAP) if (resolved.flags.presets and resolved.flags.temperament_tiles) else 0,
        size_factor=size_factor,
        size_rows=1 if size_factor else 0,
        prescale_rows=resolved.dimensions.superspace_dimensionality if resolved.flags.superspace else resolved.dimensions.dimensionality,
        all_interval_simplicity_weight=resolved.scalars.all_interval and (
            bool(size_factor) or resolved.scalars.prescaler_is_matrix),
        node_x=LABEL_WIDTH + GAP,
        node_edge=LABEL_WIDTH + GAP + TOGGLE,
    )
    return geometry, _col_bands(geometry, resolved, context), LABEL_WIDTH + GAP + TOGGLE + GAP


def _col_bands(geometry, resolved, context):
    return (
        ("quantities", COLUMN_WIDTH, resolved.flags.interval_ratios),
        ("units", COLUMN_WIDTH, resolved.flags.app_units),
        ("canonical_generators", 2 * BRACKET_WIDTH + resolved.dimensions.canonical_rank * COLUMN_WIDTH + 2 * query.matrix_label_gutter_width(geometry, "canonical_generators"), resolved.flags.canonical),
        ("generators", 2 * BRACKET_WIDTH + resolved.dimensions.rank * COLUMN_WIDTH + 2 * query.matrix_label_gutter_width(geometry, "generators"), resolved.flags.temperament_tiles),
        ("superspace_generators", 2 * BRACKET_WIDTH + resolved.dimensions.superspace_rank * COLUMN_WIDTH, resolved.flags.superspace),
        ("superspace_primes", 2 * BRACKET_WIDTH + resolved.dimensions.superspace_dimensionality * COLUMN_WIDTH + 2 * geometry.matrix_label_superspace_primes_width, resolved.flags.superspace),
        ("primes", 2 * BRACKET_WIDTH + resolved.dimensions.dimensionality_shown * COLUMN_WIDTH + 2 * query.outer_gutter_width(geometry, "primes"), resolved.flags.temperament_tiles),
        ("detempering", 2 * BRACKET_WIDTH + resolved.dimensions.rank * COLUMN_WIDTH, resolved.flags.generator_detempering),
        ("commas", commas_band_width(resolved, resolved.dimensions.comma_count_shown), resolved.flags.temperament_tiles),
        ("held", query.interval_list_width(resolved.dimensions.held_count_shown, "held"), resolved.flags.optimization),
        ("targets", query.interval_list_width(resolved.dimensions.target_count_shown, "targets"), resolved.flags.tuning_tiles and context.targets_in_use),
        ("interest", query.interval_list_width(resolved.dimensions.interest_count_shown, "interest"), resolved.flags.interest),
    )


def _define_row_bands(geometry, resolved):
    row_bands = (
        ("counts", ROW_HEIGHT, resolved.flags.counts, "counts"),
        ("quantities", ROW_HEIGHT, resolved.flags.interval_ratios, "interval ratios"),
        ("units", ROW_HEIGHT, resolved.flags.app_units, "units"),
        ("scaling_factors", ROW_HEIGHT, resolved.unchanged.shown, "scaling factors"),
        ("vectors", resolved.dimensions.dimensionality * ROW_HEIGHT, resolved.flags.interval_vectors, "interval vectors"),
        ("canonical", resolved.dimensions.canonical_rank * ROW_HEIGHT, resolved.flags.canonical, "canonical mapping"),
        ("mapping", resolved.dimensions.rank_shown * ROW_HEIGHT, resolved.flags.temperament_tiles, "mapping"),
        ("superspace_vectors", resolved.dimensions.superspace_dimensionality * ROW_HEIGHT, resolved.flags.superspace, "superspace interval vectors"),
        ("superspace_mapping", resolved.dimensions.superspace_rank * ROW_HEIGHT, resolved.flags.superspace, "superspace mapping"),
        ("superspace_projection", resolved.dimensions.superspace_dimensionality * ROW_HEIGHT, resolved.flags.superspace_projection, "superspace projection"),
        ("projection", resolved.dimensions.dimensionality * ROW_HEIGHT, resolved.flags.projection, "projection"),
        ("tuning", ROW_HEIGHT, resolved.flags.tuning_tiles, "tuning"),
        ("just", ROW_HEIGHT, resolved.flags.tuning_tiles, "just tuning"),
        ("retune", ROW_HEIGHT, resolved.flags.tuning_tiles, "retuning"),
        ("prescaling", (geometry.prescale_rows + geometry.size_rows) * ROW_HEIGHT + query.prescale_size_gap(geometry), resolved.flags.prescaling_shown, "complexity prescaling"),
        ("complexity", ROW_HEIGHT, resolved.flags.complexity_shown, "complexity"),
        ("weight", ROW_HEIGHT, resolved.flags.weighting, "weight"),
        ("damage", ROW_HEIGHT, resolved.flags.tuning_tiles, "damage"),
    )
    row_bands = tuple(
        (key, height, present, terminology.substitute(label, resolved.flags.terminology_mode))
        for key, height, present, label in row_bands
    )
    present_caption_rows = frozenset(
        key for key, _h, present, _l in row_bands if present and key in BANDS["caption"].rows)
    return replace(geometry, present_caption_rows=present_caption_rows), row_bands


def _layout_columns(geometry, resolved, context, column_bands, content_x0) -> Geometry:
    column_x, column_width, content_width, open_column_width = {}, {}, {}, {}
    x = content_x0
    first_present = True
    previous_title_oh = None
    for key, natural, present in column_bands:
        if not present:
            continue
        collapsed_col = f"column:{key}" in context.collapsed
        hug_width = max(natural, caption_floor(geometry, resolved, key), control_floor(resolved, context, key), symbol_floor(geometry, resolved, key), count_floor(resolved, key))
        if first_present:
            hug_width = max(hug_width, _title_w(geometry.column_header[key]) - 2 * PAD)
            first_present = False
        open_column_width[key] = hug_width
        if collapsed_col:
            column_width[key] = content_width[key] = min(hug_width, _title_w(geometry.column_header[key]))
        else:
            content_width[key] = natural
            column_width[key] = hug_width
        half_oh = _title_w(geometry.column_header[key]) / 2 - column_width[key] / 2
        if previous_title_oh is not None:
            x += max(GAP, TITLE_MARGIN + previous_title_oh + half_oh)
        column_x[key] = x
        x += column_width[key]
        previous_title_oh = half_oh
    content_x = {key: column_x[key] + (column_width[key] - content_width[key]) / 2 for key in column_x}
    return replace(
        geometry, column_x=column_x, column_width=column_width, content_width=content_width,
        open_column_width=open_column_width, total_width=x + GAP, content_x=content_x,
        primes_x=content_x.get("primes"), commas_x=content_x.get("commas"),
        targets_x=content_x.get("targets"), interest_x=content_x.get("interest"),
        held_x=content_x.get("held"), detempering_x=content_x.get("detempering"),
        canonical_generators_x=content_x.get("canonical_generators"), superspace_generators_x=content_x.get("superspace_generators"),
        superspace_primes_x=content_x.get("superspace_primes"))


def _init_row_geometry(geometry):
    branch_top_y = HEADER_HEIGHT + (GAP - TOGGLE) / 2 + TOGGLE
    geometry = replace(geometry, header_y=0, column_node_y=HEADER_HEIGHT + (GAP - TOGGLE) / 2,
                       branch_top_y=branch_top_y, FAN=(GAP - PAD) / 2)
    return geometry, branch_top_y + GAP + GRIP_BAND


def _layout_rows(geometry, resolved, context, row_bands, tile_extra, rows_top_y) -> Geometry:
    show_charts = resolved.flags.charts
    rows: dict[str, RowBand] = {}
    y = rows_top_y
    for key, natural, present, label in row_bands:
        if not present:
            continue
        band = _compute_row_band(geometry, resolved, context, key, natural, label, tile_extra, show_charts, y)
        rows[key] = band
        y += band.tile_height + GAP
    return replace(geometry, rows=rows, total_height=y,
                   fanout_y=geometry.branch_top_y + geometry.FAN)


def _row_interval_handle(geometry, resolved, context, key, folded):
    return (key == "vectors" and not folded and context.settings.get("drag_to_combine")
            and ((resolved.dimensions.comma_count >= 2 and query.column_open(geometry, context.collapsed, "commas"))
                 or (resolved.dimensions.target_count >= 2 and not resolved.scalars.all_interval and query.column_open(geometry, context.collapsed, "targets"))
                 or (resolved.dimensions.held_count >= 2 and query.column_open(geometry, context.collapsed, "held"))
                 or (resolved.dimensions.interest_count >= 2 and query.column_open(geometry, context.collapsed, "interest"))))


def _compute_row_band(geometry, resolved, context, key, natural, label, tile_extra, show_charts, y):
    folded = f"row:{key}" in context.collapsed
    framed = key in BANDS["frame"].rows and not folded
    has_matrix_label = (resolved.flags.header_symbols and key in BANDS["col_label"].rows and not folded)
    toggle_band = TOGGLE + 2 * TOGGLE_INSET - PAD
    interval_handle = _row_interval_handle(geometry, resolved, context, key, folded)
    handle_band = (ROW_HANDLE_WIDTH + ROW_HANDLE_GAP) if interval_handle else 0
    base_head = 0 if folded else max(toggle_band, MATRIX_LABEL_HEIGHT + 2 * MATRIX_LABEL_PADDING if has_matrix_label else toggle_band)
    head = base_head + handle_band
    top_frame = (FRAME_HEIGHT + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    bot_frame = (BRACE_HEIGHT + FRAME_GAP + FRAME_OVERHANG) if framed else 0
    charted = show_charts and key in BANDS["chart"].rows and not folded and natural == ROW_HEIGHT
    chart_band = (CHART_HEIGHT + CHART_GAP) if charted else 0
    caption = caption_band(geometry, resolved, context, key, folded)
    symbol = BANDS["symbol"].height if ((resolved.flags.symbols or resolved.flags.equivalences)
                                     and key in BANDS["symbol"].rows and not folded) else 0
    units = BANDS["units"].height if (resolved.flags.tile_units and key in BANDS["units"].rows and not folded) else 0
    preset = preset_band_height(geometry, resolved, key) if (((resolved.flags.presets and key in BANDS["preset"].rows)
                                     or (context.settings["all_interval"] and key == "vectors"))
                                    and not folded) else 0
    comma_picker = (COMMAPICK_GAP + ROW_HEIGHT) if (key == "vectors" and resolved.flags.presets
                                       and query.column_open(geometry, context.collapsed, "commas")
                                       and (resolved.dimensions.comma_count > 0 or resolved.commas.pending is not None) and not folded) else 0
    plain_text = plain_text_band(geometry, key, folded)
    symbol += BAND_GAP if symbol else 0
    caption += BAND_GAP if caption else 0
    units += BAND_GAP if units else 0
    plain_text += BAND_GAP if plain_text else 0
    row_height = STRIP if folded else natural
    chart_top = (y + head + top_frame) if charted else None
    interval_handle_top = (y + (handle_band - ROW_HANDLE_WIDTH) // 2) if interval_handle else None
    matrix_label_top = (y + handle_band + (base_head - MATRIX_LABEL_HEIGHT) // 2) if has_matrix_label else None
    trailing_band = symbol + caption + units + preset + plain_text + comma_picker + tile_extra.get(key, 0)
    foot = 0 if (folded or trailing_band) else toggle_band
    tile_height = (head + top_frame + chart_band + row_height + bot_frame + comma_picker + symbol + caption + units
              + preset + plain_text + tile_extra.get(key, 0) + foot)
    return RowBand(
        y=y + head + top_frame + chart_band, height=row_height, label=label,
        tile_height=tile_height, tile_top=y, frame=bot_frame, symbol=symbol, caption=caption, units=units, plain_text=plain_text,
        preset=preset, scheme_button=0, num_subrows=round(natural / ROW_HEIGHT), comma_picker=comma_picker,
        chart_top=chart_top, interval_handle_top=interval_handle_top, matrix_label_top=matrix_label_top)


def _group_geometry_fields(geometry, resolved):
    group_n = {"generators": resolved.dimensions.rank, "primes": resolved.dimensions.dimensionality_shown, "commas": resolved.dimensions.vector_count_shown,
               "targets": resolved.dimensions.target_count_shown,
               "interest": resolved.dimensions.interest_count_shown, "held": resolved.dimensions.held_count_shown, "detempering": resolved.dimensions.rank,
               "canonical_generators": resolved.dimensions.canonical_rank, "superspace_generators": resolved.dimensions.superspace_rank, "superspace_primes": resolved.dimensions.superspace_dimensionality}
    content_x = geometry.content_x
    left_fn = {"generators": lambda i: query.generator_left(geometry, i),
               "primes": lambda i: query.prime_left(geometry, i),
               "commas": lambda i: query.comma_left(geometry, resolved, i),
               "targets": lambda i: query.interval_left(geometry, "targets", i),
               "interest": lambda i: query.interval_left(geometry, "interest", i),
               "held": lambda i: query.interval_left(geometry, "held", i),
               "detempering": lambda i: query.detempering_left(geometry, i),
               "canonical_generators": lambda i: query.canonical_generator_left(geometry, i),
               "superspace_generators": lambda i: query.superspace_generator_left(geometry, i),
               "superspace_primes": lambda i: query.superspace_prime_left(geometry, i)}
    return {
        "group_elem": {"generators": "generator", "primes": "prime", "commas": "comma", "targets": "target",
                       "interest": "interest", "held": "held", "detempering": "detempering",
                       "canonical_generators": "canonical_generator", "superspace_generators": "superspace_generator", "superspace_primes": "superspace_prime"},
        "group_n": group_n,
        "group_left": {g: tuple(function(i) for i in range(group_n[g])) if g in content_x else ()
                       for g, function in left_fn.items()},
        "group_ratio": {
            "primes": tuple(service.element_ratio(e) for e in resolved.dimensions.elements),
            "commas": tuple(resolved.commas.ratios[:resolved.dimensions.comma_count]) + tuple(resolved.unchanged.ratios),
            "targets": tuple(resolved.targets.ratios),
            "interest": tuple(resolved.interest.ratios),
            "held": tuple(resolved.held.ratios),
            "detempering": tuple(resolved.scalars.generators),
            "superspace_primes": tuple(service.element_ratio(e) for e in resolved.dimensions.superspace_primes),
        }}


def _init_group_geometry(geometry, resolved, context) -> Geometry:
    geometry = replace(geometry, **_group_geometry_fields(geometry, resolved))
    plus_stub_x = {column_key: query.column_plus_x(geometry, resolved, column_key)
                   for column_key in ("generators", "primes", "commas", "targets", "interest", "held")
                   if query.plus_shows(geometry, resolved, context.collapsed, context.state, column_key)}
    row_plus_y = {}
    if query.tile_open(geometry, context.collapsed, "vectors", "quantities") and (resolved.flags.nonstandard_domain or resolved.scalars.standard_domain):
        row_plus_y["vectors"] = query.vector_top(geometry, resolved.dimensions.dimensionality_shown) + ROW_HEIGHT / 2
    if query.tile_open(geometry, context.collapsed, "mapping", "quantities") and context.state.nullity > 0:
        row_plus_y["mapping"] = query.map_top(geometry, resolved.dimensions.rank_shown) + ROW_HEIGHT / 2
    return replace(geometry, plus_stub_x=plus_stub_x, row_plus_y=row_plus_y)


def _resolve_tile_extras(geometry, resolved, context):
    tile_controls = context.settings["tile_controls"]
    ranges_on = (resolved.flags.tuning_ranges and resolved.flags.tuning_tiles and "row:tuning" not in context.collapsed
                 and query.column_open(geometry, context.collapsed, "generators") and "tile:tuning:generators" not in context.collapsed)
    tuning_range_chart = ranges_on and resolved.flags.charts
    tuning_range_mode = ranges_on and tile_controls
    tuning_ranges_chart = tuning_range_chart or tuning_range_mode
    range_parts = ([RANGE_CHART_HEIGHT] if tuning_range_chart else []) + ([RANGE_MODE_HEIGHT] if tuning_range_mode else [])
    tuning_ranges_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_HEIGHT + BOX_TITLE_GAP
                           + sum(range_parts) + max(0, len(range_parts) - 1) * RANGE_GAP) if tuning_ranges_chart else 0
    prescaling_box_control = resolved.flags.prescaling_box_show and query.column_open(geometry, context.collapsed, "superspace_primes" if resolved.flags.superspace else "primes") and not resolved.flags.presets and tile_controls
    prescaling_box_extra = (RANGE_GAP + control_region_band_height(PRESET_HEIGHT + CAPTION_LINE)) if prescaling_box_control else 0
    complexity_box_control = resolved.flags.complexity_box_show and query.column_open(geometry, context.collapsed, "targets") and tile_controls
    complexity_box_extra = (RANGE_GAP + control_region_band_height(ROW_HEIGHT + resolved.scalars.control_symbol_height + 3 * CAPTION_LINE)) if complexity_box_control else 0
    optimization_control = (resolved.flags.optimization and "row:damage" not in context.collapsed
                and query.column_open(geometry, context.collapsed, "targets") and "tile:damage:targets" not in context.collapsed and tile_controls)
    mean_damage_caption = "retuning magnitude" if resolved.scalars.all_interval else "power mean"
    if context.tuning_optimized:
        mean_damage_caption = f"minimized {mean_damage_caption}"
    optimization_cap_lines = _wrap_lines(mean_damage_caption, OPTIMIZATION_MEAN_DAMAGE_WIDTH) if optimization_control else 1
    show_approach = (service.domain_has_nonprimes(resolved.dimensions.elements)
                     and "row:damage" not in context.collapsed and query.column_open(geometry, context.collapsed, "targets")
                     and "tile:damage:targets" not in context.collapsed and tile_controls)
    approach_section = (RADIO_BOX_HEIGHT + RADIO_BOX_GAP) if (optimization_control and show_approach) else 0
    optimization_extra = ((RANGE_GAP + OPTIMIZATION_PADDING_T + OPTIMIZATION_TITLE_HEIGHT + OPTIMIZATION_TITLE_GAP + ROW_HEIGHT + resolved.scalars.control_symbol_height
                  + optimization_cap_lines * CAPTION_LINE + approach_section + OPTIMIZATION_PADDING_B) if optimization_control else 0)
    approach_extra = (RANGE_GAP + control_region_band_height(RADIO_BOX_HEIGHT)) if (show_approach and not optimization_control) else 0
    slope_control = (resolved.flags.weighting and tile_controls
                  and "row:weight" not in context.collapsed
                  and query.column_open(geometry, context.collapsed, "targets") and "tile:weight:targets" not in context.collapsed)
    slope_locked = slope_control and (service.is_all_interval(context.tuning_scheme)
                                   or resolved.scalars.custom_weights_deviate)
    slope_extra = (RANGE_GAP + control_region_band_height(RADIO_BOX_HEIGHT)) if slope_control else 0
    geometry = replace(
        geometry, tuning_ranges_chart=tuning_ranges_chart, tuning_range_chart=tuning_range_chart, tuning_range_mode=tuning_range_mode,
        tuning_ranges_extra=tuning_ranges_extra, prescaling_box_control=prescaling_box_control, prescaling_box_extra=prescaling_box_extra,
        complexity_box_control=complexity_box_control, complexity_box_extra=complexity_box_extra, optimization_control=optimization_control, optimization_extra=optimization_extra,
        optimization_cap_lines=optimization_cap_lines, show_approach=show_approach, approach_extra=approach_extra,
        slope_control=slope_control, slope_extra=slope_extra, slope_locked=slope_locked,
        mean_damage_caption=mean_damage_caption)
    return geometry, {
        "tuning": tuning_ranges_extra,
        "prescaling": prescaling_box_extra,
        "complexity": complexity_box_extra,
        "weight": slope_extra,
        "damage": optimization_extra + approach_extra,
    }


def _resolve_plain_text_strings(geometry, resolved, context) -> Geometry:
    plain_text_strings = (service.plain_text_values(context.state, context.tuning_scheme, context.target_spec,
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
                                                   targets=resolved.targets.ratios, tuning_map=resolved.tuning.tuning_map,
                                                   target_weights=resolved.tuning.target_weights,
                                                   target_sizes=resolved.targets.sizes,
                                                   comma_sizes=resolved.commas.sizes,
                                                   superspace_tuning_map=(geometry.superspace_tuning_map
                                                                   if resolved.flags.superspace else None)))
                     if resolved.flags.plain_text_values else {})
    if not resolved.flags.ebk:
        plain_text_strings = {k: service.ebk_to_simple_matrix(v) for k, v in plain_text_strings.items()}
    return replace(geometry, plain_text_strings=plain_text_strings)

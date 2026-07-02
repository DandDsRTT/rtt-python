from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    COUNTS,
    DETEMPERING_COUNTS,
    OPTIMIZATION_COUNTS,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    SUPERSPACE_COUNTS,
)
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BUTTON,
    COLUMN_WIDTH,
    DASH,
    GAP,
    GRIP_BAND,
    HEADER_HEIGHT,
    LABEL_WIDTH,
    PAD,
    ROW_HEIGHT,
    TOGGLE,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_emit_model import EmitResult, element_cell_kind, voice
from rtt.app.spreadsheet_models import _QtyList
from rtt.app.spreadsheet_text import (
    _count_sym,
    _fold_glyph,
    _foldable_ids,
    _pretransform_label,
    _sub,
)


def emit_headers(resolved, geometry, context) -> EmitResult:
    cells: list = []
    for key in geometry.column_x:
        hx = geometry.column_x[key] + query.outer_gutter_width(geometry, key)
        hw = geometry.column_width[key] - 2 * query.outer_gutter_width(geometry, key)
        cells.append(CellBox(f"header:{key}", hx, geometry.header_y, hw, HEADER_HEIGHT, "column_header", text=geometry.column_header[key]))
        glyph = _fold_glyph(f"column:{key}" in context.collapsed)
        tx = hx + (hw - TOGGLE) / 2
        cells.append(CellBox(f"toggle:column:{key}", tx, geometry.column_node_y, TOGGLE, TOGGLE, "columntoggle", text=glyph))
    for key in geometry.rows:
        label = geometry.rows[key].label
        if geometry.size_factor or resolved.scalars.prescaler_is_matrix:
            label = _pretransform_label(label)
            label = label.replace(" pretransforming", " pre-transforming")
        cells.append(CellBox(f"label:{key}", 0, geometry.rows[key].y, LABEL_WIDTH, geometry.rows[key].height, "row_label", text=label))
        glyph = _fold_glyph(f"row:{key}" in context.collapsed)
        ty = geometry.rows[key].y + (geometry.rows[key].height - TOGGLE) / 2
        cells.append(CellBox(f"toggle:row:{key}", geometry.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))
    foldable = _foldable_ids(cells)
    if foldable:
        all_collapsed = foldable <= context.collapsed
        cells.append(CellBox("toggle:all", geometry.node_x, geometry.column_node_y, TOGGLE, TOGGLE, "alltoggle",
                             text=_fold_glyph(all_collapsed)))
    return EmitResult(cells=tuple(cells))


def emit_counts_row(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, context.collapsed, "counts"):
        return EmitResult()
    cardinality = {"generators": resolved.dimensions.rank, "primes": resolved.dimensions.dimensionality, "commas": context.state.nullity, "targets": resolved.dimensions.target_count, "held": resolved.dimensions.held_count,
                   "detempering": resolved.dimensions.rank,
                   "superspace_generators": resolved.dimensions.superspace_rank, "superspace_primes": resolved.dimensions.superspace_dimensionality}
    def count_face(sym, value):
        glyph = _count_sym(sym) if resolved.flags.symbols else ""
        equiv = f" = {value}" if resolved.flags.equivalences else ""
        return glyph + equiv

    for column_key, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
        if not query.tile_open(geometry, context.collapsed, "counts", column_key):
            continue
        if column_key == "commas" and resolved.unchanged.shown:
            comma_half_width = resolved.dimensions.comma_count * COLUMN_WIDTH + resolved.unchanged.empty_comma_width
            nullity_face = count_face("n", context.state.nullity)
            if comma_half_width and nullity_face:
                comma_half_x = geometry.commas_x if resolved.unchanged.empty_comma_width else query.comma_left(geometry, resolved, 0)
                cells.append(CellBox("count:commas", comma_half_x, geometry.rows["counts"].y, comma_half_width, ROW_HEIGHT,
                                     "count", text=nullity_face))
            unchanged_face = count_face("u", resolved.dimensions.unchanged_count)
            if unchanged_face:
                cells.append(CellBox("count:commas:u", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown), geometry.rows["counts"].y, resolved.dimensions.unchanged_count * COLUMN_WIDTH, ROW_HEIGHT,
                                     "count", text=unchanged_face))
            continue
        face = count_face(sym, cardinality[column_key])
        if not face:
            continue
        cnt_x, cnt_width = query.tile_span_box(geometry, "counts", column_key)
        cells.append(CellBox(f"count:{column_key}", cnt_x, geometry.rows["counts"].y, cnt_width, ROW_HEIGHT,
                             "count", text=face))
    return EmitResult(cells=tuple(cells))


def emit_units(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not resolved.flags.tile_units:
        return EmitResult()
    _emit_units_matrix(cells, resolved, geometry, context)
    _emit_units_const(cells, resolved, geometry, context)
    _emit_units_columns(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_units_matrix(cells, resolved, geometry, context) -> None:
    matrix_units = {
        "vectors": (resolved.dimensions.dimensionality, lambda i: query.vector_top(geometry, i), lambda i: f"{resolved.labels.domain_label}{_sub(i + 1)}/"),
        "canonical": (resolved.dimensions.canonical_rank, lambda i: query.canonical_top(geometry, i), lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
        "projection": (resolved.dimensions.dimensionality, lambda i: query.projection_top(geometry, i), lambda i: f"{resolved.labels.domain_label}{_sub(i + 1)}/"),
        "mapping": (resolved.dimensions.rank_shown, lambda i: query.map_top(geometry, i), lambda i: f"g{_sub(i + 1)}/"),
        "superspace_vectors": (resolved.dimensions.superspace_dimensionality, lambda i: query.superspace_vector_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
        "superspace_mapping": (resolved.dimensions.superspace_rank, lambda i: query.superspace_map_top(geometry, i), lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
        "superspace_projection": (resolved.dimensions.superspace_dimensionality, lambda i: query.superspace_projection_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
    }
    for key, (n, top, label) in matrix_units.items():
        if not query.tile_open(geometry, context.collapsed, key, "units"):
            continue
        for i in range(n):
            cells.append(CellBox(f"units_column:{key}:{i}", geometry.column_x["units"], top(i),
                                 geometry.column_width["units"], ROW_HEIGHT, "units", text=label(i)))


def _emit_units_const(cells, resolved, geometry, context) -> None:
    const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                   "complexity": f"{resolved.scalars.complexity_unit}/", "weight": f"{resolved.scalars.weight_unit}/",
                   "damage": f"{resolved.scalars.damage_unit}/"}
    for key, text in const_units.items():
        if not query.tile_open(geometry, context.collapsed, key, "units"):
            continue
        n = geometry.rows[key].num_subrows
        for i in range(n):
            cell_id = f"units_column:{key}:{i}" if n > 1 else f"units_column:{key}"
            cells.append(CellBox(cell_id, geometry.column_x["units"], geometry.rows[key].y + i * ROW_HEIGHT,
                                 geometry.column_width["units"], ROW_HEIGHT, "units", text=text))


def _emit_units_columns(cells, resolved, geometry, context) -> None:
    if "units" not in geometry.rows:
        return
    uy = geometry.rows["units"].y
    column_units = {
        "canonical_generators": (resolved.dimensions.canonical_rank, lambda i: query.canonical_generator_left(geometry, i), lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
        "generators": (resolved.dimensions.rank, lambda i: query.generator_left(geometry, i), lambda i: f"/g{_sub(i + 1)}"),
        "primes": (resolved.dimensions.dimensionality, lambda i: query.prime_left(geometry, i), lambda i: f"/{resolved.labels.domain_label}{_sub(i + 1)}"),
        "superspace_generators": (resolved.dimensions.superspace_rank, lambda i: query.superspace_generator_left(geometry, i), lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
        "superspace_primes": (resolved.dimensions.superspace_dimensionality, lambda i: query.superspace_prime_left(geometry, i), lambda i: f"/p{_sub(i + 1)}"),
        "commas": (resolved.dimensions.vector_count_shown, lambda i: query.comma_left(geometry, resolved, i), lambda _i: "/1"),
        "detempering": (resolved.dimensions.rank, lambda i: query.detempering_left(geometry, i), lambda _i: "/1"),
        "targets": (resolved.dimensions.target_count_shown, lambda i: query.interval_left(geometry, "targets", i), lambda _i: "/1"),
        "interest": (resolved.dimensions.interest_count_shown, lambda i: query.interval_left(geometry, "interest", i), lambda _i: "/1"),
        "held": (resolved.dimensions.held_count_shown, lambda i: query.interval_left(geometry, "held", i), lambda _i: "/1"),
    }
    for key, (n, left, label) in column_units.items():
        if not query.tile_open(geometry, context.collapsed, "units", key):
            continue
        for i in range(n):
            cells.append(CellBox(f"units_row:{key}:{i}", left(i), uy, COLUMN_WIDTH, ROW_HEIGHT,
                                 "units", text=label(i)))


def emit_quantities_row(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if "quantities" not in geometry.rows:
        return EmitResult()
    quantity_y = geometry.rows["quantities"].y

    def branch_minus(cell_id, column_key, i, kind, **kw):
        cells.append(CellBox(cell_id, query.sub_axis_x(geometry, column_key, i) - COLUMN_WIDTH / 2, geometry.fanout_y, COLUMN_WIDTH,
                             quantity_y - geometry.fanout_y, kind, **kw))

    _emit_qty_generators(cells, resolved, geometry, context, quantity_y, branch_minus)
    _emit_qty_canonical_generators(cells, resolved, geometry, context, quantity_y)
    _emit_qty_primes(cells, resolved, geometry, context, quantity_y, branch_minus)
    _emit_qty_superspace_generators(cells, resolved, geometry, context, quantity_y)
    _emit_qty_superspace_primes(cells, resolved, geometry, context, quantity_y)
    _emit_qty_commas(cells, resolved, geometry, context, quantity_y, branch_minus)
    _emit_qty_detempering(cells, resolved, geometry, context, quantity_y)
    _emit_qty_interests(cells, resolved, geometry, context, quantity_y, branch_minus)
    _emit_qty_grips(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_qty_generators(cells, resolved, geometry, context, quantity_y, branch_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "generators"):
        for g in range(resolved.dimensions.rank):
            cells.append(CellBox(f"quantities_generator:{g}", query.generator_left(geometry, g), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "generator_ratio", text=resolved.scalars.generators[g], generator=g))
        if resolved.dimensions.rank > 1:
            branch_minus("generator_minus", "generators", resolved.dimensions.rank - 1, "generator_minus", generator=resolved.dimensions.rank - 1)


def _emit_qty_canonical_generators(cells, resolved, geometry, context, quantity_y) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "canonical_generators"):
        for g in range(resolved.dimensions.canonical_rank):
            cells.append(CellBox(f"canonical_generator:{g}", query.canonical_generator_left(geometry, g), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "generator_ratio", text=resolved.canonical.generators[g]))


def _emit_qty_primes(cells, resolved, geometry, context, quantity_y, branch_minus) -> None:
    if not query.tile_open(geometry, context.collapsed, "quantities", "primes"):
        return
    for p in range(resolved.dimensions.dimensionality):
        text = str(resolved.dimensions.elements[p])
        kind = element_cell_kind(text) if resolved.flags.nonstandard_domain else "prime"
        cells.append(CellBox(f"prime:{p}", query.prime_left(geometry, p), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, kind, text=text, prime=p))
        voice(cells, "quantities:primes", p, resolved.tuning.tuning_map.just_map[p])
    if resolved.scalars.element_draft:
        draft_text = context.pending_element or "?/?"
        cells.append(CellBox("prime:pending", query.prime_left(geometry, resolved.dimensions.dimensionality), quantity_y, COLUMN_WIDTH, ROW_HEIGHT,
                             element_cell_kind(draft_text), text=draft_text, prime=resolved.dimensions.dimensionality, pending=True))
        branch_minus("element_minus:pending", "primes", resolved.dimensions.dimensionality, "element_minus")
    if resolved.flags.nonstandard_domain:
        if resolved.dimensions.dimensionality > 1:
            for p in range(resolved.dimensions.dimensionality):
                branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
    elif resolved.scalars.domain_can_shrink:
        branch_minus("minus", "primes", resolved.dimensions.dimensionality - 1, "minus")


def _emit_qty_superspace_generators(cells, resolved, geometry, context, quantity_y) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "superspace_generators"):
        superspace_generators = service.superspace_generators(context.state)
        for g in range(resolved.dimensions.superspace_rank):
            cells.append(CellBox(f"superspace_quantity_generator:{g}", query.superspace_generator_left(geometry, g), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "generator_ratio", text=superspace_generators[g]))


def _emit_qty_superspace_primes(cells, resolved, geometry, context, quantity_y) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "superspace_primes"):
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(CellBox(f"superspace_quantity_prime:{p}", query.superspace_prime_left(geometry, p), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "comma_ratio", text=str(resolved.dimensions.superspace_primes[p]), prime=p))


def _emit_qty_commas(cells, resolved, geometry, context, quantity_y, branch_minus) -> None:
    if not query.tile_open(geometry, context.collapsed, "quantities", "commas"):
        return
    for c in range(resolved.dimensions.comma_count):
        cells.append(CellBox(f"comma:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "ratio_cell", text=resolved.commas.ratios[c], comma=c))
        voice(cells, "quantities:commas", c, resolved.tuning.comma_sizes.just[c])
    if resolved.scalars.comma_draft:
        cells.append(CellBox("comma:pending", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), quantity_y, COLUMN_WIDTH, ROW_HEIGHT,
                             "comma_ratio" if resolved.ghosts.comma else "ratio_cell",
                             text=(resolved.ghosts.comma_ratio or DASH) if resolved.ghosts.comma else "?/?",
                             comma=resolved.dimensions.comma_count, pending=True))
    if resolved.unchanged.shown:
        for j in range(resolved.dimensions.unchanged_count):
            doomed = resolved.commas.pending is not None and j == resolved.dimensions.unchanged_count - 1
            cells.append(CellBox(f"unchanged:{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), quantity_y, COLUMN_WIDTH, ROW_HEIGHT,
                                 "ratio_cell" if (resolved.unchanged.full and not doomed) else "comma_ratio",
                                 text=resolved.unchanged.ratios[j] or DASH, comma=resolved.dimensions.comma_count + j))
            voice(cells, "quantities:commas", resolved.dimensions.comma_count + j, resolved.unchanged.sizes.just[j])
    for c in range(resolved.dimensions.comma_count):
        branch_minus(f"comma_minus:{query.column_token(resolved, 'commas', c)}", "commas", c, "comma_minus", comma=c)
    if resolved.commas.pending is not None:
        branch_minus("comma_minus:pending", "commas", resolved.dimensions.comma_count, "comma_minus")


def _emit_qty_detempering(cells, resolved, geometry, context, quantity_y) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "detempering"):
        for i in range(resolved.dimensions.rank):
            cells.append(CellBox(f"detempering:{i}", query.detempering_left(geometry, i), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "comma_ratio", text=resolved.scalars.generators[i]))
            voice(cells, "quantities:detempering", i, resolved.detempering.sizes.just[i])


def _emit_qty_interests(cells, resolved, geometry, context, quantity_y, branch_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "targets"):
        _emit_qty_list(cells, resolved, _QtyList("targets", "target", resolved.dimensions.target_count, lambda i: query.interval_left(geometry, "targets", i), resolved.targets.ratios,
                                     resolved.tuning.target_sizes, resolved.targets.pending,
                                     "ratio_cell" if resolved.scalars.targets_editable else "comma_ratio",
                                     resolved.scalars.targets_editable), quantity_y, branch_minus)
    if query.tile_open(geometry, context.collapsed, "quantities", "held"):
        _emit_qty_list(cells, resolved, _QtyList("held", "held", resolved.dimensions.held_count, lambda i: query.interval_left(geometry, "held", i), resolved.held.ratios,
                                     resolved.tuning.held_sizes, resolved.held.pending, "ratio_cell", True), quantity_y, branch_minus)
    if query.tile_open(geometry, context.collapsed, "quantities", "interest"):
        _emit_qty_list(cells, resolved, _QtyList("interest", "interest", resolved.dimensions.interest_count, lambda i: query.interval_left(geometry, "interest", i), resolved.interest.ratios,
                                     resolved.tuning.interest_sizes, resolved.interest.pending, "ratio_cell", True), quantity_y, branch_minus)


def _emit_qty_list(cells, resolved, q: _QtyList, quantity_y: float, branch_minus) -> None:
    for j in range(q.count):
        cells.append(CellBox(f"{q.singular}:{query.column_token(resolved, q.group, j)}", q.left_fn(j), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, q.kind, text=q.ratios[j], comma=j))
        voice(cells, f"quantities:{q.group}", j, q.sizes.just[j])
        if q.minus_gate:
            branch_minus(f"{q.singular}_minus:{j}", q.group, j, f"{q.singular}_minus", comma=j)
    if q.pending is not None:
        cells.append(CellBox(f"{q.singular}:pending", q.left_fn(q.count), quantity_y, COLUMN_WIDTH, ROW_HEIGHT, "ratio_cell", text="?/?", comma=q.count, pending=True))
        branch_minus(f"{q.singular}_minus:pending", q.group, q.count, f"{q.singular}_minus")


def _emit_qty_grips(cells, resolved, geometry, context) -> None:
    grip_top = geometry.branch_top_y + GAP - PAD
    counts = {"commas": resolved.dimensions.comma_count, "targets": resolved.dimensions.target_count, "held": resolved.dimensions.held_count, "interest": resolved.dimensions.interest_count}
    for column_key in ("commas", "targets", "held", "interest"):
        if query.row_open(geometry, context.collapsed, "quantities") and query.plus_shows(geometry, resolved, context.collapsed, context.state, column_key):
            _qty_drag_controls(cells, resolved, geometry, column_key, counts[column_key], grip_top)
    if resolved.unchanged.shown:
        for j in range(resolved.dimensions.unchanged_count):
            if resolved.unchanged.basis[j] is not None:
                cells.append(CellBox(f"grip:unchanged:{j}", query.sub_axis_x(geometry, "commas", resolved.dimensions.comma_count_shown + j) - COLUMN_WIDTH / 2,
                                     grip_top, COLUMN_WIDTH, GRIP_BAND, "columngrip", comma=j))


def _qty_drag_controls(cells, resolved, geometry, column_key, n, grip_top) -> None:
    for i in range(n):
        cells.append(CellBox(f"grip:{column_key}:{i}", query.sub_axis_x(geometry, column_key, i) - COLUMN_WIDTH / 2,
                             grip_top, COLUMN_WIDTH, GRIP_BAND, "columngrip", comma=i))
    add_width = COLUMN_WIDTH
    if column_key == "commas" and resolved.unchanged.shown:
        add_width = resolved.unchanged.empty_comma_width if resolved.dimensions.comma_count_shown == 0 else V_SPLIT_GAP
    cells.append(CellBox(f"grip:{column_key}:add", geometry.plus_stub_x[column_key] - add_width / 2,
                         grip_top, add_width, GRIP_BAND, "columngrip"))


def emit_column_plus_controls(resolved, geometry) -> EmitResult:
    cells: list = []
    primes_plus = "element_plus" if resolved.flags.nonstandard_domain else "plus"
    for column_key, cell_id in (("generators", "generator_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                      ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
        if column_key in geometry.plus_stub_x:
            cells.append(CellBox(cell_id, geometry.plus_stub_x[column_key] - BUTTON / 2, geometry.fanout_y - BUTTON / 2, BUTTON, BUTTON, cell_id))
    return EmitResult(cells=tuple(cells))


def emit_rehomed_minus_controls(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, context.collapsed, "quantities") or not query.row_open(geometry, context.collapsed, "vectors"):
        return EmitResult()
    vtop = geometry.rows["vectors"].y

    def vector_minus(cell_id, column_key, i, kind, **kw):
        cells.append(CellBox(cell_id, query.sub_axis_x(geometry, column_key, i) - COLUMN_WIDTH / 2, geometry.fanout_y,
                             COLUMN_WIDTH, vtop - geometry.fanout_y, kind, **kw))

    _emit_rehomed_commas(resolved, geometry, context, vector_minus)
    _emit_rehomed_targets(resolved, geometry, context, vector_minus)
    _emit_rehomed_held(resolved, geometry, context, vector_minus)
    _emit_rehomed_interest(resolved, geometry, context, vector_minus)
    return EmitResult(cells=tuple(cells))


def _emit_rehomed_commas(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "commas"):
        for c in range(resolved.dimensions.comma_count):
            vector_minus(f"comma_minus:{query.column_token(resolved, 'commas', c)}", "commas", c, "comma_minus", comma=c)
        if resolved.commas.pending is not None:
            vector_minus("comma_minus:pending", "commas", resolved.dimensions.comma_count, "comma_minus")


def _emit_rehomed_targets(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "targets"):
        if resolved.scalars.targets_editable:
            for j in range(resolved.dimensions.target_count):
                vector_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
        if resolved.targets.pending is not None:
            vector_minus("target_minus:pending", "targets", resolved.dimensions.target_count, "target_minus")


def _emit_rehomed_held(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "held"):
        for i in range(resolved.dimensions.held_count):
            vector_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
        if resolved.held.pending is not None:
            vector_minus("held_minus:pending", "held", resolved.dimensions.held_count, "held_minus")


def _emit_rehomed_interest(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "interest"):
        for i in range(resolved.dimensions.interest_count):
            vector_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
        if resolved.interest.pending is not None:
            vector_minus("interest_minus:pending", "interest", resolved.dimensions.interest_count, "interest_minus")


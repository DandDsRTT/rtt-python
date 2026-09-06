from __future__ import annotations

from rtt.app import spreadsheet_brackets as bk
from rtt.app import spreadsheet_geometry_bands as bands
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.spreadsheet_constants import ROW_HEIGHT


def emit_superspace_brackets(cells, resolved, geometry, context) -> None:
    _emit_superspace_stacked_brackets(cells, resolved, geometry, context)
    _emit_superspace_projection_fit_brackets(cells, resolved, geometry, context)
    _emit_superspace_rest_brackets(cells, resolved, geometry, context)
    _emit_superspace_vectors_list_brackets(cells, resolved, geometry, context)
    _emit_superspace_mapped_list_brackets(cells, resolved, geometry, context)


def _emit_superspace_stacked_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(
        geometry, collapsed, "superspace_mapping", "superspace_primes"
    ):
        for i in range(resolved.dimensions.superspace_rank):
            bk.bracket(
                cells,
                resolved,
                geometry,
                f"superspace_map:{i}",
                "superspace_mapping",
                "superspace_primes",
                bands.superspace_map_top(geometry, i),
                ROW_HEIGHT,
                stacked=True,
            )
    if query.row_open(geometry, collapsed, "superspace_projection") and query.tile_open(
        geometry, collapsed, "superspace_projection", "superspace_primes"
    ):
        for i in range(resolved.dimensions.superspace_dimensionality):
            bk.bracket(
                cells,
                resolved,
                geometry,
                f"superspace_projection:{i}",
                "superspace_projection",
                "superspace_primes",
                bands.superspace_projection_top(geometry, i),
                ROW_HEIGHT,
                stacked=True,
            )


def _emit_superspace_projection_fit_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    top = (
        geometry.rows["superspace_projection"].y if "superspace_projection" in geometry.rows else 0
    )
    height = resolved.dimensions.superspace_dimensionality * ROW_HEIGHT
    if not query.row_open(geometry, collapsed, "superspace_projection"):
        return
    fit = (
        ("superspace_generators", "superspace_embed"),
        ("primes", "superspace_projection_basis_lift"),
        ("generators", "superspace_projection_detempering"),
        ("generator_embedding", "superspace_projection_embedding"),
        ("canonical_generators", "superspace_projection_canonical"),
        ("targets", "superspace_projection_targets"),
        ("held", "superspace_projection_held"),
    )
    for group, bid in fit:
        if query.tile_open(geometry, collapsed, "superspace_projection", group):
            bk.bracket(
                cells,
                resolved,
                geometry,
                bid,
                "superspace_projection",
                group,
                top,
                height,
                fit=True,
            )
    if resolved.unchanged.shown and query.tile_open(
        geometry, collapsed, "superspace_projection", "commas"
    ):
        bk.bracket(
            cells,
            resolved,
            geometry,
            "superspace_projection_vectors",
            "superspace_projection",
            "commas",
            top,
            height,
            fit=True,
        )


def _emit_superspace_rest_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_vectors") and query.tile_open(
        geometry, collapsed, "superspace_vectors", "superspace_primes"
    ):
        for i in range(resolved.dimensions.superspace_dimensionality):
            bk.bracket(
                cells,
                resolved,
                geometry,
                f"superspace_vector_ji_map:{i}",
                "superspace_vectors",
                "superspace_primes",
                bands.superspace_vector_top(geometry, i),
                ROW_HEIGHT,
                stacked=True,
            )
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(
        geometry, collapsed, "superspace_mapping", "primes"
    ):
        for i in range(resolved.dimensions.superspace_rank):
            bk.bracket(
                cells,
                resolved,
                geometry,
                f"superspace_mapping_lift:{i}",
                "superspace_mapping",
                "primes",
                bands.superspace_map_top(geometry, i),
                ROW_HEIGHT,
                stacked=True,
            )
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(
        geometry, collapsed, "superspace_mapping", "superspace_generators"
    ):
        bk.bracket(
            cells,
            resolved,
            geometry,
            "superspace_self_map",
            "superspace_mapping",
            "superspace_generators",
            geometry.rows["superspace_mapping"].y,
            resolved.dimensions.superspace_rank * ROW_HEIGHT,
            fit=True,
        )


def _emit_superspace_vectors_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if not query.row_open(geometry, collapsed, "superspace_vectors"):
        return
    y, height = (
        geometry.rows["superspace_vectors"].y,
        resolved.dimensions.superspace_dimensionality * ROW_HEIGHT,
    )
    lists = (
        ("primes", "superspace_vector:primes"),
        ("commas", "superspace_vector:commas"),
        ("targets", "superspace_vector:targets"),
        ("generators", "superspace_vector:detempering"),
        ("generator_embedding", "superspace_vector:generator_embedding"),
        ("canonical_generators", "superspace_vector:canonical_generators"),
        ("superspace_generators", "superspace_vectors_embed"),
    )
    for group, bid in lists:
        if query.tile_open(geometry, collapsed, "superspace_vectors", group):
            bk.bracket(
                cells, resolved, geometry, bid, "superspace_vectors", group, y, height, fit=True
            )
    if resolved.dimensions.held_count and query.tile_open(
        geometry, collapsed, "superspace_vectors", "held"
    ):
        bk.bracket(
            cells,
            resolved,
            geometry,
            "superspace_vector:held",
            "superspace_vectors",
            "held",
            y,
            height,
            fit=True,
        )


def _emit_superspace_mapped_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if not query.row_open(geometry, collapsed, "superspace_mapping"):
        return
    y, height = (
        geometry.rows["superspace_mapping"].y,
        resolved.dimensions.superspace_rank * ROW_HEIGHT,
    )
    lists = (
        ("commas", "superspace_mapped:commas"),
        ("targets", "superspace_mapped:targets"),
        ("generators", "superspace_mapped:detempering"),
        ("generator_embedding", "superspace_mapped:generator_embedding"),
        ("canonical_generators", "superspace_mapped:canonical_generators"),
    )
    for group, bid in lists:
        if query.tile_open(geometry, collapsed, "superspace_mapping", group):
            bk.bracket(
                cells, resolved, geometry, bid, "superspace_mapping", group, y, height, fit=True
            )
    if resolved.dimensions.held_count and query.tile_open(
        geometry, collapsed, "superspace_mapping", "held"
    ):
        bk.bracket(
            cells,
            resolved,
            geometry,
            "superspace_mapped:held",
            "superspace_mapping",
            "held",
            y,
            height,
            fit=True,
        )

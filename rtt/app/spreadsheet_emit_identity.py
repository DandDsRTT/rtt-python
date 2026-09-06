from __future__ import annotations

from rtt.app import spreadsheet_geometry_bands as bands
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import Cell
from rtt.app.spreadsheet_constants import COLUMN_WIDTH, ROW_HEIGHT
from rtt.app.spreadsheet_emit_model import EmitResult


def emit_identity_objects(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_identity_vector_primes(cells, resolved, geometry, context)
    for column_key, prefix, left in (
        ("generator_embedding", "selfmap", lambda k: query.generator_embedding_left(geometry, k)),
        ("generators", "mapped_detempering", lambda k: query.detempering_left(geometry, k)),
    ):
        if query.tile_open(geometry, context.collapsed, "mapping", column_key):
            _emit_identity_mapping_column(cells, resolved, geometry, column_key, prefix, left)
    _emit_identity_canonical_generators(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_identity_mapping_column(cells, resolved, geometry, column_key, prefix, left) -> None:
    rank = resolved.dimensions.rank
    for i in range(rank):
        for k in range(rank):
            cells.append(
                Cell(
                    f"cell:{prefix}:{i}:{k}",
                    left(k),
                    bands.map_top(geometry, i),
                    COLUMN_WIDTH,
                    ROW_HEIGHT,
                    "mapped",
                    text="1" if i == k else "0",
                    generator=i,
                    unit=query.cell_unit(resolved, "mapping", column_key, generator=i),
                )
            )
    if not resolved.scalars.row_draft:
        return
    for i in range(rank):
        cells.append(
            Cell(
                f"cell:{prefix}:{i}:{rank}",
                left(rank),
                query.map_top(geometry, i),
                COLUMN_WIDTH,
                ROW_HEIGHT,
                "mapped",
                text="",
                generator=i,
                pending=True,
            )
        )
    for k in range(rank + 1):
        cells.append(
            Cell(
                f"cell:{prefix}:{rank}:{k}",
                left(k),
                query.map_top(geometry, rank),
                COLUMN_WIDTH,
                ROW_HEIGHT,
                "mapped",
                text="",
                generator=rank,
                pending=True,
            )
        )


def _emit_identity_vector_primes(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "primes"):
        for i in range(resolved.dimensions.dimensionality):
            for k in range(resolved.dimensions.dimensionality):
                cells.append(
                    Cell(
                        f"cell:vector:primes:{i}:{k}",
                        query.prime_left(geometry, k),
                        bands.vector_top(geometry, i),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="1" if i == k else "0",
                        generator=i,
                        prime=k,
                        unit=query.cell_unit(resolved, "vectors", "primes", prime=k),
                    )
                )
        if resolved.scalars.element_draft:
            dp = resolved.dimensions.dimensionality
            for i in range(dp):
                cells.append(
                    Cell(
                        f"cell:vector:primes:{i}:{dp}",
                        query.prime_left(geometry, dp),
                        query.vector_top(geometry, i),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="",
                        generator=i,
                        prime=dp,
                        pending=True,
                    )
                )
            for k in range(dp + 1):
                cells.append(
                    Cell(
                        f"cell:vector:primes:{dp}:{k}",
                        query.prime_left(geometry, k),
                        query.vector_top(geometry, dp),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="",
                        generator=dp,
                        prime=k,
                        pending=True,
                    )
                )


def _emit_identity_canonical_generators(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canonical", "canonical_generators"):
        for i in range(resolved.dimensions.canonical_rank):
            for k in range(resolved.dimensions.canonical_rank):
                cells.append(
                    Cell(
                        f"cell:fcancel:{i}:{k}",
                        query.canonical_generator_left(geometry, k),
                        bands.canonical_top(geometry, i),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="1" if i == k else "0",
                        generator=i,
                        unit=query.cell_unit(
                            resolved, "canonical", "canonical_generators", generator=i
                        ),
                    )
                )
        if resolved.scalars.row_draft:
            cr = resolved.dimensions.canonical_rank
            for i in range(cr):
                cells.append(
                    Cell(
                        f"cell:fcancel:{i}:{cr}",
                        query.canonical_generator_left(geometry, cr),
                        query.canonical_top(geometry, i),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="",
                        generator=i,
                        pending=True,
                    )
                )
            for k in range(cr + 1):
                cells.append(
                    Cell(
                        f"cell:fcancel:{cr}:{k}",
                        query.canonical_generator_left(geometry, k),
                        query.canonical_top(geometry, cr),
                        COLUMN_WIDTH,
                        ROW_HEIGHT,
                        "mapped",
                        text="",
                        generator=cr,
                        pending=True,
                    )
                )

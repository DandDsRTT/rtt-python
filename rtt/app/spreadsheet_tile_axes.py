from __future__ import annotations

from typing import NamedTuple

GENERATORS = "generators"
PRIMES = "primes"
COMMAS = "commas"
TARGETS = "targets"
HELD = "held"
INTEREST = "interest"
CANONICAL_GENERATORS = "canonical_generators"
DETEMPERING = "detempering"
UNCHANGED = "unchanged"
SUPERSPACE_GENERATORS = "superspace_generators"
SUPERSPACE_PRIMES = "superspace_primes"

FIXED = None


class TileAxes(NamedTuple):
    prefix: str
    rows: object
    cols: object


def axis_count(dims, axis) -> int:
    return {
        GENERATORS: dims.rank,
        DETEMPERING: dims.rank,
        UNCHANGED: dims.rank,
        PRIMES: dims.dimensionality,
        COMMAS: dims.comma_count,
        TARGETS: dims.target_count,
        HELD: dims.held_count,
        INTEREST: dims.interest_count,
        CANONICAL_GENERATORS: dims.canonical_rank,
        SUPERSPACE_GENERATORS: dims.superspace_rank,
        SUPERSPACE_PRIMES: dims.superspace_dimensionality,
    }[axis]


MATRIX_TILES: tuple[TileAxes, ...] = (
    TileAxes("cell:mapping", GENERATORS, PRIMES),
    TileAxes("cell:canonical", CANONICAL_GENERATORS, PRIMES),
    TileAxes("cell:embed", PRIMES, GENERATORS),
    TileAxes("cell:embed_c", PRIMES, CANONICAL_GENERATORS),
    TileAxes("cell:projection", PRIMES, PRIMES),
    TileAxes("cell:selfmap", GENERATORS, GENERATORS),
    TileAxes("cell:inverse_form", CANONICAL_GENERATORS, CANONICAL_GENERATORS),
    TileAxes("cell:form", GENERATORS, CANONICAL_GENERATORS),
    TileAxes("cell:fcancel", CANONICAL_GENERATORS, CANONICAL_GENERATORS),
    TileAxes("cell:mapped", GENERATORS, TARGETS),
    TileAxes("cell:hmapped", GENERATORS, HELD),
    TileAxes("cell:imapped", GENERATORS, INTEREST),
    TileAxes("cell:mapped_comma", GENERATORS, COMMAS),
    TileAxes("cell:mapped_detempering", GENERATORS, DETEMPERING),
    TileAxes("cell:mapped_unchanged", GENERATORS, UNCHANGED),
    TileAxes("cell:comma", PRIMES, COMMAS),
    TileAxes("cell:held", PRIMES, HELD),
    TileAxes("cell:interest", PRIMES, INTEREST),
    TileAxes("cell:unchanged", PRIMES, UNCHANGED),
    TileAxes("cell:vector:primes", PRIMES, PRIMES),
    TileAxes("cell:vector:targets", TARGETS, PRIMES),
    TileAxes("cell:vector:detempering", DETEMPERING, PRIMES),
    TileAxes("cell:projection_targets", TARGETS, PRIMES),
    TileAxes("cell:projection_held", HELD, PRIMES),
    TileAxes("cell:projection_interest", INTEREST, PRIMES),
    TileAxes("cell:projection_detempering", DETEMPERING, PRIMES),
    TileAxes("cell:projection_vectors", PRIMES, COMMAS),
    TileAxes("cell:canonical_mapped", CANONICAL_GENERATORS, TARGETS),
    TileAxes("cell:canonical_hmapped", CANONICAL_GENERATORS, HELD),
    TileAxes("cell:canonical_imapped", CANONICAL_GENERATORS, INTEREST),
    TileAxes("cell:canonical_detempering", CANONICAL_GENERATORS, DETEMPERING),
    TileAxes("cell:canonical_mapped_comma", CANONICAL_GENERATORS, COMMAS),
    TileAxes("cell:canonical_mapped_unchanged", CANONICAL_GENERATORS, UNCHANGED),
)

VALUE_ROW_TILES: tuple[TileAxes, ...] = (
    TileAxes("tuning:generator", FIXED, GENERATORS),
    TileAxes("tuning:canonical_generator", FIXED, CANONICAL_GENERATORS),
    TileAxes("tuning:prime", FIXED, PRIMES),
    TileAxes("tuning:target", FIXED, TARGETS),
    TileAxes("tuning:comma", FIXED, COMMAS),
    TileAxes("tuning:detempering", FIXED, DETEMPERING),
    TileAxes("just:prime", FIXED, PRIMES),
    TileAxes("just:target", FIXED, TARGETS),
    TileAxes("just:comma", FIXED, COMMAS),
    TileAxes("just:detempering", FIXED, DETEMPERING),
    TileAxes("retune:prime", FIXED, PRIMES),
    TileAxes("retune:target", FIXED, TARGETS),
    TileAxes("retune:comma", FIXED, COMMAS),
    TileAxes("retune:detempering", FIXED, DETEMPERING),
    TileAxes("damage:target", FIXED, TARGETS),
    TileAxes("weight:target", FIXED, TARGETS),
)

REGISTRY: tuple[TileAxes, ...] = MATRIX_TILES + VALUE_ROW_TILES

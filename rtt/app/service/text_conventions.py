from __future__ import annotations

from collections import namedtuple

EbkConvention = namedtuple(
    "EbkConvention", "structure outer_open outer_close inner_open inner_close sep"
)

_DASH = "—"

_MAP = EbkConvention("row", "⟨", "]", "", "", " ")
_GENMAP = EbkConvention("row", "{", "]", "", "", " ")
_SCALARS = EbkConvention("row", "[", "]", "", "", " ")
_SCALARS_BARE = EbkConvention("row", "", "", "", "", " ")
_VEC = EbkConvention("list", "[", "]", "[", "⟩", " ")
_VEC_BARE = EbkConvention("list", "", "", "[", "⟩", " ")
_MAPPED = EbkConvention("list", "[", "]", "[", "}", " ")
_MAPPED_BARE = EbkConvention("list", "", "", "[", "}", " ")
_EMBED = EbkConvention("list", "{", "]", "[", "⟩", " ")
_GENMAPPED = EbkConvention("list", "{", "]", "[", "}", " ")
_BASIS = EbkConvention("list", "⟨", "]", "[", "⟩", " ")
_STACK_BRACE = EbkConvention("stack", "[", "}", "⟨", "]", "")
_STACK_BRACE_SP = EbkConvention("stack", "[", "}", "⟨", "]", " ")
_STACK_ANGLE = EbkConvention("stack", "[", "⟩", "⟨", "]", "")
_BARE_PRESCALER = EbkConvention("stack", "[", "⟩", "⟨", "]", " ")
_CANON_STACK = EbkConvention("stack", "[", "}", "⟨", "]", " ")
_CANON_GEN_STACK = EbkConvention("stack", "[", "}", "{", "]", " ")

EBK_CONVENTIONS = {
    ("vectors", "commas"): _VEC,
    ("vectors", "targets"): _VEC,
    ("vectors", "detempering"): _VEC,
    ("vectors", "held"): _VEC,
    ("vectors", "interest"): _VEC_BARE,
    ("vectors", "primes"): _STACK_ANGLE,
    ("mapping", "primes"): _STACK_BRACE_SP,
    ("mapping", "commas"): _MAPPED,
    ("mapping", "targets"): _MAPPED,
    ("mapping", "held"): _MAPPED,
    ("mapping", "interest"): _MAPPED_BARE,
    ("mapping", "gens"): _GENMAPPED,
    ("mapping", "detempering"): _GENMAPPED,
    ("mapping", "canongens"): _CANON_GEN_STACK,
    ("canon", "primes"): _CANON_STACK,
    ("canon", "gens"): _CANON_GEN_STACK,
    ("canon", "canongens"): _CANON_GEN_STACK,
    ("canon", "detempering"): _GENMAPPED,
    ("canon", "commas"): _MAPPED,
    ("canon", "targets"): _MAPPED,
    ("canon", "held"): _MAPPED,
    ("canon", "interest"): _MAPPED_BARE,
    ("scaling_factors", "commas"): _SCALARS,
    ("projection", "commas"): _VEC,
    ("projection", "targets"): _VEC,
    ("projection", "held"): _VEC,
    ("projection", "interest"): _VEC_BARE,
    ("projection", "detempering"): _EMBED,
    ("projection", "primes"): _STACK_ANGLE,
    ("projection", "gens"): _EMBED,
    ("projection", "canongens"): _EMBED,
    ("projection", "superspace_generators"): _EMBED,
    ("projection", "superspace_primes"): _STACK_ANGLE,
    ("tuning", "gens"): _GENMAP,
    ("tuning", "canongens"): _GENMAP,
    ("tuning", "primes"): _MAP,
    ("tuning", "commas"): _SCALARS,
    ("tuning", "detempering"): _GENMAP,
    ("tuning", "targets"): _SCALARS,
    ("tuning", "held"): _SCALARS,
    ("tuning", "interest"): _SCALARS_BARE,
    ("tuning", "superspace_generators"): _GENMAP,
    ("tuning", "superspace_primes"): _MAP,
    ("just", "primes"): _MAP,
    ("just", "commas"): _SCALARS,
    ("just", "detempering"): _SCALARS,
    ("just", "targets"): _SCALARS,
    ("just", "held"): _SCALARS,
    ("just", "interest"): _SCALARS_BARE,
    ("just", "superspace_primes"): _MAP,
    ("retune", "primes"): _MAP,
    ("retune", "commas"): _SCALARS,
    ("retune", "detempering"): _SCALARS,
    ("retune", "targets"): _SCALARS,
    ("retune", "held"): _SCALARS,
    ("retune", "interest"): _SCALARS_BARE,
    ("retune", "superspace_primes"): _MAP,
    ("damage", "targets"): _SCALARS,
    ("weight", "targets"): _SCALARS,
    ("complexity", "primes"): _MAP,
    ("complexity", "commas"): _SCALARS,
    ("complexity", "detempering"): _SCALARS,
    ("complexity", "targets"): _SCALARS,
    ("complexity", "held"): _SCALARS,
    ("complexity", "interest"): _SCALARS_BARE,
    ("complexity", "superspace_primes"): _MAP,
    ("prescaling", "commas"): _VEC,
    ("prescaling", "detempering"): _VEC,
    ("prescaling", "targets"): _VEC,
    ("prescaling", "held"): _VEC,
    ("prescaling", "interest"): _VEC_BARE,
    ("prescaling", "superspace_primes"): _BARE_PRESCALER,
    ("superspace_vectors", "primes"): _BASIS,
    ("superspace_vectors", "superspace_primes"): _STACK_ANGLE,
    ("superspace_vectors", "commas"): _VEC,
    ("superspace_vectors", "targets"): _VEC,
    ("superspace_vectors", "detempering"): _VEC,
    ("superspace_vectors", "held"): _VEC,
    ("superspace_vectors", "interest"): _VEC_BARE,
    ("superspace_mapping", "superspace_primes"): _STACK_BRACE,
    ("superspace_mapping", "primes"): _STACK_BRACE,
    ("superspace_mapping", "superspace_generators"): _GENMAPPED,
    ("superspace_mapping", "commas"): _MAPPED,
    ("superspace_mapping", "targets"): _MAPPED,
    ("superspace_mapping", "detempering"): _GENMAPPED,
    ("superspace_mapping", "held"): _MAPPED,
    ("superspace_mapping", "interest"): _MAPPED_BARE,
    ("superspace_projection", "superspace_primes"): _STACK_ANGLE,
    ("superspace_projection", "superspace_generators"): _EMBED,
    ("superspace_projection", "primes"): _BASIS,
    ("superspace_projection", "detempering"): _EMBED,
    ("superspace_projection", "commas"): _VEC,
    ("superspace_projection", "targets"): _VEC,
    ("superspace_projection", "held"): _VEC,
    ("superspace_projection", "interest"): _VEC_BARE,
}


def ebk_convention(row_key: str, column_key: str, *, superspace: bool = False) -> EbkConvention:
    if (row_key, column_key) == ("prescaling", "primes"):
        return _BASIS if superspace else _BARE_PRESCALER
    return EBK_CONVENTIONS[(row_key, column_key)]


def matrix_orient(row_key: str, column_key: str, *, superspace: bool = False) -> str:
    return (
        "col"
        if ebk_convention(row_key, column_key, superspace=superspace).structure == "list"
        else "row"
    )


def render_ebk(convention: EbkConvention, items, formatter=str) -> str:
    oo, oc, io, ic, sep = (
        convention.outer_open,
        convention.outer_close,
        convention.inner_open,
        convention.inner_close,
        convention.sep,
    )
    if convention.structure == "row":
        return oo + sep.join(_DASH if v is None else formatter(v) for v in items) + oc
    vectors = list(items)
    dim = next((len(v) for v in vectors if v is not None), 0)
    pieces = [
        io
        + " ".join(
            [_DASH] * dim if v is None else [_DASH if x is None else formatter(x) for x in v]
        )
        + ic
        for v in vectors
    ]
    return oo + sep.join(pieces) + oc

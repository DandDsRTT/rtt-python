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
    ("projection", "ssgens"): _EMBED,
    ("projection", "ssprimes"): _STACK_ANGLE,
    ("tuning", "gens"): _GENMAP,
    ("tuning", "canongens"): _GENMAP,
    ("tuning", "primes"): _MAP,
    ("tuning", "commas"): _SCALARS,
    ("tuning", "detempering"): _GENMAP,
    ("tuning", "targets"): _SCALARS,
    ("tuning", "held"): _SCALARS,
    ("tuning", "interest"): _SCALARS_BARE,
    ("tuning", "ssgens"): _GENMAP,
    ("tuning", "ssprimes"): _MAP,
    ("just", "primes"): _MAP,
    ("just", "commas"): _SCALARS,
    ("just", "detempering"): _SCALARS,
    ("just", "targets"): _SCALARS,
    ("just", "held"): _SCALARS,
    ("just", "interest"): _SCALARS_BARE,
    ("just", "ssprimes"): _MAP,
    ("retune", "primes"): _MAP,
    ("retune", "commas"): _SCALARS,
    ("retune", "detempering"): _SCALARS,
    ("retune", "targets"): _SCALARS,
    ("retune", "held"): _SCALARS,
    ("retune", "interest"): _SCALARS_BARE,
    ("retune", "ssprimes"): _MAP,
    ("damage", "targets"): _SCALARS,
    ("weight", "targets"): _SCALARS,
    ("complexity", "primes"): _MAP,
    ("complexity", "commas"): _SCALARS,
    ("complexity", "detempering"): _SCALARS,
    ("complexity", "targets"): _SCALARS,
    ("complexity", "held"): _SCALARS,
    ("complexity", "interest"): _SCALARS_BARE,
    ("complexity", "ssprimes"): _MAP,
    ("prescaling", "commas"): _VEC,
    ("prescaling", "detempering"): _VEC,
    ("prescaling", "targets"): _VEC,
    ("prescaling", "held"): _VEC,
    ("prescaling", "interest"): _VEC_BARE,
    ("prescaling", "ssprimes"): _BARE_PRESCALER,
    ("ss_vectors", "primes"): _BASIS,
    ("ss_vectors", "ssprimes"): _STACK_ANGLE,
    ("ss_vectors", "commas"): _VEC,
    ("ss_vectors", "targets"): _VEC,
    ("ss_vectors", "detempering"): _VEC,
    ("ss_vectors", "held"): _VEC,
    ("ss_vectors", "interest"): _VEC_BARE,
    ("ss_mapping", "ssprimes"): _STACK_BRACE,
    ("ss_mapping", "primes"): _STACK_BRACE,
    ("ss_mapping", "ssgens"): _GENMAPPED,
    ("ss_mapping", "commas"): _MAPPED,
    ("ss_mapping", "targets"): _MAPPED,
    ("ss_mapping", "detempering"): _GENMAPPED,
    ("ss_mapping", "held"): _MAPPED,
    ("ss_mapping", "interest"): _MAPPED_BARE,
    ("ss_projection", "ssprimes"): _STACK_ANGLE,
    ("ss_projection", "ssgens"): _EMBED,
    ("ss_projection", "primes"): _BASIS,
    ("ss_projection", "detempering"): _EMBED,
    ("ss_projection", "commas"): _VEC,
    ("ss_projection", "targets"): _VEC,
    ("ss_projection", "held"): _VEC,
    ("ss_projection", "interest"): _VEC_BARE,
}


def ebk_convention(row_key: str, column_key: str, *, superspace: bool = False) -> EbkConvention:
    if (row_key, column_key) == ("prescaling", "primes"):
        return _BASIS if superspace else _BARE_PRESCALER
    return EBK_CONVENTIONS[(row_key, column_key)]


def render_ebk(conv: EbkConvention, items, fmt=str) -> str:
    oo, oc, io, ic, sep = (
        conv.outer_open,
        conv.outer_close,
        conv.inner_open,
        conv.inner_close,
        conv.sep,
    )
    if conv.structure == "row":
        return oo + sep.join(_DASH if v is None else fmt(v) for v in items) + oc
    vectors = list(items)
    dim = next((len(v) for v in vectors if v is not None), 0)
    pieces = [
        io
        + " ".join([_DASH] * dim if v is None else [_DASH if x is None else fmt(x) for x in v])
        + ic
        for v in vectors
    ]
    return oo + sep.join(pieces) + oc

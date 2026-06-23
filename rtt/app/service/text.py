from __future__ import annotations

from collections import namedtuple

from rtt.app.service.core import cents, prescale_text

EbkConvention = namedtuple(
    "EbkConvention", "structure outer_open outer_close inner_open inner_close sep"
)

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


def ebk_convention(rkey: str, ckey: str, *, superspace: bool = False) -> EbkConvention:
    if (rkey, ckey) == ("prescaling", "primes"):
        return _BASIS if superspace else _BARE_PRESCALER
    return EBK_CONVENTIONS[(rkey, ckey)]


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


_DASH = "—"


_EBK_OPEN = "[⟨{"
_EBK_CLOSE = "]⟩}"
_KET_CLOSE = "⟩}"
_TRANSPOSE = "ᵀ"


def _flatten_brackets(group: str) -> str:
    return "".join("[" if c in _EBK_OPEN else "]" if c in _EBK_CLOSE else c for c in group)


def _group_is_vector_based(group: str) -> bool:
    inner = group[1:-1].lstrip()
    if inner and inner[0] in _EBK_OPEN:
        return inner[0] == "["
    return group[-1] in _KET_CLOSE


def ebk_to_simple_matrix(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in _EBK_OPEN:
            depth, j = 0, i
            while j < n:
                if text[j] in _EBK_OPEN:
                    depth += 1
                elif text[j] in _EBK_CLOSE:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                out.append(text[i:])
                break
            group = text[i : j + 1]
            out.append(
                _flatten_brackets(group) + (_TRANSPOSE if _group_is_vector_based(group) else "")
            )
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def simple_matrix_to_ebk(text: str, vector_based: bool) -> str:
    text = text.replace(_TRANSPOSE, "")
    start = text.find("[")
    if start == -1:
        return text
    prefix, body = text[:start], text[start:]
    open_ch, close_ch = ("[", "⟩") if vector_based else ("⟨", "]")
    wrapped = body[1:].lstrip().startswith("[")
    out, depth = [], 0
    for c in body:
        if c == "[":
            depth += 1
            out.append("[" if (wrapped and depth == 1) else open_ch)
        elif c == "]":
            out.append("]" if (wrapped and depth == 1) else close_ch)
            depth -= 1
        else:
            out.append(c)
    return prefix + "".join(out)


def _ket_list(vectors, close: str, wrap: bool = True) -> str:
    return render_ebk(
        EbkConvention("list", "[" if wrap else "", "]" if wrap else "", "[", close, " "), vectors
    )


def projection_ebk(matrix, d: int, cols: int | None = None) -> str:
    cols = d if cols is None else cols
    grid = matrix if matrix is not None else [(_DASH,) * cols for _ in range(d)]
    return render_ebk(_STACK_ANGLE, grid)


def embedding_ebk(matrix, d: int, r: int) -> str:
    grid = matrix if matrix is not None else [(_DASH,) * r for _ in range(d)]
    return render_ebk(_EMBED, list(zip(*grid, strict=False)))


def _prescale_vector_list(
    vectors, col: str = "[⟩", outer: str = "[]", decimals: bool = True
) -> str:
    oo, oc = (outer[0], outer[1]) if outer else ("", "")
    structure = "stack" if col[0] == "⟨" else "list"
    conv = EbkConvention(structure, oo, oc, col[0], col[1], " ")
    return render_ebk(conv, vectors, fmt=lambda x: prescale_text(x, decimals))


def vector_list_pending_text(committed_vectors, pending) -> tuple[str, str, str]:
    committed = _ket_list(committed_vectors, "⟩")
    draft = "[" + " ".join(str(x) for x in pending if x is not None) + "⟩"
    return committed[:-1] + " ", draft, "]"


def mapping_pending_text(committed_ebk, pending) -> tuple[str, str, str]:
    draft = "⟨" + " ".join(str(x) for x in pending if x is not None) + "]"
    return committed_ebk[:-1] + " ", draft, "}"


def _cents_map(values, decimals: bool = True) -> str:
    return render_ebk(_MAP, values, fmt=lambda v: cents(v, decimals))


def _cents_list(values, wrap: bool = True, decimals: bool = True) -> str:
    return render_ebk(_SCALARS if wrap else _SCALARS_BARE, values, fmt=lambda v: cents(v, decimals))


def _cents_genmap(values, decimals: bool = True) -> str:
    return render_ebk(_GENMAP, values, fmt=lambda v: cents(v, decimals))

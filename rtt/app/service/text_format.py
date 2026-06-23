from __future__ import annotations

from rtt.app.service.core import cents, prescale_text
from rtt.app.service.text_conventions import (
    _DASH,
    _EMBED,
    _GENMAP,
    _MAP,
    _SCALARS,
    _SCALARS_BARE,
    _STACK_ANGLE,
    EbkConvention,
    render_ebk,
)

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

from __future__ import annotations

import re
from fractions import Fraction

from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, quotient_to_pcv
from rtt.library.temperament import Temperament, Variance

_COVARIANT_RE = re.compile(r"\[?\s*[<⟨{][^\[]*")
_ROW_VECTOR_RE = re.compile(r"[⟨{<]([\d\-+*/.,\s]*)[\]|]\s*")
_COL_VECTOR_RE = re.compile(r"[\[|]([\d\-+*/.,\s]*)[}⟩>]\s*")
_SPLIT_RE = re.compile(r"(?:\s*,\s*)|\s+")
_DOMAIN_BASIS_PREFIX_RE = re.compile(r"^([\d./]+)\s+(.*)$", re.DOTALL)

# A grade-g multivector (wedgie) repeats its variance bracket g times — ⟨⟨…]] for a
# covariant bivector, [[…⟩⟩ for a contravariant one (EBK extension 2; conventions O11/O20).
# The pointed (variance-bearing) brackets doubled — two opening or two closing angles/curlies,
# whitespace allowed — mark grade ≥ 2. (Square ]] / [[ is NOT a signal: an outer-wrapped map
# ends ]] and a comma basis opens [[.) Such an object is not a map/vector, so we reject it
# rather than silently parse the inner single bracket's contents.
_MULTIVECTOR_RE = re.compile(r"[⟨<{]\s*[⟨<{]|[⟩>}]\s*[⟩>}]")
# Characters allowed to appear *between* the vectors (outer wrappers, separators): anything
# else left over once the vectors are removed is junk, and the string is rejected.
_STRUCTURAL_CHARS = frozenset("[]{}()<>⟨⟩|, \t\n\r")
_SECOR_ELISION_RE = re.compile(r",\s+,")


def is_covariant_ebk(ebk: str) -> bool:
    """Whether the EBK string denotes a covariant (mapping / covector) temperament."""
    return _COVARIANT_RE.fullmatch(ebk) is not None


def parse_temperament_data(data: str | Temperament) -> Temperament:
    if isinstance(data, Temperament):  # already-structured input passes through
        return data
    domain_basis = None
    prefix = _DOMAIN_BASIS_PREFIX_RE.match(data)
    if prefix:
        domain_basis = parse_domain_basis(prefix.group(1))
        data = prefix.group(2)
    if _MULTIVECTOR_RE.search(data):
        raise ValueError(f"repeated (multivector) brackets are not a map/vector: {data!r}")
    row_match = _ROW_VECTOR_RE.search(data)
    col_match = _COL_VECTOR_RE.search(data)
    if row_match and col_match:
        # bras AND kets at one nesting level — a valid EBK matrix is a ket of bras OR a bra of
        # kets, never both mixed, so applying half of it would silently drop the other rows.
        raise ValueError(f"mixed bra/ket variance is not valid EBK: {data!r}")
    if is_covariant_ebk(data):
        variance = Variance.ROW
        matches = list(_ROW_VECTOR_RE.finditer(data))
    else:
        variance = Variance.COL
        matches = list(_COL_VECTOR_RE.finditer(data))
    _reject_junk(data, matches)
    matrix = tuple(parse_ebk_vector(m.group(1)) for m in matches)
    return Temperament(matrix, variance, domain_basis)


def _reject_junk(data: str, matches: list) -> None:
    """Raise if anything other than the vectors and their structural wrappers is present —
    the old leniency silently ignored arbitrary junk around the vectors (``junk [-4 4 -1⟩
    junk`` committed the comma)."""
    residue = list(data)
    for match in matches:
        for i in range(match.start(), match.end()):
            residue[i] = " "
    stray = {ch for ch in residue if ch not in _STRUCTURAL_CHARS}
    if stray:
        raise ValueError(f"stray content outside the EBK vectors {sorted(stray)!r}: {data!r}")


def parse_quotients(text: str) -> list[Fraction]:
    """Parse a quotient-list string like ``"{2/1, 3/2, 5/4}"`` into fractions."""
    return [Fraction(token) for token in re.findall(r"[\d/]+", text)]


def parse_quotient_list(text: str, d: int) -> tuple[tuple[int, ...], ...]:
    """Parse a quotient-list string like ``"{2/1, 3/2, 5/4}"`` into vectors (each a
    prime-count vector padded to ``d`` entries)."""
    pcvs = tuple(quotient_to_pcv(q) for q in parse_quotients(text))
    return pad_vectors_with_zeros_up_to_d(pcvs, d)


def parse_domain_basis(text: str) -> tuple:
    """Parse a dot-separated domain basis like ``2.3.7`` into ``(2, 3, 7)``."""
    return tuple(Fraction(p) if "/" in p else int(p) for p in text.split("."))


def parse_ebk_vector(text: str) -> tuple:
    """Parse one EBK vector's entries; a bare empty entry (``,,``) becomes None."""
    return tuple(_to_number(token) for token in _SPLIT_RE.split(_expand_secor_elisions(text.strip())))


def _expand_secor_elisions(text: str) -> str:
    """Expand the Secor zero-run elision: a ``, ,`` (group-separator commas with only
    whitespace between) stands for a whole group of three zeros dropped, so ``[-3 0, , 1⟩``
    means ``[-3 0 0 0 0 1⟩`` (conventions O12; EDGE CASES "zero entries and elision"). A bare
    ``,,`` with no space is left as a single blank (None) draft entry."""
    prev = None
    while prev != text:
        prev = text
        text = _SECOR_ELISION_RE.sub(", 0 0 0,", text, count=1)
    return text


def _to_number(token: str):
    if token == "":
        return None
    if "." in token:
        return float(token)
    if "/" in token:
        return Fraction(token)
    return int(token)

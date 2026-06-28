from __future__ import annotations

import re

DD = "dd"
WIKI = "wiki"
BOTH = "both"

_PHRASE_WIKI_TERMS = (
    ("interval vectors", "monzos"),
    ("interval-vectors", "monzos"),
    ("interval vector", "monzo"),
    ("prime-count vector", "monzo"),
    ("unchanged interval basis", "eigenmonzo list"),
)

_SCHEME_WIKI_NAMES = {
    "minimax-S": "TOP",
    "held-octave minimax-S": "CTOP",
    "destretched-octave minimax-S": "POTOP",
    "minimax-ES": "TE",
    "held-octave minimax-ES": "CTE",
    "destretched-octave minimax-ES": "POTE",
    "minimax-E-copfr-S": "Frobenius",
    "minimax-sopfr-S": "BOP",
    "minimax-E-sopfr-S": "BE",
    "minimax-lils-S": "Weil",
    "held-octave minimax-lils-S": "CWOP",
    "destretched-octave minimax-lils-S": "Kees",
    "minimax-E-lils-S": "WE",
    "held-octave minimax-E-lils-S": "CWE",
    "destretched-octave minimax-E-lils-S": "POWE",
}

_PHRASE_PATTERNS = tuple(
    (re.compile(rf"\b{re.escape(dd_term)}\b", re.IGNORECASE), wiki_term)
    for dd_term, wiki_term in _PHRASE_WIKI_TERMS
)


def _paired(dd_term, wiki_term, mode):
    return wiki_term if mode == WIKI else f"{dd_term} ({wiki_term})"


def substitute(text, mode=DD):
    if mode == DD or not text:
        return text
    substituted = text
    for pattern, wiki_term in _PHRASE_PATTERNS:
        substituted = pattern.sub(lambda m, w=wiki_term: _paired(m.group(0), w, mode), substituted)
    return substituted


def substitute_captions(captions, mode=DD):
    if mode == DD:
        return captions
    return {key: substitute(name, mode) for key, name in captions.items()}


def scheme(name, mode=DD):
    if mode == DD or name is None:
        return name
    wiki_name = _SCHEME_WIKI_NAMES.get(name)
    if wiki_name is None:
        return name
    return _paired(name, wiki_name, mode)

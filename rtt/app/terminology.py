from __future__ import annotations

import re

_PHRASE_WIKI_TERMS = (
    ("interval vectors", "monzos"),
    ("interval-vectors", "monzos"),
    ("interval vector", "monzo"),
    ("prime-count vector", "monzo"),
    ("unrotated vector list", "eigenmonzo and comma list"),
    ("unchanged-interval basis", "eigenmonzo list"),
    ("comma basis", "comma list"),
)

_SCHEME_WIKI_NAMES = {
    "minimax-S": "TOP",
    "minimax-ES": "TE",
    "held-octave minimax-ES": "CTE",
    "destretched-octave minimax-ES": "POTE",
    "minimax-sopfr-S": "BOP",
    "minimax-E-sopfr-S": "BE",
    "minimax-lils-S": "Weil",
    "minimax-E-lils-S": "WE",
    "held-octave minimax-E-lils-S": "CWE",
}

_PHRASE_PATTERNS = tuple(
    (re.compile(rf"\b{re.escape(dd_term)}\b", re.IGNORECASE), wiki_term)
    for dd_term, wiki_term in _PHRASE_WIKI_TERMS
)


def wiki(text, dd_terminology=True):
    if dd_terminology or not text:
        return text
    substituted = text
    for pattern, wiki_term in _PHRASE_PATTERNS:
        substituted = pattern.sub(wiki_term, substituted)
    return substituted


def wiki_captions(captions, dd_terminology=True):
    if dd_terminology:
        return captions
    return {key: wiki(name, dd_terminology) for key, name in captions.items()}


def scheme_name(name, dd_terminology=True):
    if dd_terminology or name is None:
        return name
    return _SCHEME_WIKI_NAMES.get(name, name)

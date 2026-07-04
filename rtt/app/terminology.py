from __future__ import annotations

import re

DD = "dd"
WIKI = "wiki"
BOTH = "both"

_PHRASE_WIKI_TERMS = (
    ("unchanged interval basis", "eigenmonzo list"),
    ("unrotated vector list", "eigenmonzo and comma list"),
    ("unrotated vector", "eigenmonzo and comma"),
    ("generator detempering", "generator preimage transversal"),
    ("canonically mapped intervals", "canonical tmonzos"),
    ("prime-count vector", "monzo"),
    ("unchanged interval", "eigenmonzo"),
    ("interval vectors", "monzos"),
    ("mapped intervals", "tmonzos"),
    ("interval vector", "monzo"),
    ("mapped interval", "tmonzo"),
    ("held intervals", "constraints"),
    ("held interval", "constraint"),
    ("mapping", "val list"),
    ("map", "val"),
)

_VERB_GUARDS = {"map": r"(?![-\s]+intervals?\b)"}


def _normalize(term):
    return re.sub(r"[-\s]+", " ", term.strip().lower())


_WIKI_BY_DD = {_normalize(dd_term): wiki_term for dd_term, wiki_term in _PHRASE_WIKI_TERMS}


def _term_pattern(dd_term):
    body = r"[-\s]+".join(re.escape(token) for token in dd_term.split())
    return body + _VERB_GUARDS.get(_normalize(dd_term), "")


_COMBINED_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(
        _term_pattern(dd_term)
        for dd_term, _ in sorted(_PHRASE_WIKI_TERMS, key=lambda pair: -len(pair[0]))
    )
    + r")\b",
    re.IGNORECASE,
)


def _paired(dd_term, wiki_term, mode):
    return wiki_term if mode == WIKI else f"{dd_term} ({wiki_term})"


def _wiki(text):
    return _COMBINED_PATTERN.sub(lambda match: _WIKI_BY_DD[_normalize(match.group(0))], text)


def substitute(text, mode=DD):
    if mode == DD or not text:
        return text
    return _COMBINED_PATTERN.sub(
        lambda match: _paired(match.group(0), _WIKI_BY_DD[_normalize(match.group(0))], mode), text
    )


def substitute_name(text, mode=DD):
    if mode == DD or not text:
        return text
    wiki = _wiki(text)
    if mode == WIKI:
        return wiki
    return text if wiki == text else f"{text} ({wiki})"


def substitute_stacked(text, mode=DD):
    if mode == DD or not text:
        return text
    if mode == WIKI:
        return _wiki(text)
    collapsed = re.sub(r"\s+", " ", text).strip()
    wiki = _wiki(collapsed)
    return text if wiki == collapsed else f"{collapsed}\n({wiki})"


def substitute_names(names, mode=DD):
    if mode == DD:
        return names
    return {key: substitute_name(name, mode) for key, name in names.items()}


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


def scheme(name, mode=DD):
    if mode == DD or name is None:
        return name
    wiki_name = _SCHEME_WIKI_NAMES.get(name)
    if wiki_name is None:
        return name
    return _paired(name, wiki_name, mode)

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from rtt.bot.corpus import GuideCorpus, Section
from rtt.bot.wikitext import clean_wikitext

_TOKEN_RE = re.compile(
    r"[0-9]+(?:\.[0-9]+)+(?:/[0-9]+)?|[a-z0-9]+(?:-[a-z0-9]+)+|[0-9]+/[0-9]+|[a-z0-9]+"
)
_COMPOUND_SPLIT_RE = re.compile(r"[-./]")
_K1 = 1.5
_B = 0.75
_LEAF_HEADING_WEIGHT = 3
_IRREGULAR_PLURALS = {
    "bases": "basis",
    "matrices": "matrix",
    "indices": "index",
    "vertices": "vertex",
    "axes": "axis",
    "analyses": "analysis",
}
_BRIDGE_PATH = Path(__file__).with_name("search_bridge.txt")


def stem(token: str) -> str:
    if token in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[token]
    if not token.isalpha() or len(token) <= 3:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(("sses", "ches", "shes", "xes", "zes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith(("ss", "us", "is", "ous")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text.lower()):
        parts = _COMPOUND_SPLIT_RE.split(token)
        if len(parts) == 1:
            tokens.append(stem(token))
            continue
        stemmed = [stem(part) for part in parts if part]
        tokens.append(stem(token) if "/" in token or "." in token else "-".join(stemmed))
        tokens.extend(stemmed)
    return tokens


def _bridge_rules() -> list[tuple[re.Pattern, str]]:
    rules = []
    for line in _BRIDGE_PATH.read_text(encoding="utf-8").splitlines():
        phrase, _, replacement = line.partition("->")
        phrase, replacement = phrase.strip(), replacement.strip()
        flags = 0 if phrase.isupper() else re.IGNORECASE
        rules.append((re.compile(rf"\b{re.escape(phrase)}\b", flags), replacement))
    return rules


_BRIDGE_RULES = _bridge_rules()


def bridge_query(query: str) -> str:
    additions = [replacement for pattern, replacement in _BRIDGE_RULES if pattern.search(query)]
    return " ".join([query, *additions])


@dataclass(frozen=True)
class SearchHit:
    section: Section
    score: float


def _field_tokens(section: Section) -> list[str]:
    ancestors, leaf = section.heading_path[:-1], section.heading_path[-1:]
    tokens = tokenize(section.document) if not section.heading_path else []
    tokens += tokenize(" ".join(ancestors))
    tokens += tokenize(" ".join(leaf)) * _LEAF_HEADING_WEIGHT
    return tokens + tokenize(clean_wikitext(section.text))


class SearchIndex:
    def __init__(self, corpus: GuideCorpus) -> None:
        self._sections = corpus.sections
        self._term_counts = [Counter(_field_tokens(s)) for s in self._sections]
        self._lengths = [sum(counts.values()) for counts in self._term_counts]
        self._average_length = max(1.0, sum(self._lengths) / max(1, len(self._lengths)))
        self._document_frequency = Counter(term for counts in self._term_counts for term in counts)

    def _idf(self, term: str) -> float:
        n = len(self._sections)
        df = self._document_frequency.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _score(self, index: int, terms: set[str]) -> float:
        counts = self._term_counts[index]
        length_factor = 1 - _B + _B * self._lengths[index] / self._average_length
        score = 0.0
        for term in terms:
            tf = counts.get(term, 0)
            if tf:
                score += self._idf(term) * tf * (_K1 + 1) / (tf + _K1 * length_factor)
        return score

    def search(self, query: str, limit: int = 8) -> list[SearchHit]:
        terms = set(tokenize(bridge_query(query)))
        scored = ((self._score(i, terms), i) for i in range(len(self._sections)))
        ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
        return [SearchHit(self._sections[i], score) for score, i in ranked[:limit]]

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from rtt.bot.corpus import GuideCorpus, Section

_TOKEN_RE = re.compile(r"[0-9]+/[0-9]+|[a-z0-9]+")
_RATIO_RE = re.compile(r"^[0-9]+/[0-9]+$")
_K1 = 1.5
_B = 0.75
_SUFFIXES = (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", ""))


def stem(token: str) -> str:
    if len(token) < 5 or not token.isalpha() or token.endswith("ss"):
        return token
    for suffix, replacement in _SUFFIXES:
        if token.endswith(suffix):
            return token[: -len(suffix)] + replacement
    return token


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text.lower()):
        if _RATIO_RE.match(token):
            tokens.append(token)
            tokens.extend(token.split("/"))
        else:
            tokens.append(stem(token))
    return tokens


@dataclass(frozen=True)
class SearchHit:
    section: Section
    score: float


def _indexed_text(section: Section) -> str:
    return " ".join((section.document, *section.heading_path, section.text))


class SearchIndex:
    def __init__(self, corpus: GuideCorpus) -> None:
        self._sections = corpus.sections
        self._term_counts = [Counter(tokenize(_indexed_text(s))) for s in self._sections]
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
        terms = set(tokenize(query))
        scored = ((self._score(i, terms), i) for i in range(len(self._sections)))
        ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
        return [SearchHit(self._sections[i], score) for score, i in ranked[:limit]]

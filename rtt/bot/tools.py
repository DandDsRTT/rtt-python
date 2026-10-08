from __future__ import annotations

import re

from rtt.bot.corpus import GuideCorpus
from rtt.bot.search import SearchIndex, bridge_query, tokenize
from rtt.bot.wikitext import clean_wikitext

_WHITESPACE_RE = re.compile(r"\s+")
_SNIPPET_CHARS = 240
_SNIPPET_LEAD = 60
_SECTION_CHARS = 40_000
_LIMIT_RANGE = (1, 20)


class ToolError(Exception):
    pass


def _first_match(flat: str, terms: set[str]) -> int:
    lowered = flat.lower()
    positions = [
        m.start() for term in terms for m in [re.search(rf"\b{re.escape(term)}", lowered)] if m
    ]
    return min(positions, default=0)


def _snippet(text: str, terms: set[str]) -> str:
    flat = _WHITESPACE_RE.sub(" ", clean_wikitext(text)).strip()
    start = max(0, _first_match(flat, terms) - _SNIPPET_LEAD)
    window = flat[start : start + _SNIPPET_CHARS]
    return ("…" if start else "") + window + ("…" if start + _SNIPPET_CHARS < len(flat) else "")


def search_guide(index: SearchIndex, query: str, limit: int) -> str:
    hits = index.search(query, limit=min(max(limit, _LIMIT_RANGE[0]), _LIMIT_RANGE[1]))
    if not hits:
        return "No sections match that query."
    terms = set(tokenize(bridge_query(query)))
    return "\n".join(
        f"{h.section.identifier} ({len(h.section.text)} chars) — {_snippet(h.section.text, terms)}"
        for h in hits
    )


def _resolve(corpus: GuideCorpus, section_id: str):
    candidates = corpus.matching_sections(section_id)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        listed = "; ".join(s.identifier for s in candidates[:12])
        raise ToolError(f"{section_id!r} names more than one section: {listed}")
    raise ToolError(
        f"No section is identified by {section_id!r}; call guide_contents to list "
        "the exact identifiers of a document's sections."
    )


def read_guide_section(corpus: GuideCorpus, section_id: str) -> str:
    section = _resolve(corpus, section_id)
    text = section.text
    if len(text) > _SECTION_CHARS:
        text = (
            text[:_SECTION_CHARS]
            + f"\n… section truncated at {_SECTION_CHARS} characters; the rest is not shown."
        )
    return f"# {section.identifier}\n\n{text}"


def guide_contents(corpus: GuideCorpus, document: str = "") -> str:
    if not document:
        return "\n".join(corpus.document_titles())
    identifiers = corpus.contents(document)
    if not identifiers:
        raise ToolError(
            f"No document is titled {document!r}; call guide_contents with an empty "
            "document to list the titles."
        )
    return "\n".join(identifiers)

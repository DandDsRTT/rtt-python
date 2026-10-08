from __future__ import annotations

import re

from rtt.bot.corpus import GuideCorpus
from rtt.bot.search import SearchIndex

_WHITESPACE_RE = re.compile(r"\s+")
_SNIPPET_CHARS = 240


class ToolError(Exception):
    pass


def _snippet(text: str) -> str:
    flat = _WHITESPACE_RE.sub(" ", text).strip()
    return flat if len(flat) <= _SNIPPET_CHARS else flat[:_SNIPPET_CHARS] + "…"


def search_guide(index: SearchIndex, query: str, limit: int = 8) -> str:
    hits = index.search(query, limit=limit)
    if not hits:
        return "No sections match that query."
    return "\n".join(f"{h.section.identifier} — {_snippet(h.section.text)}" for h in hits)


def read_guide_section(corpus: GuideCorpus, section_id: str) -> str:
    try:
        section = corpus.section(section_id)
    except KeyError:
        raise ToolError(
            f"No section is identified by {section_id!r}; call guide_contents to list "
            "the exact identifiers of a document's sections."
        ) from None
    return f"# {section.identifier}\n\n{section.text}"


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

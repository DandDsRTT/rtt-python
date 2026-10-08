from __future__ import annotations

import re

_DROPPED_LINKS_RE = re.compile(r"\[\[(?:Category|File):.*?\]\]", re.S)
_REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)
_MATH_RE = re.compile(r"<math>(.*?)</math>", re.S)
_LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+")
_NESTED_BRACES_RE = re.compile(r"\{\{+|\}\}+")
_MAP_TEMPLATE_RE = re.compile(r"\{\{\s*(?:map|bra)\s*\|\s*([^{}|]*?)\s*\}\}")
_VECTOR_TEMPLATE_RE = re.compile(r"\{\{\s*(?:vector|ket)\s*\|\s*([^{}|]*?)\s*\}\}")
_OTHER_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_LINK_RE = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_QUOTES_RE = re.compile(r"'{2,3}")
_TABLE_LINE_RE = re.compile(r"^\s*(?:\{\||\|\}|\|-).*$", re.M)
_CELL_MARK_RE = re.compile(r"^\s*[!|]\s*|\s*(?:\|\||!!)\s*", re.M)


def _template_text(match: re.Match) -> str:
    parts = match.group(0)[2:-2].split("|")
    return parts[-1] if len(parts) > 1 else ""


def _plain_math(match: re.Match) -> str:
    inner = _LATEX_COMMAND_RE.sub("", match.group(1))
    return " " + _NESTED_BRACES_RE.sub(lambda m: m.group(0)[0], inner) + " "


def _render_inline(text: str) -> str:
    text = _DROPPED_LINKS_RE.sub("", text)
    text = _REF_RE.sub(" ", text)
    text = _MAP_TEMPLATE_RE.sub(r"⟨\1]", text)
    text = _VECTOR_TEMPLATE_RE.sub(r"[\1⟩", text)
    text = _OTHER_TEMPLATE_RE.sub(_template_text, text)
    return _LINK_RE.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), text)


def _strip_structure(text: str) -> str:
    text = _MATH_RE.sub(_plain_math, text)
    text = _LATEX_COMMAND_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return _QUOTES_RE.sub("", text)


def _strip_tables(text: str) -> str:
    text = _TABLE_LINE_RE.sub("", text)
    return _CELL_MARK_RE.sub(" ", text)


def clean_wikitext(text: str) -> str:
    return _strip_tables(_strip_structure(_render_inline(text))).strip()

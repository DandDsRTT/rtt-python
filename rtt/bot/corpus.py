from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rtt.bot.wikitext import clean_wikitext

_HEADING_RE = re.compile(r"^(={1,6})\s*(.+?)\s*\1\s*$")


@dataclass(frozen=True)
class GuideDocument:
    title: str
    text: str


@dataclass(frozen=True)
class Section:
    document: str
    heading_path: tuple[str, ...]
    identifier: str
    text: str


def _is_visible_file(path: Path, guide_root: Path) -> bool:
    relative = path.relative_to(guide_root)
    return path.is_file() and not any(part.startswith(".") for part in relative.parts)


def load_guide_documents(guide_root: Path) -> list[GuideDocument]:
    files = [p for p in guide_root.rglob("*") if _is_visible_file(p, guide_root)]
    if not files:
        raise FileNotFoundError(f"no guide documents under {guide_root}")
    documents = [GuideDocument(p.name, p.read_text(encoding="utf-8")) for p in files]
    return sorted(documents, key=lambda d: d.title)


def _heading_text(raw: str) -> str:
    return " ".join(clean_wikitext(raw).split())


def _section_bodies(document: GuideDocument) -> list[tuple[tuple[str, ...], str]]:
    bodies: list[tuple[tuple[str, ...], str]] = []
    stack: list[tuple[int, str]] = []
    lines: list[str] = []
    for line in document.text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading is None:
            lines.append(line)
            continue
        bodies.append((tuple(text for _, text in stack), "\n".join(lines).strip()))
        lines = []
        level = len(heading.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, _heading_text(heading.group(2))))
    bodies.append((tuple(text for _, text in stack), "\n".join(lines).strip()))
    return bodies


def _unique_identifiers(document: str, paths: list[tuple[str, ...]]) -> list[str]:
    seen: dict[str, int] = {}
    identifiers = []
    for path in paths:
        base = " > ".join((document, *path))
        seen[base] = seen.get(base, 0) + 1
        identifiers.append(base if seen[base] == 1 else f"{base} ({seen[base]})")
    return identifiers


def split_into_sections(document: GuideDocument) -> list[Section]:
    bodies = _section_bodies(document)
    identifiers = _unique_identifiers(document.title, [path for path, _ in bodies])
    return [
        Section(document.title, path, identifier, text)
        for (path, text), identifier in zip(bodies, identifiers, strict=True)
    ]


class GuideCorpus:
    def __init__(self, documents: list[GuideDocument]) -> None:
        self._documents = documents
        self.sections = [s for d in documents for s in split_into_sections(d)]
        self._by_identifier = {s.identifier: s for s in self.sections}

    @classmethod
    def load(cls, guide_root: Path) -> GuideCorpus:
        return cls(load_guide_documents(guide_root))

    def section(self, identifier: str) -> Section:
        return self._by_identifier[identifier]

    def matching_sections(self, name: str) -> list[Section]:
        if name in self._by_identifier:
            return [self._by_identifier[name]]
        return [
            s
            for s in self.sections
            if s.identifier.endswith(" > " + name) or (not s.heading_path and s.document == name)
        ]

    def document_titles(self) -> list[str]:
        return [d.title for d in self._documents]

    def contents(self, document_title: str) -> list[str]:
        return [s.identifier for s in self.sections if s.document == document_title]

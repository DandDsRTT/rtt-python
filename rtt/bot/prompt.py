from __future__ import annotations

from pathlib import Path

from rtt.bot.corpus import GuideCorpus
from rtt.bot.library_reference import library_reference

PROMPTS_DIR = Path(__file__).with_name("prompts")


def _asset(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def _document_list(corpus: GuideCorpus) -> str:
    titles = "\n".join(f"- {title}" for title in corpus.document_titles())
    return f"# Knowledge base documents\n\n{titles}"


def system_prompt(corpus: GuideCorpus) -> str:
    parts = [
        _asset("persona.md"),
        _document_list(corpus),
        _asset("guide_map.md"),
        "# rtt.library reference\n\n" + library_reference().strip(),
        _asset("library_examples.md"),
    ]
    return "\n\n".join(parts) + "\n"

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from rtt.bot.compute import run_rtt_python
from rtt.bot.corpus import GuideCorpus
from rtt.bot.search import SearchIndex
from rtt.bot.tools import ToolError, guide_contents, read_guide_section, search_guide


def _schema(properties: dict, required: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _definition(name: str, description: str, schema: dict) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "eager_input_streaming": True,
        "input_schema": schema,
    }


TOOL_DEFINITIONS = (
    _definition(
        "search_guide",
        "Full-text search over every section of Dave Keenan & Douglas Blumeyer's guide to RTT "
        "and the related Xenharmonic Wiki articles. Returns the best-matching section "
        "identifiers with a short snippet each, best first. Search with the guide's own "
        "vocabulary (e.g. 'held-interval', 'defactoring', 'minimax-ES', '81/80'); run several "
        "searches with different wordings when the first one misses.",
        _schema(
            {
                "query": {"type": "string", "description": "Search terms."},
                "limit": {
                    "type": "integer",
                    "description": "How many sections to return, 1-20; 8 is a sensible choice.",
                },
            },
            ("query", "limit"),
        ),
    ),
    _definition(
        "read_guide_section",
        "Return the full wikitext of one guide section, by the exact identifier that "
        "search_guide or guide_contents reported (e.g. '3. Tuning fundamentals > Power means > "
        "Formula'). Read the relevant sections before answering anything about definitions, "
        "formulas, conventions, or history.",
        _schema(
            {"section_id": {"type": "string", "description": "A section identifier."}},
            ("section_id",),
        ),
    ),
    _definition(
        "guide_contents",
        "With an empty document title, list the titles of every document in the knowledge "
        "base. With a title, list that document's section identifiers in reading order, so "
        "you can browse a chapter and open sections by name.",
        _schema(
            {
                "document": {
                    "type": "string",
                    "description": "A document title exactly as listed, or an empty string.",
                }
            },
            ("document",),
        ),
    ),
    _definition(
        "run_rtt_python",
        "Run a Python snippet with the rtt.library package importable (the project's RTT math "
        "library: parsing extended bra-ket strings, canonical forms, comma bases, mappings, "
        "equal-temperament maps, tuning optimization, damage, complexity, exterior algebra). "
        "Use it for every computation instead of doing arithmetic by hand, and print what "
        "you need to see. Returns stdout; a failing snippet returns its traceback.",
        _schema(
            {"code": {"type": "string", "description": "A complete Python program."}},
            ("code",),
        ),
    ),
)


@dataclass(frozen=True)
class ToolOutcome:
    text: str
    is_error: bool = False


class ToolBox:
    def __init__(self, corpus: GuideCorpus, index: SearchIndex, repo_root: Path) -> None:
        self._handlers: dict[str, Callable[..., str]] = {
            "search_guide": partial(search_guide, index),
            "read_guide_section": partial(read_guide_section, corpus),
            "guide_contents": partial(guide_contents, corpus),
            "run_rtt_python": lambda code: run_rtt_python(code, repo_root),
        }

    def definitions(self) -> list[dict]:
        return [dict(definition) for definition in TOOL_DEFINITIONS]

    def run(self, name: str, arguments: object) -> ToolOutcome:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolOutcome(f"There is no tool named {name!r}.", is_error=True)
        problem = _argument_problem(_schema_of(name), arguments)
        if problem:
            received = json.dumps(arguments, ensure_ascii=False, default=str)
            return ToolOutcome(
                json.dumps({"INVALID_JSON": received, "problem": problem}, ensure_ascii=False),
                is_error=True,
            )
        try:
            return ToolOutcome(handler(**arguments))
        except ToolError as error:
            return ToolOutcome(str(error), is_error=True)
        except Exception as error:
            return ToolOutcome(f"{type(error).__name__}: {error}", is_error=True)


def _schema_of(name: str) -> dict:
    return next(d["input_schema"] for d in TOOL_DEFINITIONS if d["name"] == name)


_JSON_TYPES = {"string": str, "integer": int}


def _argument_problem(schema: dict, arguments: object) -> str:
    if not isinstance(arguments, dict):
        return "Tool arguments must be a JSON object."
    properties = schema["properties"]
    for key in schema["required"]:
        if key not in arguments:
            return f"Missing required argument {key!r}."
    for key, value in arguments.items():
        if key not in properties:
            return f"Unexpected argument {key!r}."
        expected = _JSON_TYPES[properties[key]["type"]]
        if not isinstance(value, expected) or isinstance(value, bool):
            return f"Argument {key!r} must be a {properties[key]['type']}."
    return ""

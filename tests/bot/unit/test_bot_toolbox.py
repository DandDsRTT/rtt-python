import json
from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.search import SearchIndex
from rtt.bot.toolbox import TOOL_NAMES, ToolBox, ToolOutcome

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = [
    GuideDocument("A", Path("A"), "== Comma ==\nMeantone tempers out 81/80, the syntonic comma.\n"),
]


def _toolbox():
    corpus = GuideCorpus(DOCS)
    return ToolBox(corpus, SearchIndex(corpus), REPO_ROOT)


class TestToolDefinitions:
    def test_every_tool_is_strict_eager_and_closed_to_extra_properties(self):
        definitions = _toolbox().definitions()
        assert [d["name"] for d in definitions] == list(TOOL_NAMES)
        for definition in definitions:
            schema = definition["input_schema"]
            assert definition["strict"] is True
            assert definition["eager_input_streaming"] is True
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) <= set(schema["properties"])
            assert definition["description"]

    def test_tool_names_cover_search_read_contents_and_compute(self):
        assert TOOL_NAMES == ("search_guide", "read_guide_section", "guide_contents", "run_rtt_python")


class TestToolBoxRun:
    def test_dispatches_to_the_named_tool_and_returns_its_text(self):
        outcome = _toolbox().run("search_guide", {"query": "syntonic comma", "limit": 3})
        assert outcome == ToolOutcome("A > Comma — Meantone tempers out 81/80, the syntonic comma.")

    def test_a_tool_error_becomes_an_error_outcome_instead_of_raising(self):
        outcome = _toolbox().run("read_guide_section", {"section_id": "A > Nowhere"})
        assert outcome.is_error and "guide_contents" in outcome.text

    def test_arguments_of_the_wrong_shape_are_rejected_before_the_tool_runs(self):
        outcome = _toolbox().run("search_guide", {"query": 5, "limit": 3})
        assert outcome.is_error
        assert json.loads(outcome.text) == {
            "INVALID_JSON": '{"query": 5, "limit": 3}',
            "problem": "Argument 'query' must be a string.",
        }
        missing = _toolbox().run("search_guide", {"query": "x"})
        assert missing.is_error and "limit" in missing.text
        extra = _toolbox().run("guide_contents", {"document": "", "verbose": True})
        assert extra.is_error and "verbose" in extra.text

    def test_an_unknown_tool_name_is_an_error_outcome(self):
        outcome = _toolbox().run("teleport", {})
        assert outcome.is_error and "teleport" in outcome.text

    def test_compute_runs_through_the_toolbox(self):
        assert _toolbox().run("run_rtt_python", {"code": "print(6 * 7)"}) == ToolOutcome("42")

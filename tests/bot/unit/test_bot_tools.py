from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.search import SearchIndex
import pytest

from rtt.bot.tools import ToolError, guide_contents, read_guide_section, search_guide

DOCS = [
    GuideDocument("A", Path("A"), "== Comma ==\nMeantone tempers out 81/80, the syntonic comma.\n== Damage ==\nDamage is weighted error.\n"),
    GuideDocument("B", Path("B"), "== Power means ==\nThe power mean formula generalizes RMS and max.\n"),
]


CORPUS = GuideCorpus(DOCS)
INDEX = SearchIndex(CORPUS)


class TestGuideTools:
    def test_search_guide_lists_identifiers_with_snippets_best_first(self):
        text = search_guide(INDEX, "power mean formula", limit=2)
        lines = text.splitlines()
        assert lines[0].startswith("B > Power means")
        assert "The power mean formula" in lines[0]
        assert len(lines) == 1

    def test_search_guide_reports_when_nothing_matches(self):
        assert search_guide(INDEX, "zebra") == "No sections match that query."

    def test_read_guide_section_returns_the_full_text_under_its_identifier(self):
        text = read_guide_section(CORPUS, "A > Comma")
        assert text == "# A > Comma\n\nMeantone tempers out 81/80, the syntonic comma."

    def test_read_guide_section_rejects_unknown_identifiers_with_a_hint(self):
        with pytest.raises(ToolError, match="guide_contents"):
            read_guide_section(CORPUS, "A > Nowhere")

    def test_guide_contents_lists_documents_or_one_documents_sections(self):
        assert guide_contents(CORPUS, "") == "A\nB"
        assert guide_contents(CORPUS, "A") == "A\nA > Comma\nA > Damage"

    def test_guide_contents_rejects_unknown_documents(self):
        with pytest.raises(ToolError, match="No document"):
            guide_contents(CORPUS, "Z")

    def test_search_limit_is_clamped_to_the_advertised_range(self):
        assert search_guide(INDEX, "comma damage formula", limit=0).count("\n") == 0
        assert len(search_guide(INDEX, "comma damage formula", limit=99).splitlines()) <= 20

    def test_read_guide_section_caps_oversized_sections_and_says_so(self):
        corpus = GuideCorpus([GuideDocument("Big", Path("Big"), "x" * 50_000)])
        text = read_guide_section(corpus, "Big")
        assert len(text) < 50_000
        assert text.endswith("… section truncated at 40000 characters; the rest is not shown.")

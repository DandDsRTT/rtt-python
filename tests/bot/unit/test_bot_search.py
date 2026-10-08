from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.search import SearchIndex, tokenize


class TestTokenize:
    def test_lowercases_splits_on_punctuation_and_keeps_ratios_whole_and_split(self):
        assert tokenize("The Meantone comma, 81/80, is tempered out: <math>\\frac{81}{80}</math>") == [
            "the", "meantone", "comma", "81/80", "81", "80", "is", "temper", "out",
            "math", "frac", "81", "80", "math",
        ]

    def test_stems_plurals_and_verb_endings_so_query_forms_match_prose_forms(self):
        assert tokenize("defactoring defactored mappings complexities commas means class") == [
            "defactor", "defactor", "mapping", "complexity", "comma", "mean", "class",
        ]


DOCS = [
    GuideDocument("A", Path("A"), "== Comma ==\nMeantone tempers out 81/80, the syntonic comma.\n== Damage ==\nDamage is weighted error.\n"),
    GuideDocument("B", Path("B"), "== Power means ==\nThe power mean formula generalizes RMS and max.\n"),
]


class TestSearchIndex:
    def test_ranks_the_section_sharing_the_most_query_terms_first(self):
        index = SearchIndex(GuideCorpus(DOCS))
        hits = index.search("power mean formula", limit=2)
        assert hits[0].section.identifier == "B > Power means"
        assert hits[0].score > 0

    def test_ratio_query_finds_the_section_that_mentions_it(self):
        index = SearchIndex(GuideCorpus(DOCS))
        assert index.search("81/80", limit=1)[0].section.identifier == "A > Comma"

    def test_no_matching_terms_yields_no_hits(self):
        assert SearchIndex(GuideCorpus(DOCS)).search("zebra", limit=5) == []


class TestSearchIndexOnTheRealGuide:
    def test_defactoring_query_surfaces_a_defactoring_section(self):
        index = SearchIndex(GuideCorpus.load(Path(__file__).resolve().parents[3] / "guide"))
        top = [h.section.identifier for h in index.search("how do I defactor an enfactored mapping", limit=5)]
        assert any(identifier.startswith(("Defactoring algorithms", "Pathology of enfactoring")) for identifier in top), top

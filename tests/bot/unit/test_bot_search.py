from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.search import SearchIndex, bridge_query, clean_wikitext, tokenize


class TestTokenize:
    def test_lowercases_splits_on_punctuation_and_keeps_ratios_whole_and_split(self):
        assert tokenize("The Meantone comma, 81/80, is tempered out: <math>\\frac{81}{80}</math>") == [
            "the", "meantone", "comma", "81/80", "81", "80", "is", "tempered", "out",
            "math", "frac", "81", "80", "math",
        ]

    def test_folds_plurals_only_so_the_guides_map_mapping_distinction_survives(self):
        assert tokenize("mappings mapping maps map complexities commas means class bases matrices") == [
            "mapping", "mapping", "map", "map", "complexity", "comma", "mean", "class", "basis", "matrix",
        ]

    def test_hyphenated_names_and_dotted_bases_are_whole_tokens_as_well_as_parts(self):
        assert tokenize("minimax-ES on 2.3.7") == ["minimax-es", "minimax", "es", "on", "2.3.7", "2", "3", "7"]
        assert tokenize("held-intervals 2.9.7/5") == ["held-interval", "held", "interval", "2.9.7/5", "2", "9", "7", "5"]


DOCS = [
    GuideDocument("A", "== Comma ==\nMeantone tempers out 81/80, the syntonic comma.\n== Damage ==\nDamage is weighted error.\n"),
    GuideDocument("B", "== Power means ==\nThe power mean formula generalizes RMS and max.\n"),
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


class TestCleanWikitext:
    def test_strips_markup_renders_ebk_templates_and_keeps_math_text(self):
        raw = (
            "The {{map|12 19 28}} maps {{vector|-4 4 -1}}.<ref>cite</ref> See [[Projection|projections]] and [[Temperament]].\n"
            "[[File:pic.png|thumb]] [[Category:RTT]] <math>\\frac{81}{80}</math> '''bold''' ''it''\n"
            "{| class=\"wikitable\"\n! head\n|-\n| cell\n|}\n"
        )
        assert clean_wikitext(raw).split() == [
            "The", "⟨12", "19", "28]", "maps", "[-4", "4", "-1⟩.", "See", "projections", "and", "Temperament.",
            "{81}{80}", "bold", "it", "head", "cell",
        ]


class TestQueryBridge:
    def test_community_wording_is_expanded_into_the_guides_wording(self):
        expanded = bridge_query("What is TE tuning, and which commas are tempered out?")
        assert "minimax-ES" in expanded and "vanish" in expanded

    def test_abbreviations_match_only_in_capitals(self):
        assert "minimax-S" not in bridge_query("the top of the page")
        assert "minimax-S" in bridge_query("the TOP tuning")


DOC_WITH_LEDE = GuideDocument(
    "Temperament addition",
    "Temperament addition is the operation of adding two temperaments.\n== History ==\nPeople added things.\n== Examples ==\nMeantone plus porcupine.\n== Rank ==\nThe rank matters.\n",
)


class TestFieldWeighting:
    def test_a_what_is_question_about_a_document_reaches_its_lede_first(self):
        index = SearchIndex(GuideCorpus([DOC_WITH_LEDE, DOCS[0]]))
        assert index.search("what is temperament addition", limit=3)[0].section.identifier == "Temperament addition"

    def test_a_sections_own_heading_outweighs_a_passing_mention(self):
        index = SearchIndex(GuideCorpus([DOC_WITH_LEDE]))
        assert index.search("rank", limit=2)[0].section.identifier == "Temperament addition > Rank"

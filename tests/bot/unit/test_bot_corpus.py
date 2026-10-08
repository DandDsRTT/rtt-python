from pathlib import Path

import pytest

from rtt.bot.corpus import GuideCorpus, GuideDocument, load_guide_documents, split_into_sections

REPO_GUIDE = Path(__file__).resolve().parents[3] / "guide"


class TestLoadGuideDocuments:
    def test_loads_every_file_under_both_guide_folders_sorted_by_title(self):
        documents = load_guide_documents(REPO_GUIDE)
        assert len(documents) == 31
        assert [d.title for d in documents] == sorted(d.title for d in documents)
        assert all(isinstance(d, GuideDocument) for d in documents)


SAMPLE = """Intro paragraph.

== Tuning ==
Tuning body.

=== Steps ===
Steps body.

== Examples ==
First examples body.

== Examples ==
Second examples body.
"""


class TestSplitIntoSections:
    def test_preamble_and_each_heading_become_sections_with_heading_paths(self):
        sections = split_into_sections(GuideDocument("Doc", Path("Doc"), SAMPLE))
        assert [s.heading_path for s in sections] == [
            (),
            ("Tuning",),
            ("Tuning", "Steps"),
            ("Examples",),
            ("Examples",),
        ]
        assert sections[0].text == "Intro paragraph."
        assert sections[2].text == "Steps body."

    def test_identifiers_join_document_and_headings_and_disambiguate_repeats(self):
        sections = split_into_sections(GuideDocument("Doc", Path("Doc"), SAMPLE))
        assert [s.identifier for s in sections] == [
            "Doc",
            "Doc > Tuning",
            "Doc > Tuning > Steps",
            "Doc > Examples",
            "Doc > Examples (2)",
        ]


class TestGuideCorpus:
    def test_real_guide_sections_have_unique_identifiers_and_known_section_is_findable(self):
        corpus = GuideCorpus.load(REPO_GUIDE)
        identifiers = [s.identifier for s in corpus.sections]
        assert len(identifiers) == len(set(identifiers))
        formula = corpus.section("3. Tuning fundamentals > Power means > Formula")
        assert formula.document == "3. Tuning fundamentals"
        assert "<math>" in formula.text

    def test_unknown_identifier_raises_key_error(self):
        corpus = GuideCorpus([GuideDocument("Doc", Path("Doc"), SAMPLE)])
        with pytest.raises(KeyError):
            corpus.section("Doc > Nowhere")

    def test_contents_lists_a_documents_section_identifiers_in_order(self):
        corpus = GuideCorpus([GuideDocument("Doc", Path("Doc"), SAMPLE)])
        assert corpus.contents("Doc") == [
            "Doc",
            "Doc > Tuning",
            "Doc > Tuning > Steps",
            "Doc > Examples",
            "Doc > Examples (2)",
        ]
        assert corpus.document_titles() == ["Doc"]

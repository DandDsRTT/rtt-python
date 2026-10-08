from pathlib import Path

import pytest

from rtt.bot.corpus import GuideCorpus, GuideDocument, load_guide_documents, split_into_sections

REPO_GUIDE = Path(__file__).resolve().parents[3] / "guide"


class TestLoadGuideDocuments:
    def test_loads_every_file_under_both_guide_folders_sorted_by_title(self):
        documents = load_guide_documents(REPO_GUIDE)
        on_disk = sorted(p.name for p in REPO_GUIDE.rglob("*") if p.is_file() and not p.name.startswith("."))
        assert [d.title for d in documents] == on_disk
        assert all(isinstance(d, GuideDocument) for d in documents)

    def test_skips_hidden_files_such_as_finder_metadata(self, tmp_path):
        (tmp_path / "Real article").write_text("Body.", encoding="utf-8")
        (tmp_path / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1\x80")
        assert [d.title for d in load_guide_documents(tmp_path)] == ["Real article"]

    def test_an_empty_or_missing_guide_root_is_an_error_not_an_empty_bot(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="no guide documents"):
            load_guide_documents(tmp_path / "nowhere")
        with pytest.raises(FileNotFoundError, match="no guide documents"):
            load_guide_documents(tmp_path)


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
        sections = split_into_sections(GuideDocument("Doc", SAMPLE))
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
        sections = split_into_sections(GuideDocument("Doc", SAMPLE))
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
        formula = corpus.section("3. Tuning fundamentals > Optimization > Power means > Formula")
        assert formula.document == "3. Tuning fundamentals"
        assert "<math>" in formula.text

    def test_unknown_identifier_raises_key_error(self):
        corpus = GuideCorpus([GuideDocument("Doc", SAMPLE)])
        with pytest.raises(KeyError):
            corpus.section("Doc > Nowhere")

    def test_contents_lists_a_documents_section_identifiers_in_order(self):
        corpus = GuideCorpus([GuideDocument("Doc", SAMPLE)])
        assert corpus.contents("Doc") == [
            "Doc",
            "Doc > Tuning",
            "Doc > Tuning > Steps",
            "Doc > Examples",
            "Doc > Examples (2)",
        ]
        assert corpus.document_titles() == ["Doc"]


class TestHeadingLevels:
    def test_single_equals_headings_open_the_top_level_and_nest_the_double_ones(self):
        text = "Lede.\n= Setup =\nSetup body.\n== Step one ==\nOne.\n= Method =\nMethod body.\n== Step two ==\nTwo.\n"
        sections = split_into_sections(GuideDocument("Doc", text))
        assert [s.heading_path for s in sections] == [(), ("Setup",), ("Setup", "Step one"), ("Method",), ("Method", "Step two")]
        assert [s.identifier for s in sections][-1] == "Doc > Method > Step two"

    def test_a_deeper_heading_after_a_shallower_one_pops_back_to_its_parent(self):
        text = "== A ==\n=== A1 ===\n==== A1a ====\n== B ==\n=== B1 ===\n"
        assert [s.heading_path for s in split_into_sections(GuideDocument("D", text))][1:] == [
            ("A",), ("A", "A1"), ("A", "A1", "A1a"), ("B",), ("B", "B1"),
        ]

    def test_heading_identifiers_carry_plain_text_not_wiki_markup(self):
        text = "== <math>g_{\\text{min}}>1</math> ==\nx\n== <span style=\"color: red;\">Red</span> ==\ny\n"
        assert [s.identifier for s in split_into_sections(GuideDocument("D", text))][1:] == [
            "D > g_{min}>1",
            "D > Red",
        ]

    def test_real_guide_level_one_headings_become_sections(self):
        corpus = GuideCorpus.load(REPO_GUIDE)
        assert corpus.section("6. Tuning computation > General method").text
        assert corpus.section("3. Tuning fundamentals > Initial definitions > Tuning").text

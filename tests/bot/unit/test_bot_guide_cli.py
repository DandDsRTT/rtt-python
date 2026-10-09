import io

import pytest

from rtt.bot.guide import main


@pytest.fixture(autouse=True)
def _guide_only(monkeypatch, tmp_path):
    monkeypatch.setattr("rtt.bot.guide.CORRESPONDENCE_ROOT", tmp_path / "no-correspondence")


def _run(*argv):
    out = io.StringIO()
    status = main(list(argv), out)
    return status, out.getvalue()


class TestGuideCommands:
    def test_search_prints_ranked_section_lines_best_first(self):
        status, text = _run("search", "destretching vs holding", "-n", "3")
        assert status == 0
        lines = text.rstrip("\n").splitlines()
        assert len(lines) == 3
        assert lines[0].startswith("3. Tuning fundamentals > Held-intervals > Destretching vs. holding (")

    def test_read_prints_a_section_and_an_unknown_identifier_exits_nonzero(self):
        status, text = _run("read", "6. Tuning computation > General method")
        assert status == 0 and text.startswith("# 6. Tuning computation > General method\n")
        status, text = _run("read", "Nowhere > Nothing")
        assert status == 1 and "guide_contents" in text

    def test_contents_lists_documents_or_one_documents_sections(self):
        status, text = _run("contents")
        assert status == 0 and "3. Tuning fundamentals\n" in text
        status, text = _run("contents", "Uniform map")
        assert status == 0 and text.splitlines()[0] == "Uniform map"
        assert all(line.startswith("Uniform map") for line in text.splitlines())

    def test_reference_prints_the_library_signatures(self):
        status, text = _run("reference")
        assert status == 0 and "parse_temperament_data(data: str | Temperament) -> Temperament" in text

from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument, load_correspondence_documents
from rtt.bot.prompt import system_prompt
from rtt.bot.search import SearchIndex
from rtt.bot.tools import guide_contents, search_guide

REPO_GUIDE = Path(__file__).resolve().parents[3] / "guide"
THREAD = (
    "Email thread: held-intervals\nParticipants: Dave Keenan, Douglas Blumeyer\n"
    "Messages: 2 (2021-03-01 to 2021-03-02)\nThread id: abc\n\n== 2021-03-01 Douglas Blumeyer ==\n"
    "what about constrained?\n\n== 2021-03-02 Dave Keenan ==\nI think held is better than constrained.\n"
)


def _correspondence(tmp_path):
    root = tmp_path / "correspondence"
    root.mkdir()
    (root / "2021-03-01 held-intervals").write_text(THREAD, encoding="utf-8")
    (root / ".DS_Store").write_bytes(b"\x00")
    return root


class TestCorrespondenceInTheCorpus:
    def test_threads_load_as_email_documents_with_one_section_per_message(self, tmp_path):
        documents = load_correspondence_documents(_correspondence(tmp_path))
        assert [d.title for d in documents] == ["Email: 2021-03-01 held-intervals"]
        corpus = GuideCorpus(documents)
        assert corpus.contents("Email: 2021-03-01 held-intervals") == [
            "Email: 2021-03-01 held-intervals",
            "Email: 2021-03-01 held-intervals > 2021-03-01 Douglas Blumeyer",
            "Email: 2021-03-01 held-intervals > 2021-03-02 Dave Keenan",
        ]

    def test_a_missing_correspondence_folder_is_simply_empty(self, tmp_path):
        assert load_correspondence_documents(tmp_path / "nowhere") == []
        assert load_correspondence_documents(None) == []

    def test_emails_are_searchable_but_listed_apart_from_the_guide(self, tmp_path):
        corpus = GuideCorpus.load(REPO_GUIDE, _correspondence(tmp_path))
        hit = search_guide(SearchIndex(corpus), "Dave thinks held is better than constrained", limit=1)
        assert hit.startswith("Email: 2021-03-01 held-intervals > 2021-03-02 Dave Keenan (")
        listing = guide_contents(corpus, "")
        assert "Email:" not in listing.replace("(1 email threads; list them with the document 'emails')", "")
        assert listing.endswith("(1 email threads; list them with the document 'emails')")
        assert guide_contents(corpus, "emails") == "Email: 2021-03-01 held-intervals"

    def test_system_prompt_counts_the_threads_instead_of_listing_them(self, tmp_path):
        prompt = system_prompt(GuideCorpus([GuideDocument("A", "Body.")] + load_correspondence_documents(_correspondence(tmp_path))))
        assert "- A\n" in prompt
        assert "Plus 1 email threads between Dave Keenan and Douglas Blumeyer" in prompt
        assert "- Email:" not in prompt

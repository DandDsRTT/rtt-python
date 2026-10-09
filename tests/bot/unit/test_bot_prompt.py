from pathlib import Path

from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.prompt import PROMPTS_DIR, system_prompt

DOCS = [
    GuideDocument("A", "== Comma ==\nMeantone tempers out 81/80.\n"),
    GuideDocument("Zed", "Body.\n"),
]


class TestSystemPrompt:
    def test_opens_with_the_persona_then_lists_documents_then_the_library_reference(self):
        prompt = system_prompt(GuideCorpus(DOCS))
        persona = (PROMPTS_DIR / "persona.md").read_text(encoding="utf-8").strip()
        assert prompt.startswith(persona)
        documents_at = prompt.index("# Knowledge base documents")
        reference_at = prompt.index("# rtt.library reference")
        assert documents_at < reference_at
        assert "\n- A\n- Zed\n" in prompt
        assert "parse_temperament_data(data: str | Temperament) -> Temperament" in prompt

    def test_every_prompt_asset_is_spliced_in_the_fixed_order(self):
        prompt = system_prompt(GuideCorpus(DOCS))
        positions = [prompt.index(f"# {name}") for name in ("Knowledge base documents", "Guide map", "rtt.library reference", "rtt.library examples")]
        assert positions == sorted(positions)

    def test_is_deterministic_across_calls_so_the_cached_prefix_holds(self):
        assert system_prompt(GuideCorpus(DOCS)) == system_prompt(GuideCorpus(DOCS))


class TestGuideMapAsset:
    def test_describes_every_document_of_the_real_guide_under_its_corpus_title(self):
        corpus = GuideCorpus.load(Path(__file__).resolve().parents[3] / "guide")
        guide_map = (PROMPTS_DIR / "guide_map.md").read_text(encoding="utf-8")
        headings = {line[3:] for line in guide_map.splitlines() if line.startswith("## ")}
        assert set(corpus.document_titles()) <= headings
        assert "## Historical names and their systematic names" in guide_map


class TestPersonaAsset:
    def test_interval_kind_terms_are_not_hyphenated(self):
        persona = (PROMPTS_DIR / "persona.md").read_text(encoding="utf-8")
        assert "held interval" in persona and "target interval" in persona
        assert "held-interval" not in persona and "target-interval" not in persona

"""The guide-chapter reveal slider — a viewing preference that progressively shows the Show
controls as a reader advances through D&D's guide (``settings.CHAPTER`` + the slider in app.py).
The slider gates only the PANEL's controls; the grid (the toggle values) is untouched."""

import re

import rtt.app.app as app
from rtt.app import marks, page_assets
from rtt.app import settings as show_settings
from rtt.app import tooltips


class TestWebChapters:
    def test_every_show_toggle_has_a_chapter(self):
        assert set(show_settings.CHAPTER) == set(show_settings.DEFAULTS), "CHAPTER must cover EXACTLY the Show toggles — a new toggle can't ship without a reveal # chapter (else the slider would never show or hide it), and a stale key can't linger"

    def test_terminology_defaults_to_dd_and_is_always_available(self):
        assert show_settings.defaults()["terminology"] == "dd"
        assert show_settings.reveal_chapter("terminology") == show_settings.CHAPTER_MIN

    def test_chapter_values_sit_within_the_slider_range(self):
        for key, ch in show_settings.CHAPTER.items():
            assert show_settings.CHAPTER_MIN <= ch <= show_settings.CHAPTER_STAR, (key, ch)

    def test_the_slider_range_and_default_position(self):
        assert show_settings.CHAPTER_DEFAULT == 4
        assert show_settings.CHAPTER_MIN == 2
        assert show_settings.CHAPTER_STAR > 9

    def test_every_revealed_chapter_has_a_readout_title(self):
        for ch in range(show_settings.CHAPTER_MIN, show_settings.CHAPTER_STAR + 1):
            assert show_settings.CHAPTER_TITLES[ch].strip()

    def test_reveal_chapter_never_precedes_an_ancestor(self):
        for key in show_settings.DEFAULTS:
            for anc in show_settings.ancestors_of(key):
                assert show_settings.reveal_chapter(key) >= show_settings.CHAPTER[anc], (key, anc)

    def test_revealed_grows_monotonically_and_ends_complete(self):
        seen: set = set()
        for ch in range(show_settings.CHAPTER_MIN, show_settings.CHAPTER_STAR + 1):
            now = show_settings.revealed(ch)
            assert seen <= now
            seen = now
        assert show_settings.revealed(show_settings.CHAPTER_STAR) == set(show_settings.DEFAULTS)

    def test_default_position_reveals_the_early_controls_and_hides_the_later_ones(self):
        shown = show_settings.revealed(show_settings.CHAPTER_DEFAULT)
        assert {"counts", "temperament_tiles", "tuning_tiles", "gridded_values", "presets",
                "math_expressions", "optimization", "tuning_ranges", "weighting", "interest",
                "interval_ratios", "interval_vectors"} <= shown
        assert not ({"units", "domain_units", "all_interval", "alt_complexity", "nonstandard_domain"} & shown)
        for key in ("projection", "generator_detempering", "identity_objects",
                    "form_controls", "form_colorization", "custom_weights"):
            assert show_settings.reveal_chapter(key) == show_settings.CHAPTER_STAR
            assert key not in shown

    def test_equivalences_reveals_with_symbols_at_chapter_two(self):
        assert show_settings.CHAPTER["equivalences"] == 2
        assert show_settings.reveal_chapter("equivalences") == 2

    def test_interest_reveals_with_the_tuning_story_not_at_the_mappings_chapter(self):
        assert show_settings.reveal_chapter("interest") == 3, "intervals of interest belong to the # tuning story (tuning_tiles/optimization reveal at 3), so the simplest chapter-2 mappings view omits them"
        assert "interest" not in show_settings.revealed(show_settings.CHAPTER_MIN), "the guided tour opens # at chapter 2 showing only the mapping and the comma — interest must not appear there"
        assert "interest" in show_settings.revealed(show_settings.CHAPTER_DEFAULT), "it is back by the # default-chapter home the tour ramps up to"

    def test_star_notch_title_is_short(self):
        assert show_settings.CHAPTER_TITLES[show_settings.CHAPTER_STAR] == "beyond the guide"

    def test_chapter_slider_is_a_standalone_preference_not_a_show_setting(self):
        assert isinstance(page_assets._CHAPTER_KEY, str), "like dark mode: its own store key, separate from the serialized document, so 'select all / # none' and Reset (which act only on editor.settings) never move it"
        assert page_assets._CHAPTER_KEY not in (page_assets._STORE_KEY, page_assets._DARK_KEY)
        assert "chapter" not in show_settings.DEFAULTS

    def test_chapter_slider_carries_chrome_hover_text(self):
        assert tooltips.CHROME_HELP["chapter"].strip()
        assert "chapter" not in tooltips.SHOW_HELP

    def test_unrevealed_controls_are_hidden_two_ways_by_dedicated_css_classes(self):
        m = re.search(r"\.rtt-chapter-hidden\s*\{([^}]*)\}", page_assets._CSS)
        assert m and "display:none" in m.group(1).replace(" ", "")
        m2 = re.search(r"\.rtt-chap-invisible\s*\{([^}]*)\}", page_assets._CSS)
        assert m2 and "visibility:hidden" in m2.group(1).replace(" ", "")

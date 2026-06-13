"""The guide-chapter reveal slider — a viewing preference that progressively shows the Show
controls as a reader advances through D&D's guide (``settings.CHAPTER`` + the slider in app.py).
The slider gates only the PANEL's controls; the grid (the toggle values) is untouched."""

import re

import rtt.app.app as app
from rtt.app import settings as show_settings
from rtt.app import tooltips


def test_every_show_toggle_has_a_chapter():
    # CHAPTER must cover EXACTLY the Show toggles — a new toggle can't ship without a reveal
    # chapter (else the slider would never show or hide it), and a stale key can't linger.
    assert set(show_settings.CHAPTER) == set(show_settings.DEFAULTS)


def test_chapter_values_sit_within_the_slider_range():
    for key, ch in show_settings.CHAPTER.items():
        assert show_settings.CHAPTER_MIN <= ch <= show_settings.CHAPTER_STAR, (key, ch)


def test_the_slider_range_and_default_position():
    assert show_settings.CHAPTER_DEFAULT == 4   # the default-state mockup sits at chapter 4
    assert show_settings.CHAPTER_MIN == 2       # chapter 1 (Introductions) has no app content
    assert show_settings.CHAPTER_STAR > 9       # the ★ notch sits past the guide's chapters


def test_every_revealed_chapter_has_a_readout_title():
    # the live readout names each notch, so every slider position must have a title
    for ch in range(show_settings.CHAPTER_MIN, show_settings.CHAPTER_STAR + 1):
        assert show_settings.CHAPTER_TITLES[ch].strip()


def test_reveal_chapter_never_precedes_an_ancestor():
    # a sub-control is revealed no earlier than the layer it refines, so a shown child never
    # strands above a still-hidden parent (reveal_chapter takes the max along the ancestor chain)
    for key in show_settings.DEFAULTS:
        for anc in show_settings.ancestors_of(key):
            assert show_settings.reveal_chapter(key) >= show_settings.CHAPTER[anc], (key, anc)


def test_revealed_grows_monotonically_and_ends_complete():
    seen: set = set()
    for ch in range(show_settings.CHAPTER_MIN, show_settings.CHAPTER_STAR + 1):
        now = show_settings.revealed(ch)
        assert seen <= now  # the slider only ever reveals more as it advances, never un-reveals
        seen = now
    # the ★ notch shows everything — no control is left permanently hidden
    assert show_settings.revealed(show_settings.CHAPTER_STAR) == set(show_settings.DEFAULTS)


def test_default_position_reveals_the_early_controls_and_hides_the_later_ones():
    shown = show_settings.revealed(show_settings.CHAPTER_DEFAULT)
    assert {"counts", "temperament_boxes", "tuning_boxes", "gridded_values"} <= shown
    # ch5+ controls stay hidden at the default ch4
    assert not ({"domain_units", "optimization", "all_interval", "weighting",
                 "nonstandard_domain"} & shown)
    # the outside-guide controls wait for the ★ notch
    for key in ("projection", "generator_detempering", "identity_objects",
                "form_controls", "form_colorization"):
        assert show_settings.reveal_chapter(key) == show_settings.CHAPTER_STAR
        assert key not in shown


def test_chapter_slider_is_a_standalone_preference_not_a_show_setting():
    # like dark mode: its own store key, separate from the serialized document, so "select all /
    # none" and Reset (which act only on editor.settings) never move it
    assert isinstance(app._CHAPTER_KEY, str)
    assert app._CHAPTER_KEY not in (app._STORE_KEY, app._DARK_KEY)
    assert "chapter" not in show_settings.DEFAULTS


def test_chapter_slider_carries_chrome_hover_text():
    assert tooltips.CHROME_HELP["chapter"].strip()
    assert "chapter" not in tooltips.SHOW_HELP  # it's chrome, like the dark-mode toggle


def test_unrevealed_controls_are_hidden_by_a_dedicated_css_class():
    m = re.search(r"\.rtt-chap-hidden\s*\{([^}]*)\}", app._CSS)
    assert m and "display:none" in m.group(1).replace(" ", "")

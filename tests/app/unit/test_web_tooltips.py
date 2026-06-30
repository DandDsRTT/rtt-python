"""Hover-text (tooltip) help for the Show settings and the interactive controls."""

import re
from pathlib import Path

import pytest

from rtt.app import grid_tables, tooltips
from rtt.app import settings as show_settings
from rtt.app.editor import Editor

_GUIDE_DIR = Path(__file__).resolve().parents[3] / "guide" / \
    "Dave Keenan & Douglas Blumeyer's guide to RTT"


def _chapter_text(chapter: str) -> str:
    matches = [f for f in _GUIDE_DIR.iterdir() if f.name.endswith(chapter)]
    assert len(matches) == 1, f"no unique guide file for chapter {chapter!r}: {matches}"
    return matches[0].read_text(encoding="utf-8")


_INTERACTIVE_KINDS = [
    ("mapping", "cell:mapping:primes:0:0"),
    ("commacell", "cell:comma:commas:0:0"),
    ("interestcell", "cell:interest:0:0"),
    ("heldcell", "cell:held:0:0"),
    ("targetcell", "cell:target:0:0"),
    ("prescalercell", "cell:prescaling:primes:0:0"),
    ("gentuningcell", "cell:tuning:gens:0"),
    ("plain_text_edit", "plain_text:mapping:primes"),
    ("rangemode", "rangemode:tuning:gens"),
    ("minus", "minus:2"),
    ("plus", "plus"),
    ("gen_minus", "gen_minus"),
    ("gen_plus", "gen_plus"),
    ("map_minus", "map_minus:0"),
    ("map_plus", "map_plus"),
    ("basis_minus", "basis_minus"),
    ("comma_minus", "comma_minus:0"),
    ("comma_plus", "comma_plus"),
    ("interest_minus", "interest_minus:0"),
    ("interest_plus", "interest_plus"),
    ("held_minus", "held_minus:0"),
    ("held_plus", "held_plus"),
    ("target_minus", "target_minus:0"),
    ("target_plus", "target_plus"),
    ("rowtoggle", "rowtoggle:row:tuning"),
    ("coltoggle", "coltoggle:col:targets"),
    ("tiletoggle", "tiletoggle:tile:mapping:primes"),
    ("alltoggle", "alltoggle"),
]


_DISAMBIGUATED = [
    ("powerinput", "optimization:power"),
    ("powerinput", "control:q"),
    ("powerdisplay", "control:dual"),
    ("control_select", "control:complexity"),
    ("control_select", "control:slope"),
    ("control_check", "control:diminuator"),
    ("control_check", "control:all_interval"),
    ("formchooser", "formchooser:mapping"),
    ("formchooser", "formchooser:comma_basis"),
    ("preset", "preset:temperament"),
    ("preset", "preset:tuning"),
    ("preset", "preset:target"),
    ("preset", "preset:prescaler"),
    ("preset", "preset:tuning:gens"),
    ("preset", "preset:temperament:commas"),
    ("plain_text_edit", "plain_text:mapping:primes"),
    ("plain_text_edit", "plain_text:vectors:commas"),
    ("plain_text_edit", "plain_text:tuning:gens"),
    ("plain_text_edit", "plain_text:vectors:targets"),
    ("plain_text_edit", "plain_text:prescaling:primes"),
    ("element_minus", "element_minus:1"),
    ("element_minus", "element_minus:basis:2"),
    ("element_minus", "element_minus:pending"),
    ("element_minus", "element_minus:basis:pending"),
]


def _help(kind, cell_id):
    return tooltips.control_help(kind, cell_id)


def _rendered_cells():
    """Cells from a broad sweep of builds: the out-of-box document, plus one with every
    implemented Show layer on and nothing collapsed. The union covers the reachable
    interactive + read-only surface, so a new unclassified kind can't slip through."""
    cells = list(Editor().layout().cells)
    full = Editor()
    for key in full.settings:
        full.settings[key] = key in show_settings.IMPLEMENTED
    full.set_collapsed(set())
    cells += full.layout().cells
    return cells


class TestWebTooltips:
    def test_show_help_covers_every_toggle_with_nonempty_text(self):
        assert set(tooltips.SHOW_HELP) == set(show_settings.DEFAULTS) - {"terminology"}
        assert all(text.strip() for text in tooltips.SHOW_HELP.values())

    @pytest.mark.parametrize("kind", sorted(tooltips.READONLY_KINDS))
    def test_control_help_is_none_for_readonly_kinds(self, kind):
        assert tooltips.control_help(kind, f"{kind}:mapping:primes") is None

    @pytest.mark.parametrize("kind, cell_id", _INTERACTIVE_KINDS)
    def test_control_help_is_present_for_interactive_kinds(self, kind, cell_id):
        assert (tooltips.control_help(kind, cell_id) or "").strip()

    @pytest.mark.parametrize("kind, cell_id", _DISAMBIGUATED)
    def test_disambiguated_controls_each_have_text(self, kind, cell_id):
        assert (_help(kind, cell_id) or "").strip()

    def test_overloaded_kinds_resolve_to_distinct_text_per_role(self):
        assert _help("powerinput", "optimization:power") != _help("powerinput", "control:q")
        assert len({_help("control_select", "control:complexity"),
                    _help("control_select", "control:slope")}) == 2
        assert _help("control_check", "control:diminuator") != _help("control_check", "control:all_interval")
        assert _help("formchooser", "formchooser:mapping") != _help("formchooser", "formchooser:comma_basis")
        assert len({_help("preset", "preset:temperament"),
                    _help("preset", "preset:tuning"),
                    _help("preset", "preset:target"),
                    _help("preset", "preset:prescaler")}) == 4
        assert _help("preset", "preset:tuning:gens") == _help("preset", "preset:tuning")
        assert _help("element_minus", "element_minus:1") == _help("element_minus", "element_minus:basis:2")
        assert _help("element_minus", "element_minus:pending") == _help("element_minus", "element_minus:basis:pending")
        assert _help("element_minus", "element_minus:1") != _help("element_minus", "element_minus:pending")

    def test_target_preset_help_describes_an_integer_or_odd_limit_not_a_prime_limit(self):
        help_text = tooltips.control_help("preset", "preset:target")
        assert "prime limit" not in help_text
        assert "integer limit" in help_text and "odd limit" in help_text

    def test_mean_damage_help_names_a_different_quantity_per_mode(self):
        target = tooltips.mean_damage_help(all_interval=False)
        allint = tooltips.mean_damage_help(all_interval=True)
        assert target.strip() and allint.strip()
        assert target != allint
        assert "⟪𝐝⟫ₚ" in target and "target" in target
        assert "retuning" in allint and "every interval" in allint

    def test_target_limit_help_distinguishes_the_two_errors(self):
        odd = tooltips.target_limit_help("odd")
        whole = tooltips.target_limit_help("whole")
        assert odd.strip() and whole.strip() and odd != whole
        assert "odd" in odd, "tells the user the OLD limit must be odd"
        assert "whole number" in whole

    def test_every_editable_dual_has_a_distinct_tooltip(self):
        ids = [f"plain_text:{row_key}:{column_key}" for row_key, column_key in grid_tables.EDITABLE_PLAIN_TEXT]
        texts = [tooltips.control_help("plain_text_edit", cell_id) for cell_id in ids]
        assert all((t or "").strip() for t in texts)
        assert len(set(texts)) == len(ids)

    def test_every_rendered_cell_is_classified_for_tooltips(self):
        for cb in _rendered_cells():
            text = tooltips.control_help(cb.kind, cb.id)
            if cb.kind in tooltips.READONLY_KINDS and cb.id not in tooltips.HELPED_READONLY_IDS:
                assert text is None, f"read-only {cb.kind!r} ({cb.id}) should carry no tooltip"
            else:
                assert (text or "").strip(), (
                    f"control {cb.kind!r} ({cb.id}) has no hover text — add it in rtt/app/tooltips.py")

    def test_chrome_help_covers_the_app_chrome_buttons(self):
        assert set(tooltips.CHROME_HELP) == {"settings", "chapter", "select_all", "terminology",
                                             "dark_mode", "undo", "redo", "reset", "share", "tour"}
        assert all(text.strip() for text in tooltips.CHROME_HELP.values())

    def test_audio_help_covers_the_five_bank_controls_with_global_wording(self):
        assert set(tooltips.AUDIO_HELP) == {"mute", "wave", "mode", "hold", "root"}
        assert len(set(tooltips.AUDIO_HELP.values())) == 5
        for text in tooltips.AUDIO_HELP.values():
            assert text.strip() and "this tile" not in text

    def test_guide_url_builds_wiki_subpage_and_section_anchor(self):
        assert tooltips.guide_url("Tuning fundamentals", "Damage, error, and weight") == (
            tooltips.GUIDE_BASE + "/Tuning_fundamentals#Damage,_error,_and_weight")
        assert tooltips.guide_url("Mappings", "") == tooltips.GUIDE_BASE + "/Mappings"
        for gh in tooltips.GUIDE_HELP.values():
            if gh.page:
                assert gh.url.startswith("https://en.xen.wiki/w/")
                assert not gh.url.startswith(tooltips.GUIDE_BASE)
                assert " " not in gh.url
                assert not gh.location.startswith("D&D's Guide")
            elif gh.chapter:
                assert gh.url.startswith(tooltips.GUIDE_BASE + "/")
                assert " " not in gh.url
                assert gh.location.startswith("D&D's Guide > ")
            else:
                assert gh.url == "" and gh.location == ""

    @pytest.mark.parametrize("key,gh", sorted(tooltips.GUIDE_HELP.items()))
    def test_guide_help_text_is_a_clean_general_blurb(self, key, gh):
        assert gh.text.strip() == gh.text and gh.text.endswith("."), "the blurb is Guide-voiced prose describing the object in general — NOT a verbatim quote and # NOT tied to whatever temperament happens to be loaded (the comma basis once read 'the meantone # comma', which only held for the default)"
        assert "meantone" not in gh.text.lower(), f"{key} blurb names a specific temperament"

    @pytest.mark.parametrize("key,gh", sorted(tooltips.GUIDE_HELP.items()))
    def test_guide_help_section_is_a_real_heading_in_its_chapter(self, key, gh):
        if not gh.chapter:
            return
        heading = re.compile(rf"^=+\s*{re.escape(gh.section)}\s*=+\s*$", re.MULTILINE)
        assert heading.search(_chapter_text(gh.chapter)), f"no heading {gh.section!r} in {gh.chapter!r}"

    def test_tile_guide_help_for_cell_only_fires_on_three_part_tile_ids(self):
        assert tooltips.tile_guide_help_for_cell("caption:mapping:primes") is \
            tooltips.GUIDE_HELP[("mapping", "primes")]
        assert tooltips.tile_guide_help_for_cell("symbol:tuning:gens") is \
            tooltips.GUIDE_HELP[("tuning", "gens")]
        assert tooltips.tile_guide_help_for_cell("caption:counts:commas") is \
            tooltips.GUIDE_HELP[("counts", "commas")]
        for non_tile in ("caption:q", "symbol:dual", "caption:slope", "caption:all_interval",
                         "caption:counts:commas:u", "optimization:power:symbol",
                         "optimization:mean_damage:caption"):
            assert tooltips.tile_guide_help_for_cell(non_tile) is None

    def test_every_rendered_caption_and_symbol_cell_id_parses_without_error(self):
        for cb in _rendered_cells():
            if cb.kind in ("symbol", "caption"):
                tooltips.tile_guide_help_for_cell(cb.id)

    def test_pretransform_relabels_the_prescaler_help_to_pretransformer(self):
        preset = tooltips.control_help("preset", "preset:prescaler")
        assert "prescaler" in preset and "pretransformer" not in preset
        preset_pt = tooltips.control_help("preset", "preset:prescaler", pretransform=True)
        assert "pretransformer" in preset_pt and "prescaler" not in preset_pt
        assert "prescaler" in tooltips.control_help("plain_text_edit", "plain_text:prescaling:primes"), "the prescaler plain-text dual editor's hover relabels too (it also names the prescaler)"
        assert "pretransformer" in tooltips.control_help(
            "plain_text_edit", "plain_text:prescaling:primes", pretransform=True)
        plain = tooltips.tile_guide_help_for_cell("caption:prescaling:primes")
        pretransformed = tooltips.tile_guide_help_for_cell("caption:prescaling:primes", pretransform=True)
        assert "prescaler" in plain.text and "pretransformer" not in plain.text
        assert "pretransformer" in pretransformed.text and "prescaler" not in pretransformed.text
        assert pretransformed.url == plain.url and pretransformed.location == plain.location

    def test_pretransform_leaves_help_without_the_prescaler_word_unchanged(self):
        for kind, cell_id in (("mapping", "cell:mapping:primes:0:0"), ("preset", "preset:tuning")):
            assert tooltips.control_help(kind, cell_id) == tooltips.control_help(kind, cell_id, pretransform=True)
        assert tooltips.tile_guide_help_for_cell("caption:mapping:primes", pretransform=True) is \
            tooltips.GUIDE_HELP[("mapping", "primes")]

    def test_guide_help_covers_only_real_tiles_and_resolves_by_tile_key(self):
        captioned = {(r, c) for r, c in grid_tables.CAPTIONS}
        for (row_key, column_key), gh in tooltips.GUIDE_HELP.items():
            assert (row_key, column_key) in captioned, f"{(row_key, column_key)} is not a captioned tile"
            assert tooltips.tile_guide_help(row_key, column_key) is gh
        assert tooltips.tile_guide_help("mapping", "nonsense") is None

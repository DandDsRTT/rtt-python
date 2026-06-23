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


def test_show_help_covers_every_toggle_with_nonempty_text():
    # every Show toggle (live or greyed) carries explanatory hover text, and no extras
    assert set(tooltips.SHOW_HELP) == set(show_settings.DEFAULTS)
    assert all(text.strip() for text in tooltips.SHOW_HELP.values())


@pytest.mark.parametrize("kind", sorted(tooltips.READONLY_KINDS))
def test_control_help_is_none_for_readonly_kinds(kind):
    # the read-only output kinds are declared once, in tooltips.READONLY_KINDS
    assert tooltips.control_help(kind, f"{kind}:mapping:primes") is None


# interactive kinds whose meaning is fixed by the kind alone (a representative id each)
_INTERACTIVE_KINDS = [
    ("mapping", "cell:mapping:primes:0:0"),
    ("commacell", "cell:comma:commas:0:0"),
    ("interestcell", "cell:interest:0:0"),
    ("heldcell", "cell:held:0:0"),
    ("targetcell", "cell:target:0:0"),
    ("prescalercell", "cell:prescaling:primes:0:0"),
    ("gentuningcell", "cell:tuning:gens:0"),
    ("ptextedit", "ptext:mapping:primes"),
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


@pytest.mark.parametrize("kind, cid", _INTERACTIVE_KINDS)
def test_control_help_is_present_for_interactive_kinds(kind, cid):
    assert (tooltips.control_help(kind, cid) or "").strip()


# kinds that back several controls, told apart by id (the id carries the role)
_DISAMBIGUATED = [
    ("powerinput", "optimization:power"),
    ("powerinput", "control:q"),
    ("powerdisplay", "control:dual"),  # dual(q) is derived → a read-only powerdisplay that still carries help
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
    ("preset", "preset:tuning:gens"),         # a copied chooser in a second tile
    ("preset", "preset:temperament:commas"),
    ("ptextedit", "ptext:mapping:primes"),
    ("ptextedit", "ptext:vectors:commas"),
    ("ptextedit", "ptext:tuning:gens"),
    ("ptextedit", "ptext:vectors:targets"),
    ("ptextedit", "ptext:prescaling:primes"),
    ("element_minus", "element_minus:1"),             # the per-element domain remove (quantities axis)
    ("element_minus", "element_minus:basis:2"),       # ...and its interval-vectors spine twin
    ("element_minus", "element_minus:pending"),       # the ?/? draft's cancel (quantities axis)
    ("element_minus", "element_minus:basis:pending"),  # ...and its spine twin
]


def _help(kind, cid):
    return tooltips.control_help(kind, cid)


@pytest.mark.parametrize("kind, cid", _DISAMBIGUATED)
def test_disambiguated_controls_each_have_text(kind, cid):
    assert (_help(kind, cid) or "").strip()


def test_overloaded_kinds_resolve_to_distinct_text_per_role():
    # one powerinput is the optimization power 𝑝, another the complexity norm power 𝑞
    assert _help("powerinput", "optimization:power") != _help("powerinput", "control:q")
    # the two alt.-complexity choosers each describe their own dimension
    assert len({_help("control_select", "control:complexity"),
                _help("control_select", "control:slope")}) == 2
    # the two control_check boxes (diminuator, all-interval) describe different things
    assert _help("control_check", "control:diminuator") != _help("control_check", "control:all_interval")
    assert _help("formchooser", "formchooser:mapping") != _help("formchooser", "formchooser:comma_basis")
    # the four preset choosers differ; a copied chooser reads like its base
    assert len({_help("preset", "preset:temperament"),
                _help("preset", "preset:tuning"),
                _help("preset", "preset:target"),
                _help("preset", "preset:prescaler")}) == 4
    assert _help("preset", "preset:tuning:gens") == _help("preset", "preset:tuning")
    # the domain − reads "remove this element" per-element, "cancel the draft" for the ?/? draft —
    # on both axes, told apart by the ":pending" suffix in the id
    assert _help("element_minus", "element_minus:1") == _help("element_minus", "element_minus:basis:2")
    assert _help("element_minus", "element_minus:pending") == _help("element_minus", "element_minus:basis:pending")
    assert _help("element_minus", "element_minus:1") != _help("element_minus", "element_minus:pending")


def test_target_preset_help_describes_an_integer_or_odd_limit_not_a_prime_limit():
    # the target chooser's limit is an integer limit (the TILT triangle) or an odd limit (the OLD
    # diamond), never a prime limit — an earlier wording wrongly called it a prime limit.
    help_text = tooltips.control_help("preset", "preset:target")
    assert "prime limit" not in help_text
    assert "integer limit" in help_text and "odd limit" in help_text


def test_mean_damage_help_names_a_different_quantity_per_mode():
    # the optimization mean damage is a read-only value but still carries help, and that help must
    # track the scheme: target-based it is the minimized damage ⟪𝐝⟫ₚ over the target list;
    # all-interval it is the retuning magnitude minimized over every interval. Two distinct,
    # non-empty wordings, each naming the quantity the live symbol shows.
    target = tooltips.mean_damage_help(all_interval=False)
    allint = tooltips.mean_damage_help(all_interval=True)
    assert target.strip() and allint.strip()
    assert target != allint
    assert "⟪𝐝⟫ₚ" in target and "target" in target
    assert "retuning" in allint and "every interval" in allint


def test_target_limit_help_distinguishes_the_two_errors():
    # the two target-limit problems service.target_limit_problem reports each get their own
    # wording (the hover tip AND the toast read the same string): an even odd-limit-diamond limit
    # must be odd; any limit must be a whole number. Distinct, non-empty, and naming the fix.
    odd = tooltips.target_limit_help("odd")
    whole = tooltips.target_limit_help("whole")
    assert odd.strip() and whole.strip() and odd != whole
    assert "odd" in odd  # tells the user the OLD limit must be odd
    assert "whole number" in whole


def test_every_editable_dual_has_a_distinct_tooltip():
    # the editable plain-text duals are exactly EDITABLE_PTEXT (the layout's source of truth);
    # each must carry its own hover text so no editable value is left unexplained
    ids = [f"ptext:{rkey}:{ckey}" for rkey, ckey in grid_tables.EDITABLE_PTEXT]
    texts = [tooltips.control_help("ptextedit", cid) for cid in ids]
    assert all((t or "").strip() for t in texts)
    assert len(set(texts)) == len(ids)


def _rendered_cells():
    """Cells from a broad sweep of builds: the out-of-box document, plus one with every
    implemented Show layer on and nothing collapsed. The union covers the reachable
    interactive + read-only surface, so a new unclassified kind can't slip through."""
    cells = list(Editor().layout().cells)
    full = Editor()
    for key in full.settings:
        full.settings[key] = key in show_settings.IMPLEMENTED
    full.collapsed = set()  # expand every row / column / tile so all their cells render
    cells += full.layout().cells
    return cells


def test_every_rendered_cell_is_classified_for_tooltips():
    # the safety net behind control_help: sweep a full build and require each rendered cell to
    # be either a declared read-only output (no tooltip) or an interactive control with hover
    # text. A brand-new control kind with no tooltips.py entry trips this — closing the gap a
    # hardcoded test list would leave open. The optimization mean damage is the lone read-only
    # exception (MEAN_DAMAGE_IDS): it carries help despite being a value, so it must read like a
    # control here, not like a bare output.
    for cb in _rendered_cells():
        text = tooltips.control_help(cb.kind, cb.id)
        if cb.kind in tooltips.READONLY_KINDS and cb.id not in tooltips.HELPED_READONLY_IDS:
            assert text is None, f"read-only {cb.kind!r} ({cb.id}) should carry no tooltip"
        else:
            assert (text or "").strip(), (
                f"control {cb.kind!r} ({cb.id}) has no hover text — add it in rtt/app/tooltips.py")


def test_chrome_help_covers_the_app_chrome_buttons():
    # the always-present chrome: settings drawer, the guide-chapter reveal slider, select-all, the
    # dark-mode toggle, undo, redo, reset, share, and the guided-tour replay button
    assert set(tooltips.CHROME_HELP) == {"settings", "chapter", "select_all", "dark_mode",
                                         "undo", "redo", "reset", "share", "tour"}
    assert all(text.strip() for text in tooltips.CHROME_HELP.values())


def test_audio_help_covers_the_five_bank_controls_with_global_wording():
    # the single dummy-tile audio bank's five controls each carry distinct, non-empty help; the
    # wording is global ("every pitch", never "this tile") now that one bank drives every speaker.
    # mute leads the bank and doubles as the kill switch (muting silences all sounding audio).
    assert set(tooltips.AUDIO_HELP) == {"mute", "wave", "mode", "hold", "root"}
    assert len(set(tooltips.AUDIO_HELP.values())) == 5
    for text in tooltips.AUDIO_HELP.values():
        assert text.strip() and "this tile" not in text


def test_guide_url_builds_wiki_subpage_and_section_anchor():
    # chapter → subpage (spaces → underscores); section → MediaWiki #anchor (spaces → underscores)
    assert tooltips.guide_url("Tuning fundamentals", "Damage, error, and weight") == (
        tooltips.GUIDE_BASE + "/Tuning_fundamentals#Damage,_error,_and_weight")
    assert tooltips.guide_url("Mappings", "") == tooltips.GUIDE_BASE + "/Mappings"
    for gh in tooltips.GUIDE_HELP.values():
        if gh.page:                  # a standalone Xen Wiki page (not part of the guide)
            assert gh.url.startswith("https://en.xen.wiki/w/")
            assert not gh.url.startswith(tooltips.GUIDE_BASE)
            assert " " not in gh.url
            assert not gh.location.startswith("D&D's Guide")   # no guide prefix on a non-guide link
        elif gh.chapter:
            assert gh.url.startswith(tooltips.GUIDE_BASE + "/")
            assert " " not in gh.url
            assert gh.location.startswith("D&D's Guide > ")
        else:                        # a blurb with no link at all
            assert gh.url == "" and gh.location == ""


@pytest.mark.parametrize("key,gh", sorted(tooltips.GUIDE_HELP.items()))
def test_guide_help_text_is_a_clean_general_blurb(key, gh):
    # the blurb is Guide-voiced prose describing the object in general — NOT a verbatim quote and
    # NOT tied to whatever temperament happens to be loaded (the comma basis once read "the meantone
    # comma", which only held for the default)
    assert gh.text.strip() == gh.text and gh.text.endswith(".")
    assert "meantone" not in gh.text.lower(), f"{key} blurb names a specific temperament"


@pytest.mark.parametrize("key,gh", sorted(tooltips.GUIDE_HELP.items()))
def test_guide_help_section_is_a_real_heading_in_its_chapter(key, gh):
    # the linked section anchor resolves: a == heading == with that exact text exists in the chapter
    if not gh.chapter:               # link-less tile: nothing to resolve
        return
    heading = re.compile(rf"^=+\s*{re.escape(gh.section)}\s*=+\s*$", re.MULTILINE)
    assert heading.search(_chapter_text(gh.chapter)), f"no heading {gh.section!r} in {gh.chapter!r}"


def test_tile_guide_help_for_cell_only_fires_on_three_part_tile_ids():
    # the make_cell hook keys off a cell id; control cells share the "caption"/"symbol" kinds but
    # carry non-tile ids of 2 parts (caption:q, symbol:dual) or 4 (caption:counts:commas:u), and the
    # optimization tiles put the kind LAST (optimization:power:symbol). None of these may be parsed
    # as a (row, col) tile — only a real symbol:row:col / caption:row:col resolves.
    assert tooltips.tile_guide_help_for_cell("caption:mapping:primes") is \
        tooltips.GUIDE_HELP[("mapping", "primes")]
    assert tooltips.tile_guide_help_for_cell("symbol:tuning:gens") is \
        tooltips.GUIDE_HELP[("tuning", "gens")]
    # the counts captions ARE real tiles now (caption:counts:commas → nullity), but the nullity-of-
    # unchanged split keeps a 4-part id that must not resolve
    assert tooltips.tile_guide_help_for_cell("caption:counts:commas") is \
        tooltips.GUIDE_HELP[("counts", "commas")]
    for non_tile in ("caption:q", "symbol:dual", "caption:slope", "caption:all_interval",
                     "caption:counts:commas:u", "optimization:power:symbol",
                     "optimization:mean_damage:caption"):
        assert tooltips.tile_guide_help_for_cell(non_tile) is None


def test_every_rendered_caption_and_symbol_cell_id_parses_without_error():
    # a full build's caption/symbol cells all flow through tile_guide_help_for_cell in make_cell;
    # every one must parse safely (a 2-part control id once unpacked into 3 and crashed render)
    for cb in _rendered_cells():
        if cb.kind in ("symbol", "caption"):
            tooltips.tile_guide_help_for_cell(cb.id)  # must not raise


def test_guide_help_covers_only_real_tiles_and_resolves_by_tile_key():
    # every registry key is a real (row, col) tile, and tile_guide_help round-trips it
    captioned = {(r, c) for r, c in grid_tables.CAPTIONS}
    for (rkey, ckey), gh in tooltips.GUIDE_HELP.items():
        assert (rkey, ckey) in captioned, f"{(rkey, ckey)} is not a captioned tile"
        assert tooltips.tile_guide_help(rkey, ckey) is gh
    assert tooltips.tile_guide_help("mapping", "nonsense") is None

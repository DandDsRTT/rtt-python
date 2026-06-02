"""Hover-text (tooltip) help for the Show settings and the interactive controls."""

import pytest

from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web import tooltips


def test_show_help_covers_every_toggle_with_nonempty_text():
    # every Show toggle (live or greyed) carries explanatory hover text, and no extras
    assert set(tooltips.SHOW_HELP) == set(show_settings.DEFAULTS)
    assert all(text.strip() for text in tooltips.SHOW_HELP.values())


# read-only cell kinds are outputs, not controls, so they get no tooltip
_READONLY_KINDS = [
    "prime", "formcell", "colheader", "rowlabel", "mapped", "vec", "tval",
    "genratio", "target", "commaratio", "mathexpr", "ptext", "ptextpending",
    "symbol", "matlabel", "units", "caption", "count", "boxtitle",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "chart", "rangechart",
]


@pytest.mark.parametrize("kind", _READONLY_KINDS)
def test_control_help_is_none_for_readonly_kinds(kind):
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
    ("optimize", "optimization:button"),
    ("minus", "minus:2"),
    ("plus", "plus"),
    ("basis_minus", "basis_minus"),
    ("comma_minus", "comma_minus"),
    ("comma_plus", "comma_plus"),
    ("interest_minus", "interest_minus:0"),
    ("interest_plus", "interest_plus"),
    ("held_minus", "held_minus:0"),
    ("held_plus", "held_plus"),
    ("rowtoggle", "rowtoggle:row:tuning"),
    ("coltoggle", "coltoggle:col:targets"),
    ("tiletoggle", "tiletoggle:tile:mapping:primes"),
    ("alltoggle", "alltoggle"),
    ("speaker", "speaker:mapping:primes:0"),
    ("audio_wave", "audio_wave:mapping:primes"),
    ("audio_mode", "audio_mode:mapping:primes"),
    ("audio_hold", "audio_hold:mapping:primes"),
    ("audio_root", "audio_root:mapping:primes"),
]


@pytest.mark.parametrize("kind, cid", _INTERACTIVE_KINDS)
def test_control_help_is_present_for_interactive_kinds(kind, cid):
    assert (tooltips.control_help(kind, cid) or "").strip()


# kinds that back several controls, told apart by id (the id carries the role)
_DISAMBIGUATED = [
    ("powerinput", "optimization:power"),
    ("powerinput", "control:q"),
    ("powerinput", "control:dual"),
    ("control_select", "control:prescaler"),
    ("control_select", "control:complexity"),
    ("control_select", "control:slope"),
    ("control_check", "control:diminuator"),
    ("control_check", "control:all_interval"),
    ("formchooser", "formchooser:mapping"),
    ("formchooser", "formchooser:comma_basis"),
    ("preselect", "preselect:temperament"),
    ("preselect", "preselect:tuning"),
    ("preselect", "preselect:target"),
    ("preselect", "preselect:tuning:gens"),         # a copied chooser in a second tile
    ("preselect", "preselect:temperament:commas"),
    ("ptextedit", "ptext:mapping:primes"),
    ("ptextedit", "ptext:vectors:commas"),
    ("ptextedit", "ptext:tuning:gens"),
    ("ptextedit", "ptext:vectors:targets"),
    ("ptextedit", "ptext:prescaling:primes"),
]


def _help(kind, cid):
    return tooltips.control_help(kind, cid)


@pytest.mark.parametrize("kind, cid", _DISAMBIGUATED)
def test_disambiguated_controls_each_have_text(kind, cid):
    assert (_help(kind, cid) or "").strip()


def test_overloaded_kinds_resolve_to_distinct_text_per_role():
    # one powerinput is the optimization power 𝑝, another the complexity norm power 𝑞
    assert _help("powerinput", "optimization:power") != _help("powerinput", "control:q")
    # the three alt.-complexity choosers each describe their own dimension
    assert len({_help("control_select", "control:prescaler"),
                _help("control_select", "control:complexity"),
                _help("control_select", "control:slope")}) == 3
    assert _help("control_check", "control:diminuator") != _help("control_check", "control:all_interval")
    assert _help("formchooser", "formchooser:mapping") != _help("formchooser", "formchooser:comma_basis")
    # the three preset choosers differ; a copied chooser reads like its base
    assert len({_help("preselect", "preselect:temperament"),
                _help("preselect", "preselect:tuning"),
                _help("preselect", "preselect:target")}) == 3
    assert _help("preselect", "preselect:tuning:gens") == _help("preselect", "preselect:tuning")


def test_every_editable_dual_has_a_distinct_tooltip():
    # the editable plain-text duals are exactly EDITABLE_PTEXT (the layout's source of truth);
    # each must carry its own hover text so no editable value is left unexplained
    ids = [f"ptext:{rkey}:{ckey}" for rkey, ckey in spreadsheet.EDITABLE_PTEXT]
    texts = [tooltips.control_help("ptextedit", cid) for cid in ids]
    assert all((t or "").strip() for t in texts)
    assert len(set(texts)) == len(ids)


def test_chrome_help_covers_the_app_chrome_buttons():
    # the always-present chrome: settings drawer, select-all, undo, redo, reset
    assert set(tooltips.CHROME_HELP) == {"settings", "select_all", "undo", "redo", "reset"}
    assert all(text.strip() for text in tooltips.CHROME_HELP.values())

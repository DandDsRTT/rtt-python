"""Hover-text (tooltip) help for the Show settings and the interactive controls."""

import pytest

from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web import tooltips
from rtt.web.editor import Editor


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
    ("optimize", "optimization:button"),
    ("minus", "minus:2"),
    ("plus", "plus"),
    ("gen_minus", "gen_minus"),
    ("gen_plus", "gen_plus"),
    ("map_minus", "map_minus:0"),
    ("map_plus", "map_plus"),
    ("basis_minus", "basis_minus"),
    ("comma_minus", "comma_minus"),
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
    assert _help("control_check", "control:diminuator") != _help("control_check", "control:all_interval")
    assert _help("formchooser", "formchooser:mapping") != _help("formchooser", "formchooser:comma_basis")
    # the four preset choosers differ; a copied chooser reads like its base
    assert len({_help("preset", "preset:temperament"),
                _help("preset", "preset:tuning"),
                _help("preset", "preset:target"),
                _help("preset", "preset:prescaler")}) == 4
    assert _help("preset", "preset:tuning:gens") == _help("preset", "preset:tuning")


def test_target_preset_help_describes_an_integer_or_odd_limit_not_a_prime_limit():
    # the target chooser's limit is an integer limit (the TILT triangle) or an odd limit (the OLD
    # diamond), never a prime limit — an earlier wording wrongly called it a prime limit.
    help_text = tooltips.control_help("preset", "preset:target")
    assert "prime limit" not in help_text
    assert "integer limit" in help_text and "odd limit" in help_text


def test_objective_help_names_a_different_quantity_per_mode():
    # the optimization objective is a read-only value but still carries help, and that help must
    # track the scheme: target-based it is the minimized damage ⟪𝐝⟫ₚ over the target list;
    # all-interval it is the retuning magnitude minimized over every interval. Two distinct,
    # non-empty wordings, each naming the quantity the live symbol shows.
    target = tooltips.objective_help(all_interval=False)
    allint = tooltips.objective_help(all_interval=True)
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
    ids = [f"ptext:{rkey}:{ckey}" for rkey, ckey in spreadsheet.EDITABLE_PTEXT]
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
    # hardcoded test list would leave open. The optimization objective is the lone read-only
    # exception (OBJECTIVE_IDS): it carries help despite being a value, so it must read like a
    # control here, not like a bare output.
    for cb in _rendered_cells():
        text = tooltips.control_help(cb.kind, cb.id)
        if cb.kind in tooltips.READONLY_KINDS and cb.id not in tooltips.HELPED_READONLY_IDS:
            assert text is None, f"read-only {cb.kind!r} ({cb.id}) should carry no tooltip"
        else:
            assert (text or "").strip(), (
                f"control {cb.kind!r} ({cb.id}) has no hover text — add it in rtt/web/tooltips.py")


def test_chrome_help_covers_the_app_chrome_buttons():
    # the always-present chrome: settings drawer, select-all, the dark-mode toggle, undo, redo, reset
    assert set(tooltips.CHROME_HELP) == {"settings", "select_all", "dark_mode", "undo", "redo", "reset"}
    assert all(text.strip() for text in tooltips.CHROME_HELP.values())

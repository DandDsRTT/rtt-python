"""Editor view-model contract tests.

Behavioral scenarios (expand/shrink/change/undo) are covered by
test_web_integration.py; here we pin the Editor's own state-machine contract:
the initial state, undo availability, and the shrink guard.
"""

from fractions import Fraction

from rtt.web import service, settings, spreadsheet
from rtt.web.editor import INITIAL_MAPPING, Editor


def test_editor_starts_at_meantone_with_no_undo():
    editor = Editor()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.state.comma_basis == ((4, -4, 1),)
    assert editor.can_undo is False
    assert editor.can_redo is False


def test_an_edit_enables_undo():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    assert editor.can_undo is True


def test_canonicalize_mapping_restores_canonical_form_undoably():
    editor = Editor()  # starts at meantone ((1,1,0),(0,1,4)), a non-canonical generating set
    editor.canonicalize_mapping()
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))  # the canonical form
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING  # the form choice is an undoable edit


def test_canonicalize_comma_basis_restores_canonical_form_undoably():
    editor = Editor()
    editor.edit_comma_basis([[-8, 8, -2]])  # a non-saturated basis (the syntonic comma doubled)
    editor.canonicalize_comma_basis()
    assert editor.state.comma_basis == ((4, -4, 1),)  # defactored + canonicalized
    editor.undo()
    assert editor.state.comma_basis == ((-8, 8, -2),)  # undoable


def test_set_complexity_prescaler_swaps_the_weighting_prescaler_into_the_layout():
    editor = Editor()
    assert service.prescaler_of(editor.tuning_scheme) == "log-prime"  # the default (Tenney)
    editor.set_complexity_prescaler("prime")  # the alt.-complexity control (box 𝐋)
    assert service.prescaler_of(editor.tuning_scheme) == "prime"
    # and the swap flows into the prescaling matrix: sopfr's diagonal IS the primes
    lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                            tuning_scheme=editor.tuning_scheme)
    diag = {c.id: c.text for c in lay.cells if c.id.startswith("cell:prescaling:") and c.id[-3] == c.id[-1]}
    assert diag["cell:prescaling:0:0"] == "2"
    assert diag["cell:prescaling:1:1"] == "3"
    assert diag["cell:prescaling:2:2"] == "5"


def test_set_complexity_euclidean_switches_the_complexity_norm():
    editor = Editor()
    assert service.is_euclidean(editor.tuning_scheme) is False  # taxicab default
    editor.set_complexity_euclidean(True)  # the alt.-complexity control (box 𝒄)
    assert service.is_euclidean(editor.tuning_scheme) is True
    editor.set_complexity_euclidean(False)
    assert service.is_euclidean(editor.tuning_scheme) is False


def test_redo_restores_an_undone_action():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    edited = editor.state.mapping
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING
    assert editor.can_redo is True
    editor.redo()
    assert editor.state.mapping == edited
    assert editor.can_redo is False


def test_a_fresh_edit_clears_the_redo_history():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.can_redo is True
    editor.edit_mapping([[1, 1, 0], [0, 1, 5]])  # a new action invalidates redo
    assert editor.can_redo is False


def test_undo_with_empty_stack_is_a_noop():
    editor = Editor()
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING


def test_add_comma_starts_a_blank_pending_draft_without_touching_the_temperament():
    editor = Editor()
    assert editor.pending_comma is None
    editor.add_comma()
    assert editor.pending_comma == [None, None, None]  # a blank d-length draft
    assert editor.state.comma_basis == ((4, -4, 1),)  # the temperament is unchanged...
    assert editor.state.r == 2  # ...the mapping keeps its rows...
    assert editor.can_undo is False  # ...and starting a draft is not an undoable edit


def test_filling_the_pending_comma_with_an_independent_comma_commits_and_reranks():
    editor = Editor()
    editor.add_comma()
    editor.set_pending_comma([4, -5, 1])  # an independent second comma
    assert editor.pending_comma is None  # committed, no longer pending
    assert editor.state.comma_basis == ((4, -4, 1), (4, -5, 1))
    assert (editor.state.r, editor.state.n) == (1, 2)  # the mapping dropped a row (d = r + n)
    assert editor.can_undo is True  # the commit is the undoable edit


def test_incomplete_or_dependent_pending_comma_is_held_not_committed():
    editor = Editor()
    editor.add_comma()
    editor.set_pending_comma([4, None, 1])  # still being typed
    assert editor.pending_comma == [4, None, 1] and editor.state.r == 2  # held, no re-rank
    editor.set_pending_comma([8, -8, 2])  # complete but dependent (2x the existing comma)
    assert editor.pending_comma == [8, -8, 2] and editor.state.r == 2  # not a new comma -> held


def test_removing_a_pending_comma_cancels_the_draft():
    editor = Editor()
    assert editor.can_remove_comma is False  # the sole real comma cannot be removed
    editor.add_comma()
    assert editor.can_remove_comma is True  # ...but a pending draft can be cancelled
    editor.remove_comma()
    assert editor.pending_comma is None
    assert editor.state.comma_basis == ((4, -4, 1),)  # unchanged
    assert editor.can_undo is False  # cancelling a draft is not an undoable edit


def test_removing_a_real_comma_drops_the_last_when_no_draft_is_pending():
    editor = Editor()
    editor.add_comma()
    editor.set_pending_comma([4, -5, 1])  # commit a 2nd comma -> 2 real, no pending
    assert editor.pending_comma is None and len(editor.state.comma_basis) == 2
    editor.remove_comma()  # no draft -> drop the last real comma
    assert editor.state.comma_basis == ((4, -4, 1),)
    assert editor.state.r == 2  # the mapping regained its row


def test_editor_starts_with_default_tuning_scheme_and_target_spec():
    editor = Editor()
    assert editor.tuning_scheme == service.DEFAULT_TUNING_SCHEME
    assert editor.target_spec == "TILT"


def test_selecting_a_tuning_scheme_and_target_spec_updates_them():
    editor = Editor()
    editor.set_tuning_scheme("POTE")
    editor.set_target_spec("OLD")
    assert editor.tuning_scheme == "POTE"
    assert editor.target_spec == "OLD"


def test_a_manual_target_limit_is_weakly_held_and_reverts_when_the_domain_changes():
    editor = Editor()  # domain 2.3.5
    editor.set_target_spec("9-TILT")
    assert editor.target_spec == "9-TILT"  # the manual limit holds within its domain
    editor.set_target_spec("11-OLD")
    assert editor.target_spec == "11-OLD"  # switching family keeps a manual limit
    editor.expand()  # domain 2.3.5.7 — a domain change
    assert editor.target_spec == "OLD"  # ...reverts to the bare family (domain default)


def test_a_manual_target_limit_does_not_resurrect_when_the_domain_returns():
    # the manual limit is forgotten on the FIRST domain change, so round-tripping
    # back to the original domain shows that domain's default, not the old choice
    editor = Editor()  # 5-limit meantone (d=3)
    editor.set_target_spec("7-TILT")
    editor.edit_comma_basis([[-5, 2, 2, -1], [-10, 1, 0, 3]])  # 7-limit Miracle (d=4)
    editor.edit_comma_basis([[-4, 4, -1]])  # back to a 5-limit temperament (d=3)
    assert editor.target_spec == "TILT"  # the 5-limit default, NOT the stale 7-TILT


def test_setting_a_bare_family_clears_any_manual_limit():
    editor = Editor()
    editor.set_target_spec("9-TILT")
    editor.set_target_spec("OLD")  # no number -> domain-tracked default
    assert editor.target_spec == "OLD"


def test_scheme_and_target_spec_are_view_selections_outside_undo():
    # they are display/analysis choices, not temperament edits, so they neither
    # push onto the undo stack nor get reverted by undoing a temperament change
    editor = Editor()
    editor.set_tuning_scheme("CTE")
    assert editor.can_undo is False  # selecting a scheme is not an undoable edit
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.tuning_scheme == "CTE"  # undo reverts the mapping, not the scheme


def test_range_mode_starts_monotone_and_is_a_view_selection_outside_undo():
    # which generator tuning range the ranges chart shows (monotone vs tradeoff) is
    # a display choice like the tuning scheme, so it starts at a default, is settable,
    # and stays put across undo (it is not a temperament edit)
    editor = Editor()
    assert editor.range_mode == "monotone"
    editor.set_range_mode("tradeoff")
    assert editor.range_mode == "tradeoff"
    assert editor.can_undo is False  # choosing a range mode is not an undoable edit
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.range_mode == "tradeoff"  # undo reverts the mapping, not the mode


def test_domain_expand_shrink_are_inert_on_a_nonstandard_domain():
    # the domain +/- walk the standard primes, which doesn't apply to a nonprime
    # subgroup — they must leave a nonstandard temperament untouched, never silently
    # reverting it to a prime limit
    editor = Editor()
    editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    before = editor.state
    assert editor.can_shrink is False and editor.can_expand is False
    editor.expand()
    editor.shrink()
    assert editor.state is before  # unchanged by either control


def test_standard_domain_can_still_expand():
    editor = Editor()  # 2.3.5
    assert editor.can_expand is True
    editor.expand()
    assert editor.state.d == 4 and editor.state.domain_basis == (2, 3, 5, 7)


def test_cannot_shrink_below_one_dimension():
    editor = Editor()
    assert editor.can_shrink is True  # starts at d=3
    editor.shrink()
    editor.shrink()
    assert editor.state.d == 1
    assert editor.can_shrink is False


def test_interest_intervals_add_edit_remove():
    editor = Editor()
    assert editor.interest_monzos == []  # starts empty
    editor.add_interest()
    assert editor.interest_monzos == [(0, 0, 0)]  # a blank 1/1 (zero monzo) at the current d
    editor.set_interest_monzos([[-1, 1, 0], [0, 0, 0]])  # edit it to 3/2 and add a second
    assert editor.interest_monzos == [(-1, 1, 0), (0, 0, 0)]
    editor.remove_interest(1)
    assert editor.interest_monzos == [(-1, 1, 0)]


def test_interest_intervals_are_view_data_outside_undo():
    # like the tuning/target selections, the interest set is curated display data,
    # not a temperament edit: editing it does not push undo, and undoing a temperament
    # change leaves it untouched
    editor = Editor()
    editor.add_interest()
    assert editor.can_undo is False  # adding an interval of interest is not undoable
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.undo()
    assert editor.interest_monzos == [(0, 0, 0)]  # the undo reverts the mapping, not the set


def test_try_edit_mapping_text_applies_a_valid_ebk_map():
    editor = Editor()
    assert editor.try_edit_mapping_text("[⟨1 0 0] ⟨0 1 0] ⟨0 0 1]}") is True
    assert editor.state.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))  # just intonation


def test_try_edit_mapping_text_loads_a_nonstandard_domain_from_its_prefix():
    # the mapping box round-trips the prefixed EBK that plain_text_values now emits, so
    # typing a domain prefix loads that nonstandard temperament (Barbados over 2.3.13/5)
    editor = Editor()
    assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
    assert editor.state.domain_basis == (2, 3, Fraction(13, 5))
    assert editor.state.mapping == ((1, 2, 2), (0, -2, -3))
    assert editor.can_undo is True


def test_try_edit_mapping_text_rejects_bad_input_without_changing_state():
    editor = Editor()
    before = editor.state.mapping
    assert editor.try_edit_mapping_text("garbage") is False
    assert editor.try_edit_mapping_text("[1 0 0⟩") is False  # a vector, not a map
    assert editor.try_edit_mapping_text("⟨1 1.5 0]") is False  # a non-integer entry
    assert editor.state.mapping == before  # an unparseable edit leaves the grid untouched
    assert editor.can_undo is False  # ...and pushes nothing onto the undo stack


def test_try_edit_comma_basis_text_applies_a_valid_ebk_vector():
    editor = Editor()
    assert editor.try_edit_comma_basis_text("[4 -4 1⟩") is True
    assert editor.state.comma_basis == ((4, -4, 1),)


def test_try_edit_comma_basis_text_rejects_bad_input_without_changing_state():
    editor = Editor()
    before = editor.state.comma_basis
    assert editor.try_edit_comma_basis_text("nonsense") is False
    assert editor.try_edit_comma_basis_text("⟨1 0 0]") is False  # a map, not a vector
    assert editor.state.comma_basis == before

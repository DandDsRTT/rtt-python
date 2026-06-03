"""Editor view-model contract tests.

Behavioral scenarios (expand/shrink/change/undo) are covered by
test_web_integration.py; here we pin the Editor's own state-machine contract:
the initial state, undo availability, and the shrink guard.
"""

from fractions import Fraction

from rtt.web import service, settings, spreadsheet
from rtt.web.editor import INITIAL_COLLAPSED, INITIAL_MAPPING, Editor


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
    assert service.prescaler_of(editor.tuning_scheme) == "log-prime"  # the default
    editor.set_complexity_prescaler("prime")  # the alt.-complexity control (box 𝐋)
    assert service.prescaler_of(editor.tuning_scheme) == "prime"
    # and the swap flows into the prescaling matrix: sopfr's diagonal IS the primes
    lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                            tuning_scheme=editor.tuning_scheme)
    on = {c.id: c.text for c in lay.cells}
    assert on["cell:prescaling:primes:0:0"] == "2"  # the diagonal (row i, prime column i)
    assert on["cell:prescaling:primes:1:1"] == "3"
    assert on["cell:prescaling:primes:2:2"] == "5"


def test_custom_prescaler_starts_unset_and_is_a_diagonal_d_tuple():
    # the editor stores a "custom prescaler" override (the diagonal of 𝐿) the bare prescaler
    # tile's editable cells write to. Unset by default — every downstream calculation falls
    # back to the scheme's computed prescaler (the trait-driven log_prime / prime / identity
    # diagonals); set, the override drives the matrix display AND the tuning math
    editor = Editor()
    assert editor.custom_prescaler is None  # nothing typed yet -> scheme controls everything


def test_set_custom_prescaler_entry_seeds_then_edits_one_diagonal_cell():
    # the editor exposes a single-cell setter the bare prescaler tile's input cells call on
    # change. The first write seeds the diagonal from the current scheme's prescaler so the
    # unedited cells keep their displayed values (no silent reset to zeros); the seed is the
    # d-tuple complexity_prescaler returns for the live scheme
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 7.5)
    seed = service.complexity_prescaler(editor.state.mapping, service.DEFAULT_TUNING_SCHEME)
    assert editor.custom_prescaler == (seed[0], 7.5, seed[2])
    editor.set_custom_prescaler_entry(2, 11.0)  # a second edit keeps the first
    assert editor.custom_prescaler == (seed[0], 7.5, 11.0)


def test_clear_custom_prescaler_reverts_to_the_scheme():
    editor = Editor()
    editor.set_custom_prescaler_entry(0, 4.0)
    assert editor.custom_prescaler is not None
    editor.clear_custom_prescaler()
    assert editor.custom_prescaler is None  # the cells revert to the scheme's diagonal


def test_picking_a_preset_prescaler_clears_the_custom_override():
    # the prescaler preset is the user's reset path: picking "log-prime" / "prime" /
    # "identity" CLEARS the custom override AND swaps the scheme's prescaler trait, so the
    # cells go back to the scheme's computed diagonal
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 9.9)
    editor.set_complexity_prescaler("prime")
    assert editor.custom_prescaler is None  # picking a preset wipes the override
    assert service.prescaler_of(editor.tuning_scheme) == "prime"


def test_picking_a_predefined_complexity_clears_the_custom_override():
    # the predefined-complexity master chooser (box 𝒄) likewise reaches into the prescaler
    # (each named complexity carries its own prescaler), so it too clears any custom diagonal
    editor = Editor()
    editor.set_custom_prescaler_entry(0, 3.3)
    editor.set_complexity_name("sopfr")  # sopfr brings the prime-diagonal prescaler in
    assert editor.custom_prescaler is None
    assert service.prescaler_of(editor.tuning_scheme) == "prime"


def test_displayed_prescaler_name_tracks_the_scheme_and_falls_back_on_a_manual_edit():
    # the prescaler preset mirrors editor.displayed_prescaler_name: the scheme's prescaler
    # while untouched, then "-" (None) once a manual diagonal edit deviates from it — the same
    # fallback the tuning-scheme chooser uses for a hand-edited generator tuning
    editor = Editor()
    assert editor.displayed_prescaler_name == "log-prime"  # the default scheme's prescaler
    editor.set_custom_prescaler_entry(1, 9.9)  # a deviating hand-edit
    assert editor.displayed_prescaler_name is None
    editor.clear_custom_prescaler()
    assert editor.displayed_prescaler_name == "log-prime"  # reverts with the override gone


def test_round_trip_prescaler_edit_returns_to_the_scheme_name():
    # deviate one cell, then type its SHOWN value back (what the user actually does). The cell shows
    # the rounded value, so the stored diagonal isn't bit-identical to the scheme's, but it displays
    # the same — so displayed_prescaler_name must recover "log-prime" (and the grid's 𝑋 = 𝐿 awareness)
    editor = Editor()
    shown = float(service.prescale_text(
        service.complexity_prescaler(editor.state.mapping, editor.tuning_scheme)[1]))
    editor.set_custom_prescaler_entry(1, 9.9)     # deviate
    assert editor.displayed_prescaler_name is None
    editor.set_custom_prescaler_entry(1, shown)   # return it to the shown log-prime value
    assert editor.displayed_prescaler_name == "log-prime"


def test_set_custom_prescaler_text_holds_a_typed_diagonal():
    # the bare prescaler 𝐿 tile's editable plain text (the matrix-form EBK) parses to a
    # d-tuple diagonal, replaces the override wholesale (the d-1 untouched cells take the
    # typed values, NOT a re-seed from the scheme), and is undoable like the other duals.
    editor = Editor()
    ok = editor.set_custom_prescaler_text("[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩")
    assert ok is True
    assert editor.custom_prescaler == (1.0, 4.0, 2.322)
    # undoable like the other typed-text setters
    editor.undo()
    assert editor.custom_prescaler is None
    editor.redo()
    assert editor.custom_prescaler == (1.0, 4.0, 2.322)


def test_set_custom_prescaler_text_rejects_unparseable_or_malformed_input():
    # an unparseable / wrong-shape / non-diagonal string leaves the override (and the
    # undo stack) untouched, so the caller can redden the input box rather than mangle 𝐿.
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 7.5)  # establish a non-None starting state
    before = editor.custom_prescaler
    undo_steps_before = editor.can_undo
    assert editor.set_custom_prescaler_text("garbage") is False
    assert editor.custom_prescaler == before  # unchanged after the rejected edit
    # an off-diagonal nonzero is malformed (𝐿 is diagonal), so it too is rejected
    assert editor.set_custom_prescaler_text("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩") is False
    assert editor.custom_prescaler == before
    # the wrong size (a 2×2 matrix when d == 3) is rejected
    assert editor.set_custom_prescaler_text("[⟨1 0] ⟨0 2]⟩") is False
    assert editor.custom_prescaler == before
    assert editor.can_undo == undo_steps_before  # no redundant undo step on a rejection


def test_custom_prescaler_edits_are_undoable():
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 7.5)
    assert editor.can_undo is True  # writing to a cell is a document change
    editor.undo()
    assert editor.custom_prescaler is None  # undo reverts the edit
    editor.redo()
    assert editor.custom_prescaler is not None and editor.custom_prescaler[1] == 7.5


def test_set_complexity_euclidean_switches_the_complexity_norm():
    editor = Editor()
    assert service.is_euclidean(editor.tuning_scheme) is False  # taxicab default
    editor.set_complexity_euclidean(True)  # the alt.-complexity control (box 𝒄)
    assert service.is_euclidean(editor.tuning_scheme) is True
    editor.set_complexity_euclidean(False)
    assert service.is_euclidean(editor.tuning_scheme) is False


def test_set_complexity_name_sets_the_whole_complexity_shape():
    editor = Editor()
    assert service.complexity_name_of(editor.tuning_scheme) == "lp"  # default
    editor.set_complexity_name("sopfr")  # the predefined-complexities master chooser (box 𝒄)
    assert service.complexity_name_of(editor.tuning_scheme) == "sopfr"
    assert service.prescaler_of(editor.tuning_scheme) == "prime"  # sopfr's prescaler flowed in
    editor.set_complexity_name("lols")  # holds the octave just
    assert service.held_intervals(editor.tuning_scheme) == ("2/1",)


def test_set_diminuator_replaced_toggles_the_size_factor():
    editor = Editor()
    assert service.diminuator_replaced(editor.tuning_scheme) is False  # lp default uses it
    editor.set_diminuator_replaced(True)  # the box-𝐋 "replace diminuator" checkbox: lp -> lils
    assert service.diminuator_replaced(editor.tuning_scheme) is True
    editor.set_diminuator_replaced(False)
    assert service.diminuator_replaced(editor.tuning_scheme) is False


def test_set_all_interval_toggles_the_scheme_target_set():
    editor = Editor()
    assert service.is_all_interval(editor.tuning_scheme) is False  # all-interval OFF by default
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # target-based default is unity-weighted
    # the unchecked state targets the displayed interval-list family (the editor's live target spec)
    assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
    editor.set_all_interval(True)  # the target-controls checkbox: switch to all-interval
    assert service.is_all_interval(editor.tuning_scheme) is True
    # an all-interval scheme is simplicity-weighted by construction, so the toggle forces it
    assert editor.displayed_tuning_scheme_name == "minimax-S"
    assert service.weight_slope_of(editor.tuning_scheme) == "simplicity-weight"
    editor.set_all_interval(False)  # back to target-based -> the unity-weighted default
    assert service.is_all_interval(editor.tuning_scheme) is False
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
    editor.undo()  # the toggle is an undoable edit
    assert service.is_all_interval(editor.tuning_scheme) is True


def test_set_tuning_scheme_preserves_the_target_mode():
    # picking a scheme from the chooser keeps the current target mode (the all-interval checkbox):
    # target-based by default (the chooser's T-prefixed entries), all-interval once the box is on
    editor = Editor()
    editor.set_tuning_scheme("minimax-ES")  # target-based by default => over the target list
    assert not service.is_all_interval(editor.tuning_scheme)
    assert editor.displayed_tuning_scheme_name == "minimax-ES"  # named (chooser shows "T minimax-ES")
    assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
    editor.set_all_interval(True)  # switch to all-interval
    editor.set_tuning_scheme("minimax-S")  # now applies all-interval (bare name)
    assert service.is_all_interval(editor.tuning_scheme)
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def test_set_weight_slope_swaps_the_damage_weight_slope():
    editor = Editor()
    assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"  # minimax-U default
    # the default unity weight makes every target weight 1
    flat = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                             tuning_scheme=editor.tuning_scheme)
    assert all(c.text == "1.000" for c in flat.cells if c.id.startswith("weight:target:"))
    # the weight box's damage-weight-slope chooser swaps it; simplicity weight makes each weight
    # 1/complexity, so they are no longer all 1
    editor.set_weight_slope("simplicity-weight")
    assert service.weight_slope_of(editor.tuning_scheme) == "simplicity-weight"
    lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True},
                            tuning_scheme=editor.tuning_scheme)
    weights = [c.text for c in lay.cells if c.id.startswith("weight:target:")]
    assert weights and not all(w == "1.000" for w in weights)


def test_the_weighting_choosers_are_undoable_like_every_other_change():
    # the weight-slope / predefined-complexity / ignore-diminuator choosers are document
    # changes like the other alt.-complexity controls, so they join the one undo history
    editor = Editor()
    editor.set_weight_slope("simplicity-weight")  # off the unity default
    assert editor.can_undo is True
    editor.undo()
    assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"  # reverted to the default
    editor.set_complexity_name("sopfr")
    editor.undo()
    assert service.complexity_name_of(editor.tuning_scheme) == "lp"  # reverted
    editor.set_diminuator_replaced(True)
    editor.undo()
    assert service.diminuator_replaced(editor.tuning_scheme) is False  # reverted


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
    assert editor.tuning_scheme == service.DEFAULT_DOCUMENT_SCHEME  # target-based, unity-weighted
    assert service.is_all_interval(editor.tuning_scheme) is False  # all-interval OFF by default
    assert editor.target_spec == "TILT"


def test_selecting_a_tuning_scheme_and_target_spec_updates_them():
    editor = Editor()
    editor.set_tuning_scheme("destretched-octave minimax-ES")
    editor.set_target_spec("OLD")
    assert service.base_scheme_name(editor.tuning_scheme) == "destretched-octave minimax-ES"
    assert editor.target_spec == "OLD"
    # target-based: the scheme tracks the chosen family (its target set follows the displayed list)
    assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == "OLD"


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


def test_scheme_and_target_spec_changes_are_undoable():
    # the whole document is one undo history: selecting a tuning scheme or target set
    # is an undoable change, reverted by undo and reapplied by redo
    editor = Editor()
    editor.set_tuning_scheme("held-octave minimax-ES")
    assert editor.can_undo is True
    editor.set_target_spec("OLD")
    editor.undo()
    assert editor.target_spec == "TILT"  # undo reverts the target choice
    editor.undo()
    assert service.base_scheme_name(editor.tuning_scheme) \
        == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)  # ...then the scheme
    editor.redo()
    assert service.base_scheme_name(editor.tuning_scheme) == "held-octave minimax-ES"  # redo reapplies it


def test_range_mode_starts_monotone_and_is_undoable():
    # which generator tuning range the ranges chart shows (monotone vs tradeoff) starts
    # at a default, is settable, and — like every document change — is undoable
    editor = Editor()
    assert editor.range_mode == "monotone"
    editor.set_range_mode("tradeoff")
    assert editor.range_mode == "tradeoff"
    assert editor.can_undo is True  # choosing a range mode is an undoable change
    editor.undo()
    assert editor.range_mode == "monotone"  # undo reverts the mode


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


def test_add_remove_generator_change_rank_and_dimensionality():
    editor = Editor()  # meantone, d=3 r=2 n=1
    editor.add_generator()
    assert (editor.state.r, editor.state.d, editor.state.n) == (3, 4, 1)  # +r, +d, n held
    assert editor.state.domain_basis == (2, 3, 5, 7)  # the new prime joins the domain
    editor.remove_generator()
    assert (editor.state.r, editor.state.d, editor.state.n) == (2, 3, 1)  # back, −r −d
    editor.undo()
    assert editor.state.d == 4  # each is a single undoable step


def test_generator_controls_are_inert_on_a_nonstandard_domain():
    # adding a generator picks the next standard prime, so (like the domain ±) it must
    # leave a nonprime subgroup untouched rather than silently reverting it to a prime limit
    editor = Editor()
    editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    before = editor.state
    assert editor.can_add_generator is False and editor.can_remove_generator is False
    editor.add_generator()
    editor.remove_generator()
    assert editor.state is before  # unchanged by either control


def test_cannot_remove_the_sole_generator():
    editor = Editor()
    editor.edit_mapping(((1, 0, 0),))  # a rank-1 temperament
    assert editor.can_remove_generator is False  # nothing to remove down to rank 0
    assert editor.can_add_generator is True  # ...but you can still add one


def test_add_remove_mapping_row_change_rank_holding_dimensionality():
    editor = Editor()  # meantone, d=3 r=2 n=1
    editor.remove_mapping_row(0)  # drop a generator (any row)
    assert (editor.state.r, editor.state.d, editor.state.n) == (1, 3, 2)  # −r, +n, d held
    editor.add_mapping_row()  # un-temper a comma
    assert (editor.state.r, editor.state.d, editor.state.n) == (2, 3, 1)  # +r, −n, d held
    editor.undo()
    assert editor.state.r == 1  # each is a single undoable step


def test_mapping_row_guards():
    editor = Editor()
    editor.edit_mapping(((1, 0, 0),))  # rank-1, d=3, n=2
    assert editor.can_remove_mapping_row is False  # can't drop the sole row
    assert editor.can_add_mapping_row is True  # ...n>0, a comma to un-temper
    editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))  # JI, n=0
    assert editor.can_add_mapping_row is False  # nothing tempered to un-temper


def test_add_and_remove_target_set_a_manual_override():
    editor = Editor()  # default TILT targets, no manual override yet
    assert editor.target_override is None
    n = len(service.target_interval_set(editor.target_spec, editor.state.domain_basis))
    editor.remove_target(0)  # drop the first target → materializes the spec list as an override
    assert editor.target_override is not None and len(editor.target_override) == n - 1
    editor.add_target()  # start a blank draft (no override change yet)
    assert editor.pending_target == [None, None, None] and len(editor.target_override) == n - 1
    editor.set_pending_target([-1, 1, 0])  # fill it in -> commits 3/2 to the override
    assert len(editor.target_override) == n and editor.target_override[-1] == "3/2"
    editor.undo()  # undo the commit...
    assert len(editor.target_override) == n - 1
    editor.undo()  # ...then the remove — each committed ± is a single undoable step
    assert editor.target_override is None


def test_adding_a_target_starts_a_blank_pending_draft():
    editor = Editor()
    assert editor.pending_target is None
    editor.add_target()
    assert editor.pending_target == [None, None, None]  # a blank d-length draft
    assert editor.target_override is None  # not committed (the spec set is untouched)
    assert editor.can_undo is False  # starting a draft is not an undoable edit


def test_a_partly_filled_target_draft_is_held_until_complete():
    editor = Editor()
    n = len(service.target_interval_set(editor.target_spec, editor.state.domain_basis))
    editor.add_target()
    editor.set_pending_target([-1, None, 0])  # still being typed
    assert editor.pending_target == [-1, None, 0] and editor.target_override is None  # held
    editor.set_pending_target([-1, 1, 0])  # complete -> materializes the set + commits 3/2
    assert editor.pending_target is None and editor.target_override[-1] == "3/2"
    assert len(editor.target_override) == n + 1
    assert editor.can_undo is True  # the commit is the undoable edit


def test_cancelling_a_target_draft_discards_it():
    editor = Editor()
    editor.add_target()
    editor.cancel_pending_target()
    assert editor.pending_target is None and editor.target_override is None
    assert editor.can_undo is False  # cancelling a draft is not an undoable edit


def test_interest_intervals_add_edit_remove():
    editor = Editor()
    assert editor.interest_vectors == []  # starts empty
    editor.add_interest()
    assert editor.interest_vectors == []  # add only starts a blank draft (no committed 1/1)...
    assert editor.pending_interest == [None, None, None]  # ...a red, blank, d-length draft
    editor.set_pending_interest([-1, 1, 0])  # fill it in -> commits 3/2
    assert editor.interest_vectors == [(-1, 1, 0)] and editor.pending_interest is None
    editor.set_interest_vectors([[-1, 1, 0], [2, 0, -1]])  # editing existing cells replaces the set
    assert editor.interest_vectors == [(-1, 1, 0), (2, 0, -1)]
    editor.remove_interest(0)
    assert editor.interest_vectors == [(2, 0, -1)]


def test_adding_an_interval_of_interest_starts_a_blank_pending_draft():
    # like add_comma: a blank, red-outlined draft column the user fills in, NOT a committed
    # 1/1. Starting it touches neither the document nor the undo history.
    editor = Editor()
    assert editor.pending_interest is None
    editor.add_interest()
    assert editor.pending_interest == [None, None, None]  # a blank d-length draft
    assert editor.interest_vectors == []  # not committed
    assert editor.can_undo is False  # starting a draft is not an undoable edit


def test_a_partly_filled_interest_draft_is_held_until_complete():
    editor = Editor()
    editor.add_interest()
    editor.set_pending_interest([-1, None, 0])  # still being typed
    assert editor.pending_interest == [-1, None, 0] and editor.interest_vectors == []  # held
    editor.set_pending_interest([-1, 1, 0])  # complete -> commits 3/2 and clears the draft
    assert editor.pending_interest is None and editor.interest_vectors == [(-1, 1, 0)]
    assert editor.can_undo is True  # the commit is the undoable edit


def test_cancelling_an_interval_of_interest_draft_discards_it():
    editor = Editor()
    editor.add_interest()
    editor.cancel_pending_interest()
    assert editor.pending_interest is None and editor.interest_vectors == []
    assert editor.can_undo is False  # cancelling a draft is not an undoable edit


def test_interest_intervals_changes_are_undoable():
    # the interest set is part of the one document history: committing a filled-in draft (or
    # editing an existing interval) is an undoable change; starting the blank draft is not
    editor = Editor()
    editor.add_interest()
    assert editor.can_undo is False  # starting the blank draft is not undoable...
    editor.set_pending_interest([-1, 1, 0])  # ...committing the filled-in draft is
    assert editor.can_undo is True
    editor.undo()
    assert editor.interest_vectors == []  # undo reverts the committed interval


def test_held_intervals_add_edit_remove():
    editor = Editor()
    assert editor.held_vectors == []  # starts empty
    editor.add_held()
    assert editor.held_vectors == []  # add only starts a blank draft (no committed 1/1)...
    assert editor.pending_held == [None, None, None]  # ...a red, blank, d-length draft
    editor.set_pending_held([1, 0, 0])  # fill it in -> holds the octave
    assert editor.held_vectors == [(1, 0, 0)] and editor.pending_held is None
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])  # editing existing cells replaces the set
    assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]
    editor.remove_held(0)
    assert editor.held_vectors == [(-1, 1, 0)]


def test_adding_a_held_interval_starts_a_blank_pending_draft():
    editor = Editor()
    assert editor.pending_held is None
    editor.add_held()
    assert editor.pending_held == [None, None, None]  # a blank d-length draft
    assert editor.held_vectors == []  # not committed
    assert editor.can_undo is False  # starting a draft is not an undoable edit


def test_a_partly_filled_held_draft_is_held_until_complete():
    editor = Editor()
    editor.add_held()
    editor.set_pending_held([1, None, 0])  # still being typed
    assert editor.pending_held == [1, None, 0] and editor.held_vectors == []  # held
    editor.set_pending_held([1, 0, 0])  # complete -> holds the octave and clears the draft
    assert editor.pending_held is None and editor.held_vectors == [(1, 0, 0)]
    assert editor.can_undo is True  # the commit is the undoable edit


def test_cancelling_a_held_interval_draft_discards_it():
    editor = Editor()
    editor.add_held()
    editor.cancel_pending_held()
    assert editor.pending_held is None and editor.held_vectors == []
    assert editor.can_undo is False  # cancelling a draft is not an undoable edit


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


def test_optimize_button_freezes_the_tuning_and_lock_toggles_auto():
    editor = Editor()
    # default: lock off, nothing frozen yet -> the grid shows the auto optimum (None)
    assert editor.optimize_locked is False
    assert editor.effective_generator_tuning() is None
    # single click optimizes once: the generator tuning freezes at the current optimum
    editor.optimize()
    frozen = editor.effective_generator_tuning()
    assert frozen is not None and len(frozen) == editor.state.r
    # double click locks auto-optimize on -> back to the auto optimum (None)
    editor.toggle_optimize_lock()
    assert editor.optimize_locked is True
    assert editor.effective_generator_tuning() is None
    # double click again unlocks -> freezes at the optimum again
    editor.toggle_optimize_lock()
    assert editor.optimize_locked is False
    assert editor.effective_generator_tuning() is not None


def test_set_generator_tuning_text_freezes_a_typed_genmap():
    editor = Editor()
    # typing a valid cents genmap freezes it as the manual tuning, with auto-optimize off
    assert editor.set_generator_tuning_text("{1200.000 701.955]") is True
    assert editor.effective_generator_tuning() == (1200.0, 701.955)
    assert editor.optimize_locked is False
    assert editor.can_undo is True
    # an auto-locked editor: typing a tuning turns the lock off (manual vs auto are exclusive)
    locked = Editor()
    locked.toggle_optimize_lock()
    assert locked.optimize_locked is True
    locked.set_generator_tuning_text("{1200 700]")
    assert locked.optimize_locked is False
    assert locked.effective_generator_tuning() == (1200.0, 700.0)
    # the wrong count or junk is rejected, leaving the tuning untouched
    assert editor.set_generator_tuning_text("{1200]") is False  # one value, need two
    assert editor.set_generator_tuning_text("garbage") is False
    assert editor.effective_generator_tuning() == (1200.0, 701.955)


def test_set_generator_tuning_component_overrides_one_generator():
    editor = Editor()
    optimum = editor._optimum_generator_tuning()
    # with nothing frozen, editing one generator seeds the rest from the current optimum
    editor.set_generator_tuning_component(1, 700.0)
    eff = editor.effective_generator_tuning()
    assert eff[1] == 700.0 and eff[0] == optimum[0]
    assert editor.optimize_locked is False and editor.can_undo is True


def test_displayed_tuning_scheme_name_drops_to_none_when_the_tuning_deviates():
    # the tuning chooser shows the scheme name only while the displayed tuning realises that
    # scheme; once it deviates the name drops to None (the chooser then shows "-").
    editor = Editor()
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # default: the scheme's own optimum
    # hand-editing the generator tuning map off the optimum is a deviation
    editor.set_generator_tuning_component(1, 700.0)
    assert editor.displayed_tuning_scheme_name is None
    # a control-refined scheme (a finite optimization power) has no name either
    fresh = Editor()
    fresh.set_optimization_power(2.0)
    assert fresh.displayed_tuning_scheme_name is None


def test_displayed_tuning_scheme_name_keeps_the_name_when_the_tuning_still_matches():
    # freezing at the scheme's optimum (the optimize button) is not a deviation — the frozen
    # tuning equals the optimum — so the name stays.
    editor = Editor()
    editor.optimize()
    assert editor.effective_generator_tuning() is not None  # a tuning is frozen
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    # a stale frozen tuning the grid ignores (its generator count no longer fits the mapping,
    # here after the domain expands and re-ranks) also keeps the name — the grid then shows the
    # scheme's optimum, not the stale override
    editor.expand()
    assert len(editor.effective_generator_tuning()) != editor.state.r
    assert editor.displayed_tuning_scheme_name == "minimax-U"


def test_displayed_tuning_scheme_name_drops_to_none_when_a_held_interval_deviates_the_tuning():
    # adding a held interval re-optimizes the tuning to hold it just; when that pulls the tuning
    # off the BARE scheme's optimum, the displayed tuning no longer realises the established scheme,
    # so the chooser must show "-". Regression: the deviation check only watched a manual generator
    # override against the held-AWARE optimum, so a held-interval-induced deviation slipped through
    # and the name wrongly stuck.
    editor = Editor()
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    editor.set_held_vectors([(-1, 1, 0)])  # hold 3/2 -> pulls the tuning off bare minimax-U
    assert editor.displayed_tuning_scheme_name is None
    # a held interval the bare scheme ALREADY satisfies (the octave, tuned pure by minimax-U) is
    # not a deviation — the optimum is unchanged — so the name stays
    octave = Editor()
    octave.set_held_vectors([(1, 0, 0)])
    assert octave.displayed_tuning_scheme_name == "minimax-U"


def test_displayed_tuning_scheme_name_keeps_the_name_with_a_typed_target_list():
    # a typed explicit target list changes WHICH intervals the scheme optimises over, but it is
    # still the same named scheme (the target set is a separate control from the tuning scheme),
    # so the chooser keeps the name — not "-". The bare-scheme comparison must therefore optimise
    # over the SAME typed target list as the displayed tuning, else a typed list reads as a false
    # deviation.
    editor = Editor()
    editor.set_target_override_vectors([(-1, 1, 0), (-2, 0, 1)])  # type 3/2, 5/4 as the target list
    assert editor.target_override == ("3/2", "5/4")
    assert editor.displayed_tuning_scheme_name == "minimax-U"


def test_set_tuning_scheme_clears_a_manual_generator_tuning_override():
    # picking a scheme from the chooser means "tune to this scheme": any manual generator-tuning
    # override (a hand-edited generator tuning map) is dropped, snapping back to the scheme's
    # optimum — so re-selecting the scheme after deviating actually re-applies it.
    editor = Editor()
    editor.set_generator_tuning_component(1, 700.0)  # deviate from the optimum
    assert editor.displayed_tuning_scheme_name is None
    editor.set_tuning_scheme("minimax-S")  # re-apply the scheme from the chooser
    assert editor.effective_generator_tuning() is None  # override cleared -> the scheme's optimum
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def test_tuning_is_optimized_tracks_whether_the_grid_shows_the_optimum():
    # the objective wraps in min() only while the displayed tuning sits at the scheme's optimum.
    editor = Editor()
    assert editor.tuning_is_optimized is True  # default: the grid shows the freshly-computed optimum
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit a generator off the optimum
    assert editor.tuning_is_optimized is False
    editor.optimize()  # the optimize button snaps back to the optimum
    assert editor.tuning_is_optimized is True


def test_tuning_is_optimized_holds_under_the_auto_lock_and_held_intervals():
    # auto-optimize (the lock) recomputes the optimum on every change, so it is always optimized
    locked = Editor()
    locked.toggle_optimize_lock()
    assert locked.optimize_locked and locked.tuning_is_optimized is True
    # a held interval re-optimizes to a held-CONSTRAINED optimum — still optimized (unlike the
    # scheme NAME, which drops to "-" because the held tuning leaves the bare scheme), so min() stays
    held = Editor()
    held.add_held()
    held.set_held_vectors([(-1, 1, 0)])  # hold 3/2
    assert held.displayed_tuning_scheme_name is None  # the name leaves the bare scheme...
    assert held.tuning_is_optimized is True            # ...but the displayed tuning is its optimum
    held.set_generator_tuning_component(1, 700.0)      # hand-edit off the held optimum
    assert held.tuning_is_optimized is False


def test_layout_wraps_the_objective_symbol_in_min_while_optimized():
    # end to end: the editor feeds tuning_is_optimized into the layout, so the rendered objective
    # symbol carries the min() wrap while optimized and drops it after a manual generator deviation.
    editor = Editor()
    editor.set_show("optimization", True)

    def objective_symbol() -> str:
        return {c.id: c for c in editor.layout().cells}["optimization:objective:symbol"].text

    assert objective_symbol() == "min(⟪𝐝⟫ₚ)"  # default: the displayed tuning is the scheme's optimum
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit a generator off the optimum
    assert objective_symbol() == "⟪𝐝⟫ₚ"


def test_set_target_override_text_and_vectors():
    editor = Editor()
    # typing a vector list overrides the target set with those intervals, stored as ratios
    assert editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩") is True
    assert editor.target_override == ("2/1", "3/2")
    assert editor.can_undo is True
    # junk is rejected, leaving the override untouched
    assert editor.set_target_override_text("garbage") is False
    assert editor.target_override == ("2/1", "3/2")
    # editing the vector grid sets the override from the typed columns (2^2 = 4/1, 5^1 = 5/1)
    editor.set_target_override_vectors([[2, 0, 0], [0, 0, 1]])
    assert editor.target_override == ("4/1", "5/1")


def test_choosing_a_target_spec_or_changing_domain_clears_the_target_override():
    editor = Editor()
    editor.set_target_override_text("[1 0 0⟩")
    assert editor.target_override is not None
    editor.set_target_spec("OLD")  # the chooser and the manual list are alternatives
    assert editor.target_override is None
    # a domain change also resets the (domain-specific) manual list to the new default
    editor.set_target_override_text("[1 0 0⟩")
    editor.expand()
    assert editor.target_override is None


def test_target_override_round_trips_serialize_and_older_docs_lack_it():
    editor = Editor()
    editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")
    data = editor.serialize()
    fresh = Editor()
    fresh.load(data)
    assert fresh.target_override == ("2/1", "3/2")
    del data["target_override"]  # a doc saved before the override existed loads as None
    older = Editor()
    older.load(data)
    assert older.target_override is None


def test_optimize_follows_a_changed_target_interval_list():
    # the optimize button minimizes damage over the target intervals, so changing the list must
    # retune. Before, the optimum ignored a typed override (it read the scheme's named TILT set),
    # so re-optimizing after editing the list was a no-op — the bug Douglas hit.
    editor = Editor()
    editor.optimize()  # freeze the TILT-family optimum
    tilt_optimum = editor.generator_tuning
    editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")  # change the list to just 2/1 + 3/2
    editor.optimize()  # re-optimize over the new list
    assert editor.generator_tuning != tilt_optimum  # the tuning followed the new targets


def test_show_settings_start_at_defaults_and_changes_are_undoable():
    editor = Editor()
    assert editor.settings == settings.defaults()  # the Editor owns the Show settings
    editor.set_show("charts", True)
    assert editor.settings["charts"] is True
    assert editor.can_undo is True  # toggling a Show setting is an undoable change
    editor.undo()
    assert editor.settings["charts"] is False
    editor.redo()
    assert editor.settings["charts"] is True


def test_select_all_then_none_over_implemented_toggles():
    editor = Editor()
    editor.set_all_show(True)  # the panel's select-all
    assert all(editor.settings[k] for k in settings.IMPLEMENTED)
    editor.set_all_show(False)  # ...and select-none
    assert not any(editor.settings[k] for k in settings.IMPLEMENTED)
    editor.undo()  # one undo restores the whole all-on set (a single action)
    assert all(editor.settings[k] for k in settings.IMPLEMENTED)


def test_deselecting_a_parent_also_deselects_its_subcontrols():
    # a hidden parent must not leave its sub-controls' content stranded on screen:
    # deselecting "temperament boxes" turns its "colorization" sub-control off too
    editor = Editor()
    editor.set_show("temperament_colorization", True)
    assert editor.settings["temperament_colorization"] is True
    editor.set_show("temperament_boxes", False)
    assert editor.settings["temperament_boxes"] is False
    assert editor.settings["temperament_colorization"] is False


def test_deselecting_a_parent_cascades_through_nested_subcontrols():
    # the cascade is transitive: "tuning boxes" -> "weighting" -> "all-interval"/"alt.
    # complexity", so deselecting the grandparent turns the grandchildren off too (else
    # their panel rows orphan and their content lingers when the grandparent is hidden)
    editor = Editor()
    for key in ("weighting", "all_interval", "alt_complexity", "tuning_ranges", "optimization"):
        editor.set_show(key, True)
    editor.set_show("tuning_boxes", False)
    for key in ("tuning_boxes", "weighting", "all_interval", "alt_complexity",
                "tuning_ranges", "optimization"):
        assert editor.settings[key] is False


def test_the_subcontrol_cascade_is_one_undoable_action():
    editor = Editor()
    editor.set_show("temperament_colorization", True)
    editor.set_show("temperament_boxes", False)  # deselects parent + sub-control together
    assert editor.settings["temperament_colorization"] is False
    editor.undo()  # a single undo brings the parent AND its sub-control back
    assert editor.settings["temperament_boxes"] is True
    assert editor.settings["temperament_colorization"] is True


def test_selecting_a_parent_does_not_force_its_subcontrols_on():
    # only deselecting cascades; re-selecting a parent leaves the (now-off) sub-controls
    # off rather than resurrecting them
    editor = Editor()
    editor.set_show("temperament_boxes", False)
    editor.set_show("temperament_boxes", True)
    assert editor.settings["temperament_colorization"] is False


def test_selecting_a_subcontrol_pulls_its_parent_on():
    # the mirror of the off-cascade: a refinement can't show without the layer it refines, so
    # selecting it pulls the parent on too (equivalences shows symbols as equations, mnemonics
    # underlines a name). Enabling equivalences/mnemonics therefore enables symbols/names.
    editor = Editor()
    assert editor.settings["symbols"] is False
    editor.set_show("equivalences", True)
    assert editor.settings["equivalences"] is True
    assert editor.settings["symbols"] is True  # pulled on with its refinement
    editor.set_show("names", False)  # cascades mnemonics off
    editor.set_show("mnemonics", True)
    assert editor.settings["names"] is True  # pulled back on with its refinement


def test_selecting_a_nested_subcontrol_pulls_its_whole_parent_chain_on():
    # the pull-on is transitive, mirroring the off-cascade: "all-interval" -> "weighting" ->
    # "tuning boxes", so selecting the grandchild pulls both ancestors on (else it would show
    # while the box it lives in stays hidden)
    editor = Editor()
    editor.set_show("tuning_boxes", False)  # cascades the whole tuning column off
    assert editor.settings["weighting"] is False
    editor.set_show("all_interval", True)
    for key in ("all_interval", "weighting", "tuning_boxes"):
        assert editor.settings[key] is True


def test_expand_collapse_state_is_owned_and_undoable():
    editor = Editor()
    # the commas/interest columns and the vectors row start folded (the mockup default)
    assert editor.collapsed == set(INITIAL_COLLAPSED)
    editor.toggle_collapsed("col:commas")  # unfold the commas column
    assert "col:commas" not in editor.collapsed
    assert editor.can_undo is True  # folding/unfolding is an undoable change
    editor.undo()
    assert "col:commas" in editor.collapsed
    editor.set_collapsed({"row:tuning"})  # the master expand/collapse-all replaces the set
    assert editor.collapsed == {"row:tuning"}
    editor.undo()
    assert "col:commas" in editor.collapsed  # back to the prior fold state


def test_reset_restores_every_default_as_one_undoable_action():
    editor = Editor()
    assert editor.can_reset is False  # a fresh editor is already at the defaults
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])  # a value change
    editor.set_tuning_scheme("held-octave minimax-ES")  # a view selection
    editor.set_show("charts", True)               # a Show setting
    editor.toggle_collapsed("col:commas")         # an expand/collapse change
    assert editor.can_reset is True
    editor.reset()
    assert editor.state.mapping == INITIAL_MAPPING
    assert service.base_scheme_name(editor.tuning_scheme) \
        == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)
    assert service.is_all_interval(editor.tuning_scheme) is False  # reset restores all-interval OFF
    assert editor.settings == settings.defaults()
    assert "col:commas" in editor.collapsed
    assert editor.can_reset is False
    editor.undo()  # a single undo brings the whole prior document back
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
    assert service.base_scheme_name(editor.tuning_scheme) == "held-octave minimax-ES"
    assert editor.settings["charts"] is True
    assert "col:commas" not in editor.collapsed


def test_serialize_load_round_trips_the_whole_document():
    editor = Editor()
    editor.edit_mapping([[1, 0, -4], [0, 1, 4]])
    editor.set_tuning_scheme("destretched-octave minimax-ES")
    editor.set_target_spec("9-OLD")
    editor.set_interest_vectors([[-1, 1, 0]])
    editor.set_held_vectors([[1, 0, 0]])
    editor.set_range_mode("tradeoff")
    editor.set_show("charts", True)
    editor.toggle_collapsed("col:commas")
    data = editor.serialize()

    restored = Editor()
    restored.load(data)
    assert restored.state.mapping == ((1, 0, -4), (0, 1, 4))
    # the full target-based scheme round-trips (the chosen 9-OLD family is baked into its prefix)
    assert restored.tuning_scheme == "9-OLD destretched-octave minimax-ES"
    assert restored.target_spec == "9-OLD"
    assert restored.interest_vectors == [(-1, 1, 0)]
    assert restored.held_vectors == [(1, 0, 0)]
    assert restored.range_mode == "tradeoff"
    assert restored.settings["charts"] is True
    assert "col:commas" not in restored.collapsed
    assert restored.can_undo is False  # a load is a fresh start, not an undoable step


def test_serialize_survives_the_json_layer_with_an_infinite_optimization_power():
    # minimax uses an infinite Lp power; the JSON layer writes a raw float inf as null,
    # so the scheme is encoded with an "inf" sentinel and decoded back to a real float
    import json

    editor = Editor()
    editor.set_optimization_power(float("inf"))
    data = editor.serialize()
    assert data["tuning_scheme"]["optimization_power"] == "inf"
    json.loads(json.dumps(data))  # the document survives a JSON round-trip (no inf -> null)
    restored = Editor()
    restored.load(data)
    assert service.optimization_power(restored.tuning_scheme) == float("inf")


def test_serialize_load_round_trips_a_finite_power_spec():
    editor = Editor()
    editor.set_optimization_power(2.0)  # miniRMS
    restored = Editor()
    restored.load(editor.serialize())
    assert service.optimization_power(restored.tuning_scheme) == 2.0


def test_serialize_load_round_trips_a_nonstandard_domain():
    editor = Editor()
    editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # Barbados over 2.3.13/5
    restored = Editor()
    restored.load(editor.serialize())
    assert restored.state.domain_basis == (2, 3, Fraction(13, 5))
    assert restored.state.mapping == ((1, 2, 2), (0, -2, -3))


def test_load_tolerates_a_state_saved_before_a_setting_existed():
    # an older saved document may lack a Show key added since; load fills it from defaults
    editor = Editor()
    data = editor.serialize()
    del data["settings"]["charts"]
    restored = Editor()
    restored.load(data)
    assert restored.settings["charts"] is settings.defaults()["charts"]


def test_load_pins_a_shelved_toggle_to_its_default():
    # a saved document can carry a toggle that has since been shelved (pulled from
    # IMPLEMENTED because the feature isn't ready to expose). Loading it must not
    # resurrect that feature: greyed toggles are pinned to their defaults whatever the
    # blob says, so IMPLEMENTED stays the single source of truth for what the grid shows.
    assert "alt_complexity" not in settings.IMPLEMENTED  # precondition: it's shelved
    editor = Editor()
    data = editor.serialize()
    data["settings"]["alt_complexity"] = True  # a value the panel can no longer set
    restored = Editor()
    restored.load(data)
    assert restored.settings["alt_complexity"] is False  # pinned back to its default


def test_load_falls_back_when_the_core_fields_are_missing():
    # mapping_ebk and tuning_scheme must fall back like the other 11 fields rather than
    # raise KeyError — the docstring promises a missing field can't leave a half-loaded
    # state, so a truncated/older blob still loads.
    editor = Editor()
    base = editor.serialize()

    # tuning_scheme absent (mapping present): the scheme falls back to the default and the
    # rest of the document still loads.
    no_scheme = dict(base)
    del no_scheme["tuning_scheme"]
    restored = Editor()
    restored.load(no_scheme)  # must not raise
    assert service.base_scheme_name(restored.tuning_scheme) \
        == service.base_scheme_name(service.DEFAULT_DOCUMENT_SCHEME)

    # both core fields absent: still no raise (an absent mapping just leaves the editor
    # untouched, exactly like an unparseable one).
    both_missing = dict(base)
    del both_missing["mapping_ebk"]
    del both_missing["tuning_scheme"]
    Editor().load(both_missing)  # must not raise

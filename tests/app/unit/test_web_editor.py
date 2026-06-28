"""Editor view-model contract tests.

Behavioral scenarios (expand/shrink/change/undo) are covered by
test_web_integration.py; here we pin the Editor's own state-machine contract:
the initial state, undo availability, and the shrink guard.
"""

from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor


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


def test_set_mapping_form_restores_the_mapping_in_each_generator_form_undoably():
    editor = Editor()  # default meantone ((1,1,0),(0,1,4)) — the equave-reduced form
    editor.set_mapping_form("canonical")
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
    editor.set_mapping_form("mingen")
    assert editor.state.mapping == ((1, 2, 4), (0, -1, -4))
    editor.set_mapping_form("equave-reduced")
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))
    editor.undo()  # each form choice is one undoable edit
    assert editor.state.mapping == ((1, 2, 4), (0, -1, -4))


def test_set_mapping_form_positive_generator_flip_and_shift_differ():
    # sensi's canonical generator is negative, and it is NOT (c−p)-sheared, so its two
    # positive-generator forms differ: flip negates the row, shift period-shifts it positive.
    editor = Editor()
    editor.edit_mapping([[1, 6, 8], [0, 7, 9]])  # sensi, canonical
    editor.set_mapping_form("positive-generator")        # flip
    assert editor.state.mapping == ((1, 6, 8), (0, -7, -9))
    editor.set_mapping_form("positive-generator-shift")  # shift → the wiki's ~9/7-generator form
    assert editor.state.mapping == ((1, -1, -1), (0, 7, 9))
    editor.undo()  # each form choice is one undoable edit
    assert editor.state.mapping == ((1, 6, 8), (0, -7, -9))


def test_edit_form_matrix_restores_the_mapping_in_the_typed_generating_set_undoably():
    # editing the interactive 𝐹 tile re-stores M = F·M_C: the SAME temperament in a new generating set,
    # so the canonical mapping (and comma basis) is unchanged and 𝐹 reads back what was typed. Use a
    # non-involution 𝐹 = ((1,2),(0,1)) so F ≠ F⁻¹ (a real round-trip, not a coincidence).
    editor = Editor()  # default meantone ((1,1,0),(0,1,4)), canonical ((1,0,-4),(0,1,4))
    canon, commas = service.canonical_mapping(editor.state.mapping), editor.state.comma_basis
    assert editor.edit_form_matrix(((1, 2), (0, 1))) is True
    assert editor.state.mapping == ((1, 2, 4), (0, 1, 4))             # M = F·M_C
    assert service.canonical_mapping(editor.state.mapping) == canon    # same temperament...
    assert editor.state.comma_basis == commas                         # ...same commas
    assert service.inverse_form_matrix(editor.state.mapping) == ((1, 2), (0, 1))  # the 𝐹 tile reads back the typed matrix
    editor.undo()  # one undoable edit
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))


def test_edit_form_matrix_rejects_a_non_unimodular_matrix():
    # a typed 𝐹 with det ≠ ±1 isn't a generator-basis change of the same temperament — rejected,
    # leaving the state (and undo stack) untouched, so the caller can redden the box / toast
    editor = Editor()
    before = editor.state
    assert editor.edit_form_matrix(((2, 0), (0, 1))) is False  # det 2 — not unimodular
    assert editor.state is before and editor.can_undo is False
    assert editor.try_edit_form_matrix_text("[{2 0]{0 1]}") is False  # the plain-text path rejects too
    assert editor.try_edit_form_matrix_text("garble") is False        # unparseable
    assert editor.state is before


def test_try_edit_form_matrix_text_parses_and_applies():
    editor = Editor()
    assert editor.try_edit_form_matrix_text("[{1 2]{0 1]}") is True
    assert editor.state.mapping == ((1, 2, 4), (0, 1, 4))  # M = F·M_C


def test_canonicalize_comma_basis_restores_canonical_form_undoably():
    editor = Editor()
    editor.edit_comma_basis([[-8, 8, -2]])  # a non-saturated basis (the syntonic comma doubled)
    editor.canonicalize_comma_basis()
    assert editor.state.comma_basis == ((4, -4, 1),)  # defactored + canonicalized
    editor.undo()
    assert editor.state.comma_basis == ((-8, 8, -2),)  # undoable


def test_set_comma_basis_form_restores_the_comma_basis_in_each_normal_form_undoably():
    editor = Editor()  # default meantone — comma basis canonical [⟨4 -4 1⟩] (80/81, downward)
    assert editor.state.comma_basis == ((4, -4, 1),)
    editor.set_comma_basis_form("positive-ratio")  # flip to the upward 81/80
    assert editor.state.comma_basis == ((-4, 4, -1),)
    assert service.identify_comma_basis_form(editor.state.comma_basis) == "positive-ratio"
    editor.set_comma_basis_form("minimal")  # a single comma's minimal form is itself, made positive
    assert editor.state.comma_basis == ((-4, 4, -1),)
    editor.set_comma_basis_form("canonical")
    assert editor.state.comma_basis == ((4, -4, 1),)
    editor.undo()  # each form choice is one undoable edit
    assert editor.state.comma_basis == ((-4, 4, -1),)


def test_set_comma_basis_form_minimal_simplifies_septimal_meantone():
    editor = Editor()
    editor.edit_comma_basis([[4, -4, 1, 0], [13, -10, 0, 1]])  # septimal meantone, canonical
    editor.set_comma_basis_form("minimal")
    # the wiki's comma list [81/80, 126/125] — simpler than the canonical [81/80, 57344/59049]
    assert editor.state.comma_basis == ((-4, 4, -1, 0), (1, 2, -3, 1))


def _mapping_form_cell(editor) -> str:
    editor.settings["form_controls"] = True  # the <choose form> dropdowns are a Show toggle
    return {c.id: c for c in editor.layout().cells}["formchooser:mapping"].text


def test_mapping_chooser_shows_the_picked_form_even_when_forms_coincide():
    # the mapping analogue of the comma-basis coincidence bug: sensi's shift form ((1,-1,-1),(0,7,9))
    # is ALSO its mingen form, so identify_mapping_form (earliest match wins) would snap the dropdown
    # to "minimal-generator". The explicit pick is sticky — the chooser shows the shift form chosen.
    editor = Editor()
    editor.edit_mapping([[1, 6, 8], [0, 7, 9]])  # sensi, canonical
    editor.set_mapping_form("positive-generator-shift")
    assert editor.state.mapping == ((1, -1, -1), (0, 7, 9))
    # the cell carries the resolved form KEY (the dropdown maps it to its "positive-generator
    # (shift)" label for display); stickiness means it stays on shift, not the coinciding mingen
    assert _mapping_form_cell(editor) == "positive-generator-shift"


def _comma_form_cell(editor) -> str:
    editor.settings["form_controls"] = True  # the <choose form> dropdowns are a Show toggle
    return {c.id: c for c in editor.layout().cells}["formchooser:comma_basis"].text


def test_chooser_shows_the_picked_form_even_when_forms_coincide():
    # the reported bug: meantone's minimal comma form EQUALS its positive-ratio form (a single comma
    # is already minimal), so picking "minimal" used to snap the dropdown to "positive-ratio" (the
    # earlier coinciding option). The pick is now sticky — the chooser shows what the user chose.
    editor = Editor()
    editor.set_comma_basis_form("positive-ratio")
    assert _comma_form_cell(editor) == "positive-ratio"
    editor.set_comma_basis_form("minimal")  # same matrix, different intent
    assert _comma_form_cell(editor) == "minimal"
    # the pick lies DORMANT (not forgotten) while the matrix isn't in it: editing to the canonical
    # 80/81 reads "canonical" because the matrix really is canonical there...
    editor.edit_comma_basis([[4, -4, 1]])  # canonical 80/81 (each comma's sign flipped)
    assert _comma_form_cell(editor) == "canonical"
    # ...and flipping every comma back to 81/80 — the minimal form again — RESTORES "minimal", not
    # the coinciding "positive-ratio" the user never chose (the reported deeper bug)
    editor.edit_comma_basis([[-4, 4, -1]])  # back to 81/80
    assert _comma_form_cell(editor) == "minimal"


def test_chooser_form_pick_survives_undo_and_redo():
    # the pick rides in the document, so undo/redo return the chooser to the form chosen for each
    # state — even when forms coincide (positive-ratio and minimal share meantone's one comma)
    editor = Editor()
    editor.set_comma_basis_form("positive-ratio")
    editor.set_comma_basis_form("minimal")   # coincides with positive-ratio
    editor.set_comma_basis_form("canonical")
    assert _comma_form_cell(editor) == "canonical"
    editor.undo()
    assert _comma_form_cell(editor) == "minimal"         # the most recent pick for this matrix
    editor.undo()
    assert _comma_form_cell(editor) == "positive-ratio"  # the pick before that
    editor.redo()
    assert _comma_form_cell(editor) == "minimal"         # redo restores it going forward


def test_set_complexity_prescaler_swaps_the_weighting_prescaler_into_the_layout():
    editor = Editor()
    assert service.prescaler_of(editor.tuning_scheme) == "log-prime"  # the default
    editor.set_complexity_prescaler("prime")  # the alt.-complexity control (box 𝐋)
    assert service.prescaler_of(editor.tuning_scheme) == "prime"
    # the prescaling matrix is gated on alternative complexity (or an all-interval scheme); turning
    # it on reveals it, and the prescaler swap is slope-independent so the diagonal still reads its primes
    editor.set_weight_slope("simplicity-weight")
    # and the swap flows into the prescaling matrix: sopfr's diagonal IS the primes
    lay = spreadsheet.build(editor.state, {**settings.defaults(), "weighting": True, "alt_complexity": True},
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
    editor.set_custom_prescaler_entry(1, 1, 7.5)
    seed = service.complexity_prescaler(editor.state.mapping, service.DEFAULT_TUNING_SCHEME)
    assert editor.custom_prescaler == (seed[0], 7.5, seed[2])
    editor.set_custom_prescaler_entry(2, 2, 11.0)  # a second edit keeps the first
    assert editor.custom_prescaler == (seed[0], 7.5, 11.0)


def test_set_custom_prescaler_entry_promotes_to_a_matrix_on_an_off_diagonal_edit():
    # editing an OFF-diagonal cell makes the pretransformer a full d×d matrix (a non-diagonal
    # pretransformer): it seeds the square from the scheme's diagonal (zeros off it) and sets the
    # one entry. A diagonal-only override stays a flat tuple; this is the promotion to a matrix.
    editor = Editor()
    seed = service.complexity_prescaler(editor.state.mapping, service.DEFAULT_TUNING_SCHEME)
    editor.set_custom_prescaler_entry(0, 1, 0.5)  # off the diagonal
    M = editor.custom_prescaler
    assert isinstance(M[0], tuple)  # promoted: the rows are tuples (a 2-D matrix)
    assert M[0][1] == 0.5
    assert (M[0][0], M[1][1], M[2][2]) == (seed[0], seed[1], seed[2])  # diagonal seeded from the scheme
    assert M[2][0] == 0.0  # an untouched off-diagonal entry is zero
    # once a matrix, a diagonal edit updates the matrix entry in place (it stays a matrix)
    editor.set_custom_prescaler_entry(2, 2, 9.0)
    assert isinstance(editor.custom_prescaler[0], tuple) and editor.custom_prescaler[2][2] == 9.0


def test_load_round_trips_a_matrix_pretransformer_override():
    import json

    # a non-diagonal pretransformer (a matrix override) survives serialize/load, not just a diagonal
    editor = Editor()
    editor.set_custom_prescaler_entry(0, 1, 0.5)
    e2 = Editor()
    e2.load(editor.serialize())
    assert e2.custom_prescaler == editor.custom_prescaler
    assert isinstance(e2.custom_prescaler[0], tuple)  # still a matrix
    # and through a real JSON round-trip (lists, not tuples) too
    e3 = Editor()
    e3.load(json.loads(json.dumps(editor.serialize())))
    assert e3.custom_prescaler == editor.custom_prescaler


def test_load_drops_a_crash_inducing_prescaler_and_still_renders():
    # a persisted document can smuggle in a bad custom_prescaler that never went through the UI
    # handler's validation — e.g. a 0 on the diagonal. Under a simplicity-weight scheme that makes
    # a prime's complexity 0 and its simplicity weight infinite, which scipy linprog rejects, so a
    # naive load+layout used to crash the render (ValueError: A_ub must not contain inf/nan). load
    # now validates the restored prescaler the same way the UI does and drops an invalid one to
    # None (the scheme's own prescaler), so the page still builds.
    editor = Editor()
    editor.set_weight_slope("simplicity-weight")
    doc = editor.serialize()
    doc["custom_prescaler"] = [0.0, 1.585, 2.322]  # a 0 diagonal smuggled via persistence
    editor.load(doc)
    assert editor.custom_prescaler is None  # the crash-inducing prescaler was dropped
    editor.layout()  # builds without raising

    # an inf entry (also unsolvable) is dropped just the same
    editor2 = Editor()
    editor2.set_weight_slope("simplicity-weight")
    doc2 = editor2.serialize()
    doc2["custom_prescaler"] = [float("inf"), 1.585, 2.322]
    editor2.load(doc2)
    assert editor2.custom_prescaler is None
    editor2.layout()


def test_load_keeps_a_valid_custom_prescaler():
    # the guard only drops crash-inducing prescalers — a legitimate hand-edited diagonal still
    # round-trips through load untouched
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 1, 7.5)
    saved = editor.custom_prescaler
    e2 = Editor()
    e2.load(editor.serialize())
    assert e2.custom_prescaler == saved


def test_picking_a_preset_prescaler_clears_the_custom_override():
    # the prescaler preset is the user's reset path: picking "log-prime" / "prime" /
    # "identity" CLEARS the custom override AND swaps the scheme's prescaler trait, so the
    # cells go back to the scheme's computed diagonal
    editor = Editor()
    editor.set_custom_prescaler_entry(1, 1, 9.9)
    editor.set_complexity_prescaler("prime")
    assert editor.custom_prescaler is None  # picking a preset wipes the override
    assert service.prescaler_of(editor.tuning_scheme) == "prime"


def test_picking_a_predefined_complexity_clears_the_custom_override():
    # the predefined-complexity master chooser (box 𝒄) likewise reaches into the prescaler
    # (each named complexity carries its own prescaler), so it too clears any custom diagonal
    editor = Editor()
    editor.set_custom_prescaler_entry(0, 0, 3.3)
    editor.set_complexity_name("sopfr")  # sopfr brings the prime-diagonal prescaler in
    assert editor.custom_prescaler is None
    assert service.prescaler_of(editor.tuning_scheme) == "prime"


def test_displayed_prescaler_name_tracks_the_scheme_and_falls_back_on_a_manual_edit():
    # the prescaler preset mirrors editor.displayed_prescaler_name: the scheme's prescaler
    # while untouched, then "-" (None) once a manual diagonal edit deviates from it — the same
    # fallback the tuning-scheme chooser uses for a hand-edited generator tuning
    editor = Editor()
    assert editor.displayed_prescaler_name == "log-prime"  # the default scheme's prescaler
    editor.set_custom_prescaler_entry(1, 1, 9.9)  # a deviating hand-edit
    assert editor.displayed_prescaler_name is None
    editor.undo()
    assert editor.displayed_prescaler_name == "log-prime"  # reverts with the override gone


def test_round_trip_prescaler_edit_returns_to_the_scheme_name():
    # deviate one cell, then type its SHOWN value back (what the user actually does). The cell shows
    # the rounded value, so the stored diagonal isn't bit-identical to the scheme's, but it displays
    # the same — so displayed_prescaler_name must recover "log-prime" (and the grid's 𝑋 = 𝐿 awareness)
    editor = Editor()
    shown = float(service.prescale_text(
        service.complexity_prescaler(editor.state.mapping, editor.tuning_scheme)[1]))
    editor.set_custom_prescaler_entry(1, 1, 9.9)     # deviate
    assert editor.displayed_prescaler_name is None
    editor.set_custom_prescaler_entry(1, 1, shown)   # return it to the shown log-prime value
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
    editor.set_custom_prescaler_entry(1, 1, 7.5)  # establish a non-None starting state
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
    editor.set_custom_prescaler_entry(1, 1, 7.5)  # a diagonal edit (row == col)
    assert editor.can_undo is True  # writing to a cell is a document change
    editor.undo()
    assert editor.custom_prescaler is None  # undo reverts the edit
    editor.redo()
    assert editor.custom_prescaler is not None and editor.custom_prescaler[1] == 7.5


def test_set_complexity_norm_power_sets_the_complexity_norm():
    editor = Editor()
    assert service.complexity_norm_power(editor.tuning_scheme) == 1  # taxicab default (q=1)
    editor.set_complexity_norm_power(2)  # the editable q field (box 𝒄): taxicab -> Euclidean
    assert service.complexity_norm_power(editor.tuning_scheme) == 2
    editor.set_complexity_norm_power(3)  # an arbitrary norm power, not just 1/2
    assert service.complexity_norm_power(editor.tuning_scheme) == 3


def test_set_complexity_name_sets_the_whole_complexity_shape():
    editor = Editor()
    assert service.complexity_name_of(editor.tuning_scheme) == "lp"  # default
    editor.set_complexity_name("sopfr")  # the predefined-complexities master chooser (box 𝒄)
    assert service.complexity_name_of(editor.tuning_scheme) == "sopfr"
    assert service.prescaler_of(editor.tuning_scheme) == "prime"  # sopfr's prescaler flowed in
    editor.set_complexity_name("lols")  # holds the octave just
    assert service.held_intervals(editor.tuning_scheme) == ("2/1",)


def test_nonprime_basis_approach_starts_neutral_and_holds_a_chosen_mode():
    # the chapter-9 nonstandard-domain-approach radio (prime-based / nonprime-based / neutral)
    # rides on an Editor field — it's an analysis selection, parallel to tuning_scheme, not a
    # Show toggle. Defaults to "" (the library's neutral default, which reads a nonprime element
    # as a formal prime); the setter validates the value so the field can't drift off the
    # three-mode contract.
    import pytest

    editor = Editor()
    assert editor.nonprime_basis_approach == ""  # neutral by default
    editor.set_nonprime_basis_approach("nonprime-based")
    assert editor.nonprime_basis_approach == "nonprime-based"
    editor.set_nonprime_basis_approach("prime-based")
    assert editor.nonprime_basis_approach == "prime-based"
    editor.set_nonprime_basis_approach("")  # back to neutral
    assert editor.nonprime_basis_approach == ""
    with pytest.raises(ValueError):
        editor.set_nonprime_basis_approach("bogus")


def test_nonprime_basis_approach_threads_into_the_layouts_tuning():
    # the field rides into spreadsheet.build via editor.layout() — switching the editor's
    # approach must visibly change the tuning shown in the grid for a nonprime-bearing domain
    # (same divergence as test_build_threads_nonprime_approach_through_to_the_tuning).
    editor = Editor()
    editor.state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    editor.set_tuning_scheme("minimax-C")
    neutral = {c.id: c.text for c in editor.layout().cells}
    editor.set_nonprime_basis_approach("nonprime-based")
    nonprime = {c.id: c.text for c in editor.layout().cells}
    assert neutral["tuning:gen:0"] != nonprime["tuning:gen:0"]
    assert neutral["tuning:gen:1"] != nonprime["tuning:gen:1"]


def test_nonprime_basis_approach_resets_when_the_domain_loses_its_nonprimes():
    # the radio is hidden on a domain without nonprime elements (the box appears only when at
    # least one element isn't a prime, per the maximized mockup's blue text). To keep the
    # hidden control from carrying a stale state, a domain change that flips has-nonprimes
    # False clears the field back to neutral; a change that LEAVES nonprimes in place keeps it.
    editor = Editor()  # 2.3.5 (a standard prime limit, no nonprimes)
    # BARBADOS over 2.3.13/5 — the 13/5 makes the domain carry a nonprime element
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    editor.set_nonprime_basis_approach("nonprime-based")
    # switching to ANOTHER nonprime domain (a 13/7 basis) keeps the chosen approach
    editor.state = service.from_temperament_data("2.3.13/7 [⟨1 2 2] ⟨0 -2 -3]}")
    assert editor.nonprime_basis_approach == "nonprime-based"
    # switching to a domain WITHOUT any nonprime element clears the approach back to neutral
    editor.state = service.from_mapping([[1, 1, 0], [0, 1, 4]])  # 2.3.5 standard primes
    assert editor.nonprime_basis_approach == ""


def test_prime_based_superspace_generator_edit_drives_domain_and_resets():
    # In prime-based the editable map is the superspace 𝒈L; a manual 𝒈L projects to the on-domain
    # generators (effective_generator_tuning), so every on-domain map tracks the edit. It's cleared
    # by an approach switch, a scheme pick, and a temperament edit (it's over the superspace M_L).
    editor = Editor()
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    editor.set_nonprime_basis_approach("prime-based")
    assert editor.effective_generator_tuning() is None or editor.superspace_generator_tuning is None
    optimum_domain = editor.optimum_generator_tuning()
    editor.set_superspace_generator_tuning_component(2, 999.0)
    assert editor.superspace_generator_tuning is not None and editor.superspace_generator_tuning[2] == 999.0
    projected = editor.effective_generator_tuning()
    assert projected is not None and len(projected) == len(editor.state.mapping)  # r domain generators
    assert projected != optimum_domain  # the manual 𝒈L moved the on-domain tuning off the optimum
    # an approach switch drops the manual 𝒈L (it only lives in the prime-based superspace)
    editor.set_nonprime_basis_approach("")
    assert editor.superspace_generator_tuning is None
    # ... and it's stale after a temperament edit (a genuinely different mapping over the same
    # nonstandard domain — which edit_mapping now preserves rather than resetting to standard primes)
    editor.set_nonprime_basis_approach("prime-based")
    editor.set_superspace_generator_tuning_component(0, 1200.0)
    editor.edit_mapping([[1, 0, -1], [0, 2, 3]])  # a different mapping: the superspace M_L changes
    assert editor.state.domain_basis == (2, 3, Fraction(13, 5))  # the nonstandard domain is preserved
    assert editor.superspace_generator_tuning is None  # the manual 𝒈L is over the OLD M_L — dropped


def test_turning_off_alt_complexity_resets_the_tuning_to_basic_minimax_lp():
    # alt. complexity gates the advanced tuning knobs — a non-lp interval complexity (norm power
    # 𝑞 ≠ 1) and a non-∞ optimization power 𝑝. Turning it off returns the tuning to plain minimax-lp
    # (𝑝 = ∞, the lp complexity with 𝑞 = 1), discarding the advanced choices as ONE undoable step.
    editor = Editor()
    editor.set_show("alt_complexity", True)  # also enables its ancestors (weighting, tuning_tiles)
    editor.set_complexity_norm_power(2)       # Euclidean (q = 2) — an alternative complexity
    editor.set_optimization_power(2)          # miniRMS (p = 2) — an alternative power
    editor.set_show("alt_complexity", False)  # basic mode -> reset
    assert service.optimization_power(editor.tuning_scheme) == float("inf")  # minimax again
    assert service.complexity_norm_power(editor.tuning_scheme) == 1          # lp norm again
    assert service.complexity_name_of(editor.tuning_scheme) == "lp"
    assert editor.custom_prescaler is None
    editor.undo()  # one snapshot: the toggle AND the scheme reset undo together
    assert editor.settings["alt_complexity"] is True
    assert service.optimization_power(editor.tuning_scheme) == 2
    assert service.complexity_norm_power(editor.tuning_scheme) == 2


def test_deselecting_weighting_also_resets_alt_complexity_to_basic():
    # turning off a PARENT (weighting) deselects alt_complexity beneath it, so the same reset fires:
    # the advanced power is discarded even though alt_complexity wasn't the toggle the user clicked.
    editor = Editor()
    editor.set_show("alt_complexity", True)
    editor.set_optimization_power(2)
    editor.set_show("weighting", False)  # deselects alt_complexity (a sub-control) -> reset
    assert editor.settings["alt_complexity"] is False
    assert service.optimization_power(editor.tuning_scheme) == float("inf")


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
    # check the scheme's identity directly by name (base_scheme_name); displayed_tuning_scheme_name
    # tracks it too (the always-on optimization realises a picked scheme at once, so the name follows)
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U"  # target-based default, unity-weighted
    # the unchecked state targets the displayed interval-list family (the editor's live target spec)
    assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
    editor.set_all_interval(True)  # the target-controls checkbox: switch to all-interval
    assert service.is_all_interval(editor.tuning_scheme) is True
    # an all-interval scheme is simplicity-weighted by construction, so the toggle forces it
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-S"
    assert service.weight_slope_of(editor.tuning_scheme) == "simplicity-weight"
    editor.set_all_interval(False)  # back to target-based -> the unity-weighted default
    assert service.is_all_interval(editor.tuning_scheme) is False
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U"
    assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"
    editor.undo()  # the toggle is an undoable edit
    assert service.is_all_interval(editor.tuning_scheme) is True


def test_turning_off_all_interval_show_exits_all_interval_mode():
    # the all-interval Show toggle reveals the in-grid box-𝐓 checkbox; that checkbox enters the mode.
    # Hiding the toggle while the mode is on must also LEAVE the mode — otherwise the app stays
    # all-interval with no visible control left to turn it back off.
    editor = Editor()
    editor.set_show("all_interval", True)
    editor.set_all_interval(True)
    assert service.is_all_interval(editor.tuning_scheme) is True
    editor.set_show("all_interval", False)
    assert editor.settings["all_interval"] is False
    assert service.is_all_interval(editor.tuning_scheme) is False
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-U"
    editor.undo()  # the show-toggle AND the mode exit undo together as one step
    assert editor.settings["all_interval"] is True
    assert service.is_all_interval(editor.tuning_scheme) is True


def test_deselecting_weighting_also_exits_all_interval_mode():
    # turning off the PARENT (weighting) deselects all_interval beneath it, so the same exit fires.
    editor = Editor()
    editor.set_show("all_interval", True)
    editor.set_all_interval(True)
    editor.set_show("weighting", False)  # deselects all_interval (a sub-control) -> exit mode
    assert editor.settings["all_interval"] is False
    assert service.is_all_interval(editor.tuning_scheme) is False


def test_custom_weights_starts_off_and_the_toggle_drives_it():
    # custom weights is a Show toggle that IS its mode (no separate in-grid control): selecting it
    # seeds one weight per displayed target and makes the field non-None; the flag mirrors the field
    editor = Editor()
    assert editor.custom_weights is None
    assert editor.settings["custom_weights"] is False
    n = len(editor.current_targets())
    editor.set_show("custom_weights", True)
    assert editor.custom_weights is not None and len(editor.custom_weights) == n
    assert editor.settings["custom_weights"] is True
    # selecting the great-grandchild pulls its whole chain on (weighting -> optimization -> tuning)
    for key in ("weighting", "optimization", "tuning"):
        assert editor.settings[key] is True
    editor.set_show("custom_weights", False)
    assert editor.custom_weights is None
    assert editor.settings["custom_weights"] is False


def test_custom_weights_toggle_is_one_undoable_step():
    editor = Editor()
    editor.set_show("custom_weights", True)
    editor.undo()
    assert editor.custom_weights is None and editor.settings["custom_weights"] is False
    editor.redo()
    assert editor.custom_weights is not None and editor.settings["custom_weights"] is True


def test_set_custom_weight_entry_seeds_then_edits_one_slot():
    editor = Editor()
    editor.set_show("custom_weights", True)
    seeded = editor.custom_weights
    editor.set_custom_weight_entry(1, 4.0)
    assert editor.custom_weights[1] == 4.0
    assert editor.custom_weights[0] == seeded[0]  # untouched slots keep their seeded values
    editor.set_custom_weight_entry(0, 9.0)
    assert editor.custom_weights[0] == 9.0
    assert editor.custom_weights[1] == 4.0  # the earlier edit survives


def test_picking_a_named_slope_clears_custom_weights():
    # picking unity/complexity/simplicity is the reset path away from a manual override
    editor = Editor()
    editor.set_show("custom_weights", True)
    editor.set_weight_slope("complexity-weight")
    assert editor.custom_weights is None and editor.settings["custom_weights"] is False


def test_a_complexity_or_prescaler_pick_clears_custom_weights():
    # a re-derived complexity supersedes the manual weights, so both named picks clear them
    for action in ("complexity", "prescaler"):
        editor = Editor()
        editor.set_show("custom_weights", True)
        if action == "complexity":
            editor.set_complexity_name("sopfr")
        else:
            editor.set_complexity_prescaler("prime")
        assert editor.custom_weights is None, action
        assert editor.settings["custom_weights"] is False, action


def test_all_interval_clears_the_override_but_keeps_the_custom_weights_setting():
    # all-interval has structural per-prime weights, no per-target ones — so entering it clears the
    # manual-weight OVERRIDE. But the custom-weights SETTING stays on (always checkable, so select-all
    # works); the override just does nothing until the scheme returns to target mode, when it re-seeds.
    editor = Editor()
    editor.set_show("custom_weights", True)
    assert editor.custom_weights is not None                  # seeded in target mode
    editor.set_all_interval(True)
    assert editor.custom_weights is None                      # override cleared (no per-target weights)
    assert editor.settings["custom_weights"] is True          # ...but the setting stays checkable
    editor.set_all_interval(False)                            # back to target mode
    assert editor.custom_weights is not None                  # the override re-seeds
    assert editor.settings["custom_weights"] is True


def test_custom_weights_is_checkable_while_all_interval_is_on():
    # the user's case: with all-interval mode already active, checking custom weights must STICK (so
    # select-all is always possible) — it simply applies no override until the scheme returns to
    # target mode, at which point it takes effect.
    editor = Editor()
    editor.set_all_interval(True)             # enter all-interval mode FIRST
    editor.set_show("custom_weights", True)   # then check custom weights
    assert editor.settings["custom_weights"] is True   # the setting sticks (checkable)
    assert editor.custom_weights is None               # ...but no per-target override under all-interval
    editor.set_all_interval(False)            # leave all-interval -> target mode
    assert editor.custom_weights is not None           # now the override applies (the 𝒘 cells go editable)


def test_a_target_change_re_seeds_custom_weights_keeping_the_setting():
    # the override is position-keyed to the target list, so a target drop invalidates the typed values
    # — but the (sticky) setting stays on and the override re-seeds for the new (shorter) list.
    editor = Editor()
    editor.set_show("custom_weights", True)
    n_before = len(editor.custom_weights)
    editor.remove_target(0)
    assert editor.settings["custom_weights"] is True                              # setting stays on
    assert editor.custom_weights is not None and len(editor.custom_weights) == n_before - 1  # re-seeded


def test_a_domain_change_re_seeds_custom_weights_keeping_the_setting():
    editor = Editor()
    editor.set_show("custom_weights", True)
    editor.expand()  # adds a prime (the target list is rebuilt over the new domain)
    assert editor.settings["custom_weights"] is True       # setting stays on (sticky)
    assert editor.custom_weights is not None               # re-seeded for the new domain's targets


def test_custom_weights_round_trip_and_resync_the_toggle():
    editor = Editor()
    editor.set_show("custom_weights", True)
    editor.set_custom_weight_entry(0, 7.0)
    restored = Editor()
    restored.load(editor.serialize())
    assert restored.custom_weights == editor.custom_weights
    assert restored.settings["custom_weights"] is True  # the toggle re-derived from the field


def test_load_drops_a_bad_custom_weights_value():
    editor = Editor()
    data = editor.serialize()
    data["custom_weights"] = [1.0, -2.0, 0.0]  # a non-positive weight is unusable
    editor.load(data)
    assert editor.custom_weights is None and editor.settings["custom_weights"] is False


def test_displayed_scheme_name_names_a_control_refined_spec():
    # A scheme reached by ticking the Euclidean complexity control is stored as a refined spec, not
    # a name string — but it must still be NAMEABLE (the renderer names the spec) rather than
    # dropping to "-" for lacking a string. base_scheme_name reads its identity directly; the
    # always-on optimization realises the spec at once, so the chooser's displayed name reads the same.
    editor = Editor()
    editor.set_all_interval(True)  # minimax-S
    editor.set_complexity_norm_power(2)  # q=2 (Euclidean) -> a refined spec equal to minimax-ES
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-ES"  # the spec is named
    assert editor.displayed_tuning_scheme_name == "minimax-ES"


def test_displayed_scheme_name_is_none_for_an_unnameable_power():
    # a non-integer optimization power has no systematic name, so the chooser shows "-"
    editor = Editor()
    editor.set_optimization_power(1.5)
    assert editor.displayed_tuning_scheme_name is None


def test_set_tuning_scheme_preserves_the_target_mode():
    # picking a scheme from the chooser keeps the current target mode (the all-interval checkbox):
    # target-based by default (the chooser's T-prefixed entries), all-interval once the box is on
    editor = Editor()
    editor.set_tuning_scheme("minimax-ES")  # target-based by default => over the target list
    assert not service.is_all_interval(editor.tuning_scheme)
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-ES"  # chooser shows "T minimax-ES"
    assert service.resolve_tuning_scheme(editor.tuning_scheme).target_intervals == editor.target_spec
    editor.set_all_interval(True)  # switch to all-interval
    editor.set_tuning_scheme("minimax-S")  # now applies all-interval (bare name)
    assert service.is_all_interval(editor.tuning_scheme)
    assert service.base_scheme_name(editor.tuning_scheme) == "minimax-S"


def test_a_held_octave_scheme_holds_the_octave_in_target_mode():
    # selecting held-octave minimax-ES while target-based must actually hold the octave just. The
    # scheme is built by setting the target trait, not by gluing "TILT " in front of the name —
    # which mis-parsed ("TILT held-octave ...") and silently dropped the held-octave modifier.
    editor = Editor()  # target-based by default
    editor.set_tuning_scheme("held-octave minimax-ES")
    spec = service.resolve_tuning_scheme(editor.tuning_scheme)
    assert spec.held_intervals == "octave"  # the hold survived the target-prefixing
    assert spec.target_intervals == editor.target_spec  # ...and it is target-based, not all-interval
    tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis)
    assert abs(tuning_map.tuning_map[0] - 1200.0) < 1e-6  # prime 2 pinned exactly just


def test_all_interval_toggle_off_keeps_a_destretched_modifier():
    # toggling all-interval off from destretched-octave minimax-ES must not drop the destretch:
    # the toggle swaps the target/slope traits structurally, so the modifier survives (it once
    # vanished when the toggle rebuilt the name by concatenation).
    editor = Editor()
    editor.set_all_interval(True)
    editor.set_tuning_scheme("destretched-octave minimax-ES")
    editor.set_all_interval(False)
    spec = service.resolve_tuning_scheme(editor.tuning_scheme)
    assert spec.destretched_interval == "octave"  # the destretch survived the toggle
    assert not service.is_all_interval(editor.tuning_scheme)  # ...now target-based
    assert service.weight_slope_of(editor.tuning_scheme) == "unity-weight"  # toggle-off forces unity
    # the destretch is still named (now with the unity slope the toggle forced)
    assert service.base_scheme_name(editor.tuning_scheme) == "destretched-octave minimax-EU"


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


def test_cancelling_a_pending_comma_discards_the_draft():
    # the draft column's − cancels the DRAFT (cancel_pending_comma), leaving any real comma
    # untouched — distinct from remove_comma, which un-tempers a real comma (see below).
    editor = Editor()
    editor.add_comma()
    assert editor.pending_comma is not None  # a pending draft can be cancelled
    editor.cancel_pending_comma()
    assert editor.pending_comma is None
    assert editor.state.comma_basis == ((4, -4, 1),)  # the real comma untouched — the draft went, not it
    assert editor.can_undo is False  # cancelling a draft is not an undoable edit


def test_removing_a_real_comma_drops_the_last_by_default():
    editor = Editor()
    editor.add_comma()
    editor.set_pending_comma([4, -5, 1])  # commit a 2nd comma -> 2 real, no pending
    assert editor.pending_comma is None and len(editor.state.comma_basis) == 2
    editor.remove_comma()  # the default drops the last real comma
    assert editor.state.comma_basis == ((4, -4, 1),)
    assert editor.state.r == 2  # the mapping regained its row


def test_removing_a_comma_can_target_any_index_not_only_the_last():
    # each comma carries its own − now, so remove_comma takes the column's index: dropping the
    # FIRST of two commas un-tempers just it — a different result from dropping the last.
    editor = Editor()
    editor.add_comma()
    editor.set_pending_comma([4, -5, 1])  # 2 real commas
    two = editor.state
    assert len(two.comma_basis) == 2 and two.r == 1  # both tempered: nullity 2, rank 1
    editor.remove_comma(0)  # drop the FIRST comma, not the last
    assert editor.state.n == 1 and editor.state.r == 2          # one comma un-tempered
    assert editor.state == service.remove_comma(two, 0)         # exactly the index-0 drop...
    assert editor.state != service.remove_comma(two, -1)        # ...NOT the default last-comma drop
    editor.undo()
    assert editor.state == two  # one undoable edit restores both commas


def test_editor_starts_with_default_tuning_scheme_and_target_spec():
    editor = Editor()
    # the scheme is held as the canonical spec, equal to the resolved as-shipped document scheme
    assert editor.tuning_scheme == service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME)
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # target-based, unity-weighted
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


def test_shrinking_runs_down_to_one_prime_through_degenerate_states():
    # the − shrinks any standard prime limit down to a single prime — even through degenerate steps
    # (the remaining structure tempering a prime to a unison), parity with the comma + which reaches
    # such states freely. A domain must keep one prime, so d == 1 is the hard floor.
    editor = Editor()  # meantone, d=3
    assert editor.can_shrink is True
    editor.shrink()
    assert editor.state.d == 2 and editor.can_shrink is True  # 2.3 — still shrinkable now
    editor.shrink()
    assert editor.state.d == 1  # down to just 2/1 (the degenerate result stands)
    assert editor.can_shrink is False  # zero primes is not a domain — the floor
    editor.shrink()  # guarded — a no-op
    assert editor.state.d == 1


def test_add_remove_mapping_row_change_rank_holding_dimensionality():
    editor = Editor()  # meantone, d=3 r=2 n=1
    editor.remove_mapping_row(0)  # drop a generator (any row)
    assert (editor.state.r, editor.state.d, editor.state.n) == (1, 3, 2)  # −r, +n, d held
    editor.add_mapping_row()  # OPEN a blank green draft row (the row mirror of add_comma)
    assert editor.pending_mapping_row == [None, None, None]  # a draft, not yet committed
    assert (editor.state.r, editor.state.d, editor.state.n) == (1, 3, 2)  # the draft changes nothing yet
    editor.set_pending_mapping_row([1, 1, 0])  # type a new independent generator → commits (+r, −n)
    assert editor.pending_mapping_row is None
    assert (editor.state.r, editor.state.d, editor.state.n) == (2, 3, 1)  # +r, −n, d held
    editor.undo()
    assert editor.state.r == 1  # the commit is a single undoable step


def test_mapping_row_guards():
    editor = Editor()
    editor.edit_mapping(((1, 0, 0),))  # rank-1, d=3, n=2
    assert editor.can_remove_mapping_row is False  # can't drop the sole row
    assert editor.can_add_mapping_row is True  # ...n>0, a comma to un-temper
    editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))  # JI, n=0
    assert editor.can_add_mapping_row is False  # nothing tempered to un-temper


def test_add_mapping_row_to_combines_rows_as_one_undoable_step():
    editor = Editor()  # meantone ((1,1,0),(0,1,4))
    commas = editor.state.comma_basis
    editor.add_mapping_row_to(0, 1)  # drag the octave row onto the fifth row: row 1 += row 0
    assert editor.state.mapping == ((1, 1, 0), (1, 2, 4))
    assert editor.state.comma_basis == commas  # same temperament, new generator basis
    editor.undo()
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))  # a single undoable step


def test_add_mapping_row_starts_a_blank_pending_draft_row_without_touching_the_temperament():
    # the ROW mirror of test_add_comma_starts_a_blank_pending_draft: the mapping + opens a green
    # draft generator the user fills in, rather than silently un-tempering a comma.
    editor = Editor()  # meantone, d=3 r=2 n=1
    assert editor.pending_mapping_row is None
    editor.add_mapping_row()
    assert editor.pending_mapping_row == [None, None, None]  # a blank d-length draft row
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))    # the temperament is unchanged...
    assert (editor.state.r, editor.state.n) == (2, 1)        # ...the mapping keeps its rows...
    assert editor.can_undo is False                          # ...and starting a draft is not undoable


def test_filling_the_pending_mapping_row_with_an_independent_generator_commits_and_reranks():
    editor = Editor()  # meantone, d=3 r=2 n=1
    editor.add_mapping_row()
    editor.set_pending_mapping_row([0, 0, 1])  # a new independent generator (prime 5 held just)
    assert editor.pending_mapping_row is None  # committed, no longer pending
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4), (0, 0, 1))  # the typed row appended as-is
    assert (editor.state.r, editor.state.n) == (3, 0)  # +r, −n (full rank now), d held
    assert editor.can_undo is True  # the commit is the undoable edit
    editor.undo()
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))  # one undoable step restores it


def test_incomplete_or_dependent_pending_mapping_row_is_held_not_committed():
    editor = Editor()  # meantone, d=3 r=2 n=1
    editor.add_mapping_row()
    editor.set_pending_mapping_row([0, 0, None])  # still being typed
    assert editor.pending_mapping_row == [0, 0, None] and editor.state.r == 2  # held, no re-rank
    editor.set_pending_mapping_row([2, 2, 0])  # complete but dependent (2× existing row 0) -> no new generator
    assert editor.pending_mapping_row == [2, 2, 0] and editor.state.r == 2  # held, not committed


def test_cancel_pending_mapping_row_discards_the_draft():
    editor = Editor()
    editor.add_mapping_row()
    editor.set_pending_mapping_row([0, 0, None])  # a partly-typed draft
    editor.cancel_pending_mapping_row()
    assert editor.pending_mapping_row is None              # discarded
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))  # temperament untouched
    assert editor.can_undo is False                        # cancelling a never-committed draft is not undoable


def test_a_temperament_edit_clears_a_pending_mapping_row_draft():
    # a draft's length is tied to the current temperament, so a structural edit (or undo/redo/reset)
    # abandons it — exactly like the column drafts (_clear_pending).
    editor = Editor()
    editor.add_mapping_row()
    editor.edit_comma_basis(((4, -4, 1),))  # a temperament edit
    assert editor.pending_mapping_row is None


def test_add_mapping_row_opens_no_draft_at_full_rank():
    editor = Editor()
    editor.edit_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))  # JI, full rank, n=0
    assert editor.can_add_mapping_row is False
    editor.add_mapping_row()  # guarded: no independent generator can be added holding the d primes
    assert editor.pending_mapping_row is None


def test_add_mapping_row_to_preserves_a_frozen_tuning():
    editor = Editor()
    editor.set_generator_tuning_text("{1200.000 700.000]")  # freeze octave + a flat 700¢ fifth
    before = service.tuning_from_generators(editor.state.mapping, editor.effective_generator_tuning())
    editor.add_mapping_row_to(0, 1)  # drag the octave row onto the fifth row
    # the dragged generator's size loses the target's (1200 − 700 = 500); the target's stays put
    assert editor.effective_generator_tuning() == (500.0, 700.0)
    after = service.tuning_from_generators(editor.state.mapping, editor.effective_generator_tuning())
    assert tuple(round(x, 6) for x in after.tuning_map) == tuple(round(x, 6) for x in before.tuning_map)


def test_add_mapping_row_to_ignores_a_row_dropped_on_itself():
    editor = Editor()
    editor.add_mapping_row_to(1, 1)  # a row added to itself would double it (enfactor) — refused
    assert editor.state.mapping == ((1, 1, 0), (0, 1, 4))  # untouched
    assert editor.can_undo is False  # and not an undoable step


def test_add_comma_to_recombines_the_comma_basis_undoably():
    editor = Editor()
    editor.edit_mapping(((12, 19, 28),))  # 12-ET 5-limit: d=3 r=1 n=2 — two commas to combine
    before = editor.state.comma_basis
    editor.add_comma_to(0, 1)  # drag comma 0 onto comma 1: comma 1 += comma 0
    assert editor.state.comma_basis[1] == tuple(a + b for a, b in zip(before[1], before[0]))
    assert editor.state.mapping == ((12, 19, 28),)  # the temperament is unchanged
    editor.undo()
    assert editor.state.comma_basis == before  # a single undoable step


def test_add_comma_to_ignores_a_comma_dropped_on_itself():
    editor = Editor()
    editor.edit_mapping(((12, 19, 28),))  # 12-ET 5-limit: two commas
    before = editor.state.comma_basis
    steps = editor.undo_count
    editor.add_comma_to(0, 0)  # a comma added to itself would double it — refused
    assert editor.state.comma_basis == before  # untouched
    assert editor.undo_count == steps  # and no new undoable step


def test_add_interest_to_combines_two_intervals_of_interest_undoably():
    editor = Editor()
    editor.set_interest_vectors([(-1, 1, 0), (0, 0, 1)])  # 3/2 and 5/1
    editor.add_interest_to(0, 1)  # interest 1 += interest 0 → (-1, 1, 1) = 15/2
    assert editor.interest_vectors == [(-1, 1, 0), (-1, 1, 1)]  # the dragged one kept, the target summed
    editor.undo()
    assert editor.interest_vectors == [(-1, 1, 0), (0, 0, 1)]


def test_add_held_to_combines_two_held_intervals_undoably():
    editor = Editor()
    editor.set_held_vectors([(1, 0, 0), (-1, 1, 0)])  # 2/1 and 3/2
    editor.add_held_to(0, 1)  # held 1 += held 0 → (0, 1, 0) = 3/1
    assert editor.held_vectors == [(1, 0, 0), (0, 1, 0)]
    editor.undo()
    assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]


def test_add_target_to_multiplies_two_targets_materializing_the_override():
    editor = Editor()
    editor.set_target_override_vectors([(-1, 1, 0), (-2, 0, 1)])  # 3/2 and 5/4
    editor.add_target_to(0, 1)  # target 1 = 3/2 · 5/4 = 15/8 (the intervals' product)
    assert editor.target_override == ("3/2", "15/8")
    editor.undo()
    assert editor.target_override == ("3/2", "5/4")  # a single undoable step


def test_interval_drag_add_ignores_a_drop_on_itself():
    editor = Editor()
    editor.set_interest_vectors([(1, 0, 0), (0, 1, 0)])
    steps = editor.undo_count  # the set was one undoable step
    editor.add_interest_to(1, 1)  # dropping an interval on itself would double it — refused
    assert editor.interest_vectors == [(1, 0, 0), (0, 1, 0)]  # unchanged
    assert editor.undo_count == steps  # ...and no new undoable step pushed


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
    assert editor.pending_interest == [None, None, None]  # ...a green, blank, d-length draft
    editor.set_pending_interest([-1, 1, 0])  # fill it in -> commits 3/2
    assert editor.interest_vectors == [(-1, 1, 0)] and editor.pending_interest is None
    editor.set_interest_vectors([[-1, 1, 0], [2, 0, -1]])  # editing existing cells replaces the set
    assert editor.interest_vectors == [(-1, 1, 0), (2, 0, -1)]
    editor.remove_interest(0)
    assert editor.interest_vectors == [(2, 0, -1)]


def test_adding_an_interval_of_interest_starts_a_blank_pending_draft():
    # like add_comma: a blank, green-outlined draft column the user fills in, NOT a committed
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
    assert editor.pending_held == [None, None, None]  # ...a green, blank, d-length draft
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


# --- move_interval: drag-and-drop a column between/within the interval lists ---
# A drop slot's gap g means "insert before column g" (g == len appends); a same-list
# reorder shifts the gap down by one after the source is removed, so dragging column i
# rightward lands where the cursor pointed. One snapshot per move (a single undo step).

def test_move_interval_reorders_within_a_list_with_a_single_undo():
    editor = Editor()
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])  # octave, fifth, major third
    # drop the octave ONTO the major third (index 2) -> the octave lands at index 2 (its place)
    assert editor.move_interval("held", 0, "held", 2) is True
    assert editor.held_vectors == [(-1, 1, 0), (2, 0, -1), (1, 0, 0)]  # fifth, third, octave
    editor.undo()
    assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0), (2, 0, -1)]  # one undoable step


def test_within_list_reorder_keeps_the_moved_columns_cell_id_for_the_glide():
    # the render() path: layout(), reorder, then layout(prev_ids=...) threading the prior render's
    # identities. The moved column keeps its cell id (so the CSS left transition slides it) and lands
    # at the dropped-on slot's x — rather than the old fixed-index cell re-filling with new numbers.
    editor = Editor()
    editor.settings["optimization"] = True  # show the held column
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])  # octave, fifth, third
    lay1 = editor.layout()
    cells1 = {c.id: c for c in lay1.cells}
    front_x = cells1["cell:held:0:0"].x
    editor.move_interval("held", 2, "held", 0)  # drag the third to the front
    cells2 = {c.id: c for c in editor.layout(prev_ids=lay1.identities).cells}
    assert "cell:held:0:2" in cells2                  # the moved column (token 2) kept its id...
    assert cells2["cell:held:0:2"].x == front_x       # ...and glided to the front slot's x
    assert cells2["cell:held:0:2"].text == cells1["cell:held:0:2"].text  # carrying its own value


def test_dropping_a_column_on_its_neighbour_swaps_them():
    # the key fix: dropping A onto the adjacent B moves A to B's index (a swap) — no off-by-one,
    # no need to overshoot onto the next-but-one column
    editor = Editor()
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0], [2, 0, -1]])  # A=octave, B=fifth, C=third
    assert editor.move_interval("held", 0, "held", 1) is True  # drop A onto B
    assert editor.held_vectors == [(-1, 1, 0), (1, 0, 0), (2, 0, -1)]  # B, A, C — A & B swapped


def test_move_interval_carries_a_vector_between_two_lists():
    editor = Editor()
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])  # octave, fifth
    editor.set_interest_vectors([[2, 0, -1]])  # major third
    assert editor.move_interval("held", 0, "interest", 1) is True  # octave → end of interest
    assert editor.held_vectors == [(-1, 1, 0)]
    assert editor.interest_vectors == [(2, 0, -1), (1, 0, 0)]
    editor.undo()  # one step restores BOTH lists
    assert editor.held_vectors == [(1, 0, 0), (-1, 1, 0)]
    assert editor.interest_vectors == [(2, 0, -1)]


def test_unchanged_interval_drags_out_as_a_copy():
    # the consolidated V's unchanged half U is a derived basis (read off the tuning), so dragging one
    # of its intervals to another list COPIES it there without removing it from U — and nothing can
    # be dropped INTO U. (The default tuning is quarter-comma meantone, which holds 2/1 and 5/4.)
    editor = Editor()
    u_known = editor.list_vectors("unchanged")
    assert u_known and u_known[0] is not None        # U is known (the tuning holds rationally)
    u0 = u_known[0]
    assert editor.move_interval("unchanged", 0, "interest", 0) is True
    assert tuple(editor.interest_vectors[0]) == u0   # copied into the interest list
    assert editor.list_vectors("unchanged")[0] == u0  # …and U keeps it (derived — not removed)
    # nothing can be dropped INTO U (it isn't an editable list)
    assert editor.move_interval("interest", 0, "unchanged", 0) is False


def test_move_a_target_into_held_converts_the_ratio_and_materializes_the_override():
    editor = Editor()  # default TILT targets, no override
    targets = service.target_interval_set(editor.target_spec, editor.state.domain_basis)
    first = service.interval_vector(targets[0], editor.state.d, editor.state.domain_basis)
    assert editor.move_interval("targets", 0, "held", 0) is True
    assert editor.held_vectors == [first]  # the ratio became its vector
    assert editor.target_override is not None and len(editor.target_override) == len(targets) - 1
    assert targets[0] not in editor.target_override  # dropped from the (now materialized) set


def test_move_a_held_interval_into_commas_tempers_it_out_and_reranks():
    editor = Editor()  # comma_basis ((4,-4,1),), (r, n) == (2, 1)
    editor.set_held_vectors([[4, -5, 1]])  # an interval independent of the basis
    editor.add_interest()  # an open draft, to prove a rank move clears pending state
    assert editor.pending_interest is not None
    assert editor.move_interval("held", 0, "commas", 0) is True
    assert (editor.state.r, editor.state.n) == (1, 2)  # tempering it out raised the nullity
    assert len(editor.state.comma_basis) == 2 and editor.held_vectors == []
    assert editor.pending_interest is None  # the rank change cleared the draft
    editor.undo()
    assert (editor.state.r, editor.state.n) == (2, 1) and editor.held_vectors == [(4, -5, 1)]


def test_moving_a_dependent_interval_into_commas_is_rejected():
    editor = Editor()  # comma (4,-4,1)
    editor.set_held_vectors([[8, -8, 2]])  # 2x the syntonic comma — already tempered out
    before = editor.state.comma_basis
    assert editor.move_interval("held", 0, "commas", 0) is False  # re-ranks nothing → rejected
    assert editor.state.comma_basis == before and editor.held_vectors == [(8, -8, 2)]
    editor.undo()  # the only undoable step is set_held_vectors → the move added none
    assert editor.held_vectors == []


def test_move_a_comma_out_to_a_list_untempers_it_using_its_pre_removal_vector():
    editor = Editor()
    editor.edit_comma_basis([[4, -4, 1], [4, -5, 1]])  # two commas, (r, n) == (1, 2)
    vector = editor.state.comma_basis[-1]  # the comma we'll drag out (read before removal)
    assert editor.move_interval("commas", len(editor.state.comma_basis) - 1, "interest", 0) is True
    assert (editor.state.r, editor.state.n) == (2, 1)  # un-tempering it dropped the nullity
    assert editor.interest_vectors == [vector]


def test_dragging_out_the_sole_comma_un_tempers_it_to_just_intonation():
    # parity with the comma − (which un-temps the last comma): dragging the sole comma out to an
    # interval list un-temps it all the way to nullity 0 (just intonation) AND lands it in that list.
    editor = Editor()
    assert editor.move_interval("commas", 0, "held", 0) is True
    assert editor.state.n == 0  # nothing tempered — full rank
    assert editor.held_vectors == [(4, -4, 1)]  # 81/80 is now a held interval


def test_dragging_a_comma_out_is_blocked_with_nothing_tempered():
    # at nullity 0 there is no real comma to drag out (only the full-rank zero placeholder), so the
    # move is infeasible — the dual of "tempering in needs to genuinely raise the nullity".
    editor = Editor()
    editor.remove_comma()  # -> just intonation, n=0
    assert editor.move_interval("commas", 0, "held", 0) is False
    assert editor.held_vectors == []


def test_targets_are_inert_in_all_interval_mode():
    editor = Editor()
    editor.set_all_interval(True)
    assert service.is_all_interval(editor.tuning_scheme)
    editor.set_held_vectors([[1, 0, 0]])
    assert editor.move_interval("held", 0, "targets", 0) is False  # no user-curated target list
    assert editor.held_vectors == [(1, 0, 0)]


def test_dropping_a_column_on_itself_is_a_no_op():
    editor = Editor()
    editor.set_held_vectors([[1, 0, 0], [-1, 1, 0]])
    assert editor.move_interval("held", 1, "held", 1) is False  # a column dropped on itself
    assert editor.move_interval("held", 0, "held", 0) is False
    editor.undo()  # only set_held_vectors is undoable → the no-op moves added no steps
    assert editor.held_vectors == []


def test_reordering_targets_materializes_the_spec_into_an_override():
    editor = Editor()
    assert editor.target_override is None
    orig = service.target_interval_set(editor.target_spec, editor.state.domain_basis)
    assert editor.move_interval("targets", 0, "targets", len(orig)) is True  # first → last
    assert editor.target_override is not None and len(editor.target_override) == len(orig)
    assert editor.target_override[-1] == orig[0] and editor.target_override[0] == orig[1]


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


def test_try_edit_comma_basis_text_preserves_a_nonstandard_domain():
    # editing the comma box on a nonstandard temperament keeps the basis — the new comma
    # is read over 2.3.13/5, not the default 2.3.5 the standard primes would otherwise impose
    editor = Editor()
    assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
    assert editor.try_edit_comma_basis_text("[2 -3 2⟩") is True
    assert editor.state.domain_basis == (2, 3, Fraction(13, 5))


def test_set_pending_comma_preserves_a_nonstandard_domain():
    # committing a DRAFT comma on a nonstandard temperament keeps the basis — the new comma
    # re-ranks over 2.3.13/5, not the default 2.3.5 a standard prime limit would impose (the
    # comma-box twin of test_try_edit_comma_basis_text_preserves_a_nonstandard_domain).
    editor = Editor()
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    editor.add_comma()
    editor.set_pending_comma([0, 0, 1])  # independent -> commits, re-ranking the temperament
    assert editor.pending_comma is None  # the draft committed
    assert editor.state.n == 2
    assert editor.state.domain_basis == (2, 3, Fraction(13, 5))


def test_move_interval_into_commas_preserves_a_nonstandard_domain():
    # dragging an interval into the comma column tempers it out via the same from_comma_basis
    # path as a draft comma, so it must thread the domain too — else 2.3.13/5 silently reverts
    # to the standard 2.3.5 (the drag-and-drop twin of set_pending_comma's domain bug).
    editor = Editor()
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    editor.interest_vectors = [(0, 0, 1)]  # an interval of interest to drag into commas
    assert editor.move_interval("interest", 0, "commas", 1) is True
    assert editor.state.n == 2  # the dragged interval was tempered out (re-ranked)
    assert editor.state.domain_basis == (2, 3, Fraction(13, 5))


def test_opening_a_draft_discards_any_other_pending_draft():
    # one draft at a time: each opener clears the others, so two drafts can never co-exist and
    # corrupt the state by re-ranking from different sources of truth. Walk the openers in a ring.
    editor = Editor()
    editor.add_comma()
    assert editor.pending_comma is not None
    editor.add_interest()  # opening interest discards the comma draft
    assert editor.pending_comma is None and editor.pending_interest is not None
    editor.add_held()  # ... and so on around the ring
    assert editor.pending_interest is None and editor.pending_held is not None
    editor.add_target()
    assert editor.pending_held is None and editor.pending_target is not None
    editor.add_element()
    assert editor.pending_target is None and editor.pending_element is not None
    editor.add_comma()  # back to the start: opening comma discards the element draft
    assert editor.pending_element is None and editor.pending_comma is not None


def test_comma_and_mapping_row_drafts_cannot_coexist():
    # add_mapping_row opens a DRAFT row (the mapping-row draft, the row mirror of add_comma).
    # Opening either must discard the other, else completing one re-ranks from a different source
    # of truth (comma basis vs mapping) and silently undoes the other's edit.
    editor = Editor()
    editor.state = service.from_mapping(((12, 19, 28),))  # n = 2, so a row draft can open
    editor.add_comma()
    editor.set_pending_comma([4, -4, None])  # partial comma draft, deliberately left open
    editor.add_mapping_row()  # opening the row draft discards the comma draft
    assert editor.pending_comma is None
    assert editor.pending_mapping_row is not None
    # symmetric: opening a comma draft discards a pending mapping-row draft
    editor.set_pending_mapping_row([1, 0, None])  # partial row draft
    editor.add_comma()
    assert editor.pending_mapping_row is None
    assert editor.pending_comma is not None


def test_comma_and_element_drafts_cannot_coexist():
    # opening the element draft discards the comma draft, so committing the element (which grows d
    # 3 -> 4) can't later collide with a stale length-3 comma — which used to raise ValueError.
    editor = Editor()
    editor.state = service.from_mapping(((12, 19, 28),))
    editor.add_comma()
    editor.set_pending_comma([4, -4, None])
    editor.add_element()
    assert editor.pending_comma is None
    editor.set_pending_element("7")  # grows the domain; must not raise
    assert editor.state.d == 4


def test_optimization_is_always_on_so_a_change_retunes_immediately():
    # optimization is invisibly always on: a fresh editor is scheme-driven (no stored override, so
    # the grid recomputes the scheme's optimum on every render) and a document change — here a
    # changed target list — is reflected in the layout's tuning at once, with no apply step. No
    # stale tuning state can exist.
    editor = Editor()
    assert editor.generator_tuning is None              # scheme-driven from the start
    assert editor.effective_generator_tuning() is None  # the grid recomputes the optimum per render
    gens = lambda: {c.id: c.text for c in editor.layout().cells}["tuning:gen:1"]
    before = gens()  # the default TILT minimax-U optimum
    editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")  # change the target list to 2/1 + 3/2
    assert gens() != before  # the grid retuned on the spot — no optimize step exists


def test_set_generator_tuning_text_freezes_a_typed_genmap():
    editor = Editor()
    # typing a valid cents genmap freezes it as the manual tuning (a hand-edit override)
    assert editor.set_generator_tuning_text("{1200.000 701.955]") is True
    assert editor.effective_generator_tuning() == (1200.0, 701.955)
    assert editor.manual_tuning is True
    assert editor.can_undo is True
    # the wrong count or junk is rejected, leaving the tuning untouched
    assert editor.set_generator_tuning_text("{1200]") is False  # one value, need two
    assert editor.set_generator_tuning_text("garbage") is False
    assert editor.effective_generator_tuning() == (1200.0, 701.955)


def test_set_generator_tuning_component_overrides_one_generator():
    editor = Editor()
    optimum = editor.optimum_generator_tuning()
    # with nothing overridden, editing one generator seeds the rest from the current optimum
    editor.set_generator_tuning_component(1, 700.0)
    eff = editor.effective_generator_tuning()
    assert eff[1] == 700.0 and eff[0] == optimum[0]
    assert editor.manual_tuning is True and editor.can_undo is True


def test_editing_a_generator_cell_after_a_rank_change_seeds_from_the_optimum():
    # A rank change (domain expand, comma/mapping edit) leaves a manual generator tuning stale —
    # the OLD rank's length. Editing or nudging a generator-tuning cell must seed from the current
    # optimum, not index the stale shorter tuning (which crashed with IndexError).
    editor = Editor()
    editor.set_generator_tuning_component(1, 700.0)  # a manual override at rank 2
    editor.expand()  # 5-limit -> 7-limit, rank 2 -> 3; the manual tuning is still length 2
    assert editor.state.r == 3 and len(editor.generator_tuning) == 2  # the tuning is stale
    editor.set_generator_tuning_component(2, 700.0)  # edit the NEW 3rd generator's cell
    assert len(editor.generator_tuning) == 3 and editor.generator_tuning[2] == 700.0
    editor.nudge_generator_tuning_component(2, 5)  # wheel-nudge the new cell — also must not crash
    assert len(editor.generator_tuning) == 3


def test_target_limit_beyond_the_domain_filters_out_of_domain_intervals():
    # raising the OLD/TILT limit past the domain's prime limit must not crash: the out-of-domain
    # intervals (needing a prime the domain doesn't have) are dropped, not fed to the optimizer as
    # ragged vectors. Display and optimization stay in step (both exclude them).
    editor = Editor()  # 5-limit meantone
    editor.set_target_spec("11-OLD")  # an 11-odd-limit diamond reaches 7/4, 11/8, ... (primes 7, 11)
    shown = service.target_interval_set("11-OLD", editor.state.domain_basis)
    assert "7/4" not in shown and "11/8" not in shown  # out-of-domain intervals dropped
    assert "5/4" in shown  # in-domain ones kept
    editor.layout()  # the grid (which optimizes over the set) renders rather than crashing


def test_a_unison_target_does_not_break_simplicity_weighting():
    # a unison (1/1) has complexity 0, so a simplicity weight would be 1/0 = inf and crash the
    # solver. Unisons are dropped from the target set (no mistuning to optimize).
    editor = Editor()
    editor.set_weight_slope("simplicity-weight")
    editor.set_target_override_vectors([[0, 0, 0], [-1, 1, 0]])  # 1/1 and 3/2
    tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis,
                         targets=editor.target_override)
    assert len(tuning_map.tuning_map) == 3 and all(v == v and abs(v) < 1e6 for v in tuning_map.tuning_map)


def test_a_domain_change_forgets_stale_held_interest_and_prescaler():
    # held intervals, intervals of interest, and a hand-edited prescaler are dimension-specific
    # (d-length vectors / diagonal). A domain ± changes d, so they are forgotten — like the typed
    # target list already is — rather than lingering at the old dimension and desyncing/crashing.
    for walk in ("expand", "shrink"):
        editor = Editor()
        if walk == "shrink":
            editor.try_edit_mapping_text("[⟨1 0 -4 -13] ⟨0 1 4 10]}")  # 7-limit (d=4), room to shrink
        editor.set_held_vectors([tuple([-1, 1, 0] + [0] * (editor.state.d - 3))])
        editor.set_interest_vectors([tuple([-2, 0, 1] + [0] * (editor.state.d - 3))])
        editor.set_custom_prescaler_entry(0, 0, 2.0)
        getattr(editor, walk)()
        assert editor.held_vectors == [] and editor.interest_vectors == []
        assert editor.custom_prescaler is None
        editor.layout()  # renders cleanly with the stale state gone


def test_editing_to_a_degenerate_temperament_is_rejected():
    # a typed mapping/comma that isn't a proper temperament (dependent rows, or a prime tempered
    # to a unison) is rejected — the state is left untouched so the caller can toast and revert.
    editor = Editor()
    before = editor.state.mapping
    assert editor.try_edit_mapping_text("[⟨1 2] ⟨0 0]}") is False  # a dependent / zero row
    assert editor.state.mapping == before
    assert editor.try_edit_comma_basis_text("[1 0 0⟩") is False  # tempering out 2/1 sends prime 2 to a unison
    assert editor.state.mapping == before


def test_remove_comma_un_tempers_the_last_comma_to_just_intonation():
    # the comma − un-tempers down to AND INCLUDING the sole comma — the comma-space face of adding a
    # generator, reaching nullity 0. Removing meantone's 81/80 leaves 5-limit just intonation (the
    # identity mapping), one undoable edit.
    editor = Editor()
    editor.remove_comma()
    assert (editor.state.d, editor.state.r, editor.state.n) == (3, 3, 0)  # full rank: nothing tempered
    assert editor.state.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))  # JI over 2.3.5
    editor.undo()
    assert editor.state.comma_basis == ((4, -4, 1),)  # one undoable edit restores meantone


def test_remove_comma_is_a_noop_with_nothing_tempered():
    # at nullity 0 (full rank, no comma) there is nothing to un-temper, so the − self-guards (and
    # the UI hides it); the + adds a comma back. Reaching n=0 first, a second − must not crash.
    editor = Editor()
    editor.remove_comma()  # meantone -> JI (n=0)
    assert editor.state.n == 0
    editor.remove_comma()  # guarded no-op
    assert editor.state.n == 0 and editor.can_undo is True  # still just the one edit


def _cents_map(values):
    return tuple(service.cents(v) for v in values)  # compare tuning maps at the shown 3-dp


def test_flip_generator_reverses_the_mapping_row_and_keeps_the_tuning_map():
    editor = Editor()
    # a generator and its mapping row are the same quantity: flipping the generator's sign
    # reverses its direction, so its mapping row negates too and the prime tuning map 𝒕 = 𝒈𝑀 is
    # unchanged — the temperament sounds identical, the generator just points the other way.
    tuning_map_before = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
    row1_before, row0 = editor.state.mapping[1], editor.state.mapping[0]
    gen1_before = editor.optimum_generator_tuning()[1]
    editor.flip_generator(1)
    assert editor.state.mapping[1] == tuple(-x for x in row1_before)  # row negated
    assert editor.state.mapping[0] == row0                            # the other row untouched
    assert _cents_map([editor.optimum_generator_tuning()[1]]) == _cents_map([-gen1_before])
    tuning_map_after = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
    assert _cents_map(tuning_map_after) == _cents_map(tuning_map_before)  # 𝒕 unchanged
    assert editor.can_undo is True
    editor.undo()
    assert editor.state.mapping[1] == row1_before  # one undoable edit restores the row


def test_flip_generator_with_a_frozen_tuning_negates_its_size_and_holds_the_tuning_map():
    editor = Editor()
    editor.set_generator_tuning_component(1, 700.0)  # freeze a manual tuning off the optimum
    eff_before = editor.effective_generator_tuning()
    t_before = service.tuning_from_generators(editor.state.mapping, eff_before).tuning_map
    editor.flip_generator(1)
    eff_after = editor.effective_generator_tuning()
    assert eff_after[1] == -700.0 and eff_after[0] == eff_before[0]  # only generator 1 negated
    t_after = service.tuning_from_generators(editor.state.mapping, eff_after).tuning_map
    assert _cents_map(t_after) == _cents_map(t_before)  # the frozen tuning's 𝒕 is held


def test_nudge_generator_tuning_component_steps_by_a_thousandth_of_a_cent():
    editor = Editor()
    optimum = editor.optimum_generator_tuning()
    shown = round(optimum[1], 3)  # the cell shows this generator's tuning at 3 dp
    # one scroll-up notch raises this generator by 1/1000 of a cent (and, like a typed edit,
    # freezes the tuning as a manual override with the rest seeded from the optimum)
    editor.nudge_generator_tuning_component(1, 1)
    eff = editor.effective_generator_tuning()
    assert eff[1] == round(shown + 0.001, 3)
    assert eff[0] == optimum[0]
    assert editor.manual_tuning is True
    assert editor.can_undo is True
    # one scroll-down notch moves it the other way, back to where it started
    editor.nudge_generator_tuning_component(1, -1)
    assert editor.effective_generator_tuning()[1] == shown


def test_consecutive_generator_nudges_coalesce_into_one_undo_step():
    editor = Editor()
    shown = round(editor.optimum_generator_tuning()[1], 3)  # the cell shows the optimum at 3 dp
    # three notches in one scroll gesture on the same generator is ONE undo step — so a single
    # undo reverts the whole fine-tune, not three undos for one continuous scroll
    editor.nudge_generator_tuning_component(1, 1)
    editor.nudge_generator_tuning_component(1, 1)
    editor.nudge_generator_tuning_component(1, 1)
    assert editor.effective_generator_tuning()[1] == round(shown + 0.003, 3)
    editor.undo()
    assert editor.effective_generator_tuning() is None  # one undo: scheme-driven again, all 3 reverted
    assert editor.can_undo is False


def test_nudging_a_different_generator_starts_a_new_undo_step():
    editor = Editor()
    optimum = editor.optimum_generator_tuning()
    editor.nudge_generator_tuning_component(0, 1)  # gesture A: generator 0
    editor.nudge_generator_tuning_component(1, 1)  # gesture B: a DIFFERENT generator -> its own step
    editor.undo()  # reverts only gesture B, leaving gesture A applied
    eff = editor.effective_generator_tuning()
    assert eff[0] == round(round(optimum[0], 3) + 0.001, 3)  # A survives
    assert eff[1] == optimum[1]                               # B undone, back to the seeded optimum


def test_an_edit_between_nudges_breaks_the_coalescing():
    editor = Editor()
    editor.nudge_generator_tuning_component(1, 1)    # gesture A on generator 1
    editor.set_generator_tuning_component(0, 700.0)  # a separate typed edit on generator 0
    a_then_typed = editor.effective_generator_tuning()
    editor.nudge_generator_tuning_component(1, 1)    # gesture B on generator 1 -> its own undo step
    # one undo reverts ONLY gesture B — not the typed edit too — proving the edit ended the gesture
    # (were B still coalescing with A, the undo would jump back past the typed edit instead)
    editor.undo()
    assert editor.effective_generator_tuning() == a_then_typed


def test_displayed_tuning_scheme_name_drops_to_none_when_the_tuning_deviates():
    # the tuning chooser shows the scheme name only while the displayed tuning realises that
    # scheme; once it deviates the name drops to None (the chooser then shows "-").
    editor = Editor()
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # default: the scheme's own optimum
    # hand-editing the generator tuning map off the optimum is a deviation
    editor.set_generator_tuning_component(1, 700.0)
    assert editor.displayed_tuning_scheme_name is None
    # a control-refined scheme (a finite optimization power) is still named: miniRMS over the target
    # list reads as its systematic name now that a spec can be rendered, rather than dropping to "-"
    fresh = Editor()
    fresh.set_optimization_power(2.0)  # a finite-power (miniRMS) refined spec, realised at once
    assert fresh.displayed_tuning_scheme_name == "miniRMS-U"


def test_displayed_tuning_scheme_name_keeps_the_name_when_the_tuning_still_matches():
    # a manual tuning typed back AT the scheme's optimum (its displayed cents) is not a
    # deviation — the displayed tuning still realises the scheme — so the name stays.
    editor = Editor()
    optimum = editor.optimum_generator_tuning()
    editor.set_generator_tuning_component(1, round(optimum[1], 3))  # the cell's own shown value
    assert editor.effective_generator_tuning() is not None  # a manual tuning is set...
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # ...but it matches at 3 dp
    # a stale manual tuning the grid ignores (its generator count no longer fits the mapping,
    # here after the domain expands and re-ranks) also keeps the name — the grid then shows the
    # scheme's optimum, not the stale override
    editor.expand()
    assert len(editor.effective_generator_tuning()) != editor.state.r
    assert editor.displayed_tuning_scheme_name == "minimax-U"


def test_displayed_tuning_scheme_name_drops_to_none_when_a_held_interval_deviates_the_tuning():
    # holding an interval re-optimizes IMMEDIATELY (optimization is always on) to hold it just;
    # when that pulls the tuning off the BARE scheme's optimum, the displayed tuning no longer
    # realises the established scheme, so the chooser must show "-". Regression: the deviation
    # check only watched a manual generator override against the held-AWARE optimum, so a
    # held-interval-induced deviation slipped through and the name wrongly stuck.
    editor = Editor()
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    editor.set_held_vectors([(-1, 1, 0)])  # hold 3/2 -> pulls the tuning off bare minimax-U
    assert editor.displayed_tuning_scheme_name is None
    # a held interval the bare scheme ALREADY satisfies (the octave, tuned pure by minimax-U) is
    # not a deviation — the optimum is unchanged — so the name stays
    octave = Editor()
    octave.set_held_vectors([(1, 0, 0)])
    assert octave.displayed_tuning_scheme_name == "minimax-U"


def test_a_scheme_control_pick_tracks_the_established_scheme_name():
    # picking a different scheme re-establishes it (minimax-U -> minimax-C via the weight slope,
    # -> miniRMS-U via the optimization power); the chooser must track the new name. Optimization
    # is always on, so a scheme-driven tuning realises each newly-established scheme at once and
    # the name follows the pick rather than dropping to "-".
    editor = Editor()
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    editor.set_weight_slope("complexity-weight")
    assert editor.displayed_tuning_scheme_name == "minimax-C"
    editor.set_weight_slope("simplicity-weight")
    assert editor.displayed_tuning_scheme_name == "minimax-S"
    editor.set_weight_slope("unity-weight")
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    editor.set_optimization_power(2.0)  # a different (finite-power) scheme, still named
    assert editor.displayed_tuning_scheme_name == "miniRMS-U"


def test_a_hand_edit_blanks_the_chooser_even_after_a_scheme_pick():
    # a scheme pick names the chooser, but a SUBSEQUENT hand-edit is a genuine custom tuning that
    # leaves the scheme — so it still blanks to "-". (Order matters: only a LATER chooser pick
    # clears the hand-edit, per the sibling test below.)
    editor = Editor()
    editor.set_weight_slope("complexity-weight")
    assert editor.displayed_tuning_scheme_name == "minimax-C"  # the pick is named
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit off the optimum
    assert editor.displayed_tuning_scheme_name is None  # the custom tuning blanks it


def test_a_scheme_pick_clears_a_hand_edit_and_names_the_picked_scheme():
    # picking a scheme from the chooser ESTABLISHES it: the pick clears any manual override and
    # the grid retunes to the picked scheme's optimum — so the chooser names the pick rather than
    # staying blanked at "-". (Without an optimize button, the pick must apply itself.)
    editor = Editor()
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit -> "-"
    assert editor.displayed_tuning_scheme_name is None
    editor.set_tuning_scheme("minimax-C")  # the pick drops the hand-edit and retunes
    assert editor.manual_tuning is False
    assert editor.effective_generator_tuning() is None  # scheme-driven again
    assert editor.displayed_tuning_scheme_name == "minimax-C"


def test_manual_tuning_status_travels_with_the_document():
    # the manual-edit status is document state: it survives serialize/load (a page refresh) and is
    # restored by undo, so a hand-edited tuning keeps reading as off-scheme ("-") across both.
    editor = Editor()
    editor.set_weight_slope("complexity-weight")
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit -> "-"
    assert editor.displayed_tuning_scheme_name is None
    reloaded = Editor()
    reloaded.load(editor.serialize())
    assert reloaded.displayed_tuning_scheme_name is None  # the status persisted across a refresh
    editor.undo()  # back to before the hand-edit (the scheme pick still stands)
    assert editor.displayed_tuning_scheme_name == "minimax-C"  # the status was restored to non-manual


def test_load_reoptimizes_an_old_docs_non_manual_frozen_tuning():
    # docs saved before always-on optimization could carry a FROZEN scheme optimum: generator_tuning
    # set with manual_tuning false. That tuning was never a deliberate override, so it loads
    # scheme-driven (generator_tuning None) and re-optimizes on the spot; only a genuine manual
    # override (manual_tuning true) round-trips.
    editor = Editor()
    data = editor.serialize()
    data["generator_tuning"] = [1200.0, 696.578]  # an old doc's frozen (non-manual) optimum
    data["manual_tuning"] = False
    old = Editor()
    old.load(data)
    assert old.generator_tuning is None  # the frozen tuning was dropped -> scheme-driven
    del data["manual_tuning"]  # an even older doc without the key behaves the same
    older = Editor()
    older.load(data)
    assert older.generator_tuning is None
    # a manual override is a deliberate hand-edit — it survives the reload intact
    editor.set_generator_tuning_component(1, 700.0)
    manual = Editor()
    manual.load(editor.serialize())
    assert manual.generator_tuning == editor.generator_tuning
    assert manual.manual_tuning is True


def test_displayed_tuning_scheme_name_keeps_the_name_under_a_typed_target_list():
    # a typed explicit target list changes WHICH intervals the scheme optimises over, but it is
    # still the same named scheme (the target set is a separate control, and the chooser lists
    # target-agnostic base names). It is neither a hand-edit nor a held interval, so the chooser
    # keeps the name — the always-on optimization re-tunes over the typed list at once and the
    # name holds, which needs the bare comparison to optimise over the SAME typed list, else a
    # held interval over a typed list would mis-read.
    editor = Editor()
    editor.set_target_override_vectors([(-1, 1, 0), (-2, 0, 1)])  # type 3/2, 5/4 as the target list
    assert editor.target_override == ("3/2", "5/4")
    assert editor.displayed_tuning_scheme_name == "minimax-U"  # the scheme is unchanged -> name kept


def test_picking_a_scheme_retunes_immediately():
    # picking a scheme from the chooser applies it on the spot: the grid's displayed tuning
    # changes to the new scheme's optimum with no further step (optimization is always on, and
    # without an optimize button the pick is the only act there is).
    editor = Editor()
    gens = lambda: {c.id: c.text for c in editor.layout().cells}["tuning:gen:1"]
    before = gens()  # the default minimax-U optimum
    editor.set_tuning_scheme("minimax-S")
    assert gens() != before  # the pick alone retuned the grid
    assert editor.effective_generator_tuning() is None  # scheme-driven: no stored override
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def test_tuning_is_optimized_tracks_whether_the_grid_shows_the_optimum():
    # the mean damage wraps in min() only while the displayed tuning sits at the scheme's optimum.
    editor = Editor()
    assert editor.tuning_is_optimized is True  # default: scheme-driven, the grid shows the optimum
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit a generator off the optimum
    assert editor.tuning_is_optimized is False
    editor.back_to_scheme()  # hand the wheel back to the scheme -> the optimum again
    assert editor.tuning_is_optimized is True


def test_tuning_is_optimized_holds_under_held_intervals():
    # a held interval re-optimizes immediately to a held-CONSTRAINED optimum — still optimized
    # (unlike the scheme NAME, which drops to "-" because the held tuning leaves the bare
    # scheme), so min() stays
    held = Editor()
    held.add_held()
    held.set_held_vectors([(-1, 1, 0)])  # hold 3/2 -> the held-constrained optimum, at once
    assert held.displayed_tuning_scheme_name is None  # the name leaves the bare scheme...
    assert held.tuning_is_optimized is True            # ...but the displayed tuning is its (held) optimum
    held.set_generator_tuning_component(1, 700.0)      # hand-edit off the held optimum
    assert held.tuning_is_optimized is False


def test_layout_wraps_the_mean_damage_symbol_in_min_while_optimized():
    # end to end: the editor feeds tuning_is_optimized into the layout, so the rendered mean damage
    # symbol carries the min() wrap while optimized and drops it after a manual generator deviation.
    editor = Editor()
    editor.set_show("optimization", True)

    def mean_damage_symbol() -> str:
        return {c.id: c for c in editor.layout().cells}["optimization:mean_damage:symbol"].text

    assert mean_damage_symbol() == "min(⟪𝐝⟫ₚ)"  # default: the displayed tuning is the scheme's optimum
    editor.set_generator_tuning_component(1, 700.0)  # hand-edit a generator off the optimum
    assert mean_damage_symbol() == "⟪𝐝⟫ₚ"


def test_symbols_toggle_gates_the_control_label_symbols():
    # the math symbols that label the tuning-panel controls — 𝑝 over the optimization power,
    # min(⟪𝐝⟫ₚ) over the mean damage, 𝑞 over the complexity norm power — belong to the symbols
    # Show layer exactly like the grid's symbol row. Turning symbols off drops the symbol cells;
    # the word captions beneath them stay.
    editor = Editor()
    editor.set_show("optimization", True)
    editor.set_show("weighting", True)
    editor.set_weight_slope("complexity-weight")  # a non-unity slope reveals the complexity box

    def ids() -> set[str]:
        return {c.id for c in editor.layout().cells}

    symbol_ids = {"optimization:power:symbol", "optimization:mean_damage:symbol", "symbol:q"}
    caption_ids = {"optimization:power:caption", "optimization:mean_damage:caption", "caption:q"}

    on = ids()
    assert symbol_ids <= on
    assert caption_ids <= on

    editor.set_show("symbols", False)
    off = ids()
    assert symbol_ids.isdisjoint(off)  # every control symbol disappears
    assert caption_ids <= off          # but its word caption remains


def test_hiding_control_symbols_collapses_the_symbol_band():
    # the symbol band isn't merely hidden — it collapses, so the caption rides up directly under
    # its control (matching how the grid's symbol row collapses when symbols are off).
    editor = Editor()
    editor.set_show("optimization", True)

    def caption_top() -> float:
        return {c.id: c for c in editor.layout().cells}["optimization:power:caption"].y

    with_symbols = caption_top()
    editor.set_show("symbols", False)
    assert caption_top() < with_symbols


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


def test_the_tuning_follows_a_changed_target_interval_list():
    # the optimum minimizes damage over the target intervals, so changing the list retunes the
    # scheme-driven tuning automatically (no apply step). Before, the optimum ignored a typed
    # override (it read the scheme's named TILT set), so editing the list left the tuning put —
    # the bug Douglas hit.
    editor = Editor()
    tilt_optimum = editor.optimum_generator_tuning()  # over the default TILT family
    editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩")  # change the list to just 2/1 + 3/2
    assert editor.optimum_generator_tuning() != tilt_optimum  # the tuning followed the new targets


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
    # EVERY implemented toggle turns on with select-all — including custom weights (a sticky SETTING,
    # always checkable) and all-interval (a two-step visibility toggle). No toggle disables or resists
    # another, so select-all is always possible — and select-none turns them all back off.
    editor = Editor()
    editor.set_all_show(True)  # the panel's select-all
    assert all(editor.settings[k] for k in settings.IMPLEMENTED)  # everything on, custom weights too
    editor.set_all_show(False)  # ...and select-none
    assert not any(editor.settings[k] for k in settings.IMPLEMENTED)
    editor.undo()  # one undo restores the whole all-on set (a single action)
    assert all(editor.settings[k] for k in settings.IMPLEMENTED)


def test_deselecting_a_parent_also_deselects_its_subcontrols():
    # a hidden parent must not leave its sub-controls' content stranded on screen: deselecting
    # the "temperament" group turns its boxes AND their colorization (both direct children) off
    editor = Editor()
    editor.set_show("temperament_colorization", True)
    assert editor.settings["temperament_colorization"] is True
    editor.set_show("temperament", False)
    assert editor.settings["temperament_tiles"] is False
    assert editor.settings["temperament_colorization"] is False


def test_deselecting_a_parent_cascades_through_nested_subcontrols():
    # the cascade is transitive and now four deep: "tuning" -> "optimization" -> "weighting" ->
    # "all-interval"/"alt. complexity"/"custom weights", so deselecting the group turns the
    # grandchildren and great-grandchildren off too (else their panel rows orphan and their content
    # lingers when the group is hidden).
    editor = Editor()
    for key in ("weighting", "all_interval", "alt_complexity", "custom_weights",
                "tuning_ranges", "optimization"):
        editor.set_show(key, True)
    editor.set_show("tuning", False)
    for key in ("tuning", "tuning_tiles", "weighting", "all_interval", "alt_complexity",
                "custom_weights", "tuning_ranges", "optimization", "projection",
                "tuning_colorization"):
        assert editor.settings[key] is False


def test_deselecting_optimization_cascades_the_optimize_subaxes():
    # "optimization" is now a content+parent: deselecting it (Mode A) turns off everything beneath
    # it — weighting and its three refinements, plus tuning ranges — but leaves its siblings
    # (tuning tiles, projection) alone.
    editor = Editor()
    for key in ("weighting", "all_interval", "alt_complexity", "custom_weights", "tuning_ranges"):
        editor.set_show(key, True)
    editor.set_show("projection", True)
    editor.set_show("optimization", False)
    for key in ("optimization", "weighting", "all_interval", "alt_complexity",
                "custom_weights", "tuning_ranges"):
        assert editor.settings[key] is False, key
    assert editor.settings["tuning"] is True       # the grouping parent stays
    assert editor.settings["projection"] is True   # a sibling, untouched


def test_the_subcontrol_cascade_is_one_undoable_action():
    editor = Editor()
    editor.set_show("temperament_colorization", True)
    editor.set_show("temperament", False)  # deselects the group: boxes + colorization together
    assert editor.settings["temperament_colorization"] is False
    editor.undo()  # a single undo brings the group AND its sub-controls back
    assert editor.settings["temperament"] is True
    assert editor.settings["temperament_tiles"] is True
    assert editor.settings["temperament_colorization"] is True


def test_selecting_a_parent_does_not_force_its_subcontrols_on():
    # only deselecting cascades; re-selecting a parent leaves the (now-off) sub-controls
    # off rather than resurrecting them
    editor = Editor()
    editor.set_show("temperament", False)  # boxes + colorization off
    editor.set_show("temperament", True)   # re-expand the group
    assert editor.settings["temperament_tiles"] is False
    assert editor.settings["temperament_colorization"] is False


def test_selecting_a_subcontrol_pulls_its_parent_on():
    # the mirror of the off-cascade: a refinement can't show without the layer it refines, so
    # selecting it pulls the parent on too (equivalences shows symbols as equations, mnemonics
    # underlines a name). Enabling equivalences/mnemonics therefore enables symbols/names.
    editor = Editor()
    editor.set_show("symbols", False)  # symbols ships ON now (cascades equivalences off); turn it
    assert editor.settings["symbols"] is False  # off so the pull-on below is observable
    assert editor.settings["equivalences"] is False
    editor.set_show("equivalences", True)
    assert editor.settings["equivalences"] is True
    assert editor.settings["symbols"] is True  # pulled on with its refinement
    editor.set_show("names", False)  # cascades mnemonics off
    editor.set_show("mnemonics", True)
    assert editor.settings["names"] is True  # pulled back on with its refinement


def test_selecting_a_nested_subcontrol_pulls_its_whole_parent_chain_on():
    # the pull-on is transitive, mirroring the off-cascade: "all-interval" -> "weighting" ->
    # "optimization" -> "tuning", so selecting the great-grandchild pulls the whole chain on (else
    # it would show while the branch it lives in stays hidden). Note it pulls "optimization"/"tuning"
    # on, NOT "tuning tiles" — that is a sibling, not an ancestor.
    editor = Editor()
    editor.set_show("tuning", False)  # cascades the whole tuning group off
    assert editor.settings["weighting"] is False
    editor.set_show("all_interval", True)
    for key in ("all_interval", "weighting", "optimization", "tuning"):
        assert editor.settings[key] is True
    assert editor.settings["tuning_tiles"] is False  # a sibling, not pulled on by all-interval


def test_grouping_parents_flatten_their_box_toggles_former_children():
    # the regroup is a flatten, not an extra nesting level: what used to be a direct child of a
    # box toggle is now a direct child of the GROUP, level with the box toggle (a sibling), not
    # buried under it. So "temperament colorization" answers to "temperament" (not to
    # "temperament tiles"), and the whole tuning column answers to "tuning" (not "tuning tiles").
    assert settings.SUBCONTROLS["temperament_colorization"] == "temperament"
    assert settings.SUBCONTROLS["temperament_tiles"] == "temperament"
    # the tuning group's DIRECT children are the two modes' shared base + the two modes themselves
    for key in ("tuning_tiles", "optimization", "projection", "tuning_colorization"):
        assert settings.SUBCONTROLS[key] == "tuning", key
    # "optimization" (Mode A) parents the optimize sub-axes — weighting and tuning ranges
    assert settings.SUBCONTROLS["weighting"] == "optimization"
    assert settings.SUBCONTROLS["tuning_ranges"] == "optimization"
    # weighting's three refinements are siblings under it
    assert settings.SUBCONTROLS["all_interval"] == "weighting"
    assert settings.SUBCONTROLS["alt_complexity"] == "weighting"
    assert settings.SUBCONTROLS["custom_weights"] == "weighting"
    # deselecting "tuning tiles" (now a leaf) strands nothing — it has no sub-controls of its own
    editor = Editor()
    editor.set_show("optimization", True)
    editor.set_show("tuning_tiles", False)
    assert editor.settings["optimization"] is True  # the sibling is untouched by the box toggle


def test_form_is_a_live_layer_not_a_pure_grouping_parent():
    # "form" heads the form group like temperament/tuning, but unlike those pure grouping parents
    # it carries a real grid layer (the canonical-form subscript C), so it is LIVE (in IMPLEMENTED)
    # and NOT in GROUPING_PARENTS. It defaults OFF (the subscript is opt-in, and its group starts
    # collapsed), and being implemented its saved value is honoured rather than pinned.
    assert settings.DEFAULTS["form"] is False
    assert "form" in settings.IMPLEMENTED
    assert "form" not in settings.GROUPING_PARENTS
    assert {"temperament", "tuning"} <= settings.GROUPING_PARENTS  # the pure grouping parents
    assert settings.from_persisted({"form": True})["form"] is True  # honoured (it's implemented)


def test_expand_collapse_state_is_owned_and_undoable():
    editor = Editor()
    # nothing starts folded — the default view opens every row and column
    assert editor.collapsed == set()
    editor.toggle_collapsed("col:commas")  # fold the commas column
    assert "col:commas" in editor.collapsed
    assert editor.can_undo is True  # folding/unfolding is an undoable change
    editor.undo()
    assert "col:commas" not in editor.collapsed
    editor.set_collapsed({"row:tuning"})  # the master expand/collapse-all replaces the set
    assert editor.collapsed == {"row:tuning"}
    editor.undo()
    assert editor.collapsed == set()  # back to the prior fold state (nothing folded)


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
    assert editor.collapsed == set()  # reset folds nothing — the default board is fully expanded
    assert editor.can_reset is False
    editor.undo()  # a single undo brings the whole prior document back
    assert editor.state.mapping == ((1, 0, -4), (0, 1, 4))
    assert service.base_scheme_name(editor.tuning_scheme) == "held-octave minimax-ES"
    assert editor.settings["charts"] is True
    assert "col:commas" in editor.collapsed


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
    # the full target-based scheme round-trips: destretched-octave minimax-ES over the chosen
    # 9-OLD family. Compared as the resolved spec (robust to the name/spec representation); the
    # destretched-octave modifier in particular must survive (it once silently vanished).
    restored_spec = service.resolve_tuning_scheme(restored.tuning_scheme)
    assert restored_spec == service.resolve_tuning_scheme(editor.tuning_scheme)
    assert service.base_scheme_name(restored.tuning_scheme) == "destretched-octave minimax-ES"
    assert restored_spec.target_intervals == "9-OLD"
    assert restored.target_spec == "9-OLD"
    assert restored.interest_vectors == [(-1, 1, 0)]
    assert restored.held_vectors == [(1, 0, 0)]
    assert restored.range_mode == "tradeoff"
    assert restored.settings["charts"] is True
    assert "col:commas" in restored.collapsed
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


def test_load_pins_a_shelved_toggle_to_its_default(monkeypatch):
    # a saved document can carry a toggle that has since been shelved (pulled from
    # IMPLEMENTED because the feature isn't ready to expose). Loading it must not
    # resurrect that feature: greyed toggles are pinned to their defaults whatever the
    # blob says, so IMPLEMENTED stays the single source of truth for what the grid shows.
    # Every real toggle is live now, so simulate a shelved one by dropping a toggle from
    # IMPLEMENTED for this test (from_persisted reads the module global at call time).
    key = "form_colorization"  # any implemented, non-grouping-parent toggle
    monkeypatch.setattr(settings, "IMPLEMENTED", settings.IMPLEMENTED - {key})
    editor = Editor()
    data = editor.serialize()
    data["settings"][key] = not settings.DEFAULTS[key]  # a value the panel can no longer set
    restored = Editor()
    restored.load(data)
    assert restored.settings[key] is settings.DEFAULTS[key]  # pinned back to its default


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


def test_no_chooser_scheme_yields_an_invalid_target_less_tuning():
    # A bare simplicity name (minimax-S, miniRMS-S, …) is all-interval, but a bare UNITY or
    # COMPLEXITY name (minimax-U / minimax-C) is an invalid, unpinnable tuning that must never be
    # reachable in the app. It isn't: the tuning-scheme chooser offers those bare strings only as
    # identifiers, and picking one applies the live target set (target-based) while all-interval mode
    # forces the simplicity slope. So every option, in either mode, lands on a scheme that is either
    # all-interval or carries a concrete target list — and thus optimizes to a finite tuning, never
    # the degenerate all-zero (nan-mean-damage) solve. Locks that guarantee across the whole chooser.
    from rtt.app import presets

    editor = Editor()
    for all_interval in (False, True):
        editor.set_all_interval(all_interval)
        options = presets.tuning_scheme_options(
            all_interval, include_alternatives=True, weighting=True)
        for value in options:
            editor.set_tuning_scheme(value)
            spec = service.resolve_tuning_scheme(editor.tuning_scheme)
            if not service.is_all_interval(editor.tuning_scheme):
                assert spec.target_intervals not in (None, "", "{}"), value  # a real target applied
            tm = service.tuning(
                editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis).tuning_map
            assert all(x == x for x in tm), value  # finite (no nan) — a valid, pinnable tuning
# ── chapter-9 domain basis element editing (nonstandard-domain box on) ────────────────────────

def test_set_domain_element_relabels_in_place_and_is_undoable():
    ed = Editor()  # 2.3.5 default
    ed.set_domain_element(2, "13/5")
    assert ed.state.domain_basis == (2, 3, Fraction(13, 5))
    assert ed.state.mapping == Editor().state.mapping  # a pure relabel — coordinates held
    ed.undo()
    assert ed.state.domain_basis == (2, 3, 5)


def test_set_domain_element_rejects_a_dependent_relabel():
    ed = Editor()  # 2.3.5
    ed.set_domain_element(2, "9")  # 2.3.9 is dependent (9 = 3²) — a no-op
    assert ed.state.domain_basis == (2, 3, 5)
    assert not ed.can_undo  # nothing committed, so no undo step


def test_add_element_draft_commits_a_valid_rational_held_just():
    ed = Editor()  # 2.3.5
    ed.add_element()
    assert ed.pending_element == ""  # a blank green ?/? draft, not yet part of the domain
    assert ed.state.d == 3
    ed.set_pending_element("7")  # a valid independent addition commits and clears the draft
    assert ed.pending_element is None
    assert ed.state.domain_basis == (2, 3, 5, 7)
    assert ed.state.d == 4 and ed.state.r == 3  # held just: +d, +r
    ed.undo()
    assert ed.state.domain_basis == (2, 3, 5)


def test_pending_element_holds_an_invalid_or_partial_draft():
    ed = Editor()  # 2.3.5
    ed.add_element()
    ed.set_pending_element("9")  # dependent — kept as a pending draft, domain unchanged
    assert ed.pending_element == "9"
    assert ed.state.domain_basis == (2, 3, 5)


def test_domain_drafts_clear_on_a_domain_change():
    ed = Editor()
    ed.add_element()
    ed.shrink()  # any domain ± invalidates the draft
    assert ed.pending_element is None


def test_add_element_commits_a_nonprime_and_the_grid_builds():
    # regression: committing a held-just nonprime (2.3.5 -> 2.3.5.13/5) must not crash the build —
    # the range solver can't measure that mixed basis, so it degrades to a range-less tuning.
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.add_element()
    ed.set_pending_element("13/5")
    assert ed.state.domain_basis == (2, 3, 5, Fraction(13, 5))
    assert ed.pending_element is None
    ed.layout()  # must not raise


def test_remove_element_cancels_the_draft():
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.add_element()
    ed.remove_element()
    assert ed.pending_element is None


def test_remove_domain_element_drops_a_committed_element_and_is_undoable():
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    before = ed.state
    ed.remove_domain_element(0)  # drop the 2 — an arbitrary (non-last) element, not just the highest
    assert ed.state.domain_basis == (3, Fraction(13, 5)) and ed.state.d == 2
    assert ed.can_undo is True  # a structural edit, undoable (unlike the draft cancel)
    ed.undo()
    assert ed.state.domain_basis == before.domain_basis and ed.state.comma_basis == before.comma_basis


def test_remove_domain_element_clears_an_open_draft():
    # removing an element changes d, which would strand a length-d draft — so it clears it, like shrink
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    ed.add_element()
    assert ed.pending_element == ""
    ed.remove_domain_element(2)  # drop the 13/5
    assert ed.pending_element is None and ed.state.domain_basis == (2, 3)


def test_remove_domain_element_is_a_no_op_at_the_last_element():
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_mapping(((1,),))  # d == 1: a domain keeps at least one element
    ed.remove_domain_element(0)
    assert ed.state.d == 1 and ed.can_undo is False  # nothing removed, no snapshot taken


def test_established_projection_shows_for_the_default_meantone():
    # the default minimax-U meantone IS quarter-comma — it holds 2/1 and 5/4 at zero damage — so the
    # established-projection chooser reads "1/4-comma" with a real P, NOT a placeholder. U is read off
    # the tuning itself, not the (empty) held column.
    ed = Editor()
    assert ed.held_vectors == []                      # nothing deliberately held
    assert ed.unchanged_ratios == ("2/1", "5/4")
    assert ed.displayed_projection_scheme_name == "1/4-comma"


def test_set_established_projection_sets_the_tuning_not_the_held_column():
    ed = Editor()
    ed.set_established_projection("1/3-comma")
    # picking does NOT touch the held column — only the user deliberately holds intervals
    assert ed.held_vectors == []
    # 𝒈 actually re-solved to third-comma (1200, 694.786) — the tuning CHANGED
    assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
    # U, and so the chooser, follow from the tuning
    assert ed.unchanged_ratios == ("2/1", "6/5")
    assert ed.displayed_projection_scheme_name == "1/3-comma"
    # a deliberate tuning override isn't the bare scheme's optimum, so the scheme chooser drops to "-"
    assert ed.displayed_tuning_scheme_name is None


def test_try_edit_projection_text_retunes_or_rejects():
    # the editable P plain-text band: a valid map-list EBK string retunes to the projection it defines;
    # an unparseable or non-idempotent one returns False (state untouched) so the caller toasts/reddens
    ed = Editor()
    assert ed.try_edit_projection_text("[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩") is True  # 1/3-comma P
    assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
    assert ed.try_edit_projection_text("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩") is False   # P[0][0]=2 → P² ≠ P
    assert ed.try_edit_projection_text("not a matrix") is False
    assert ed.try_edit_projection_text("[[1 0 0⟩[0 1 0⟩[0 0 1⟩]") is False   # a vector list, not a map
    # the rejected edits left the third-comma tuning from the first (valid) edit untouched
    assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]


def test_try_edit_embedding_text_retunes_or_rejects():
    # the editable G plain-text band: a valid vector-list EBK string (its r kets transposed into d×r)
    # retunes; an invalid embedding (𝑀𝐺 ≠ 𝐼) or wrong variance/shape returns False
    ed = Editor()
    assert ed.try_edit_embedding_text("{[1 0 0⟩[1/3 -1/3 1/3⟩]") is True   # 1/3-comma G
    assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
    assert ed.try_edit_embedding_text("{[0 0 0⟩[0 0 1/4⟩]") is False       # zeroed column → 𝑀𝐺 ≠ 𝐼
    assert ed.try_edit_embedding_text("[⟨1 1 0]⟨0 1 4]}") is False         # a map, not a vector list


def test_try_edit_projection_text_is_undoable():
    ed = Editor()
    assert ed.try_edit_projection_text("[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩") is True
    assert ed.manual_tuning is True
    ed.undo()
    assert ed.manual_tuning is False  # back to the auto optimum (default 1/4-comma)
    assert ed.displayed_projection_scheme_name == "1/4-comma"


def test_set_established_projection_is_undoable():
    ed = Editor()
    ed.set_established_projection("1/3-comma")
    assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
    assert ed.displayed_projection_scheme_name == "1/3-comma"
    ed.undo()
    # undo restores the auto optimum (the default 1/4-comma meantone), not the frozen third-comma
    assert ed.manual_tuning is False
    assert ed.displayed_projection_scheme_name == "1/4-comma"


def test_established_projection_reflects_a_hand_typed_held_basis():
    # holding {2/1, 5/4} pins the tuning to quarter-comma, so U realises that named projection and
    # the chooser shows 1/4-comma without ever touching the dropdown
    ed = Editor()
    v = lambda r: tuple(service.interval_vector(r, ed.state.d, ed.state.domain_basis))
    ed.set_held_vectors([v("2/1"), v("5/4")])
    assert ed.unchanged_ratios == ("2/1", "5/4")
    assert ed.displayed_projection_scheme_name == "1/4-comma"


def test_a_held_interval_always_appears_in_the_unchanged_basis():
    # ch3: "anything in the held-interval basis will always be in the unchanged-interval basis too."
    # 9/8 is NOT one of the temperament's clean projection-candidate ratios, but the optimizer holds
    # it (zero damage), so it must be the representative U shows for its direction — not some other
    # basis of the same subspace (the pre-fix bug reported 2/1, 3/2 and dropped the held 9/8).
    ed = Editor()
    v = lambda r: tuple(service.interval_vector(r, ed.state.d, ed.state.domain_basis))
    ed.set_held_vectors([v("9/8")])
    assert "9/8" in ed.unchanged_ratios            # the held interval itself, not a stand-in
    assert ed.unchanged_ratios[0] == "9/8"         # and FIRST — it overrides the auto-picked rep
    assert service.interval_vector("9/8", ed.state.d, ed.state.domain_basis) in (
        service.unchanged_interval_basis(ed.state, ed.unchanged_ratios) or ())


def test_an_unheld_interval_is_never_faked_into_the_unchanged_basis():
    # the flip side: held-first must NOT lie. A manual tuning that genuinely does not hold the held
    # interval (here 12-EDO meantone changes 9/8) leaves it out of U, dashing the unpinned direction.
    ed = Editor()
    v = lambda r: tuple(service.interval_vector(r, ed.state.d, ed.state.domain_basis))
    ed.set_held_vectors([v("9/8")])
    ed.set_generator_tuning_component(0, 1200.0)
    ed.set_generator_tuning_component(1, 700.0)    # 12-EDO: 9/8 -> 200c, not its just 203.91c
    assert "9/8" not in ed.unchanged_ratios        # not held by THIS tuning, so not claimed unchanged


def _cents_close(a, b):
    return a is not None and b is not None and all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def test_a_held_nonprime_element_appears_in_the_unchanged_basis():
    # ch3's "anything in the held-interval basis will always be in the unchanged-interval basis too",
    # now on a NONSTANDARD (nonprime) domain: holding 9/1 over (2, 9, 5) must put 9/1 itself in U. The
    # pre-fix bug computed the editor's tuning over the STANDARD PRIMES (the domain basis was never
    # threaded into its tuning helpers), which stringified the held (0,1,0) as 3/1 — unparseable over
    # (2,9,5) — and silently dropped it, so U came back as just ('8/5',) with the held 9/1 missing.
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
    ed.set_held_vectors([(0, 1, 0)])               # 9/1, genuinely held
    assert "9/1" in ed.unchanged_ratios            # the held nonprime element itself, not a stand-in
    assert ed.unchanged_ratios[0] == "9/1"         # and FIRST — the hold overrides any auto-picked rep
    assert (0, 1, 0) in (service.unchanged_interval_basis(ed.state, ed.unchanged_ratios) or ())
    assert service.tuning_projection(ed.state, ed.unchanged_ratios) is not None  # P/G render, not dashed


def test_unchanged_basis_tuning_runs_over_the_domain_basis_not_the_standard_primes():
    # U/P/G are read off _displayed_retuning_map, which must run over the actual domain basis — the
    # SAME tuning the grid shows (spreadsheet.build) — not the standard primes. Over (2,9,5) the two
    # genuinely differ, so this pins that the editor tracks the grid, not the primes.
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
    ed.set_held_vectors([(0, 1, 0)])               # 9/1
    held = service.comma_ratios(ed.held_vectors, ed.state.domain_basis)
    grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, held=held)
    over_primes = service.tuning(ed.state.mapping, ed.tuning_scheme, held=("3/1",))  # the old, wrong basis
    editor = ed.displayed_retuning_map()
    assert _cents_close(editor, grid.retuning_map)            # tracks the grid (domain basis)
    assert not _cents_close(editor, over_primes.retuning_map)  # NOT the standard-primes tuning


def test_unchanged_basis_threads_the_nonprime_approach():
    # the grid's tuning takes BOTH the domain basis and the nonprime approach (the chapter-9 trait);
    # the editor's U/P/G must thread the approach too, or they diverge from the grid on a nonprime
    # domain whenever the approach moves the optimum. minimax-S over 2.7/3.11/3 is such a case:
    # nonprime-based retunes away from neutral. Each approach must match the grid run with it.
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    ed.set_weight_slope("simplicity-weight")       # minimax-S — where the approach changes the tuning
    seen = {}
    for approach in ("", "nonprime-based", "prime-based"):
        ed.nonprime_basis_approach = approach
        grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, approach)
        seen[approach] = ed.displayed_retuning_map()
        assert _cents_close(seen[approach], grid.retuning_map)  # the editor tracks the grid for THIS approach
    assert not _cents_close(seen[""], seen["nonprime-based"])    # the approach is load-bearing, not ignored


def test_hand_pinned_nonprime_projection_holds_over_the_domain_basis():
    # the manual-pin path (editing U / picking an established projection) shared the bug: its
    # generator-tuning solve dropped the domain basis, so pinning U={2/1, 9/1} over (2,9,5) solved
    # over the standard primes and held 3/1's worth instead — dropping the just-pinned 9/1 back out
    # of U. Threading the basis makes the pin hold the interval it names, matching the grid's 𝒈.
    ed = Editor()
    ed.settings["nonstandard_domain"] = True
    ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
    assert service.tuning_projection(ed.state, ("2/1", "9/1")) is not None  # a valid full projection
    ed.set_unchanged_basis(("2/1", "9/1"))
    assert ed.unchanged_ratios == ("2/1", "9/1")   # the pinned basis is recovered, the held 9/1 kept
    grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, held=("2/1", "9/1"))
    assert _cents_close(ed.generator_tuning, grid.generator_map)  # the pin's 𝒈 matches the grid's


def test_targets_in_use_tracks_whether_the_tuning_is_the_target_optimum():
    # with the projection box on, the target list is only computing the tuning while the displayed
    # tuning IS the scheme's target-driven optimum
    ed = Editor()
    ed.settings["projection"] = True
    assert ed.targets_in_use is True              # default: the tuning IS the TILT minimax-U optimum
    ed.set_established_projection("1/4-comma")     # 1/4-comma == that optimum, so targets still apply
    assert ed.targets_in_use is True
    deviated = Editor()
    deviated.settings["projection"] = True
    deviated.set_established_projection("1/3-comma")  # a different tuning — targets no longer compute it
    assert deviated.targets_in_use is False


def test_target_list_returns_when_the_projection_box_is_off():
    # the target-list-hiding is a projection-feature behaviour: a deviating projection hides it only
    # while the projection box is on; turning the box off brings the target list back
    ed = Editor()
    ed.settings["projection"] = True
    ed.set_established_projection("1/3-comma")
    assert ed.targets_in_use is False        # projection on + deviated → hidden
    ed.settings["projection"] = False
    assert ed.targets_in_use is True         # projection off → restored


def test_target_column_hides_when_the_tuning_deviates_from_the_optimum():
    # ch3 h+k≥r: once a projection pins the tuning away from the target optimum, the targets play no
    # role, so the whole target interval column disappears (while the projection box is on)
    ed = Editor()
    ed.settings["projection"] = True
    has_targets = lambda: any(c.id.startswith(("target:", "cell:target")) for c in ed.layout().cells)
    assert has_targets()                           # default: the target list is shown
    ed.set_established_projection("1/3-comma")      # deviate onto a projection
    assert not has_targets()                        # the target column is gone


def test_established_projection_round_trips_via_the_generator_tuning():
    # picking sets 𝒈 (a manual tuning), which serializes — so the choice survives a save/reload
    ed = Editor()
    ed.set_established_projection("Pythagorean")
    reloaded = Editor()
    reloaded.load(ed.serialize())
    assert reloaded.displayed_projection_scheme_name == "Pythagorean"


def _has_targets(ed):
    return any(c.id.startswith(("target:", "cell:target")) for c in ed.layout().cells)


def test_hand_edited_full_projection_off_the_candidate_list_hides_the_targets():
    # regression: a COMPLETE rational projection pinned by hand-editing U (here meantone's {2/1, 10/9},
    # which is NOT an established-projection ratio nor in the TILT target set) used to read as under-rank
    # — unchanged_ratios only tested those candidates — so targets_in_use stayed True and the whole
    # target column lingered (with P/G/U dashed). Recording the pinned basis fixes it: the column goes.
    ed = Editor()
    ed.settings["projection"] = True
    assert service.tuning_projection(ed.state, ("2/1", "10/9")) is not None  # a valid full projection
    ed.set_unchanged_basis(("2/1", "10/9"))
    assert ed.unchanged_ratios == ("2/1", "10/9")  # the FULL basis is recovered, not just 2/1
    assert ed.targets_in_use is False
    assert not _has_targets(ed)


def test_full_projection_hides_targets_on_a_temperament_with_no_established_projections():
    # porcupine has no established-projection presets, so the candidate pool is just the target set +
    # held column; a hand-pinned full projection ({2/1, 27/25}) outside it must still hide the column.
    ed = Editor()
    ed.settings["projection"] = True
    ed.edit_mapping(((1, 2, 3), (0, 3, 5)))  # porcupine, r=2, no established projections
    assert service.tuning_projection(ed.state, ("2/1", "27/25")) is not None
    ed.set_unchanged_basis(("2/1", "27/25"))
    assert ed.targets_in_use is False
    assert not _has_targets(ed)


def test_back_to_scheme_restores_the_targets_after_an_off_candidate_pin():
    # the pinned-basis memory clears when the wheel is handed back to the scheme, so the column returns
    ed = Editor()
    ed.settings["projection"] = True
    ed.set_unchanged_basis(("2/1", "10/9"))
    assert not _has_targets(ed)
    ed.back_to_scheme()
    assert ed.projection_basis == ()
    assert ed.targets_in_use is True
    assert _has_targets(ed)


def test_off_candidate_pin_undo_redo_keeps_the_targets_column_correct():
    # the pinned basis lives in the document, so undo/redo flips the targets column with it
    ed = Editor()
    ed.settings["projection"] = True
    ed.set_unchanged_basis(("2/1", "10/9"))
    assert not _has_targets(ed)
    ed.undo()
    assert _has_targets(ed)        # back to the scheme optimum — targets shown
    ed.redo()
    assert not _has_targets(ed)    # the pin (and its hidden column) is restored


def test_off_candidate_pin_round_trips_serialize_and_older_docs_lack_it():
    # the pinned basis serializes, so a refresh keeps the column hidden; an older doc without the key
    # loads cleanly to no pin
    ed = Editor()
    ed.settings["projection"] = True
    ed.set_unchanged_basis(("2/1", "10/9"))
    data = ed.serialize()
    assert data["projection_basis"] == ["2/1", "10/9"]
    reloaded = Editor()
    reloaded.load(data)
    reloaded.settings["projection"] = True
    assert reloaded.projection_basis == ("2/1", "10/9")
    assert reloaded.targets_in_use is False

    data.pop("projection_basis")  # an older saved document predates the field
    legacy = Editor()
    legacy.load(data)
    assert legacy.projection_basis == ()  # defaults to no pin, no crash


def test_a_typed_generator_tuning_drops_a_prior_projection_pin():
    # a free cents map need not be a rational projection, so it clears the pin and falls back to the
    # candidate search (here it lands back near the scheme optimum, so the under-rank/optimum logic runs)
    ed = Editor()
    ed.settings["projection"] = True
    ed.set_unchanged_basis(("2/1", "10/9"))
    assert ed.projection_basis == ("2/1", "10/9")
    ed.set_generator_tuning_text("1200 697")
    assert ed.projection_basis == ()


# ── audit fixes: editor-side tuning seams (Root Cause #1), stale-tuning drops (Root Cause #2), ──
# ── nonstandard-domain preservation, and input/state validation. See EVALUATION_REPORT.md. ────

BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"        # TILT minimax-U optimum ≈ (1199.872, 248.766)
BARBADOS_ALT = "2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}"      # another barbados form, optimum ≈ (1199.872, 951.106)


def test_editor_optimum_uses_the_domain_basis_not_standard_primes():
    # ebk-notation-1 / nonstandard-superspace-2: the editor's own solve must optimize over the
    # document's domain basis, exactly as the grid's solve (spreadsheet.build) does — not over the
    # standard prime limit, which froze an 822 ¢ "octave" on barbados.
    editor = Editor()
    assert editor.try_edit_mapping_text(BARBADOS)
    gens = editor.optimum_generator_tuning()
    grid = service.tuning(editor.state.mapping, editor.tuning_scheme, editor.state.domain_basis).generator_map
    assert _cents_map(gens) == _cents_map(grid)  # editor seam agrees with the grid's reference solve
    assert round(gens[0], 3) == 1199.872 and round(gens[1], 3) == 248.766  # the real optimum, not 822 ¢


def test_editor_optimized_flag_and_scheme_name_are_honest_on_a_nonstandard_domain():
    # nonstandard-superspace-2: with the editor solving over the right basis, the scheme-driven
    # default tuning IS the optimum, so tuning_is_optimized and the chooser name tell the truth
    # (they used to certify the standard-primes garbage as the scheme optimum).
    editor = Editor()
    assert editor.try_edit_mapping_text(BARBADOS_ALT)
    assert editor.tuning_is_optimized is True
    assert editor.displayed_tuning_scheme_name == "minimax-U"
    gens = editor.optimum_generator_tuning()
    assert round(gens[0], 3) == 1199.872 and round(gens[1], 3) == 951.106


def test_editor_optimum_honors_the_custom_prescaler():
    # tuning-core-3 / all-interval-alt-complexity-1: a hand-edited complexity prescaler must reach
    # the editor's solve (as it reaches the grid's), so the frozen/compared optimum is the one the
    # weight/damage rows show and min(⟪𝐝⟫ₚ) names a genuinely minimized value.
    editor = Editor()
    editor.set_weight_slope("simplicity-weight")
    editor.set_custom_prescaler_entry(0, 0, 3.0)
    gens = editor.optimum_generator_tuning()
    grid = service.tuning(editor.state.mapping, editor.tuning_scheme,
                          prescaler_override=editor.custom_prescaler).generator_map
    assert _cents_map(gens) == _cents_map(grid)
    # and a tuning typed back at the prescaler-aware optimum reads as optimized (the min() is honest)
    editor.set_generator_tuning_text("{%f %f]" % gens)
    assert editor.tuning_is_optimized is True


def test_held_interval_is_expressed_in_the_domain_basis():
    # nonstandard-superspace-3 (editor half): a held column vector (0,0,1) over 2.3.13/5 is 13/5, and
    # the editor must hand the solver "13/5", not "5/1" (the same exponents read over the prime
    # series). The held SOLVE itself relies on the library expressing it in-basis (finding C1).
    editor = Editor()
    assert editor.try_edit_mapping_text(BARBADOS_ALT)
    editor.add_held()
    editor.set_pending_held([0, 0, 1])
    assert service.comma_ratios(editor.held_vectors, editor.state.domain_basis) == ("13/5",)


def test_choose_form_drops_a_stale_manual_tuning_to_scheme_driven():
    # canonical-defactor-1: canonicalize is a generator-basis change; a manual tuning held against
    # the old generators would otherwise be reinterpreted into garbage (a negative prime cent). It
    # re-seeds to scheme-driven instead, so the displayed tuning is a tuning OF the new form.
    editor = Editor()
    editor.set_generator_tuning_text("{1200.000 696.578]")  # a manual tuning of the meantone form
    editor.canonicalize_mapping()  # ((1,1,0),(0,1,4)) -> ((1,0,-4),(0,1,4)): generators change
    assert editor.effective_generator_tuning() is None  # scheme-driven again
    assert editor.manual_tuning is False
    tuning_map = service.tuning(editor.state.mapping, editor.tuning_scheme).tuning_map
    assert all(x > 0 for x in tuning_map)  # no negative/garbage prime cents


def test_preset_pick_drops_a_stale_manual_tuning():
    # presets-sweep-1: picking a preset changes the generator basis (HNF dual); a frozen manual
    # tuning must not survive reinterpreted against the new generators.
    from rtt.app import presets
    editor = Editor()
    editor.set_generator_tuning_text("{1200.000 696.578]")
    editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS["5:Meantone"])
    assert editor.effective_generator_tuning() is None and editor.manual_tuning is False


def test_comma_drag_drops_a_stale_manual_tuning_on_a_non_canonical_mapping():
    # temperament-addition-2: add_comma_to re-duals a non-canonical mapping to canonical form (a
    # generator-basis change), so a frozen manual tuning must drop rather than describe the old rows.
    editor = Editor()
    assert editor.try_edit_mapping_text("[⟨12 19 28 34] ⟨19 30 44 53]]")  # septimal meantone, 12&19 form
    optimum = editor.optimum_generator_tuning()
    editor.set_generator_tuning_text("{%f %f]" % optimum)  # a manual tuning of THESE generators
    editor.add_comma_to(0, 1)
    assert editor.state.mapping == ((1, 0, -4, -13), (0, 1, 4, 10))  # rewritten to canonical
    assert editor.effective_generator_tuning() is None and editor.manual_tuning is False


def test_structural_edits_preserve_a_nonstandard_domain():
    # nonstandard-superspace-5 / canonical-defactor-7 (editor half): a mapping cell edit, choose-form
    # and generator sign-flip must re-dual over the SAME domain, not silently reset 2.3.13/5 -> 2.3.5.
    barbados_domain = (2, 3, Fraction(13, 5))
    for op in (
        lambda e: e.flip_generator(1),
        lambda e: e.edit_mapping([[1, 0, -1], [0, 2, 4]]),
        lambda e: e.canonicalize_mapping(),
        lambda e: e.canonicalize_comma_basis(),
    ):
        editor = Editor()
        assert editor.try_edit_mapping_text(BARBADOS_ALT)
        op(editor)
        assert editor.state.domain_basis == barbados_domain


def test_try_edit_mapping_text_rejects_malformed_domain_prefixes():
    # ebk-notation-2: a domain prefix with a zero/unit/dependent element, or a length that doesn't
    # match the matrix width, parses but would crash the next render — reject it, state untouched.
    for bad in ("0.5 [⟨1 0] ⟨0 1]]",      # element 0 (a decimal typed where a ratio was meant)
                "1.3 [⟨1 0] ⟨0 1]]",      # the unit 1 spans nothing
                "2.4 [⟨1 0] ⟨0 1]]",      # 4 = 2², dependent
                "2.3.7 [⟨1 0] ⟨0 1]]"):   # 3-element prefix on a 2-wide matrix
        editor = Editor()
        before = editor.state.mapping
        assert editor.try_edit_mapping_text(bad) is False
        assert editor.state.mapping == before  # untouched (no snapshot, no broken commit)
    # a well-formed nonstandard prefix still loads
    assert Editor().try_edit_mapping_text("2.3.7 [⟨1 1 3] ⟨0 3 -1]}") is True


def test_override_generator_clamps_an_out_of_range_component():
    # editor-state-machine-2: a rank-reducing edit can leave a frozen tuning LONGER than the new
    # rank; editing/nudging a component that only existed in the old longer tuning must no-op, not
    # IndexError (the live grid only ever offers r cells).
    editor = Editor()
    editor.add_mapping_row()
    editor.set_pending_mapping_row([0, 0, 1])           # r 2 -> 3
    editor.set_generator_tuning_component(2, 700.0)     # manual tuning length 3
    editor.add_comma()
    editor.set_pending_comma([4, -4, 1])                # re-temper: r 3 -> 2, tuning still length 3
    before = editor.generator_tuning
    editor.set_generator_tuning_component(2, 700.0)     # component 2 is past the new rank — no crash
    editor.nudge_generator_tuning_component(2, 1)       # ditto via the wheel
    assert editor.generator_tuning == before            # the out-of-range edits are clean no-ops
    editor.layout()                                     # still renders (the stale tuning reads as scheme-driven)


def test_first_comma_from_just_intonation_commits_no_phantom_unison():
    # canonical-defactor-3: tempering out the first comma from JI must replace the full-rank zero
    # placeholder, not append beside it (which committed a phantom 1/1 comma and broke d = r + n).
    editor = Editor()
    editor.remove_comma()                  # 5-limit JI: comma_basis == ((0,0,0),), n == 0
    editor.add_comma()
    editor.set_pending_comma([4, -4, 1])
    assert editor.state.comma_basis == ((4, -4, 1),) and editor.state.n == 1
    # and via a drag of a target into the commas
    editor2 = Editor()
    editor2.remove_comma()
    editor2.move_interval("targets", 0, "commas", 0)
    assert (0, 0, 0) not in editor2.state.comma_basis and editor2.state.n == 1


def test_approach_switch_clears_a_stranded_manual_flag():
    # nonstandard-superspace-8 / render-fiddle-9: switching the approach radio drops the manual
    # superspace 𝒈L; with no on-domain manual tuning left, manual_tuning must drop too, so the
    # back-to-scheme button doesn't light over a scheme-driven grid.
    editor = Editor()
    assert editor.try_edit_mapping_text(BARBADOS_ALT)
    editor.set_nonprime_basis_approach("prime-based")
    editor.set_superspace_generator_tuning_component(0, 1190.0)
    assert editor.manual_tuning is True
    editor.set_nonprime_basis_approach("")
    assert editor.superspace_generator_tuning is None
    assert editor.manual_tuning is False


def test_projection_identification_agrees_with_the_scheme_name_at_display_precision():
    # ebk-notation-7 / projection-7: the scheme-name/optimized side compares at 3-dp display
    # precision; the projection side used 1e-6, so retyping or wheel-nudging back to the shown cents
    # kept the scheme name yet dashed P/G/U. Now a manual tuning that rounds to the optimum is treated
    # AS the optimum for projection too, so the two views agree.
    editor = Editor()
    editor.set_generator_tuning_text("{1200.0 696.578]")  # the displayed 3-dp cents of 1/4-comma
    assert editor.unchanged_ratios == ("2/1", "5/4")
    assert editor.displayed_projection_scheme_name == "1/4-comma"
    # and a pure wheel up-then-down gesture lands back consistent on both sides
    editor2 = Editor()
    editor2.set_show("projection", True)
    editor2.nudge_generator_tuning_component(1, +1)
    editor2.nudge_generator_tuning_component(1, -1)
    assert editor2.tuning_is_optimized is True
    assert editor2.displayed_tuning_scheme_name == "minimax-U"
    assert editor2.unchanged_ratios == ("2/1", "5/4")
    assert editor2.displayed_projection_scheme_name == "1/4-comma"


# --- per-sub-row ET picker (set_mapping_row) / per-sub-column comma picker (set_comma) ---

from rtt.app import presets  # noqa: E402


def test_set_mapping_row_replaces_a_row_verbatim_and_is_undoable():
    editor = Editor()  # meantone, rank 2
    assert editor.set_mapping_row(0, (12, 19, 28)) is True
    assert editor.state.mapping[0] == (12, 19, 28)   # stored verbatim, not canonicalized
    assert editor.state.mapping[1] == (0, 1, 4)      # the other row is untouched
    assert (editor.state.r, editor.state.n) == (2, 1)  # rank/nullity preserved
    assert editor.can_undo is True
    editor.undo()
    assert editor.state.mapping == INITIAL_MAPPING


def test_set_mapping_row_rejects_a_dependent_row():
    editor = Editor()
    assert editor.set_mapping_row(1, (2, 2, 0)) is False  # a multiple of row 0
    assert editor.state.mapping == INITIAL_MAPPING        # untouched
    assert editor.can_undo is False


def test_set_comma_replaces_a_column_verbatim_and_is_undoable():
    editor = Editor()  # meantone, one comma (4,-4,1)
    vector = presets.comma_value_to_vector("128/125", (2, 3, 5))  # (7,0,-3)
    assert editor.set_comma(0, vector) is True
    assert editor.state.comma_basis[0] == tuple(vector)
    assert editor.state.n == 1
    assert editor.can_undo is True
    editor.undo()
    assert editor.state.comma_basis == ((4, -4, 1),)


def test_set_comma_rejects_a_dependent_comma():
    editor = Editor()
    editor.edit_comma_basis([[-4, 4, -1, 0], [1, 2, -3, 1]])  # two independent 7-limit commas
    assert editor.state.n == 2
    assert editor.set_comma(1, (-8, 8, -2, 0)) is False  # a multiple of column 0 -> rank-deficient
    assert editor.state.comma_basis == ((-4, 4, -1, 0), (1, 2, -3, 1))  # untouched
    assert editor.state.n == 2


def test_set_comma_preserves_a_nonstandard_domain():
    editor = Editor()
    editor.edit_comma_basis([(6, -1, -1)], (2, 9, 7))  # 64/63 over 2.9.7
    assert editor.state.domain_basis == (2, 9, 7)
    vector = presets.comma_value_to_vector("531441/524288", (2, 9, 7))  # (-19,6,0)
    assert editor.set_comma(0, vector) is True
    assert editor.state.domain_basis == (2, 9, 7)  # not silently reset to standard primes


def test_set_mapping_row_preserves_a_nonstandard_domain():
    editor = Editor()
    editor.edit_comma_basis([(6, -1, -1)], (2, 9, 7))  # rank-2 over 2.9.7
    val = presets.et_value_to_val("12", (2, 9, 7))  # (12,38,34)
    assert editor.set_mapping_row(0, val) is True
    assert editor.state.domain_basis == (2, 9, 7)


def test_set_projection_matrix_retunes_to_a_valid_projection_and_rejects_an_invalid_one():
    editor = Editor()  # meantone
    valid = service.tuning_projection(editor.state, ("2/1", "5/4"))  # a full rational projection
    assert editor.set_projection_matrix(valid) is True
    assert editor.can_undo is True
    not_idempotent = (("1", "0", "0"), ("0", "1", "0"), ("0", "0", "2"))
    fresh = Editor()
    assert fresh.set_projection_matrix(not_idempotent) is False
    assert fresh.can_undo is False  # rejected edits leave the state untouched


def test_set_embedding_matrix_retunes_to_a_valid_embedding_and_rejects_an_invalid_one():
    editor = Editor()  # meantone
    valid = service.tuning_embedding(editor.state, ("2/1", "5/4"))
    assert editor.set_embedding_matrix(valid) is True
    fresh = Editor()
    assert fresh.set_embedding_matrix((("0", "0"), ("0", "0"), ("0", "0"))) is False  # M·G ≠ I
    assert fresh.can_undo is False


def test_set_superspace_generator_tuning_text_holds_rl_cents_and_rejects_a_wrong_count():
    editor = Editor()
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")  # BARBADOS, rL = 3
    assert editor.set_superspace_generator_tuning_text("1200 700 400") is True
    assert editor.superspace_generator_tuning == (1200.0, 700.0, 400.0)
    assert editor.set_superspace_generator_tuning_text("1200 700") is False  # not rL values


def test_nudge_superspace_generator_tuning_component_steps_by_thousandths_of_a_cent():
    editor = Editor()
    editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    seed = editor.optimum_superspace_generator_tuning()[0]
    editor.nudge_superspace_generator_tuning_component(0, 7)
    assert editor.superspace_generator_tuning[0] == round(round(seed, 3) + 7 * 0.001, 3)

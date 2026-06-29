from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor
from _editor_support import _cents_close, _has_targets, BARBADOS_ALT


class TestEstablishedProjection:
    def test_established_projection_shows_for_the_default_meantone(self):
        ed = Editor()
        assert ed.held_vectors == []
        assert ed.unchanged_ratios == ("2/1", "5/4")
        assert ed.displayed_projection_scheme_name == "1/4-comma"

    def test_established_projection_reflects_a_hand_typed_held_basis(self):
        ed = Editor()
        v = lambda r: tuple(service.interval_vector(r, ed.state.dimensionality, ed.state.domain_basis))
        ed.set_held_vectors([v("2/1"), v("5/4")])
        assert ed.unchanged_ratios == ("2/1", "5/4")
        assert ed.displayed_projection_scheme_name == "1/4-comma"

    def test_established_projection_round_trips_via_the_generator_tuning(self):
        ed = Editor()
        ed.set_established_projection("Pythagorean")
        reloaded = Editor()
        reloaded.load(ed.serialize())
        assert reloaded.displayed_projection_scheme_name == "Pythagorean"

    def test_set_established_projection_sets_the_tuning_not_the_held_column(self):
        ed = Editor()
        ed.set_established_projection("1/3-comma")
        assert ed.held_vectors == [], "picking does NOT touch the held column — only the user deliberately holds intervals"
        assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
        assert ed.unchanged_ratios == ("2/1", "6/5"), "U, and so the chooser, follow from the tuning"
        assert ed.displayed_projection_scheme_name == "1/3-comma"
        assert ed.displayed_tuning_scheme_name is None, "a deliberate tuning override isn't the bare scheme's optimum, so the scheme chooser drops to '-'"

    def test_set_established_projection_is_undoable(self):
        ed = Editor()
        ed.set_established_projection("1/3-comma")
        assert [round(x, 3) for x in ed.effective_generator_tuning()] == [1200.0, 694.786]
        assert ed.displayed_projection_scheme_name == "1/3-comma"
        ed.undo()
        assert ed.manual_tuning is False, "undo restores the auto optimum (the default 1/4-comma meantone), not the frozen third-comma"
        assert ed.displayed_projection_scheme_name == "1/4-comma"

    def test_projection_identification_agrees_with_the_scheme_name_at_display_precision(self):
        editor = Editor()
        editor.set_generator_tuning_text("{1200.0 696.578]")
        assert editor.unchanged_ratios == ("2/1", "5/4")
        assert editor.displayed_projection_scheme_name == "1/4-comma"
        editor2 = Editor()
        editor2.set_show("projection", True)
        editor2.nudge_generator_tuning_component(1, +1)
        editor2.nudge_generator_tuning_component(1, -1)
        assert editor2.tuning_is_optimized is True
        assert editor2.displayed_tuning_scheme_name == "minimax-U"
        assert editor2.unchanged_ratios == ("2/1", "5/4")
        assert editor2.displayed_projection_scheme_name == "1/4-comma"


    from rtt.app import presets

    def test_set_projection_matrix_retunes_to_a_valid_projection_and_rejects_an_invalid_one(self):
        editor = Editor()
        valid = service.tuning_projection(editor.state, ("2/1", "5/4"))
        assert editor.set_projection_matrix(valid) is True
        assert editor.can_undo is True
        not_idempotent = (("1", "0", "0"), ("0", "1", "0"), ("0", "0", "2"))
        fresh = Editor()
        assert fresh.set_projection_matrix(not_idempotent) is False
        assert fresh.can_undo is False

    def test_set_embedding_matrix_retunes_to_a_valid_embedding_and_rejects_an_invalid_one(self):
        editor = Editor()
        valid = service.tuning_embedding(editor.state, ("2/1", "5/4"))
        assert editor.set_embedding_matrix(valid) is True
        fresh = Editor()
        assert fresh.set_embedding_matrix((("0", "0"), ("0", "0"), ("0", "0"))) is False
        assert fresh.can_undo is False


class TestUnchangedBasis:
    def test_a_held_interval_always_appears_in_the_unchanged_basis(self):
        ed = Editor()
        v = lambda r: tuple(service.interval_vector(r, ed.state.dimensionality, ed.state.domain_basis))
        ed.set_held_vectors([v("9/8")])
        assert "9/8" in ed.unchanged_ratios, "the held interval itself, not a stand-in"
        assert ed.unchanged_ratios[0] == "9/8"
        assert service.interval_vector("9/8", ed.state.dimensionality, ed.state.domain_basis) in (
            service.unchanged_interval_basis(ed.state, ed.unchanged_ratios) or ())

    def test_held_interval_is_expressed_in_the_domain_basis(self):
        editor = Editor()
        assert editor.try_edit_mapping_text(BARBADOS_ALT)
        editor.add_held()
        editor.set_pending_held([0, 0, 1])
        assert service.comma_ratios(editor.held_vectors, editor.state.domain_basis) == ("13/5",)

    def test_an_unheld_interval_is_never_faked_into_the_unchanged_basis(self):
        ed = Editor()
        v = lambda r: tuple(service.interval_vector(r, ed.state.dimensionality, ed.state.domain_basis))
        ed.set_held_vectors([v("9/8")])
        ed.set_generator_tuning_component(0, 1200.0)
        ed.set_generator_tuning_component(1, 700.0)
        assert "9/8" not in ed.unchanged_ratios, "not held by THIS tuning, so not claimed unchanged"

    def test_a_held_nonprime_element_appears_in_the_unchanged_basis(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
        ed.set_held_vectors([(0, 1, 0)])
        assert "9/1" in ed.unchanged_ratios, "the held nonprime element itself, not a stand-in"
        assert ed.unchanged_ratios[0] == "9/1"
        assert (0, 1, 0) in (service.unchanged_interval_basis(ed.state, ed.unchanged_ratios) or ())
        assert service.tuning_projection(ed.state, ed.unchanged_ratios) is not None, "P/G render, not dashed"

    def test_unchanged_basis_tuning_runs_over_the_domain_basis_not_the_standard_primes(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
        ed.set_held_vectors([(0, 1, 0)])
        held = service.comma_ratios(ed.held_vectors, ed.state.domain_basis)
        grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, held=held)
        over_primes = service.tuning(ed.state.mapping, ed.tuning_scheme, held=("3/1",))
        editor = ed.displayed_retuning_map()
        assert _cents_close(editor, grid.retuning_map)
        assert not _cents_close(editor, over_primes.retuning_map), "NOT the standard-primes tuning"

    def test_unchanged_basis_threads_the_nonprime_approach(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
        ed.set_weight_slope("simplicity-weight")
        seen = {}
        for approach in ("", "nonprime-based", "prime-based"):
            ed.nonprime_basis_approach = approach
            grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, approach)
            seen[approach] = ed.displayed_retuning_map()
            assert _cents_close(seen[approach], grid.retuning_map)
        assert not _cents_close(seen[""], seen["nonprime-based"]), "the approach is load-bearing, not ignored"

    def test_hand_pinned_nonprime_projection_holds_over_the_domain_basis(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_mapping(((1, 0, 0), (0, 1, 1)), domain_basis=(2, 9, 5))
        assert service.tuning_projection(ed.state, ("2/1", "9/1")) is not None
        ed.set_unchanged_basis(("2/1", "9/1"))
        assert ed.unchanged_ratios == ("2/1", "9/1"), "the pinned basis is recovered, the held 9/1 kept"
        grid = service.tuning(ed.state.mapping, ed.tuning_scheme, ed.state.domain_basis, held=("2/1", "9/1"))
        assert _cents_close(ed.generator_tuning, grid.generator_map)


class TestTargetsInUse:
    def test_targets_in_use_tracks_whether_the_tuning_is_the_target_optimum(self):
        ed = Editor()
        ed.settings["projection"] = True
        assert ed.targets_in_use is True
        ed.set_established_projection("1/4-comma")
        assert ed.targets_in_use is True
        deviated = Editor()
        deviated.settings["projection"] = True
        deviated.set_established_projection("1/3-comma")
        assert deviated.targets_in_use is False

    def test_target_list_returns_when_the_projection_box_is_off(self):
        ed = Editor()
        ed.settings["projection"] = True
        ed.set_established_projection("1/3-comma")
        assert ed.targets_in_use is False
        ed.settings["projection"] = False
        assert ed.targets_in_use is True

    def test_target_column_hides_when_the_tuning_deviates_from_the_optimum(self):
        ed = Editor()
        ed.settings["projection"] = True
        has_targets = lambda: any(c.id.startswith(("target:", "cell:target")) for c in ed.layout().cells)
        assert has_targets()
        ed.set_established_projection("1/3-comma")
        assert not has_targets()

    def test_hand_edited_full_projection_off_the_candidate_list_hides_the_targets(self):
        ed = Editor()
        ed.settings["projection"] = True
        assert service.tuning_projection(ed.state, ("2/1", "10/9")) is not None
        ed.set_unchanged_basis(("2/1", "10/9"))
        assert ed.unchanged_ratios == ("2/1", "10/9"), "the FULL basis is recovered, not just 2/1"
        assert ed.targets_in_use is False
        assert not _has_targets(ed)

    def test_full_projection_hides_targets_on_a_temperament_with_no_established_projections(self):
        ed = Editor()
        ed.settings["projection"] = True
        ed.edit_mapping(((1, 2, 3), (0, 3, 5)))
        assert service.tuning_projection(ed.state, ("2/1", "27/25")) is not None
        ed.set_unchanged_basis(("2/1", "27/25"))
        assert ed.targets_in_use is False
        assert not _has_targets(ed)

    def test_back_to_scheme_restores_the_targets_after_an_off_candidate_pin(self):
        ed = Editor()
        ed.settings["projection"] = True
        ed.set_unchanged_basis(("2/1", "10/9"))
        assert not _has_targets(ed)
        ed.back_to_scheme()
        assert ed.projection_basis == ()
        assert ed.targets_in_use is True
        assert _has_targets(ed)

    def test_off_candidate_pin_undo_redo_keeps_the_targets_column_correct(self):
        ed = Editor()
        ed.settings["projection"] = True
        ed.set_unchanged_basis(("2/1", "10/9"))
        assert not _has_targets(ed)
        ed.undo()
        assert _has_targets(ed)
        ed.redo()
        assert not _has_targets(ed)

    def test_off_candidate_pin_round_trips_serialize_and_older_docs_lack_it(self):
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

        data.pop("projection_basis")
        legacy = Editor()
        legacy.load(data)
        assert legacy.projection_basis == (), "defaults to no pin, no crash"

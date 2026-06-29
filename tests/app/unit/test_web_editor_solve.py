from rtt.app import service
from rtt.app.editor import Editor
from rtt.app import editor_solve
from rtt.app.editor_solve import Solve, solve_model


class TestWebEditorSolve:
    def test_solve_model_round_trips_the_default_read_model(self):
        editor = Editor()
        s = solve_model(editor)
        assert isinstance(s, Solve)
        assert s.state is editor.state
        assert s.tuning_scheme == editor.tuning_scheme
        assert s.target_spec == editor.target_spec
        assert s.settings == editor.settings
        assert s.nonprime_basis_approach == editor.nonprime_basis_approach
        assert s.held_vectors == tuple(editor.held_vectors)
        assert s.interest_vectors == tuple(editor.interest_vectors)
        assert s.target_override == editor.target_override
        assert s.generator_tuning == editor.generator_tuning
        assert s.manual_tuning == editor.manual_tuning
        assert s.projection_basis == editor.projection_basis
        assert s.custom_prescaler == editor.custom_prescaler
        assert s.custom_weights == editor.custom_weights

    def test_solve_model_round_trips_a_richly_overridden_read_model(self):
        editor = Editor()
        editor.set_tuning_scheme("minimax-C")
        editor.set_target_override_vectors([(-1, 1, 0)])
        editor.set_custom_weight_entry(0, 3.0)
        editor.set_generator_tuning_text("1200 696")
        s = solve_model(editor)
        assert s.tuning_scheme == editor.tuning_scheme
        assert s.target_override == editor.target_override and s.target_override is not None
        assert s.custom_weights == editor.custom_weights and s.custom_weights is not None
        assert s.generator_tuning == editor.generator_tuning == (1200.0, 696.0)
        assert s.manual_tuning is True
        assert s.settings["custom_weights"] is True

    def test_solve_model_captures_the_live_superspace_override_that_capture_drops(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        editor.set_nonprime_basis_approach("prime-based")
        editor.set_superspace_generator_tuning_component(2, 999.0)
        s = solve_model(editor)
        assert s.nonprime_basis_approach == "prime-based"
        assert s.superspace_generator_tuning == editor.superspace_generator_tuning
        assert s.superspace_generator_tuning[2] == 999.0
        snapshot = editor.capture()
        assert not hasattr(snapshot, "superspace_generator_tuning")
        assert not hasattr(snapshot, "nonprime_basis_approach")

    def test_displayed_scheme_name_bare_solve_omits_held_while_the_optimum_passes_it(self, monkeypatch):
        editor = Editor()
        editor.set_held_vectors([(-1, 1, 0)])
        held_seen = []
        real = editor_solve.service.tuning

        def spy(*args, **kwargs):
            held_seen.append(kwargs.get("held", "ABSENT"))
            return real(*args, **kwargs)

        monkeypatch.setattr(editor_solve.service, "tuning", spy)
        _ = editor.displayed_tuning_scheme_name
        assert "ABSENT" in held_seen
        assert any(height not in ("ABSENT", ()) and height for height in held_seen)

    def test_tuning_queries_forward_through_the_solve_model_unchanged(self):
        editor = Editor()
        editor.set_tuning_scheme("minimax-C")
        editor.set_held_vectors([(-1, 1, 0)])
        s = solve_model(editor)
        assert editor.optimum_generator_tuning() == editor_solve.optimum_generator_tuning(s)
        assert editor.displayed_tuning_scheme_name == editor_solve.displayed_tuning_scheme_name(s)
        assert editor.unchanged_ratios == editor_solve.unchanged_ratios(s)
        assert editor.targets_in_use == editor_solve.targets_in_use(s)
        assert editor.tuning_is_optimized == editor_solve.tuning_is_optimized(s)
        assert editor.displayed_retuning_map() == editor_solve.displayed_retuning_map(s)
        assert editor.displayed_projection_scheme_name == editor_solve.displayed_projection_scheme_name(s)

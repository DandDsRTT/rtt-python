import dataclasses

import pytest

from rtt.app import spreadsheet
from rtt.app.editor import Editor
from rtt.app.spreadsheet_resolved import Resolved


def _resolve(ed: Editor) -> Resolved:
    return spreadsheet.resolve(
        ed.state, ed.settings, ed.collapsed,
        tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
        interest=ed.interest_vectors, range_mode=ed.range_mode,
        pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
        generator_tuning=ed.effective_generator_tuning(),
    )


def _builder(ed: Editor) -> spreadsheet._GridBuilder:
    return spreadsheet._GridBuilder(
        ed.state, ed.settings, ed.collapsed,
        tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
        interest=ed.interest_vectors, range_mode=ed.range_mode,
        pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
        generator_tuning=ed.effective_generator_tuning(),
    )


class TestWebResolved:
    def test_resolve_produces_the_domain_model_without_rendering(self):
        model = _resolve(Editor())
        assert isinstance(model, Resolved)
        assert model.dimensions.dimensionality == 3
        assert model.dimensions.rank == 2
        assert model.targets.ratios[:3] == ("2/1", "3/1", "3/2")

    def test_resolved_is_immutable(self):
        model = _resolve(Editor())
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.dimensions = None
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.dimensions.dimensionality = 0

    def test_resolve_matches_the_builders_resolution(self):
        ed = Editor()
        b = _builder(ed)
        model = _resolve(ed)
        assert model.dimensions.dimensionality == b.resolved.dimensions.dimensionality
        assert model.dimensions.target_count == b.resolved.dimensions.target_count
        assert model.targets.ratios == b.resolved.targets.ratios
        assert model.commas.ratios == b.resolved.commas.ratios
        assert model.tuning.tuning_map is b.resolved.tuning.tuning_map
        assert model.projection.matrix == b.resolved.projection.matrix

    def test_the_resolved_model_is_the_only_copy_of_the_domain_facts(self):
        b = _builder(Editor())
        for mirrored in ("comma_ratios", "tuning_map", "generators", "show_superspace", "projection_matrix",
                         "canonical_mapping", "unchanged_ratios", "ghost_row", "all_interval"):
            assert not hasattr(b, mirrored), f"{mirrored} still shadows the resolved model on self"
        assert b.resolved.commas.ratios is not None
        assert b.resolved.flags.superspace is False

    def test_resolution_is_decoupled_from_layout(self):
        ed = Editor()
        r = spreadsheet.Resolver(
            ed.state, ed.settings, ed.collapsed,
            tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
            interest=ed.interest_vectors, range_mode=ed.range_mode,
            pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
            generator_tuning=ed.effective_generator_tuning(), resolve_only=True,
        )
        assert isinstance(r.resolved, Resolved)
        assert r.resolved.detempering.vectors is not None
        assert not hasattr(r, "tiles"), "tile declaration belongs to layout, not resolution"
        assert not hasattr(r, "col_x"), "column geometry belongs to layout, not resolution"

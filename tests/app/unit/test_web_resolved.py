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


def test_resolve_produces_the_domain_model_without_rendering():
    # the RTT model is obtainable with zero rendering: no Layout, no cells.
    model = _resolve(Editor())
    assert isinstance(model, Resolved)
    assert model.dims.d == 3
    assert model.dims.r == 2
    assert model.targets.ratios[:3] == ("2/1", "3/1", "3/2")


def test_resolved_is_immutable():
    model = _resolve(Editor())
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.dims = None
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.dims.d = 0


def test_resolve_matches_the_builders_resolution():
    # the headless model carries the same domain facts the renderer reads off self.
    ed = Editor()
    b = spreadsheet._GridBuilder(
        ed.state, ed.settings, ed.collapsed,
        tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
        interest=ed.interest_vectors, range_mode=ed.range_mode,
        pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
        generator_tuning=ed.effective_generator_tuning(),
    )
    model = _resolve(ed)
    assert model.dims.d == b.d
    assert model.dims.k == b.k
    assert model.targets.ratios == b.targets
    assert model.commas.ratios == b.comma_ratios
    assert model.tuning.tun is b.tun
    assert model.projection.matrix == b.projection_matrix

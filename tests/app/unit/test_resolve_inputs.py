import dataclasses

import pytest

from rtt.app import spreadsheet
from rtt.app.editor import Editor
from rtt.app.spreadsheet_resolve_inputs import ResolveInputs


def _builder(ed: Editor) -> spreadsheet._GridBuilder:
    return spreadsheet._GridBuilder(
        ed.state, ed.settings, ed.collapsed,
        tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
        interest=ed.interest_vectors, range_mode=ed.range_mode,
        pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
        generator_tuning=ed.effective_generator_tuning(),
    )


def test_the_builder_holds_its_raw_inputs_as_one_frozen_record():
    ed = Editor()
    b = _builder(ed)
    assert isinstance(b.inputs, ResolveInputs)
    assert b.inputs.state is ed.state
    assert b.inputs.range_mode == ed.range_mode
    assert b.inputs.held_vectors == ed.held_vectors
    assert b.inputs.pending_comma == ed.pending_comma


def test_the_builder_does_not_shadow_the_inputs_as_flat_attributes():
    b = _builder(Editor())
    for field in ("state", "tuning_scheme", "settings", "held_basis_ratios", "custom_prescaler"):
        assert not hasattr(b, field), f"{field} still shadows the inputs record on the builder"


def test_resolve_inputs_is_a_frozen_value_object():
    b = _builder(Editor())
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.inputs.state = None

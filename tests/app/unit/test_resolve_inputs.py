import dataclasses

import pytest

from rtt.app import spreadsheet
from rtt.app.editor import Editor
from rtt.app.spreadsheet_resolve_inputs import ResolveInputs, make_inputs


def _builder(ed: Editor) -> spreadsheet._GridBuilder:
    return spreadsheet._GridBuilder(
        ed.state, ed.settings, ed.collapsed,
        tuning_scheme=ed.tuning_scheme, target_spec=ed.target_spec,
        interest=ed.interest_vectors, range_mode=ed.range_mode,
        pending_comma=ed.pending_comma, held_vectors=ed.held_vectors,
        generator_tuning=ed.effective_generator_tuning(),
    )


def test_make_inputs_snapshots_the_resolve_inputs_off_the_builder():
    ed = Editor()
    b = _builder(ed)
    inputs = make_inputs(b, ed.held_vectors, ed.pending_comma)
    assert isinstance(inputs, ResolveInputs)
    assert inputs.state is b.state
    assert inputs.settings is b.settings
    assert inputs.tuning_scheme is b.tuning_scheme
    assert inputs.held_vectors == ed.held_vectors
    assert inputs.pending_comma == ed.pending_comma


def test_resolve_inputs_is_a_frozen_value_object():
    ed = Editor()
    inputs = make_inputs(_builder(ed), ed.held_vectors, ed.pending_comma)
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.state = None

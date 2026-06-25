import ast
import os

import pytest

from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_geometry_model import GEOMETRY_FIELDS, Geometry


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def _builders():
    meantone = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    yield spreadsheet._GridBuilder(meantone)
    yield spreadsheet._GridBuilder(meantone, _all_on())
    barbados = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    yield spreadsheet._GridBuilder(
        barbados, _all_on(), tuning_scheme="minimax-ES",
        held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))


@pytest.mark.parametrize("builder", list(_builders()))
def test_geometry_record_faithfully_captures_every_builder_attr(builder):
    assert isinstance(builder.geometry, Geometry)
    for name in GEOMETRY_FIELDS:
        assert getattr(builder.geometry, name) is getattr(builder, name)


def _geometry_draft_write_targets():
    source = open(os.path.join(os.path.dirname(spreadsheet.__file__), "spreadsheet_layout.py"),
                  encoding="utf-8").read()
    targets = set()

    def is_geometry_attr(node):
        return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "self"
                and node.value.attr == "geometry")

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for element in (target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]):
                    if is_geometry_attr(element):
                        targets.add(element.attr)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and is_geometry_attr(node.target):
            targets.add(node.target.attr)
    return targets


def test_every_geometry_draft_write_is_a_declared_geometry_field():
    undeclared = _geometry_draft_write_targets() - set(GEOMETRY_FIELDS)
    assert not undeclared, f"self.geometry.X written but X not declared on Geometry: {sorted(undeclared)}"

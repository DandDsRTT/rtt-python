import ast
import collections
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


def _geometry_written_shared_attrs():
    directory = os.path.join(os.path.dirname(spreadsheet.__file__))
    names = [f for f in os.listdir(directory)
             if f.startswith("spreadsheet_") and f.endswith(".py")] + ["spreadsheet.py"]
    writes, reads = collections.defaultdict(set), collections.defaultdict(set)
    for name in names:
        tree = ast.parse(open(os.path.join(directory, name), encoding="utf-8").read())

        class Visitor(ast.NodeVisitor):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    target = writes if isinstance(node.ctx, ast.Store) else reads
                    target[node.attr].add(name)
                self.generic_visit(node)

        Visitor().visit(tree)
    shared = {a for a in set(writes) | set(reads)
              if writes.get(a) and (reads.get(a, set()) - writes.get(a, set()))}
    return {a for a in shared if writes[a] == {"spreadsheet_layout.py"}}


def test_geometry_record_covers_every_geometry_written_shared_attr():
    uncaptured = _geometry_written_shared_attrs() - set(GEOMETRY_FIELDS)
    assert not uncaptured, f"geometry attrs written in layout but missing from Geometry: {sorted(uncaptured)}"

import dataclasses

import pytest

from rtt.app import service, settings, spreadsheet
from rtt.app.spreadsheet_geometry_model import Geometry


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
def test_geometry_is_a_frozen_record(builder):
    assert isinstance(builder.geometry, Geometry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        builder.geometry.total_w = 0.0


@pytest.mark.parametrize("builder", list(_builders()))
def test_builder_does_not_mirror_geometry_fields_as_flat_attrs(builder):
    for field in ("total_w", "col_x", "rows", "declared_tiles", "ptext_strings", "size_factor"):
        assert not hasattr(builder, field), f"{field} shadows geometry on the builder"

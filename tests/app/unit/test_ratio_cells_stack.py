import re

import pytest

from rtt.app import service, settings, spreadsheet

STACKED_RATIO_KINDS = frozenset(
    {
        "mapping",
        "commacell",
        "unchangedcell",
        "interestcell",
        "heldcell",
        "targetcell",
        "formcell",
        "ratiocell",
        "elementcell",
        "elementratio",
        "genratio",
        "commaratio",
        "mapped",
    }
)

_BARE_RATIO = re.compile(r"^-?\d+/\d+$")

_MEANTONE = ((1, 1, 0), (0, 1, 4))
_BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"


def _maximized():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def _all_bool_on():
    s = settings.defaults()
    for key, value in list(s.items()):
        if isinstance(value, bool):
            s[key] = True
    return s


def _projection():
    return spreadsheet.build(
        service.from_mapping(_MEANTONE), {**settings.defaults(), "projection": True},
        held_basis_ratios=("2/1", "5/4"),
    )


def _superspace_nonstandard():
    return spreadsheet.build(
        service.from_temperament_data(_BARBADOS), _all_bool_on(),
        tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),),
    )


LAYOUTS = {
    "default": lambda: spreadsheet.build(service.from_mapping(_MEANTONE)),
    "maximized": lambda: spreadsheet.build(service.from_mapping(_MEANTONE), _maximized()),
    "projection": _projection,
    "superspace_nonstandard": _superspace_nonstandard,
}


@pytest.mark.parametrize("config", sorted(LAYOUTS))
def test_every_bare_ratio_cell_renders_stacked(config):
    layout = LAYOUTS[config]()
    offenders = [
        (cell.id, cell.kind, cell.text)
        for cell in layout.cells
        if isinstance(getattr(cell, "text", None), str) and _BARE_RATIO.match(cell.text)
        and cell.kind not in STACKED_RATIO_KINDS
    ]
    assert not offenders, (
        f"{config}: these cells hold a bare ratio but use a plain-text kind that renders it "
        f"inline with a diagonal slash instead of as a stacked fraction: {offenders}"
    )

import dataclasses
import json
import math
import os
import re
from pathlib import Path

import pytest

from rtt.app import service, settings, spreadsheet

_SNAPSHOT_DIR = Path(__file__).parent / "grid_layout_snapshots"
_UPDATE = os.environ.get("RTT_UPDATE_SNAPSHOTS") == "1"

_RTOL = 1e-9
_ATOL = 1e-9


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


_MEANTONE = ((1, 1, 0), (0, 1, 4))
_BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"


def _default():
    return spreadsheet.build(service.from_mapping(_MEANTONE))


def _maximized_layout():
    return spreadsheet.build(service.from_mapping(_MEANTONE), _maximized())


def _superspace_nonstandard():
    return spreadsheet.build(
        service.from_temperament_data(_BARBADOS), _all_bool_on(),
        tuning_scheme="minimax-ES", held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),),
    )


def _all_interval():
    return spreadsheet.build(service.from_mapping(_MEANTONE), settings.defaults(), tuning_scheme="minimax-S")


def _projection():
    return spreadsheet.build(
        service.from_mapping(_MEANTONE), {**settings.defaults(), "projection": True},
        held_basis_ratios=("2/1", "5/4"),
    )


def _custom_weights():
    return spreadsheet.build(
        service.from_mapping(_MEANTONE), {**settings.defaults(), "weighting": True, "custom_weights": True},
        custom_weights=(1.0, 2.0, 3.0),
    )


def _collapsed():
    return spreadsheet.build(
        service.from_mapping(_MEANTONE), _maximized(), collapsed=frozenset({"col:primes", "row:prescaling"}),
    )


def _closed_form_math():
    return spreadsheet.build(service.from_mapping(_MEANTONE), {**settings.defaults(), "math_expressions": True})


def _many_index_groups():
    wide = service.expand_domain(service.from_mapping(_MEANTONE))
    return spreadsheet.build(
        wide, _maximized(),
        held_vectors=((-1, 1, 0, 0), (2, 0, -1, 0), (1, 1, -1, 0)),
        interest=((1, 1, -1, 0), (0, 0, 1, -1)),
    )


CONFIGS = {
    "default": _default,
    "maximized": _maximized_layout,
    "superspace_nonstandard": _superspace_nonstandard,
    "all_interval": _all_interval,
    "projection": _projection,
    "custom_weights": _custom_weights,
    "collapsed": _collapsed,
    "closed_form_math": _closed_form_math,
    "many_index_groups": _many_index_groups,
}


def _canonical(layout):
    data = dataclasses.asdict(layout)
    for collection in ("cells", "lines", "blocks"):
        records = data[collection]
        by_id = {record["id"]: record for record in records}
        if len(by_id) != len(records):
            raise AssertionError(f"duplicate ids in layout.{collection} — snapshot key would collide")
        data[collection] = by_id
    return data


def _serialize(layout):
    return json.dumps(_canonical(layout), sort_keys=True, ensure_ascii=False, default=repr)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _first_divergence(golden, actual, path=""):
    if _is_number(golden) and _is_number(actual):
        if math.isclose(golden, actual, rel_tol=_RTOL, abs_tol=_ATOL):
            return None
        return path, repr(golden), repr(actual)
    if type(golden) is not type(actual):
        return path, f"type {type(golden).__name__}", f"type {type(actual).__name__}"
    if isinstance(golden, dict):
        for key in sorted(set(golden) | set(actual)):
            if key not in golden:
                return f"{path}[{key!r}]", "<absent>", repr(actual[key])[:120]
            if key not in actual:
                return f"{path}[{key!r}]", repr(golden[key])[:120], "<absent>"
            hit = _first_divergence(golden[key], actual[key], f"{path}[{key!r}]")
            if hit:
                return hit
        return None
    if isinstance(golden, list):
        if len(golden) != len(actual):
            return f"{path}.len", str(len(golden)), str(len(actual))
        for i, (g, a) in enumerate(zip(golden, actual)):
            hit = _first_divergence(g, a, f"{path}[{i}]")
            if hit:
                return hit
        return None
    if golden != actual:
        return path, repr(golden)[:120], repr(actual)[:120]
    return None


def test_float_comparison_absorbs_cross_platform_noise_but_catches_real_drift():
    noise = _first_divergence({"v": -0.049790357257734286}, {"v": -0.04979035725727954})
    near_zero = _first_divergence({"v": 0.0}, {"v": 4.547473508864641e-13})
    assert noise is None and near_zero is None
    assert _first_divergence({"v": 216.5}, {"v": 216.501}) is not None
    assert _first_divergence({"v": 21.5}, {"v": 21.5 + 1e-7}) is not None
    assert _first_divergence({"text": "1"}, {"text": "2"}) is not None


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


@pytest.mark.parametrize("name", list(CONFIGS))
def test_every_bare_ratio_cell_renders_stacked(name):
    layout = CONFIGS[name]()
    offenders = [
        (cell.id, cell.kind, cell.text)
        for cell in layout.cells
        if isinstance(getattr(cell, "text", None), str)
        and _BARE_RATIO.match(cell.text)
        and cell.kind not in STACKED_RATIO_KINDS
    ]
    assert not offenders, (
        f"{name}: cells holding a bare ratio but using a plain-text kind that renders it inline "
        f"with a diagonal slash instead of as a stacked fraction: {offenders}")


@pytest.mark.parametrize("name", list(CONFIGS))
def test_layout_is_byte_identical_to_golden(name):
    layout = CONFIGS[name]()
    serialized = _serialize(layout)
    golden_path = _SNAPSHOT_DIR / f"{name}.json"
    if _UPDATE or not golden_path.exists():
        golden_path.write_text(serialized, encoding="utf-8")
        pytest.skip(f"wrote golden snapshot {name}")
    golden = golden_path.read_text(encoding="utf-8")
    if serialized == golden:
        return
    divergence = _first_divergence(json.loads(golden), json.loads(serialized))
    if divergence is None:
        return
    path, want, got = divergence
    raise AssertionError(
        f"Layout snapshot '{name}' diverged from golden at {path}:\n  golden: {want}\n  actual: {got}\n"
        f"If this change is intentional, regenerate with RTT_UPDATE_SNAPSHOTS=1.")

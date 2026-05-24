import math

from rtt.web import presets, service


def test_every_temperament_preset_loads_to_a_state_that_tempers_out_its_comma():
    for name, comma_basis in presets.TEMPERAMENTS:
        state = service.from_comma_basis(comma_basis)
        for comma in comma_basis:
            for row in state.mapping:
                assert sum(m * c for m, c in zip(row, comma)) == 0, name


def test_every_tuning_scheme_preset_optimizes_to_a_finite_tuning():
    mapping = ((1, 1, 0), (0, 1, 4))  # the initial meantone
    for scheme in presets.TUNING_SCHEMES:
        tun = service.tuning(mapping, scheme)
        assert all(math.isfinite(v) for v in tun.tuning_map), scheme


def test_every_target_set_preset_resolves_to_intervals_for_the_domain():
    for spec in presets.TARGET_SETS:
        intervals = service.target_interval_set(spec, (2, 3, 5))
        assert intervals and all("/" in i for i in intervals), spec

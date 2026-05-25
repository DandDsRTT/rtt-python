import math

from rtt.web import presets, service
from rtt.web.editor import INITIAL_MAPPING


def test_every_temperament_preset_loads_to_a_state_that_tempers_out_its_commas():
    for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
        state = service.from_comma_basis(comma_basis)
        for comma in comma_basis:
            for row in state.mapping:
                assert sum(m * c for m, c in zip(row, comma)) == 0, value


def test_temperament_presets_span_prime_limits_5_through_13():
    assert [limit for limit, _ in presets.TEMPERAMENTS_BY_LIMIT] == [5, 7, 11, 13]
    # each limit's commas have one component per prime in that limit (d = π(limit))
    width = {5: 3, 7: 4, 11: 5, 13: 6}
    for limit, group in presets.TEMPERAMENTS_BY_LIMIT:
        for name, commas in group:
            assert all(len(c) == width[limit] for c in commas), (limit, name)


def test_identify_round_trips_every_preset_and_rejects_non_presets():
    for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
        assert presets.identify(service.from_comma_basis(comma_basis)) == value
    # the initial meantone is the 5-limit Meantone preset
    assert presets.identify(service.from_mapping(INITIAL_MAPPING)) == "5:Meantone"
    # plain just intonation tempers nothing out, so it matches no preset
    assert presets.identify(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))) is None


def test_temperament_options_groups_by_limit_with_a_divider_before_each_group():
    options = presets.temperament_options()
    keys = list(options)
    assert [k for k in keys if k.startswith("hdr:")] == ["hdr:5", "hdr:7", "hdr:11", "hdr:13"]
    # a divider precedes its group's members, and "13-limit" appears in its label
    assert keys.index("hdr:13") < keys.index("13:Marvel")
    assert "13-limit" in options["hdr:13"] and options["13:Marvel"] == "Marvel"
    # the same name recurs across limits under distinct values (no collision)
    assert "7:Miracle" in options and "11:Miracle" in options


def test_every_tuning_scheme_preset_optimizes_to_a_finite_tuning():
    mapping = ((1, 1, 0), (0, 1, 4))  # the initial meantone
    for scheme in presets.TUNING_SCHEMES:
        tun = service.tuning(mapping, scheme)
        assert all(math.isfinite(v) for v in tun.tuning_map), scheme


def test_every_target_set_preset_resolves_to_intervals_for_the_domain():
    for spec in presets.TARGET_SETS:
        intervals = service.target_interval_set(spec, (2, 3, 5))
        assert intervals and all("/" in i for i in intervals), spec

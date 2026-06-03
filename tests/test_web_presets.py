import math

from rtt.web import presets, service
from rtt.web.editor import INITIAL_MAPPING


def test_every_temperament_preset_loads_to_a_state_that_tempers_out_its_commas():
    for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
        state = service.from_comma_basis(comma_basis)
        for comma in comma_basis:
            for row in state.mapping:
                assert sum(m * c for m, c in zip(row, comma)) == 0, value


def test_tuning_scheme_options_prefix_T_when_not_all_interval():
    # all-interval schemes are simplicity-weighted by construction, so the all-interval list is the
    # bare canonical family names. The target-based list instead offers each family at all three
    # weight slopes (its simplicity / unity / complexity variants), each label prefixing an upright
    # "T " (the target-list symbol) to mark it optimizes over the target list, not every interval.
    all_interval = presets.tuning_scheme_options(True, include_alternatives=True)
    targeted = presets.tuning_scheme_options(False, include_alternatives=True)
    assert set(all_interval) == set(presets.TUNING_SCHEMES)  # the bare canonical (simplicity) names
    assert all_interval["minimax-S"] == "minimax-S"
    assert all(label == name for name, label in all_interval.items())  # bare when all-interval
    # the lp family's three weight variants, each T-prefixed
    assert {"minimax-S", "minimax-U", "minimax-C"} <= set(targeted)
    assert targeted["minimax-S"] == "T minimax-S"
    assert targeted["minimax-U"] == "T minimax-U"
    assert targeted["minimax-C"] == "T minimax-C"
    assert all(label.startswith("T ") for label in targeted.values())
    # composes with the alternative-complexity gate: without alternatives, only the lp family —
    # its single bare simplicity name (all-interval) or its three weight variants (target-based)
    assert set(presets.tuning_scheme_options(True, include_alternatives=False)) == {"minimax-S"}
    assert set(presets.tuning_scheme_options(False, include_alternatives=False)) == {
        "minimax-S", "minimax-U", "minimax-C"}


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
    # a divider precedes its group's members; its label is just the plain limit name —
    # the flanking rules are CSS in the chooser popup, not dashes baked into the text
    assert keys.index("hdr:13") < keys.index("13:Marvel")
    assert options["hdr:13"] == "13-limit" and options["13:Marvel"] == "marvel"
    # the same name recurs across limits under distinct values (no collision)
    assert "7:Miracle" in options and "11:Miracle" in options


def test_is_divider_flags_only_limit_headers_not_presets():
    # the prime-limit header rows are inert dividers; the named presets and the ""
    # placeholder stay pickable. (Drives the chooser's disabled-row rendering.)
    assert presets.is_divider("hdr:11")
    assert not presets.is_divider("11:Miracle")
    assert not presets.is_divider("")


def test_temperament_options_show_names_lowercased_but_keep_canonical_value_keys():
    options = presets.temperament_options()
    labels = [label for key, label in options.items() if not key.startswith("hdr:")]
    assert labels  # there are temperament rows to check
    # every temperament label is shown lowercase (incl. multi-word and accented names)
    assert all(label == label.lower() for label in labels), labels
    assert options["7:Septimal Meantone"] == "septimal meantone"
    assert options["5:Würschmidt"] == "würschmidt"
    # the value keys keep the canonical proper-name casing — the stable id shared with
    # TEMPERAMENT_COMMAS / identify — even though the shown label is lowercased
    assert "5:Meantone" in options and options["5:Meantone"] == "meantone"


def test_every_tuning_scheme_preset_optimizes_to_a_finite_tuning():
    mapping = ((1, 1, 0), (0, 1, 4))  # the initial meantone
    for scheme in presets.TUNING_SCHEMES:
        tun = service.tuning(mapping, scheme)
        assert all(math.isfinite(v) for v in tun.tuning_map), scheme


def test_every_target_set_preset_resolves_to_intervals_for_the_domain():
    for spec in presets.TARGET_SETS:
        intervals = service.target_interval_set(spec, (2, 3, 5))
        assert intervals and all("/" in i for i in intervals), spec


def test_tuning_schemes_gate_alternative_complexities_behind_the_setting():
    # every scheme whose interval complexity isn't the plain log-product (lp) is an
    # alternative-complexity scheme, gated behind the alternative-complexity feature: with it
    # off the preset offers only the strictly-lp scheme; with it on, the whole family.
    assert presets.tuning_schemes(include_alternatives=False) == ("minimax-S",)
    assert presets.tuning_schemes(include_alternatives=True) == presets.TUNING_SCHEMES
    # the gated list is a strict subset, and everything withheld is genuinely non-lp
    withheld = set(presets.TUNING_SCHEMES) - set(presets.tuning_schemes(include_alternatives=False))
    assert withheld and all(service.complexity_name_of(s) != "lp" for s in withheld)


def test_prescaler_options_gate_the_alternatives_behind_the_setting():
    # the prescaler chooser offers only log-prime (the plain default) until alt-complexities are
    # un-shelved; with them on, the whole PRESCALERS family (identity = count, prime = sopfr too)
    assert presets.prescaler_options(include_alternatives=False) == ("log-prime",)
    assert presets.prescaler_options(include_alternatives=True) == tuple(service.PRESCALERS)
    # log-prime is offered in both modes (the un-gated default)
    assert "log-prime" in presets.prescaler_options(include_alternatives=True)

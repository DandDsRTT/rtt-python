import math

from rtt.app import presets, service
from rtt.app.editor import INITIAL_MAPPING


MIDDLE_PATH_5_LIMIT = {
    "Dicot", "Meantone", "Augmented", "Mavila", "Porcupine", "Blackwood",
    "Diminished", "Srutal", "Magic", "Ripple", "Hanson", "Negri", "Tetracot",
    "Superpyth", "Helmholtz", "Sensi", "Passion", "Würschmidt", "Compton",
    "Amity", "Orson", "Father", "Bug", "Vishnu", "Luna",
}
MIDDLE_PATH_7_LIMIT = {
    "Blacksmith", "Diminished", "Dominant", "August", "Pajara", "Semaphore",
    "Septimal Meantone", "Injera", "Negri", "Augene", "Keemun", "Catler",
    "Hedgehog", "Superpyth", "Sensi", "Lemba", "Porcupine", "Flattone", "Magic",
    "Doublewide", "Nautilus", "Beatles", "Liese", "Mothra", "Orwell",
    "Garibaldi", "Myna", "Miracle", "Ennealimmal",
}


_MEANTONE_FAMILY = {
    "Pythagorean": ("2/1", "3/2"),
    "1/7-comma": ("2/1", "135/128"),
    "1/6-comma": ("2/1", "45/32"),
    "1/5-comma": ("2/1", "15/8"),
    "2/9-comma": ("2/1", "75/64"),
    "1/4-comma": ("2/1", "5/4"),
    "2/7-comma": ("2/1", "25/24"),
    "1/3-comma": ("2/1", "6/5"),
}


class TestWebPresets1:
    def test_every_temperament_preset_loads_to_a_state_that_tempers_out_its_commas(self):
        for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
            state = service.from_comma_basis(comma_basis)
            for comma in comma_basis:
                for row in state.mapping:
                    assert sum(m * c for m, c in zip(row, comma)) == 0, value

    def test_tuning_scheme_options_prefix_T_when_not_all_interval(self):
        all_interval = presets.tuning_scheme_options(True, include_alternatives=True, weighting=True)
        targeted = presets.tuning_scheme_options(False, include_alternatives=True, weighting=True)
        assert set(all_interval) == set(presets.TUNING_SCHEMES)
        assert all_interval["minimax-S"] == "minimax-S"
        assert all(label == name for name, label in all_interval.items())
        assert {"minimax-S", "minimax-U", "minimax-C"} <= set(targeted)
        assert targeted["minimax-S"] == "T minimax-S"
        assert targeted["minimax-U"] == "T minimax-U"
        assert targeted["minimax-C"] == "T minimax-C"
        assert all(label.startswith("T ") for label in targeted.values())
        assert set(presets.tuning_scheme_options(True, include_alternatives=False, weighting=True)) == {"minimax-S"}
        assert set(presets.tuning_scheme_options(False, include_alternatives=False, weighting=True)) == {
            "minimax-S", "minimax-U", "minimax-C"}

    def test_tuning_scheme_options_offer_only_unity_variant_when_weighting_off(self):
        lp_only = presets.tuning_scheme_options(False, include_alternatives=False, weighting=False)
        assert lp_only == {"minimax-U": "T minimax-U"}
        full = presets.tuning_scheme_options(False, include_alternatives=True, weighting=False)
        assert "minimax-U" in full
        assert "minimax-S" not in full and "minimax-C" not in full
        assert len(full) == len(presets.tuning_schemes(include_alternatives=True))
        assert all(label.startswith("T ") for label in full.values())
        assert presets.tuning_scheme_options(True, include_alternatives=True, weighting=False) == \
            {name: name for name in presets.TUNING_SCHEMES}

    def test_temperament_presets_span_prime_limits_5_through_13(self):
        assert [limit for limit, _ in presets.TEMPERAMENTS_BY_LIMIT] == [5, 7, 11, 13]
        width = {5: 3, 7: 4, 11: 5, 13: 6}
        for limit, group in presets.TEMPERAMENTS_BY_LIMIT:
            for name, commas in group:
                assert all(len(c) == width[limit] for c in commas), (limit, name)

    def test_chooser_covers_the_full_middle_path_tables(self):
        by_limit = {limit: {name for name, _ in group}
                    for limit, group in presets.TEMPERAMENTS_BY_LIMIT}
        assert MIDDLE_PATH_5_LIMIT <= by_limit[5]
        assert MIDDLE_PATH_7_LIMIT <= by_limit[7]

    def test_identify_round_trips_every_preset_and_rejects_non_presets(self):
        for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
            assert presets.identify(service.from_comma_basis(comma_basis)) == value
        assert presets.identify(service.from_mapping(INITIAL_MAPPING)) == "5:Meantone"
        assert presets.identify(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))) is None, "plain just intonation tempers nothing out, so it matches no preset"

    def test_temperament_options_group_by_rank_then_limit(self):
        options = presets.temperament_options()
        keys = list(options)
        assert [k for k in keys if k.startswith("hdr:")] == [
            "hdr:2:5", "hdr:2:7", "hdr:2:11", "hdr:3:7", "hdr:3:11", "hdr:3:13"]
        assert options["hdr:2:5"] == "rank 2, 5-limit"
        assert options["hdr:3:13"] == "rank 3, 13-limit"
        assert keys.index("hdr:3:13") < keys.index("13:Marvel")
        assert options["13:Marvel"] == "marvel"
        assert keys.index("hdr:2:11") < keys.index("hdr:3:7")
        assert "7:Miracle" in options and "11:Miracle" in options

    def test_is_divider_flags_only_section_headers_not_presets(self):
        assert presets.is_divider("hdr:2:11")
        assert not presets.is_divider("11:Miracle")
        assert not presets.is_divider("")

    def test_temperament_options_show_names_lowercased_but_keep_canonical_value_keys(self):
        options = presets.temperament_options()
        labels = [label for key, label in options.items() if not key.startswith("hdr:")]
        assert labels
        assert all(label == label.lower() for label in labels), labels
        assert options["7:Septimal Meantone"] == "septimal meantone"
        assert options["5:Würschmidt"] == "würschmidt"
        assert "5:Meantone" in options and options["5:Meantone"] == "meantone"

    def test_every_tuning_scheme_preset_optimizes_to_a_finite_tuning(self):
        mapping = ((1, 1, 0), (0, 1, 4))
        for scheme in presets.TUNING_SCHEMES:
            tuning_map = service.tuning(mapping, scheme)
            assert all(math.isfinite(v) for v in tuning_map.tuning_map), scheme

    def test_every_target_set_preset_resolves_to_intervals_for_the_domain(self):
        for spec in presets.TARGET_SETS:
            intervals = service.target_interval_set(spec, (2, 3, 5))
            assert intervals and all("/" in i for i in intervals), spec

    def test_tuning_schemes_gate_alternative_complexities_behind_the_setting(self):
        assert presets.tuning_schemes(include_alternatives=False) == ("minimax-S",)
        assert presets.tuning_schemes(include_alternatives=True) == presets.TUNING_SCHEMES
        withheld = set(presets.TUNING_SCHEMES) - set(presets.tuning_schemes(include_alternatives=False))
        assert withheld and all(
            service.complexity_name_of(s) != "lp" or s.startswith(("held-octave", "destretched-octave"))
            for s in withheld
        )

    def test_prescaler_options_gate_the_alternatives_behind_the_setting(self):
        assert presets.prescaler_options(include_alternatives=False) == ("log-prime",)
        assert presets.prescaler_options(include_alternatives=True) == tuple(service.PRESCALERS)
        assert "log-prime" in presets.prescaler_options(include_alternatives=True)

    def test_established_projections_list_the_meantone_comma_fraction_family(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert presets.established_projections(meantone) == _MEANTONE_FAMILY

    def test_projection_options_are_value_equals_label_for_meantone(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert presets.projection_options(meantone) == {name: name for name in _MEANTONE_FAMILY}

    def test_projection_options_match_any_equivalent_meantone_form(self):
        octave_twelfth = service.from_mapping(((1, 0, -4), (0, 1, 4)))
        assert set(presets.projection_options(octave_twelfth)) == set(_MEANTONE_FAMILY)

    def test_projection_options_empty_for_a_preset_without_established_tunings(self):
        augmented = service.from_comma_basis(((7, 0, -3),))
        assert presets.identify(augmented) == "5:Augmented"
        assert presets.projection_options(augmented) == {}

    def test_projection_options_empty_for_a_non_preset_temperament(self):
        ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert presets.projection_options(ji) == {}

    def test_projection_held_ratios_resolves_a_chosen_tuning_else_none(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert presets.projection_held_ratios(meantone, "2/7-comma") == ("2/1", "25/24")
        assert presets.projection_held_ratios(meantone, None) is None
        assert presets.projection_held_ratios(meantone, "bogus") is None, "not an option"

    def test_identify_established_projection_matches_the_current_held_basis(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert presets.identify_established_projection(meantone, ("2/1", "5/4")) == "1/4-comma"
        assert presets.identify_established_projection(meantone, ("2/1", "6/5")) == "1/3-comma"
        assert presets.identify_established_projection(meantone, ("2/1", "5/3")) == "1/3-comma"

    def test_identify_established_projection_is_none_when_not_a_full_projection(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert presets.identify_established_projection(meantone, ("2/1",)) is None
        assert presets.identify_established_projection(meantone, ()) is None

    def test_identify_established_projection_is_none_for_an_unnamed_rational_tuning(self):
        meantone = service.from_mapping(INITIAL_MAPPING)
        assert service.tuning_projection(meantone, ("2/1", "10/9")) is not None
        assert presets.identify_established_projection(meantone, ("2/1", "10/9")) is None

    def test_comma_options_filter_to_the_current_domain(self):
        options_235 = presets.comma_options((2, 3, 5))
        assert "81/80" in options_235
        assert "64/63" not in options_235
        options_2357 = presets.comma_options((2, 3, 5, 7))
        assert "64/63" in options_2357
        options_297 = presets.comma_options((2, 9, 7))
        assert "64/63" in options_297
        assert "81/80" not in options_297

    def test_comma_option_labels_show_the_vector_over_the_basis(self):
        assert presets.comma_options((2, 3, 5))["81/80"].endswith("[-4 4 -1⟩")
        assert presets.comma_options((2, 9, 7))["64/63"].endswith("[6 -1 -1⟩")

    def test_et_options_offer_every_uniform_map_to_72_then_notable_edos(self):
        from rtt.library import equal_temperament
        for domain in ((2, 3, 5), (2, 3, 5, 7), (2, 9, 5)):
            options = presets.et_options(domain)
            expected = len(equal_temperament.uniform_maps(domain, 72)) + len(presets._NOTABLE_EDOS_ABOVE_72)
            assert len(options) == expected
            for n in range(1, 73):
                assert str(n) in options
        assert presets.et_options((2, 3, 5))["12"].endswith("⟨12 19 28]")
        assert presets.et_options((2, 9, 5))["12"].endswith("⟨12 38 28]")
        assert presets.et_options((2, 3, 5))["17c"].endswith("⟨17 27 40]"), "warted uniform maps are offered too, not just the integer ones: 5-limit 17c is the famous ⟨17 27 40]"

    def test_identify_comma_matches_up_to_sign_else_none(self):
        assert presets.identify_comma((-4, 4, -1), (2, 3, 5)) == "81/80"
        assert presets.identify_comma((4, -4, 1), (2, 3, 5)) == "81/80"
        assert presets.identify_comma((1, -2, 1), (2, 3, 5)) is None, "25/24, not curated"

    def test_identify_et_matches_exactly_else_none(self):
        assert presets.identify_et((12, 19, 28), (2, 3, 5)) == "12"
        assert presets.identify_et((12, 38, 28), (2, 9, 5)) == "12"
        assert presets.identify_et((1, 1, 0), (2, 3, 5)) is None

    def test_curated_pickers_round_trip_through_their_value_keys(self):
        for domain in ((2, 3, 5), (2, 3, 5, 7), (2, 9, 7)):
            for value in presets.comma_options(domain):
                vector = presets.comma_value_to_vector(value, domain)
                assert presets.identify_comma(vector, domain) == value
            for value in presets.et_options(domain):
                val = presets.et_value_to_val(value, domain)
                assert presets.identify_et(val, domain) == value


class TestWebPresets2:
    def test_curated_commas_cover_the_popular_temperament_commas(self):
        famous = {
            "81/80",
            "250/243",
            "128/125",
            "648/625",
            "135/128",
            "25/24",
            "256/243",
            "3125/3072",
            "15625/15552",
            "20000/19683",
            "16875/16384",
            "2048/2025",
            "32805/32768",
        }
        have = {ratio for _, ratio in presets.CURATED_COMMAS}
        assert famous <= have, f"missing popular commas: {sorted(famous - have)}"

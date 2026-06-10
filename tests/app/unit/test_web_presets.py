import math

from rtt.app import presets, service
from rtt.app.editor import INITIAL_MAPPING


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
    all_interval = presets.tuning_scheme_options(True, include_alternatives=True, weighting=True)
    targeted = presets.tuning_scheme_options(False, include_alternatives=True, weighting=True)
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
    assert set(presets.tuning_scheme_options(True, include_alternatives=False, weighting=True)) == {"minimax-S"}
    assert set(presets.tuning_scheme_options(False, include_alternatives=False, weighting=True)) == {
        "minimax-S", "minimax-U", "minimax-C"}


def test_tuning_scheme_options_offer_only_unity_variant_when_weighting_off():
    # the simplicity/complexity weight slopes are reachable only through the weighting feature
    # (the box-𝒘 chooser). With weighting off there is no slope chooser and the weight is unity by
    # construction, so the target-based chooser must offer only each family's unity variant
    # (T minimax-U) — never the simplicity (T minimax-S) or complexity (T minimax-C) slopes.
    lp_only = presets.tuning_scheme_options(False, include_alternatives=False, weighting=False)
    assert lp_only == {"minimax-U": "T minimax-U"}
    full = presets.tuning_scheme_options(False, include_alternatives=True, weighting=False)
    assert "minimax-U" in full
    assert "minimax-S" not in full and "minimax-C" not in full
    # exactly one (unity) variant per complexity family, still T-prefixed (target-based)
    assert len(full) == len(presets.tuning_schemes(include_alternatives=True))
    assert all(label.startswith("T ") for label in full.values())
    # all-interval is simplicity by construction and ignores the weighting gate: still the bare names
    assert presets.tuning_scheme_options(True, include_alternatives=True, weighting=False) == \
        {name: name for name in presets.TUNING_SCHEMES}


def test_temperament_presets_span_prime_limits_5_through_13():
    assert [limit for limit, _ in presets.TEMPERAMENTS_BY_LIMIT] == [5, 7, 11, 13]
    # each limit's commas have one component per prime in that limit (d = π(limit))
    width = {5: 3, 7: 4, 11: 5, 13: 6}
    for limit, group in presets.TEMPERAMENTS_BY_LIMIT:
        for name, commas in group:
            assert all(len(c) == width[limit] for c in commas), (limit, name)


# The named rank-2 temperaments of Erlich's "A Middle Path" Tables 1 & 2 (modern
# names), which the 5- and 7-limit groups are curated from. Pinned so that no
# Middle Path temperament silently goes missing from the chooser.
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


def test_chooser_covers_the_full_middle_path_tables():
    by_limit = {limit: {name for name, _ in group}
                for limit, group in presets.TEMPERAMENTS_BY_LIMIT}
    assert MIDDLE_PATH_5_LIMIT <= by_limit[5]
    assert MIDDLE_PATH_7_LIMIT <= by_limit[7]


def test_identify_round_trips_every_preset_and_rejects_non_presets():
    for value, comma_basis in presets.TEMPERAMENT_COMMAS.items():
        assert presets.identify(service.from_comma_basis(comma_basis)) == value
    # the initial meantone is the 5-limit Meantone preset
    assert presets.identify(service.from_mapping(INITIAL_MAPPING)) == "5:Meantone"
    # plain just intonation tempers nothing out, so it matches no preset
    assert presets.identify(service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))) is None


def test_temperament_options_group_by_rank_then_limit():
    options = presets.temperament_options()
    keys = list(options)
    # groups are ordered by rank first, then prime limit, each headed by a
    # "rank R, L-limit" divider; so every rank-2 group precedes the rank-3 ones
    assert [k for k in keys if k.startswith("hdr:")] == [
        "hdr:2:5", "hdr:2:7", "hdr:2:11", "hdr:3:7", "hdr:3:11", "hdr:3:13"]
    assert options["hdr:2:5"] == "rank 2, 5-limit"
    assert options["hdr:3:13"] == "rank 3, 13-limit"
    # a divider precedes its group's members; value keys stay "limit:name" (rank-free)
    assert keys.index("hdr:3:13") < keys.index("13:Marvel")
    assert options["13:Marvel"] == "marvel"
    # rank sorts ahead of limit: the rank-2 11-limit group precedes the rank-3 7-limit one
    assert keys.index("hdr:2:11") < keys.index("hdr:3:7")
    # the same name recurs across limits/ranks under distinct values (no collision)
    assert "7:Miracle" in options and "11:Miracle" in options


def test_is_divider_flags_only_section_headers_not_presets():
    # the rank/limit header rows are inert dividers; the named presets and the ""
    # placeholder stay pickable. (Drives the chooser's disabled-row rendering.)
    assert presets.is_divider("hdr:2:11")
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


# --- established projection / embedding chooser ---

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


def test_established_projections_list_the_meantone_comma_fraction_family():
    # the whole fractional-comma family is rational (n fifths reach a rational), so all eight
    # named tunings are offered — quarter-comma is no longer special
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert presets.established_projections(meantone) == _MEANTONE_FAMILY


def test_projection_options_are_value_equals_label_for_meantone():
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert presets.projection_options(meantone) == {name: name for name in _MEANTONE_FAMILY}


def test_projection_options_match_any_equivalent_meantone_form():
    # identify keys off the canonical comma signature, so the octave-twelfth form offers them too
    octave_twelfth = service.from_mapping(((1, 0, -4), (0, 1, 4)))
    assert set(presets.projection_options(octave_twelfth)) == set(_MEANTONE_FAMILY)


def test_projection_options_empty_for_a_preset_without_established_tunings():
    # augmented is a preset, but no rational named tuning is documented for it — empty chooser
    augmented = service.from_comma_basis(((7, 0, -3),))
    assert presets.identify(augmented) == "5:Augmented"
    assert presets.projection_options(augmented) == {}


def test_projection_options_empty_for_a_non_preset_temperament():
    ji = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert presets.projection_options(ji) == {}


def test_projection_held_ratios_resolves_a_chosen_tuning_else_none():
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert presets.projection_held_ratios(meantone, "2/7-comma") == ("2/1", "25/24")
    assert presets.projection_held_ratios(meantone, None) is None       # nothing chosen
    assert presets.projection_held_ratios(meantone, "bogus") is None    # not an option


def test_identify_established_projection_matches_the_current_held_basis():
    # the chooser shows whichever named tuning the current held basis realises (by projection)
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert presets.identify_established_projection(meantone, ("2/1", "5/4")) == "1/4-comma"
    assert presets.identify_established_projection(meantone, ("2/1", "6/5")) == "1/3-comma"
    # a span-equivalent basis still matches (5/3 spans the same as 6/5 with the octave)
    assert presets.identify_established_projection(meantone, ("2/1", "5/3")) == "1/3-comma"


def test_identify_established_projection_is_none_when_not_a_full_projection():
    # an under-held tuning (held octave only, or nothing) isn't a rational projection → placeholder
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert presets.identify_established_projection(meantone, ("2/1",)) is None
    assert presets.identify_established_projection(meantone, ()) is None


def test_identify_established_projection_is_none_for_an_unnamed_rational_tuning():
    # a full rational hold that matches no named tuning still shows the placeholder (holding the
    # minor whole tone 10/9 is a perfectly good rational meantone tuning, just not a named one)
    meantone = service.from_mapping(INITIAL_MAPPING)
    assert service.tuning_projection(meantone, ("2/1", "10/9")) is not None  # it IS rational
    assert presets.identify_established_projection(meantone, ("2/1", "10/9")) is None  # but unnamed

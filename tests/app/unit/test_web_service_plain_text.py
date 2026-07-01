import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format
from _service_support import _grid_with_plain_text


class TestPlainTextRows:
    def test_plain_text_mapping_is_the_ebk_string(self):
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
        assert pt[("mapping", "primes")] == "[⟨1 1 0] ⟨0 1 4]}"

    def test_plain_text_basis_and_ratio_quantities(self):
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
        assert pt[("quantities", "primes")] == "2.3.5"
        assert ("mapping", "quantities") not in pt
        assert ("quantities", "commas") not in pt, "the per-ratio quantity sets (commas, targets) are placed per column by the # layout, directly below each ratio — they are not packed into one brace-set here"
        assert ("quantities", "targets") not in pt

    def test_plain_text_interval_vectors_are_vector_lists(self):
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), "TILT minimax-S")
        assert pt[("vectors", "targets")].startswith("[[1 0 0⟩ [0 1 0⟩ [-1 1 0⟩")
        assert pt[("vectors", "primes")] == "[⟨1 0 0]⟨0 1 0]⟨0 0 1]⟩", "𝑀ⱼ = 𝐼, the domain-basis identity, is the p/p JI mapping — a covector stack closing with the # angle ⟩ (an operator, like P), not the mapping's }. (Gated on identity_objects via tile_open; # the string is always available here.)"

    def test_plain_text_mapped_list_is_a_list_of_generator_coord_vectors(self):
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), "TILT minimax-S")
        assert pt[("mapping", "targets")] == (
            "[[1 0} [1 1} [0 1} [1 -1} [-1 4} [-1 3} [-2 4} [2 -3}]"
        )

    def test_plain_text_tuning_rows_use_map_and_list_brackets_at_grid_precision(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        pt = service.plain_text_values(state, "TILT minimax-S")
        targets = service.target_interval_set("TILT", service.standard_primes(state.dimensionality))
        tuning_map = service.tuning(state.mapping, "TILT minimax-S")
        weights = service.interval_weights(state.mapping, "TILT minimax-S", targets)
        sizes = service.interval_sizes(tuning_map, targets, weights=weights)

        def cents(values):
            return " ".join(f"{v:.3f}" for v in values)

        assert pt[("tuning", "primes")] == f"⟨{cents(tuning_map.tuning_map)}]"
        assert pt[("just", "primes")] == f"⟨{cents(tuning_map.just_map)}]"
        assert pt[("retune", "primes")] == f"⟨{cents(tuning_map.retuning_map)}]"
        assert pt[("tuning", "targets")] == f"[{cents(sizes.tempered)}]"
        assert pt[("just", "targets")] == f"[{cents(sizes.just)}]"
        assert pt[("retune", "targets")] == f"[{cents(sizes.errors)}]"
        assert pt[("damage", "targets")] == f"[{cents(sizes.damage)}]"
        assert pt[("just", "primes")].startswith("⟨1200.000 ")

    def test_plain_text_generator_tuning_map_uses_curly_open_square_close(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        pt = service.plain_text_values(state)
        tuning_map = service.tuning(state.mapping)
        cents = " ".join(f"{v:.3f}" for v in tuning_map.generator_map)
        assert pt[("tuning", "generators")] == "{" + cents + "]"


class TestPlainTextColumns:
    def test_plain_text_commas_column_mirrors_the_grid(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        pt = service.plain_text_values(state)
        commas = service.comma_ratios(state.comma_basis)
        sizes = service.interval_sizes(service.tuning(state.mapping), commas)

        def cents(values):
            return " ".join(f"{v:.3f}" for v in values)

        assert pt[("vectors", "commas")] == "[[4 -4 1⟩]", "the comma basis (the editable vector matrix) lives in the interval-vectors row, # a list of vectors wrapped in an outer [ … ]"
        assert pt[("mapping", "commas")] == "[[0 0}]"
        assert pt[("tuning", "commas")] == f"[{cents(sizes.tempered)}]"
        assert pt[("just", "commas")] == f"[{cents(sizes.just)}]"

    def test_plain_text_held_column_mirrors_the_grid(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        held = [(-1, 1, 0)]
        pt = service.plain_text_values(state, held=held)
        held_ratios = service.comma_ratios(held)
        tuning_map = service.tuning(state.mapping, held=held_ratios)
        sizes = service.interval_sizes(tuning_map, held_ratios)

        def cents(values):
            return " ".join(f"{v:.3f}" for v in values)

        assert pt[("vectors", "held")] == "[[-1 1 0⟩]", "the held interval basis lives in the interval-vectors row (vectors, close ⟩)"
        assert pt[("mapping", "held")] == "[[0 1}]"
        assert pt[("tuning", "held")] == f"[{cents(sizes.tempered)}]"
        assert pt[("just", "held")] == f"[{cents(sizes.just)}]"
        assert pt[("retune", "held")] == f"[{cents(sizes.errors)}]"
        assert abs(float(pt[("retune", "held")].strip("[]"))) < 1e-3
        assert pt[("prescaling", "held")] == "[[-1 1.585 0⟩]", "the prescaling row over the held basis: 𝐿 applied to each held vector (like the comma # column's 𝐿·C). The fifth 3/2 = [-1, 1, 0] prescaled by log-prime 𝐿 = [-1, 1.585, 0]. # The 𝐿·basis products (𝐿H here, 𝐿C / 𝐿D / 𝐿T elsewhere) are matrices of prescaled # VECTORS, so each column is a ket ``[ … ⟩`` inside the symmetric outer ``[ … ]``. (The # bare prescaler 𝐿 is the exception — covector rows ``⟨ … ]`` inside outer ``[ … ⟩``.)"
        assert ("vectors", "held") not in service.plain_text_values(state)
        assert ("prescaling", "held") not in service.plain_text_values(state)

    def test_plain_text_interest_column_is_standalone_kets_not_a_matrix(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        interest = [(-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1)]
        pt = service.plain_text_values(state, interest=interest)
        interest_ratios = service.comma_ratios(interest)
        tuning_map = service.tuning(state.mapping)
        sizes = service.interval_sizes(tuning_map, interest_ratios)

        def cents(values):
            return " ".join(f"{v:.3f}" for v in values)

        assert pt[("vectors", "interest")] == "[-1 1 0⟩ [-3 2 0⟩ [1 -2 1⟩ [3 0 -1⟩"
        assert pt[("mapping", "interest")] == "[0 1} [-1 2} [-1 2} [3 -4}", "mapped into generator coords (close }), again standalone — not a bracketed matrix"
        assert pt[("tuning", "interest")] == cents(sizes.tempered), "the size rows are bare numbers — the whole interest column drops the enclosing [ … ]"
        assert pt[("just", "interest")] == cents(sizes.just)
        assert pt[("retune", "interest")] == cents(sizes.errors)
        assert "[" not in pt[("complexity", "interest")] and "]" not in pt[("complexity", "interest")]
        assert pt[("prescaling", "interest")].startswith("[") and pt[("prescaling", "interest")].endswith("⟩")
        assert not pt[("prescaling", "interest")].endswith("⟩]")
        assert ("vectors", "interest") not in service.plain_text_values(state)

    def test_plain_text_weighting_rows_mirror_the_grid(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        pt = service.plain_text_values(state)
        assert pt[("complexity", "primes")] == "⟨1.000 1.585 2.322]"
        assert pt[("complexity", "commas")] == "[12.662]"
        assert pt[("complexity", "targets")].startswith("[") and pt[("complexity", "targets")].endswith("]")
        assert pt[("weight", "targets")].startswith("[") and pt[("weight", "targets")].endswith("]")
        assert pt[("prescaling", "commas")] == "[[4 -6.340 2.322⟩]", "the prescaling row is 𝐿 applied to each vector set, a […⟩-per-vector matrix: # 𝐿·[4,-4,1] = [4,-6.34,2.322] — each prescaled vector a ket ``[ … ⟩`` (square open + # angle close), wrapped in outer [ … ] like the mockup's 𝐿C tile. The string shows the # SAME numbers as the grid — whole numbers bare (4, not 4.000)"

    def test_plain_text_lils_prescaler_grows_the_size_row_matching_the_grid(self):
        mapping = [[1, 1, 0], [0, 1, 4]]
        _t = service.prescale_text
        pre = service.complexity_prescaler(mapping, "TILT minimax-S")
        pt = service.plain_text_values(service.from_mapping(mapping), scheme="TILT minimax-lils-S")
        rows = [["0", "0", "0"] for _ in range(3)]
        for i in range(3):
            rows[i][i] = _t(pre[i])
        rows.append([_t(pre[c]) for c in range(3)])
        assert pt[("prescaling", "primes")] == "[" + " ".join("⟨" + " ".join(r) + "]" for r in rows) + "⟩"
        comma = service.from_mapping(mapping).comma_basis[0]
        column = [pre[i] * comma[i] for i in range(3)]
        column.append(sum(column))
        assert pt[("prescaling", "commas")] == "[[" + " ".join(_t(x) for x in column) + "⟩]"


class TestPlainTextTuning:
    def test_plain_text_tuning_follows_a_target_override(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        base = service.plain_text_values(state, "TILT minimax-U", "TILT")
        overridden = service.plain_text_values(state, "TILT minimax-U", "TILT", target_override=("2/1", "3/2"))
        assert overridden[("tuning", "generators")] != base[("tuning", "generators")]

    def test_plain_text_custom_prescaler_matches_the_grid(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        gb = _grid_with_plain_text(state, "TILT minimax-S", custom_prescaler=(1.0, 2.0, 3.0))
        pt = gb.geometry.plain_text_strings
        assert pt[("tuning", "primes")] == text_format._cents_map(gb.resolved.tuning.tuning_map.tuning_map)
        assert pt[("complexity", "targets")] == text_format._cents_list(gb.resolved.complexities["targets"])
        assert pt[("weight", "targets")] == text_format._cents_list(gb.resolved.tuning.target_weights)
        assert pt[("prescaling", "primes")] == "[⟨1 0 0] ⟨0 2 0] ⟨0 0 3]⟩", "the bare prescaler reads the typed diagonal (1, 2, 3), not the scheme's log-prime weights"
        plain = _grid_with_plain_text(state, "TILT minimax-S").geometry.plain_text_strings
        assert pt[("tuning", "primes")] != plain[("tuning", "primes")]
        assert pt[("prescaling", "primes")] != plain[("prescaling", "primes")]

    def test_plain_text_custom_prescaler_renders_an_off_diagonal_matrix_like_the_grid(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        matrix = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
        pt = _grid_with_plain_text(state, "TILT minimax-S", custom_prescaler=matrix).geometry.plain_text_strings
        assert pt[("prescaling", "primes")] == "[⟨1 0.500 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩"
        gb = _grid_with_plain_text(state, "TILT minimax-S", custom_prescaler=matrix)
        assert gb.geometry.plain_text_strings[("tuning", "primes")] == text_format._cents_map(gb.resolved.tuning.tuning_map.tuning_map)
        assert gb.geometry.plain_text_strings[("complexity", "targets")] == text_format._cents_list(gb.resolved.complexities["targets"])

    def test_plain_text_targets_honor_an_override(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        pt = service.plain_text_values(st, "TILT minimax-S", target_override=("2/1", "3/2"))
        assert pt[("vectors", "targets")] == "[[1 0 0⟩ [-1 1 0⟩]"
        assert pt[("tuning", "targets")].count(".") == 2

    def test_plain_text_all_interval_lils_weight_is_the_per_target_list(self):
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), scheme="minimax-lils-S")
        w = pt[("weight", "targets")]
        assert w.startswith("[") and not w.startswith("[["), "a flat list, not a nested matrix"
        assert "|" not in w


class TestPlainTextNonstandard:
    def test_plain_text_complexity_runs_over_the_nonstandard_domain_basis(self):
        state = service.parse_mapping_state("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        targets = ("13/5", "3/2")
        band = service.plain_text_values(state, "minimax-S", target_override=targets)[("complexity", "targets")]
        over_basis = service.interval_complexities(state.mapping, "minimax-S", targets, domain_basis=state.domain_basis)
        truncated = service.interval_complexities(state.mapping, "minimax-S", targets)
        assert service.cents(over_basis[0]) in band
        assert service.cents(truncated[0]) not in band, "not the prime-truncated value"

    def test_plain_text_primes_complexity_runs_over_the_domain_basis_not_standard_primes(self):
        state = service.from_temperament_data("2.3.7 [⟨1 1 3] ⟨0 2 -1]}")
        band = service.plain_text_values(state, "TILT minimax-S", "TILT")[("complexity", "primes")]
        elems = tuple(service.element_ratio(e) for e in state.domain_basis)
        over_basis = service.interval_complexities(state.mapping, "TILT minimax-S", elems,
                                                   domain_basis=state.domain_basis)
        assert band == text_format._cents_map(over_basis)
        assert service.cents(over_basis[2]) in band
        truncated = service.interval_complexities(state.mapping, "TILT minimax-S",
                                                  tuple(f"{p}/1" for p in service.standard_primes(state.dimensionality)))
        assert service.cents(truncated[2]) not in band, "not the prime-truncated log₂5 ≈ 2.322"

    def test_plain_text_threads_the_nonprime_approach_into_its_tuning(self):
        state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
        neutral = service.plain_text_values(state, "TILT minimax-S", "TILT")
        nonprime = service.plain_text_values(state, "TILT minimax-S", "TILT", nonprime_approach="nonprime-based")
        assert nonprime[("tuning", "primes")] != neutral[("tuning", "primes")]
        tuning_map = service.tuning(state.mapping, "TILT minimax-S", state.domain_basis, "nonprime-based")
        assert nonprime[("tuning", "primes")] == text_format._cents_map(tuning_map.tuning_map)

    def test_plain_text_over_a_nonstandard_domain_uses_the_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state)
        assert pt[("quantities", "primes")] == "2.3.13/5"
        assert pt[("vectors", "commas")] == "[[2 -3 2⟩]"
        tuning_map = service.tuning(state.mapping, domain_basis=state.domain_basis)
        cents = " ".join(f"{v:.3f}" for v in tuning_map.tuning_map)
        assert pt[("tuning", "primes")] == f"⟨{cents}]"

    def test_plain_text_superspace_prescaling_lifts_like_the_grid(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state, "minimax-ES", superspace=True)
        superspace_pre = service.superspace_complexity_prescaler(state, "minimax-ES")
        lifted = service.lift_vectors_to_superspace(state.domain_basis, state.comma_basis)
        expected_cols = [tuple(superspace_pre[i] * v[i] for i in range(len(superspace_pre))) for v in lifted]
        assert pt[("prescaling", "commas")] == text_format._prescale_vector_list(expected_cols)
        assert len(expected_cols[0]) == len(superspace_pre) == 4, "dL-tall (4 over the 2.3.5.13 superspace), not the unlifted d = 3 the bug showed"
        assert " 7.401" in pt[("prescaling", "commas")]


class TestPlainTextValues:
    def test_plain_text_values_includes_the_superspace_projection_when_projection_on(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=("2", "13/5"))
        assert pt[("superspace_projection", "superspace_primes")] == "[⟨1 2/3 0 0]⟨0 0 0 0]⟨0 -2/3 1 0]⟨0 2/3 0 1]⟩"
        off = service.plain_text_values(state, superspace=True, consolidate_v=False, held_basis_ratios=("2", "13/5"))
        assert ("superspace_projection", "superspace_primes") not in off
        dashed = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=())
        assert dashed[("superspace_projection", "superspace_primes")] == service.projection_ebk(None, 4)

    def test_plain_text_values_includes_every_superspace_projection_tile(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=("2", "13/5"))
        for column in ("superspace_generators", "superspace_primes", "primes", "detempering", "commas", "targets"):
            assert ("superspace_projection", column) in pt, column
        assert pt[("superspace_projection", "superspace_generators")].startswith("{") and pt[("superspace_projection", "superspace_generators")].endswith("]")
        assert pt[("superspace_projection", "primes")].startswith("⟨")
        assert pt[("superspace_projection", "detempering")].startswith("{")
        assert pt[("superspace_projection", "targets")].startswith("[")
        dashed = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=())
        assert "—" in dashed[("superspace_projection", "primes")]

    def test_plain_text_values_includes_superspace_entries_when_superspace_on(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state, superspace=True)
        assert pt[("superspace_vectors", "primes")] == "⟨[1 0 0 0⟩ [0 1 0 0⟩ [0 0 -1 1⟩]"
        ml = service.superspace_mapping(state)
        expected_ml = "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in ml) + "}"
        assert pt[("superspace_mapping", "superspace_primes")] == expected_ml
        assert pt[("superspace_vectors", "superspace_primes")] == (
            "[⟨1 0 0 0]⟨0 1 0 0]⟨0 0 1 0]⟨0 0 0 1]⟩"
        )
        assert pt[("superspace_mapping", "superspace_generators")] == "{[1 0 0} [0 1 0} [0 0 1}]"
        assert ("tuning", "superspace_generators") in pt
        assert ("tuning", "superspace_primes") in pt
        assert ("just", "superspace_primes") in pt
        assert ("retune", "superspace_primes") in pt

    def test_plain_text_values_omits_superspace_entries_when_superspace_off(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pt = service.plain_text_values(state)
        for key in (("superspace_vectors", "primes"), ("superspace_mapping", "superspace_primes"),
                    ("superspace_vectors", "superspace_primes"), ("tuning", "superspace_generators"),
                    ("tuning", "superspace_primes"), ("just", "superspace_primes"), ("retune", "superspace_primes")):
            assert key not in pt

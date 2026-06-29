from __future__ import annotations

from rtt.app import presets, service
from rtt.app.editor_state import comma_ratios_in_domain, weights_are_solvable

_GENERATOR_NUDGE_CENTS = 0.001


class _TuningCommands:
    def back_to_scheme(self) -> None:
        if not self.manual_tuning:
            return
        self.snapshot()
        self.generator_tuning = None
        self.pending.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()

    def set_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, len(self.state.mapping))
        if gens is None:
            return False
        self.snapshot()
        self.generator_tuning = gens
        self.manual_tuning = True
        self.projection_basis = ()
        return True

    def _override_generator(self, i: int, transform, *, snapshot: bool = True) -> None:
        override = self.effective_generator_tuning()
        base = list(
            override
            if override is not None and len(override) == len(self.state.mapping)
            else self.optimum_generator_tuning()
        )
        if not 0 <= i < len(base):
            return
        base[i] = float(transform(base[i]))
        if snapshot:
            self.snapshot()
        self.generator_tuning = tuple(base)
        self.manual_tuning = True
        self.projection_basis = ()

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        self._override_generator(i, lambda _current: cents)

    def nudge_generator_tuning_component(self, i: int, steps: int) -> None:
        self._override_generator(
            i,
            lambda current: round(round(current, 3) + steps * _GENERATOR_NUDGE_CENTS, 3),
            snapshot=self.pending.nudging_generator != i,
        )
        self.pending.nudging_generator = i

    def flip_generator(self, i: int) -> None:
        override = self.effective_generator_tuning()
        mapping = [list(row) for row in self.state.mapping]
        mapping[i] = [-x for x in mapping[i]]
        self.edit_mapping(mapping)
        if override is not None and len(override) == len(mapping):
            flipped = list(override)
            flipped[i] = -flipped[i]
            self.generator_tuning = tuple(flipped)
            self.manual_tuning = True

    def set_superspace_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, service.superspace_rank(self.state))
        if gens is None:
            return False
        self.snapshot()
        self.pending.superspace_generator_tuning = gens
        self.manual_tuning = True
        return True

    def set_superspace_generator_tuning_component(self, i: int, cents: float) -> None:
        manual = self.pending.superspace_generator_tuning
        rL = service.superspace_rank(self.state)
        base = list(
            manual
            if manual is not None and len(manual) == rL
            else self.optimum_superspace_generator_tuning()
        )
        base[i] = float(cents)
        self.snapshot()
        self.pending.superspace_generator_tuning = tuple(base)
        self.manual_tuning = True

    def nudge_superspace_generator_tuning_component(self, i: int, steps: int) -> None:
        rL = service.superspace_rank(self.state)
        manual = self.pending.superspace_generator_tuning
        base = list(
            manual
            if manual is not None and len(manual) == rL
            else self.optimum_superspace_generator_tuning()
        )
        self.set_superspace_generator_tuning_component(
            i, round(round(base[i], 3) + steps * _GENERATOR_NUDGE_CENTS, 3)
        )

    def try_edit_projection_text(self, text: str) -> bool:
        matrix = service.parse_projection(text)
        if matrix is None:
            return False
        return self.set_projection_matrix(matrix)

    def try_edit_embedding_text(self, text: str) -> bool:
        matrix = service.parse_embedding(text, self.state.dimensionality, len(self.state.mapping))
        if matrix is None:
            return False
        return self.set_embedding_matrix(matrix)

    def set_tuning_scheme(self, name: str) -> None:
        self.snapshot()
        target = "{}" if service.is_all_interval(self.tuning_scheme) else self.target_spec
        self.tuning_scheme = service.scheme_with_targets(name, target)
        self.generator_tuning = None
        self.pending.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()

    def set_established_projection(self, name: str | None) -> None:
        ratios = presets.projection_held_ratios(self.state, name)
        if ratios is None:
            return
        self._hold_as_manual_tuning(ratios)

    def _hold_as_manual_tuning(self, ratios) -> None:
        self.snapshot()
        self.generator_tuning = service.tuning(
            self.state.mapping,
            self.tuning_scheme,
            self.state.domain_basis,
            self.nonprime_basis_approach,
            held=tuple(ratios),
            prescaler_override=self.custom_prescaler,
            targets=self.target_override,
            weights_override=self.custom_weights,
        ).generator_map
        self.pending.superspace_generator_tuning = None
        self.manual_tuning = True
        self.projection_basis = tuple(ratios)

    def set_unchanged_basis(self, ratios) -> None:
        if service.tuning_projection(self.state, tuple(ratios)) is None:
            return
        self._hold_as_manual_tuning(ratios)

    def set_projection_matrix(self, projection) -> bool:
        U = service.unchanged_basis_from_projection(self.state, projection)
        if U is None:
            return False
        self.set_unchanged_basis(comma_ratios_in_domain(self.state, U))
        return True

    def set_embedding_matrix(self, embedding) -> bool:
        U = service.unchanged_basis_from_embedding(self.state, embedding)
        if U is None:
            return False
        self.set_unchanged_basis(comma_ratios_in_domain(self.state, U))
        return True

    def set_complexity_prescaler(self, prescaler: str) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_prescaler(self.tuning_scheme, prescaler)
        self.custom_prescaler = None
        self.turn_off_custom_weights()

    def set_complexity_norm_power(self, power: float) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_complexity_norm_power(self.tuning_scheme, power)

    def set_optimization_power(self, power: float) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_power(self.tuning_scheme, power)

    def set_weight_slope(self, slope: str) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)
        self.turn_off_custom_weights()

    def set_nonprime_basis_approach(self, approach: str) -> None:
        if approach not in ("", "prime-based", "nonprime-based"):
            raise ValueError(f"unknown nonprime basis approach: {approach!r}")
        self.nonprime_basis_approach = approach
        self.pending.superspace_generator_tuning = None
        if self.generator_tuning is None:
            self.manual_tuning = False

    def set_complexity_name(self, name: str) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_complexity(self.tuning_scheme, name)
        self.custom_prescaler = None
        self.turn_off_custom_weights()

    def set_custom_prescaler_entry(self, i: int, j: int, value: float) -> None:
        self.snapshot()
        if self.custom_prescaler is None:
            self.custom_prescaler = tuple(
                service.complexity_prescaler(self.state.mapping, self.tuning_scheme)
            )
        is_matrix = isinstance(self.custom_prescaler[0], (tuple, list))
        if i == j and not is_matrix:
            diag = list(self.custom_prescaler)
            diag[i] = float(value)
            self.custom_prescaler = tuple(diag)
        else:
            d = self.state.dimensionality
            rows = (
                [list(r) for r in self.custom_prescaler]
                if is_matrix
                else [
                    [self.custom_prescaler[r] if r == c else 0.0 for c in range(d)]
                    for r in range(d)
                ]
            )
            rows[i][j] = float(value)
            self.custom_prescaler = tuple(tuple(r) for r in rows)

    def set_custom_prescaler_text(self, text: str) -> bool:
        diag = service.parse_prescaler_diagonal(text, self.state.dimensionality)
        if diag is None:
            return False
        self.snapshot()
        self.custom_prescaler = diag
        return True

    def set_diminuator_replaced(self, replaced: bool) -> None:
        self.snapshot()
        self.tuning_scheme = service.scheme_with_diminuator(self.tuning_scheme, replaced)

    def set_all_interval(self, all_interval: bool) -> None:
        self.snapshot()
        self.apply_all_interval(all_interval)

    def set_custom_weight_entry(self, i: int, value: float) -> None:
        self.snapshot()
        if self.custom_weights is None:
            self.custom_weights = tuple(self.displayed_target_weights())
            self.settings["custom_weights"] = True
        weights = list(self.custom_weights)
        if 0 <= i < len(weights):
            weights[i] = float(value)
            self.custom_weights = tuple(weights)

    def set_custom_weights(self, weights) -> None:
        weights = tuple(float(w) for w in weights)
        if not weights_are_solvable(weights):
            return
        self.snapshot()
        self.custom_weights = weights
        self.settings["custom_weights"] = True

from __future__ import annotations

from rtt.app import presets, service
from rtt.app.editor_document import Document, weights_are_solvable
from rtt.app.editor_structure import StructureOps
from rtt.app.editor_view import TuningView

_GENERATOR_NUDGE_CENTS = 0.001


class TuningOps:
    def __init__(self, doc: Document, view: TuningView, structure: StructureOps) -> None:
        self.doc = doc
        self.pending = doc.pending
        self.view = view
        self.structure = structure

    def back_to_scheme(self) -> None:
        if not self.doc.manual_tuning:
            return
        self.doc.snapshot()
        self.doc.generator_tuning = None
        self.pending.superspace_generator_tuning = None
        self.doc.manual_tuning = False
        self.doc.projection_basis = ()

    def set_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, len(self.doc.state.mapping))
        if gens is None:
            return False
        self.doc.snapshot()
        self.doc.generator_tuning = gens
        self.doc.manual_tuning = True
        self.doc.projection_basis = ()
        return True

    def _override_generator(self, i: int, transform, *, snapshot: bool = True) -> None:
        override = self.view.effective_generator_tuning()
        base = list(
            override
            if override is not None and len(override) == len(self.doc.state.mapping)
            else self.view.optimum_generator_tuning()
        )
        if not 0 <= i < len(base):
            return
        base[i] = float(transform(base[i]))
        if snapshot:
            self.doc.snapshot()
        self.doc.generator_tuning = tuple(base)
        self.doc.manual_tuning = True
        self.doc.projection_basis = ()

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
        override = self.view.effective_generator_tuning()
        mapping = [list(row) for row in self.doc.state.mapping]
        mapping[i] = [-x for x in mapping[i]]
        self.structure.edit_mapping(mapping)
        if override is not None and len(override) == len(mapping):
            flipped = list(override)
            flipped[i] = -flipped[i]
            self.doc.generator_tuning = tuple(flipped)
            self.doc.manual_tuning = True

    def set_superspace_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, service.superspace_rank(self.doc.state))
        if gens is None:
            return False
        self.doc.snapshot()
        self.pending.superspace_generator_tuning = gens
        self.doc.manual_tuning = True
        return True

    def set_superspace_generator_tuning_component(self, i: int, cents: float) -> None:
        manual = self.pending.superspace_generator_tuning
        rL = service.superspace_rank(self.doc.state)
        base = list(
            manual
            if manual is not None and len(manual) == rL
            else self.view.optimum_superspace_generator_tuning()
        )
        base[i] = float(cents)
        self.doc.snapshot()
        self.pending.superspace_generator_tuning = tuple(base)
        self.doc.manual_tuning = True

    def nudge_superspace_generator_tuning_component(self, i: int, steps: int) -> None:
        rL = service.superspace_rank(self.doc.state)
        manual = self.pending.superspace_generator_tuning
        base = list(
            manual
            if manual is not None and len(manual) == rL
            else self.view.optimum_superspace_generator_tuning()
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
        matrix = service.parse_embedding(text, self.doc.state.d, len(self.doc.state.mapping))
        if matrix is None:
            return False
        return self.set_embedding_matrix(matrix)

    def set_tuning_scheme(self, name: str) -> None:
        self.doc.snapshot()
        target = "{}" if service.is_all_interval(self.doc.tuning_scheme) else self.doc.target_spec
        self.doc.tuning_scheme = service.scheme_with_targets(name, target)
        self.doc.generator_tuning = None
        self.pending.superspace_generator_tuning = None
        self.doc.manual_tuning = False
        self.doc.projection_basis = ()

    def set_established_projection(self, name: str | None) -> None:
        ratios = presets.projection_held_ratios(self.doc.state, name)
        if ratios is None:
            return
        self._hold_as_manual_tuning(ratios)

    def _hold_as_manual_tuning(self, ratios) -> None:
        doc = self.doc
        doc.snapshot()
        doc.generator_tuning = service.tuning(
            doc.state.mapping,
            doc.tuning_scheme,
            doc.state.domain_basis,
            doc.nonprime_basis_approach,
            held=tuple(ratios),
            prescaler_override=doc.custom_prescaler,
            targets=doc.target_override,
            weights_override=doc.custom_weights,
        ).generator_map
        self.pending.superspace_generator_tuning = None
        doc.manual_tuning = True
        doc.projection_basis = tuple(ratios)

    def set_unchanged_basis(self, ratios) -> None:
        if service.tuning_projection(self.doc.state, tuple(ratios)) is None:
            return
        self._hold_as_manual_tuning(ratios)

    def set_projection_matrix(self, projection) -> bool:
        U = service.unchanged_basis_from_projection(self.doc.state, projection)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.doc.state.domain_basis))
        return True

    def set_embedding_matrix(self, embedding) -> bool:
        U = service.unchanged_basis_from_embedding(self.doc.state, embedding)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.doc.state.domain_basis))
        return True

    def set_complexity_prescaler(self, prescaler: str) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_prescaler(self.doc.tuning_scheme, prescaler)
        self.doc.custom_prescaler = None
        self.doc.turn_off_custom_weights()

    def set_complexity_norm_power(self, power: float) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_complexity_norm_power(
            self.doc.tuning_scheme, power
        )

    def set_optimization_power(self, power: float) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_power(self.doc.tuning_scheme, power)

    def set_weight_slope(self, slope: str) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_weight_slope(self.doc.tuning_scheme, slope)
        self.doc.turn_off_custom_weights()

    def set_nonprime_basis_approach(self, approach: str) -> None:
        if approach not in ("", "prime-based", "nonprime-based"):
            raise ValueError(f"unknown nonprime basis approach: {approach!r}")
        self.doc.nonprime_basis_approach = approach
        self.pending.superspace_generator_tuning = None
        if self.doc.generator_tuning is None:
            self.doc.manual_tuning = False

    def set_complexity_name(self, name: str) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_complexity(self.doc.tuning_scheme, name)
        self.doc.custom_prescaler = None
        self.doc.turn_off_custom_weights()

    def set_custom_prescaler_entry(self, i: int, j: int, value: float) -> None:
        self.doc.snapshot()
        if self.doc.custom_prescaler is None:
            self.doc.custom_prescaler = tuple(
                service.complexity_prescaler(self.doc.state.mapping, self.doc.tuning_scheme)
            )
        is_matrix = isinstance(self.doc.custom_prescaler[0], (tuple, list))
        if i == j and not is_matrix:
            diag = list(self.doc.custom_prescaler)
            diag[i] = float(value)
            self.doc.custom_prescaler = tuple(diag)
        else:
            d = self.doc.state.d
            rows = (
                [list(r) for r in self.doc.custom_prescaler]
                if is_matrix
                else [
                    [self.doc.custom_prescaler[r] if r == c else 0.0 for c in range(d)]
                    for r in range(d)
                ]
            )
            rows[i][j] = float(value)
            self.doc.custom_prescaler = tuple(tuple(r) for r in rows)

    def set_custom_prescaler_text(self, text: str) -> bool:
        diag = service.parse_prescaler_diagonal(text, self.doc.state.d)
        if diag is None:
            return False
        self.doc.snapshot()
        self.doc.custom_prescaler = diag
        return True

    def set_diminuator_replaced(self, replaced: bool) -> None:
        self.doc.snapshot()
        self.doc.tuning_scheme = service.scheme_with_diminuator(self.doc.tuning_scheme, replaced)

    def set_all_interval(self, all_interval: bool) -> None:
        self.doc.snapshot()
        self.doc.apply_all_interval(all_interval)

    def set_custom_weight_entry(self, i: int, value: float) -> None:
        self.doc.snapshot()
        if self.doc.custom_weights is None:
            self.doc.custom_weights = tuple(self.doc.displayed_target_weights())
            self.doc.settings["custom_weights"] = True
        weights = list(self.doc.custom_weights)
        if 0 <= i < len(weights):
            weights[i] = float(value)
            self.doc.custom_weights = tuple(weights)

    def set_custom_weights(self, weights) -> None:
        weights = tuple(float(w) for w in weights)
        if not weights_are_solvable(weights):
            return
        self.doc.snapshot()
        self.doc.custom_weights = weights
        self.doc.settings["custom_weights"] = True

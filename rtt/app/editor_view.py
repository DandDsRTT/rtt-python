from __future__ import annotations

import logging

from rtt.app import presets, service
from rtt.app.editor_state import _same_cents_map

_log = logging.getLogger(__name__)


class _TuningQueries:
    def optimum_tuning(self) -> service.Tuning:
        held = (
            service.comma_ratios(self.held_vectors, self.state.domain_basis)
            if self.held_vectors
            else ()
        )
        return service.tuning(
            self.state.mapping,
            self.tuning_scheme,
            self.state.domain_basis,
            self.nonprime_basis_approach,
            held=held,
            prescaler_override=self.custom_prescaler,
            targets=self.target_override,
            weights_override=self.custom_weights,
        )

    def optimum_generator_tuning(self) -> tuple[float, ...]:
        return self.optimum_tuning().generator_map

    def optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        return service.superspace_tuning(
            self.state, self.tuning_scheme, "prime-based"
        ).generator_map

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        superspace = self.pending.superspace_generator_tuning
        if (
            superspace is not None
            and self.nonprime_basis_approach == "prime-based"
            and service.domain_has_nonprimes(self.state.domain_basis)
        ):
            return service.project_superspace_generators_to_domain(self.state, superspace)
        return self.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        bare = service.tuning(
            self.state.mapping,
            self.tuning_scheme,
            self.state.domain_basis,
            self.nonprime_basis_approach,
            prescaler_override=self.custom_prescaler,
            targets=self.target_override,
            weights_override=self.custom_weights,
        ).generator_map
        held_optimum = self.optimum_generator_tuning() if self.held_vectors else bare
        override = self.effective_generator_tuning()
        displayed = (
            override
            if override is not None and len(override) == len(self.state.mapping)
            else held_optimum
        )
        if not _same_cents_map(displayed, held_optimum):
            if self.manual_tuning:
                return None
        elif not _same_cents_map(held_optimum, bare):
            return None
        return service.base_scheme_name(self.tuning_scheme)

    @property
    def tuning_is_optimized(self) -> bool:
        override = self.effective_generator_tuning()
        if override is None or len(override) != len(self.state.mapping):
            return True
        return _same_cents_map(override, self.optimum_generator_tuning())

    @property
    def displayed_prescaler_name(self) -> str | None:
        return service.displayed_prescaler_name(
            self.state.mapping, self.tuning_scheme, self.custom_prescaler
        )

    def displayed_retuning_map(self) -> tuple[float, ...] | None:
        try:
            generators = self.effective_generator_tuning()
            if generators is not None and len(generators) == self.state.r:
                optimum = self.optimum_tuning()
                if not _same_cents_map(generators, optimum.generator_map):
                    return service.tuning_from_generators(
                        self.state.mapping, generators, self.state.domain_basis
                    ).retuning_map
                return optimum.retuning_map
            return self.optimum_tuning().retuning_map
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("displayed_retuning_map dashed: %r", exc)
            return None

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        retuning = self.displayed_retuning_map()
        if retuning is None:
            return ()
        held = (
            tuple(service.comma_ratios(self.held_vectors, self.state.domain_basis))
            if self.held_vectors
            else ()
        )
        candidates = (
            held
            + self.projection_basis
            + presets.projection_candidate_ratios(self.state)
            + tuple(service.target_interval_set(self.target_spec, self.state.domain_basis))
        )
        return service.unchanged_ratios_of_tuning(self.state, retuning, candidates)

    @property
    def targets_in_use(self) -> bool:
        if not self.settings.get("projection"):
            return True
        if not self.manual_tuning:
            return True
        if len(self.unchanged_ratios) < self.state.r:
            return True
        displayed = self.effective_generator_tuning()
        if displayed is None:
            return True
        try:
            optimum = self.optimum_generator_tuning()
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("optimum solve failed; treating displayed tuning as optimal: %r", exc)
            return True
        return len(displayed) == len(optimum) and all(
            abs(a - b) < 1e-6 for a, b in zip(displayed, optimum, strict=False)
        )

    @property
    def displayed_projection_scheme_name(self) -> str | None:
        return presets.identify_established_projection(self.state, self.unchanged_ratios)

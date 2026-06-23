from __future__ import annotations

import logging

from rtt.app import presets, service
from rtt.app.editor_document import Document, _same_cents_map

_log = logging.getLogger(__name__)


class TuningView:
    def __init__(self, doc: Document) -> None:
        self.doc = doc

    def optimum_tuning(self) -> service.Tuning:
        doc = self.doc
        held = (
            service.comma_ratios(doc.held_vectors, doc.state.domain_basis)
            if doc.held_vectors
            else ()
        )
        return service.tuning(
            doc.state.mapping,
            doc.tuning_scheme,
            doc.state.domain_basis,
            doc.nonprime_basis_approach,
            held=held,
            prescaler_override=doc.custom_prescaler,
            targets=doc.target_override,
            weights_override=doc.custom_weights,
        )

    def optimum_generator_tuning(self) -> tuple[float, ...]:
        return self.optimum_tuning().generator_map

    def optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        return service.superspace_tuning(
            self.doc.state, self.doc.tuning_scheme, "prime-based"
        ).generator_map

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        doc = self.doc
        superspace = doc.pending.superspace_generator_tuning
        if (
            superspace is not None
            and doc.nonprime_basis_approach == "prime-based"
            and service.domain_has_nonprimes(doc.state.domain_basis)
        ):
            return service.project_superspace_generators_to_domain(doc.state, superspace)
        return doc.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        doc = self.doc
        bare = service.tuning(
            doc.state.mapping,
            doc.tuning_scheme,
            doc.state.domain_basis,
            doc.nonprime_basis_approach,
            prescaler_override=doc.custom_prescaler,
            targets=doc.target_override,
            weights_override=doc.custom_weights,
        ).generator_map
        held_optimum = self.optimum_generator_tuning() if doc.held_vectors else bare
        override = self.effective_generator_tuning()
        displayed = (
            override
            if override is not None and len(override) == len(doc.state.mapping)
            else held_optimum
        )
        if not _same_cents_map(displayed, held_optimum):
            if doc.manual_tuning:
                return None
        elif not _same_cents_map(held_optimum, bare):
            return None
        return service.base_scheme_name(doc.tuning_scheme)

    @property
    def tuning_is_optimized(self) -> bool:
        override = self.effective_generator_tuning()
        if override is None or len(override) != len(self.doc.state.mapping):
            return True
        return _same_cents_map(override, self.optimum_generator_tuning())

    @property
    def displayed_prescaler_name(self) -> str | None:
        doc = self.doc
        return service.displayed_prescaler_name(
            doc.state.mapping, doc.tuning_scheme, doc.custom_prescaler
        )

    def _displayed_retuning_map(self) -> tuple[float, ...] | None:
        doc = self.doc
        try:
            generators = self.effective_generator_tuning()
            if generators is not None and len(generators) == doc.state.r:
                optimum = self.optimum_tuning()
                if not _same_cents_map(generators, optimum.generator_map):
                    return service.tuning_from_generators(
                        doc.state.mapping, generators, doc.state.domain_basis
                    ).retuning_map
                return optimum.retuning_map
            return self.optimum_tuning().retuning_map
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("_displayed_retuning_map dashed: %r", exc)
            return None

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        doc = self.doc
        retuning = self._displayed_retuning_map()
        if retuning is None:
            return ()
        held = (
            tuple(service.comma_ratios(doc.held_vectors, doc.state.domain_basis))
            if doc.held_vectors
            else ()
        )
        candidates = (
            held
            + doc.projection_basis
            + presets.projection_candidate_ratios(doc.state)
            + tuple(service.target_interval_set(doc.target_spec, doc.state.domain_basis))
        )
        return service.unchanged_ratios_of_tuning(doc.state, retuning, candidates)

    @property
    def targets_in_use(self) -> bool:
        doc = self.doc
        if not doc.settings.get("projection"):
            return True
        if not doc.manual_tuning:
            return True
        if len(self.unchanged_ratios) < doc.state.r:
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
        return presets.identify_established_projection(self.doc.state, self.unchanged_ratios)

from __future__ import annotations

from dataclasses import replace

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_layout import compute_geometry
from rtt.app.spreadsheet_resolve_draft import ResolveDraft
from rtt.app.spreadsheet_resolve_inputs import ResolveInputs
from rtt.app.spreadsheet_resolve_intervals import resolve_interval_sets
from rtt.app.spreadsheet_resolve_steps import (
    determine_ghosts,
    resolve_canonical_mapped,
    resolve_complexities,
    resolve_detempering,
    resolve_prescaler_and_domain_labels,
    resolve_projection_data,
    resolve_superspace_dims,
    unpack_show_flags,
)
from rtt.app.spreadsheet_resolved import freeze


class Resolver:
    def __init__(self, state, settings=None, collapsed=None,
                 tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
                 pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
                 custom_prescaler=None, custom_weights=None, tuning_optimized=False,
                 pending_interest=None, pending_held=None, pending_target=None, previous_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, held_basis_ratios=(), displayed_projection_name=None,
                 targets_in_use=True, pending_mapping_row=None, preview_remove=None,
                 mapping_form=None, comma_basis_form=None, resolve_only=False):
        self._resolve_only = resolve_only
        self.inputs = ResolveInputs(
            state=state,
            settings=settings if settings is not None else _default_settings(),
            collapsed=collapsed or frozenset(),
            tuning_scheme=tuning_scheme if tuning_scheme is not None else service.DEFAULT_DOCUMENT_SCHEME,
            target_spec=target_spec if target_spec is not None else service.DEFAULT_TARGET_SPEC,
            interest=interest,
            range_mode=range_mode,
            pending_interest=pending_interest,
            pending_held=pending_held,
            pending_target=pending_target,
            pending_element=pending_element,
            pending_mapping_row=pending_mapping_row,
            pending_comma=pending_comma,
            custom_prescaler=custom_prescaler,
            custom_weights=custom_weights,
            tuning_optimized=tuning_optimized,
            nonprime_approach=nonprime_approach,
            superspace_generator_tuning=superspace_generator_tuning,
            displayed_tuning_name=displayed_tuning_name,
            displayed_projection_name=displayed_projection_name,
            held_basis_ratios=held_basis_ratios,
            held_vectors=held_vectors,
            generator_tuning=generator_tuning,
            target_override=target_override,
            targets_in_use=targets_in_use,
            mapping_form=mapping_form,
            comma_basis_form=comma_basis_form,
            preview_remove=preview_remove,
            previous_ids=previous_ids or {},
        )
        self._build()

    def _build(self) -> None:
        ghosts = determine_ghosts(self.inputs)
        self.inputs = replace(self.inputs, preview_remove=ghosts.preview_remove)
        inputs = self.inputs
        draft = ResolveDraft(ghost_row=ghosts.ghost_row, ghost_comma=ghosts.ghost_comma,
                             displayed_tuning_name=inputs.displayed_tuning_name,
                             displayed_projection_name=inputs.displayed_projection_name)
        draft = unpack_show_flags(inputs, draft)
        draft = resolve_superspace_dims(inputs, draft)
        draft = resolve_prescaler_and_domain_labels(inputs, draft)
        draft = resolve_interval_sets(inputs, draft)
        draft = resolve_complexities(inputs, draft)
        draft = resolve_detempering(inputs, draft)
        draft = resolve_canonical_mapped(inputs, draft)
        draft = resolve_projection_data(inputs, draft)
        self.resolved = freeze(draft)
        if self._resolve_only:
            return

        self.geometry = compute_geometry(self.resolved, build_context(self))

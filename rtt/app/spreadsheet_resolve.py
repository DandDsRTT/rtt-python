from __future__ import annotations

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_layout import compute_geometry
from rtt.app.spreadsheet_resolve_draft import ResolveDraft
from rtt.app.spreadsheet_resolve_inputs import make_inputs
from rtt.app.spreadsheet_resolve_intervals import resolve_interval_sets
from rtt.app.spreadsheet_resolve_steps import (
    determine_ghosts,
    resolve_canon_mapped,
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
                 pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, held_basis_ratios=(), displayed_projection_name=None,
                 targets_in_use=True, pending_mapping_row=None, preview_remove=None,
                 mapping_form=None, comma_basis_form=None, resolve_only=False):
        self._resolve_only = resolve_only
        self.prev_ids = prev_ids or {}
        self.mapping_form = mapping_form
        self.comma_basis_form = comma_basis_form
        self.preview_remove = preview_remove
        self.targets_in_use = targets_in_use
        self.state = state
        self.settings = settings
        self.collapsed = collapsed
        self.tuning_scheme = tuning_scheme
        self.target_spec = target_spec
        self.interest = interest
        self.range_mode = range_mode
        self.pending_interest = pending_interest
        self.pending_held = pending_held
        self.pending_target = pending_target
        self.pending_element = pending_element
        self.pending_mapping_row = pending_mapping_row
        self.custom_prescaler = custom_prescaler
        self.custom_weights = custom_weights
        self.tuning_optimized = tuning_optimized
        self.nonprime_approach = nonprime_approach
        self.superspace_generator_tuning = superspace_generator_tuning
        self.displayed_tuning_name = displayed_tuning_name
        self.held_basis_ratios = held_basis_ratios
        self.displayed_projection_name = displayed_projection_name
        self.generator_tuning = generator_tuning
        self.target_override = target_override

        if self.settings is None:
            self.settings = _default_settings()
        if self.tuning_scheme is None:
            self.tuning_scheme = service.DEFAULT_DOCUMENT_SCHEME
        if self.target_spec is None:
            self.target_spec = service.DEFAULT_TARGET_SPEC
        self.collapsed = self.collapsed or frozenset()
        self._build(held_vectors, pending_comma)

    def _build(self, held_vectors, pending_comma) -> None:
        inputs = make_inputs(self, held_vectors, pending_comma)
        ghosts = determine_ghosts(inputs)
        self.preview_remove = ghosts.preview_remove
        draft = ResolveDraft(ghost_row=ghosts.ghost_row, ghost_comma=ghosts.ghost_comma,
                             displayed_tuning_name=self.displayed_tuning_name,
                             displayed_projection_name=self.displayed_projection_name)
        draft = unpack_show_flags(inputs, draft)
        draft = resolve_superspace_dims(inputs, draft)
        draft = resolve_prescaler_and_domain_labels(inputs, draft)
        draft = resolve_interval_sets(inputs, draft)
        draft = resolve_complexities(inputs, draft)
        draft = resolve_detempering(inputs, draft)
        draft = resolve_canon_mapped(inputs, draft)
        draft = resolve_projection_data(inputs, draft)
        self.resolved = freeze(draft)
        if self._resolve_only:
            return

        self.geometry = compute_geometry(self.resolved, build_context(self))

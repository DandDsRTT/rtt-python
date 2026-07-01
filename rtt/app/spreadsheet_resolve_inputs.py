from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolveInputs:
    state: object
    settings: object
    collapsed: object
    tuning_scheme: object
    target_spec: object
    interest: object
    range_mode: str
    pending_interest: object
    pending_held: object
    pending_target: object
    pending_element: object
    pending_mapping_row: object
    pending_comma: object
    custom_prescaler: object
    custom_weights: object
    tuning_optimized: bool
    nonprime_approach: str
    superspace_generator_tuning: object
    displayed_tuning_name: object
    displayed_projection_name: object
    held_basis_ratios: object
    held_vectors: object
    generator_tuning: object
    target_override: object
    targets_in_use: bool
    mapping_form: object
    comma_basis_form: object
    preview_remove: object
    previous_ids: object

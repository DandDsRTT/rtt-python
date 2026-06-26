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
    prev_ids: object


def make_inputs(builder, held_vectors, pending_comma) -> ResolveInputs:
    return ResolveInputs(
        state=builder.state,
        settings=builder.settings,
        collapsed=builder.collapsed,
        tuning_scheme=builder.tuning_scheme,
        target_spec=builder.target_spec,
        interest=builder.interest,
        range_mode=builder.range_mode,
        pending_interest=builder.pending_interest,
        pending_held=builder.pending_held,
        pending_target=builder.pending_target,
        pending_element=builder.pending_element,
        pending_mapping_row=builder.pending_mapping_row,
        pending_comma=pending_comma,
        custom_prescaler=builder.custom_prescaler,
        custom_weights=builder.custom_weights,
        tuning_optimized=builder.tuning_optimized,
        nonprime_approach=builder.nonprime_approach,
        superspace_generator_tuning=builder.superspace_generator_tuning,
        displayed_tuning_name=builder.displayed_tuning_name,
        displayed_projection_name=builder.displayed_projection_name,
        held_basis_ratios=builder.held_basis_ratios,
        held_vectors=held_vectors,
        generator_tuning=builder.generator_tuning,
        target_override=builder.target_override,
        targets_in_use=builder.targets_in_use,
        mapping_form=builder.mapping_form,
        comma_basis_form=builder.comma_basis_form,
        preview_remove=builder.preview_remove,
        prev_ids=builder.prev_ids,
    )

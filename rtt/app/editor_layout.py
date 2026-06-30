from __future__ import annotations

from rtt.app import spreadsheet
from rtt.app.editor_document import Document
from rtt.app.layout import Layout


def build(document: Document, prev_ids=None, preview_remove=None) -> Layout:
    pending = document.pending
    return spreadsheet.build(
        document.state,
        document.settings,
        document.collapsed,
        tuning_scheme=document.tuning_scheme,
        target_spec=document.target_spec,
        interest=document.interest_vectors,
        range_mode=document.range_mode,
        pending_comma=pending.pending_comma,
        held_vectors=document.held_vectors,
        generator_tuning=document.effective_generator_tuning(),
        target_override=document.target_override,
        custom_prescaler=document.custom_prescaler,
        custom_weights=document.custom_weights,
        tuning_optimized=document.tuning_is_optimized,
        pending_interest=pending.pending_interest,
        pending_held=pending.pending_held,
        pending_target=pending.pending_target,
        pending_element=pending.pending_element,
        pending_mapping_row=pending.pending_mapping_row,
        nonprime_approach=document.nonprime_basis_approach,
        superspace_generator_tuning=pending.superspace_generator_tuning,
        displayed_tuning_name=document.displayed_tuning_scheme_name,
        held_basis_ratios=document.unchanged_ratios,
        displayed_projection_name=document.displayed_projection_scheme_name,
        targets_in_use=document.targets_in_use,
        mapping_form=document.preferred_form.get("mapping"),
        comma_basis_form=document.preferred_form.get("comma_basis"),
        prev_ids=prev_ids,
        preview_remove=preview_remove,
    )

from __future__ import annotations

from rtt.app import spreadsheet
from rtt.app.editor_document import Document
from rtt.app.layout import Layout


def build(doc: Document, prev_ids=None, preview_remove=None) -> Layout:
    pending = doc.pending
    return spreadsheet.build(
        doc.state,
        doc.settings,
        doc.collapsed,
        tuning_scheme=doc.tuning_scheme,
        target_spec=doc.target_spec,
        interest=doc.interest_vectors,
        range_mode=doc.range_mode,
        pending_comma=pending.pending_comma,
        held_vectors=doc.held_vectors,
        generator_tuning=doc.effective_generator_tuning(),
        target_override=doc.target_override,
        custom_prescaler=doc.custom_prescaler,
        custom_weights=doc.custom_weights,
        tuning_optimized=doc.tuning_is_optimized,
        pending_interest=pending.pending_interest,
        pending_held=pending.pending_held,
        pending_target=pending.pending_target,
        pending_element=pending.pending_element,
        pending_mapping_row=pending.pending_mapping_row,
        nonprime_approach=doc.nonprime_basis_approach,
        superspace_generator_tuning=pending.superspace_generator_tuning,
        displayed_tuning_name=doc.displayed_tuning_scheme_name,
        held_basis_ratios=doc.unchanged_ratios,
        displayed_projection_name=doc.displayed_projection_scheme_name,
        targets_in_use=doc.targets_in_use,
        mapping_form=doc.preferred_form.get("mapping"),
        comma_basis_form=doc.preferred_form.get("comma_basis"),
        prev_ids=prev_ids,
        preview_remove=preview_remove,
    )

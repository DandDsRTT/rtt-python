from __future__ import annotations

from dataclasses import replace
from typing import NamedTuple

from rtt.app import service
from rtt.app.spreadsheet_text import _min_width_for_lines, assign_column_tokens


def resolve_interval_sets(inputs, draft):
    draft = replace(draft, generators=service.generators(inputs.state.mapping, draft.elements))
    draft = resolve_targets(inputs, draft)
    draft = resolve_canonical_form(inputs, draft)
    draft = resolve_held(inputs, draft)
    draft = resolve_tuning(inputs, draft)
    draft = resolve_commas(inputs, draft)
    draft = resolve_unchanged(inputs, draft)
    draft = resolve_interest(inputs, draft)
    return resolve_col_ids(inputs, draft)


def resolve_targets(inputs, draft):
    targets = service.displayed_targets(inputs.state, inputs.tuning_scheme, inputs.target_spec, inputs.target_override)
    all_interval = service.is_all_interval(inputs.tuning_scheme)
    targets_editable = not all_interval
    target_count = len(targets)
    pending_target = list(inputs.pending_target) if (inputs.pending_target is not None and targets_editable) else None
    return replace(
        draft, targets=targets, all_interval=all_interval, targets_editable=targets_editable, target_count=target_count,
        pending_target=pending_target, target_count_shown=target_count + (1 if pending_target is not None else 0),
        mapped=service.mapped_intervals(inputs.state.mapping, targets, draft.elements))


def resolve_canonical_form(inputs, draft):
    canonical_mapping = service.canonical_mapping(inputs.state.mapping)
    mapping_form_key = service.resolve_mapping_form(
        inputs.state.mapping, inputs.mapping_form, inputs.state.domain_basis)
    form_is_canonical = mapping_form_key == "canonical"
    return replace(
        draft, canonical_mapping=canonical_mapping, canonical_rank=len(canonical_mapping),
        inverse_form_M=service.inverse_form_matrix(inputs.state.mapping),
        canonical_generators=service.generators(canonical_mapping, draft.elements),
        form_M=service.form_matrix(inputs.state.mapping),
        mapping_form_key=mapping_form_key,
        comma_basis_form_key=(service.resolve_comma_basis_form(
            inputs.state.comma_basis, inputs.comma_basis_form, inputs.state.domain_basis) if inputs.state.nullity else ""),
        form_is_canonical=form_is_canonical,
        show_form_subscript=draft.show_form and form_is_canonical,
        show_canonical=draft.show_form_tiles and not form_is_canonical)


def resolve_held(inputs, draft):
    held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.dimensionality)) for m in inputs.held_vectors) if draft.show_optimization else ()
    held_count = len(held)
    pending_held = list(inputs.pending_held) if (inputs.pending_held is not None and draft.show_optimization) else None
    return replace(
        draft, target_vectors=service.target_interval_vectors(draft.targets, draft.dimensionality, draft.elements),
        held=held, held_count=held_count, pending_held=pending_held, held_count_shown=held_count + (1 if pending_held is not None else 0),
        held_ratios=service.comma_ratios(held, draft.elements))


def resolve_tuning(inputs, draft):
    if inputs.generator_tuning is not None and len(inputs.generator_tuning) == len(inputs.state.mapping):
        tuning_map = service.tuning_from_generators(inputs.state.mapping, inputs.generator_tuning, draft.elements)
        from_generators = True
    else:
        tuning_map = service.tuning(inputs.state.mapping, inputs.tuning_scheme, draft.elements, inputs.nonprime_approach, held=draft.held_ratios,
                             prescaler_override=inputs.custom_prescaler,
                             targets=draft.targets if inputs.target_override is not None else None,
                             weights_override=inputs.custom_weights)
        from_generators = False
    target_weights = service.interval_weights(inputs.state.mapping, inputs.tuning_scheme, draft.targets,
                                              prescaler_override=inputs.custom_prescaler,
                                              domain_basis=draft.elements, weights_override=inputs.custom_weights)
    return replace(
        draft, tuning_map=tuning_map, _tuning_map_from_generators=from_generators, _optimum_target_override=inputs.target_override,
        target_weights=target_weights,
        target_sizes=service.interval_sizes(tuning_map, draft.targets, draft.elements, weights=target_weights),
        held_mapped=service.mapped_intervals(inputs.state.mapping, draft.held_ratios, draft.elements),
        held_sizes=service.interval_sizes(tuning_map, draft.held_ratios, draft.elements))


def resolve_commas(inputs, draft):
    comma_ratios = service.comma_ratios(inputs.state.comma_basis, draft.elements) if inputs.state.nullity else ()
    return replace(
        draft, comma_ratios=comma_ratios, comma_count=len(comma_ratios),
        mapped_commas=service.mapped_commas(inputs.state.mapping, inputs.state.comma_basis),
        comma_sizes=service.interval_sizes(draft.tuning_map, comma_ratios, draft.elements))


def resolve_unchanged(inputs, draft):
    _udata = (service.unchanged_interval_data(inputs.state, inputs.held_basis_ratios, draft.tuning_map,
                                              inputs.tuning_scheme, draft.elements, inputs.custom_prescaler)
              if (draft.show_temperament_tiles and draft.show_tuning_tiles and inputs.settings["projection"]) else None)
    unchanged = _initial_unchanged(_udata)
    unchanged_count = len(_udata.basis) if _udata is not None else 0
    born_u = draft.ghost_unchanged and _udata is not None
    if born_u:
        unchanged, unchanged_count = _extend_unchanged_with_slot(unchanged, unchanged_count)
    pending = list(inputs.pending_comma) if inputs.pending_comma is not None else None
    comma_draft = pending is not None or draft.ghost_comma
    comma_count_shown = draft.comma_count + (1 if comma_draft else 0)
    if _udata is not None:
        _rename_commas_to_unrotated(draft.effective_names)
        if draft.show_equivalences:
            _append_unchanged_name_equivalence(draft.effective_names)
    return replace(
        draft, show_unchanged=_udata is not None, unchanged_count=unchanged_count, born_u=born_u,
        unchanged_basis=unchanged.basis, unchanged_ratios=unchanged.ratios,
        unchanged_mapped=unchanged.mapped, unchanged_sizes=unchanged.sizes,
        unchanged_complexities=unchanged.complexities, pending=pending, comma_draft=comma_draft,
        comma_count_shown=comma_count_shown, vector_count_shown=comma_count_shown + unchanged_count,
        empty_comma_width=(_min_width_for_lines("nullity", 1) if (_udata is not None and comma_count_shown == 0) else 0))


def _extend_unchanged_with_slot(unchanged, unchanged_count):
    s = unchanged.sizes
    grown = _Unchanged(
        basis=(*tuple(unchanged.basis), None),
        ratios=(*tuple(unchanged.ratios), None),
        mapped=tuple((*tuple(row), None) for row in unchanged.mapped),
        sizes=service.IntervalSizes(
            (*tuple(s.tempered), None), (*tuple(s.just), None),
            (*tuple(s.errors), None), (*tuple(s.damage), None)),
        complexities=(*tuple(unchanged.complexities), None))
    return grown, unchanged_count + 1


def resolve_interest(inputs, draft):
    interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.dimensionality)) for m in inputs.interest)
    interest_count = len(interest)
    pending_interest = list(inputs.pending_interest) if inputs.pending_interest is not None else None
    element_draft = draft.show_nonstandard_domain and inputs.pending_element is not None
    interest_ratios = service.comma_ratios(interest, draft.elements)
    return replace(
        draft, interest=interest, interest_count=interest_count, pending_interest=pending_interest,
        interest_count_shown=interest_count + (1 if pending_interest is not None else 0), element_draft=element_draft,
        dimensionality_shown=draft.dimensionality + (1 if element_draft else 0), interest_ratios=interest_ratios,
        interest_mapped=service.mapped_intervals(inputs.state.mapping, interest_ratios, draft.elements),
        interest_sizes=service.interval_sizes(draft.tuning_map, interest_ratios, draft.elements))


def resolve_col_ids(inputs, draft):
    column_ids = {
        name: assign_column_tokens(inputs.previous_ids.get(name), keys, claim_unmatched=claim)
        for name, keys, claim in (("targets", draft.targets, False),
                                  ("held", draft.held_ratios, False),
                                  ("interest", draft.interest_ratios, False),
                                  ("commas", draft.comma_ratios, True),
                                  ("generators", tuple(tuple(row) for row in inputs.state.mapping), True))
    }
    column_ids["detempering"] = column_ids["generators"]
    return replace(draft, _col_ids=column_ids)


class _Unchanged(NamedTuple):
    basis: object
    ratios: object
    mapped: object
    sizes: object
    complexities: object


def _initial_unchanged(udata):
    if udata is not None:
        return _Unchanged(udata.basis, udata.ratios, udata.mapped, udata.sizes, udata.complexities)
    return _Unchanged(None, (), (), service.IntervalSizes((), (), (), ()), ())


def _rename_commas_to_unrotated(effective_names):
    for (rk, ck), name in list(effective_names.items()):
        if ck != "commas":
            continue
        renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
        if renamed.count("list") > 1:
            renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
        effective_names[(rk, ck)] = renamed


def _append_unchanged_name_equivalence(effective_names):
    key = ("vectors", "commas")
    if key in effective_names:
        effective_names[key] += " = comma basis | unchanged interval basis"

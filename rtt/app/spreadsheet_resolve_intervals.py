from __future__ import annotations

from dataclasses import replace
from typing import NamedTuple

from rtt.app import service
from rtt.app.spreadsheet_text import _min_width_for_lines, assign_column_tokens


def resolve_interval_sets(inputs, draft):
    draft = resolve_ghost_previews(inputs, draft)
    draft = resolve_targets(inputs, draft)
    draft = resolve_canon_form(inputs, draft)
    draft = resolve_held(inputs, draft)
    draft = resolve_tuning(inputs, draft)
    draft = resolve_commas(inputs, draft)
    draft = resolve_unchanged(inputs, draft)
    draft = resolve_interest(inputs, draft)
    draft = resolve_ghost_mapped(inputs, draft)
    return resolve_col_ids(inputs, draft)


def resolve_ghost_previews(inputs, draft):
    elements = draft.elements
    ghost_new = ghost_row_map = ghost_row_ratio = None
    ghost_comma_vec = ghost_comma_ratio = None
    if draft.ghost_row:
        ghost_new = service.remove_comma(inputs.state, inputs.preview_remove[1])
        ghost_row_map = ghost_new.mapping[-1]
        born_gens = service.generators(ghost_new.mapping, elements)
        ghost_row_ratio = born_gens[-1] if born_gens else ""
    elif draft.ghost_comma:
        ghost_new = service.remove_mapping_row(inputs.state, inputs.preview_remove[1])
        ghost_comma_vec = ghost_new.comma_basis[-1] if ghost_new.comma_basis else None
        born_crs = service.comma_ratios(ghost_new.comma_basis, elements) if ghost_new.comma_basis else ()
        ghost_comma_ratio = born_crs[-1] if born_crs else ""
    return replace(
        draft, gens=service.generators(inputs.state.mapping, elements), ghost_new=ghost_new,
        ghost_row_map=ghost_row_map, ghost_row_ratio=ghost_row_ratio, ghost_row_mapped={},
        ghost_comma_vec=ghost_comma_vec, ghost_comma_ratio=ghost_comma_ratio,
        ghost_comma_mapped=(), ghost_comma_just=0.0, ghost_comma_complexity=0.0)


def resolve_targets(inputs, draft):
    targets = service.displayed_targets(inputs.state, inputs.tuning_scheme, inputs.target_spec, inputs.target_override)
    all_interval = service.is_all_interval(inputs.tuning_scheme)
    targets_editable = not all_interval
    k = len(targets)
    pending_target = list(inputs.pending_target) if (inputs.pending_target is not None and targets_editable) else None
    return replace(
        draft, targets=targets, all_interval=all_interval, targets_editable=targets_editable, k=k,
        pending_target=pending_target, k_shown=k + (1 if pending_target is not None else 0),
        mapped=service.mapped_intervals(inputs.state.mapping, targets, draft.elements))


def resolve_canon_form(inputs, draft):
    canon_mapping = service.canonical_mapping(inputs.state.mapping)
    mapping_form_key = service.resolve_mapping_form(
        inputs.state.mapping, inputs.mapping_form, inputs.state.domain_basis)
    form_is_canonical = mapping_form_key == "canonical"
    return replace(
        draft, canon_mapping=canon_mapping, rc=len(canon_mapping),
        form_M=service.form_matrix(inputs.state.mapping),
        canon_gens=service.generators(canon_mapping, draft.elements),
        inverse_form_M=service.inverse_form_matrix(inputs.state.mapping),
        mapping_form_key=mapping_form_key,
        comma_basis_form_key=(service.resolve_comma_basis_form(
            inputs.state.comma_basis, inputs.comma_basis_form, inputs.state.domain_basis) if inputs.state.n else ""),
        form_is_canonical=form_is_canonical,
        show_form_subscript=draft.show_form and form_is_canonical,
        show_canon=draft.show_form_tiles and not form_is_canonical)


def resolve_held(inputs, draft):
    held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in inputs.held_vectors) if draft.show_optimization else ()
    nh = len(held)
    pending_held = list(inputs.pending_held) if (inputs.pending_held is not None and draft.show_optimization) else None
    return replace(
        draft, target_vectors=service.target_interval_vectors(draft.targets, draft.d, draft.elements),
        held=held, nh=nh, pending_held=pending_held, nh_shown=nh + (1 if pending_held is not None else 0),
        held_ratios=service.comma_ratios(held, draft.elements))


def resolve_tuning(inputs, draft):
    if inputs.generator_tuning is not None and len(inputs.generator_tuning) == len(inputs.state.mapping):
        tun = service.tuning_from_generators(inputs.state.mapping, inputs.generator_tuning, draft.elements)
        from_generators = True
    else:
        tun = service.tuning(inputs.state.mapping, inputs.tuning_scheme, draft.elements, inputs.nonprime_approach, held=draft.held_ratios,
                             prescaler_override=inputs.custom_prescaler, targets=inputs.target_override,
                             weights_override=inputs.custom_weights)
        from_generators = False
    target_weights = service.interval_weights(inputs.state.mapping, inputs.tuning_scheme, draft.targets,
                                              prescaler_override=inputs.custom_prescaler,
                                              domain_basis=draft.elements, weights_override=inputs.custom_weights)
    return replace(
        draft, tun=tun, _tun_from_generators=from_generators, _optimum_target_override=inputs.target_override,
        target_weights=target_weights,
        target_sizes=service.interval_sizes(tun, draft.targets, draft.elements, weights=target_weights),
        held_mapped=service.mapped_intervals(inputs.state.mapping, draft.held_ratios, draft.elements),
        held_sizes=service.interval_sizes(tun, draft.held_ratios, draft.elements))


def resolve_commas(inputs, draft):
    comma_ratios = service.comma_ratios(inputs.state.comma_basis, draft.elements) if inputs.state.n else ()
    return replace(
        draft, comma_ratios=comma_ratios, nc=len(comma_ratios),
        mapped_commas=service.mapped_commas(inputs.state.mapping, inputs.state.comma_basis),
        comma_sizes=service.interval_sizes(draft.tun, comma_ratios, draft.elements))


def resolve_unchanged(inputs, draft):
    _udata = (service.unchanged_interval_data(inputs.state, inputs.held_basis_ratios, draft.tun,
                                              inputs.tuning_scheme, draft.elements, inputs.custom_prescaler)
              if (draft.show_temperament_tiles and draft.show_tuning_tiles and inputs.settings["projection"]) else None)
    unchanged = _initial_unchanged(_udata)
    nu = len(_udata.basis) if _udata is not None else 0
    born_u = draft.ghost_row and _udata is not None
    if born_u:
        unchanged, nu, born_u = augment_born_unchanged(inputs, draft, unchanged, nu)
    pending = list(inputs.pending_comma) if inputs.pending_comma is not None else None
    comma_draft = pending is not None or draft.ghost_comma
    nc_shown = draft.nc + (1 if comma_draft else 0)
    if _udata is not None:
        _rename_commas_to_unrotated(draft.effective_captions)
        if draft.show_equivalences:
            _append_unchanged_caption_equivalence(draft.effective_captions)
    return replace(
        draft, show_unchanged=_udata is not None, nu=nu, born_u=born_u,
        unchanged_basis=unchanged.basis, unchanged_ratios=unchanged.ratios,
        unchanged_mapped=unchanged.mapped, unchanged_sizes=unchanged.sizes,
        unchanged_complexities=unchanged.complexities, pending=pending, comma_draft=comma_draft,
        nc_shown=nc_shown, nv_shown=nc_shown + nu,
        empty_comma_w=(_min_width_for_lines("nullity", 1) if (_udata is not None and nc_shown == 0) else 0))


def augment_born_unchanged(inputs, draft, unchanged, nu):
    tun_new = service.tuning(draft.ghost_new.mapping, inputs.tuning_scheme, draft.elements,
                             inputs.nonprime_approach, held=inputs.held_basis_ratios,
                             prescaler_override=inputs.custom_prescaler)
    ud_new = service.unchanged_interval_data(draft.ghost_new, inputs.held_basis_ratios, tun_new,
                                             inputs.tuning_scheme, draft.elements, inputs.custom_prescaler)
    if ud_new is None or len(ud_new.basis) <= nu:
        return unchanged, nu, False
    bratio = ud_new.ratios[-1]
    bm = service.mapped_intervals(inputs.state.mapping, (bratio,), draft.elements) if bratio is not None else None
    s, n = unchanged.sizes, ud_new.sizes
    grown = _Unchanged(
        basis=(*tuple(unchanged.basis), ud_new.basis[-1]),
        ratios=(*tuple(unchanged.ratios), bratio),
        mapped=tuple((*tuple(row), bm[i][0] if bm is not None else None) for i, row in enumerate(unchanged.mapped)),
        sizes=service.IntervalSizes(
            (*tuple(s.tempered), n.tempered[-1]), (*tuple(s.just), n.just[-1]),
            (*tuple(s.errors), n.errors[-1]), (*tuple(s.damage), n.damage[-1])),
        complexities=(*tuple(unchanged.complexities), ud_new.complexities[-1]))
    return grown, nu + 1, True


def resolve_interest(inputs, draft):
    interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in inputs.interest)
    mi = len(interest)
    pending_interest = list(inputs.pending_interest) if inputs.pending_interest is not None else None
    element_draft = draft.show_nonstandard_domain and inputs.pending_element is not None
    interest_ratios = service.comma_ratios(interest, draft.elements)
    return replace(
        draft, interest=interest, mi=mi, pending_interest=pending_interest,
        mi_shown=mi + (1 if pending_interest is not None else 0), element_draft=element_draft,
        d_shown=draft.d + (1 if element_draft else 0), interest_ratios=interest_ratios,
        interest_mapped=service.mapped_intervals(inputs.state.mapping, interest_ratios, draft.elements),
        interest_sizes=service.interval_sizes(draft.tun, interest_ratios, draft.elements))


def resolve_ghost_mapped(inputs, draft):
    if draft.ghost_row and draft.ghost_new is not None:
        nm = draft.ghost_new.mapping

        def _newborn_mapped(ratios):
            return tuple(service.mapped_intervals(nm, (r,), draft.elements)[-1][0] if r is not None else None
                         for r in ratios)
        return replace(draft, ghost_row_mapped={
            key: _newborn_mapped(ratios)
            for key, ratios in (("targets", draft.targets), ("interest", draft.interest_ratios),
                                ("held", draft.held_ratios), ("commas", draft.comma_ratios),
                                ("unchanged", draft.unchanged_ratios))})
    if draft.ghost_comma and draft.ghost_comma_ratio:
        col = service.mapped_intervals(inputs.state.mapping, (draft.ghost_comma_ratio,), draft.elements)
        return replace(
            draft, ghost_comma_mapped=tuple(row[0] for row in col),
            ghost_comma_just=service.interval_sizes(draft.tun, (draft.ghost_comma_ratio,), draft.elements).just[0],
            ghost_comma_complexity=service.interval_complexities(
                inputs.state.mapping, inputs.tuning_scheme, (draft.ghost_comma_ratio,),
                prescaler_override=inputs.custom_prescaler, domain_basis=draft.elements)[0])
    return draft


def resolve_col_ids(inputs, draft):
    col_ids = {
        name: assign_column_tokens(inputs.prev_ids.get(name), keys, claim_unmatched=claim)
        for name, keys, claim in (("targets", draft.targets, False),
                                  ("held", draft.held_ratios, False),
                                  ("interest", draft.interest_ratios, False),
                                  ("commas", draft.comma_ratios, True),
                                  ("gens", tuple(tuple(row) for row in inputs.state.mapping), True))
    }
    col_ids["detempering"] = col_ids["gens"]
    return replace(draft, _col_ids=col_ids)


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


def _rename_commas_to_unrotated(effective_captions):
    for (rk, ck), name in list(effective_captions.items()):
        if ck != "commas":
            continue
        renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
        if renamed.count("list") > 1:
            renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
        effective_captions[(rk, ck)] = renamed


def _append_unchanged_caption_equivalence(effective_captions):
    key = ("vectors", "commas")
    if key in effective_captions:
        effective_captions[key] += " = comma basis | unchanged interval basis"

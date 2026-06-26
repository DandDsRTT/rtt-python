from __future__ import annotations

from dataclasses import replace

from rtt.app import service
from rtt.app.spreadsheet_constants import SYMBOL_H
from rtt.app.spreadsheet_models import _resolve_prescaler_labels, _resolve_show_flags


def unpack_show_flags(inputs, draft):
    _f = _resolve_show_flags(inputs.settings, inputs.collapsed)
    show_symbols, show_weighting, show_math = _f.symbols, _f.weighting, _f.math
    complexity_shown = (show_weighting
                        and service.damage_weight_slope(inputs.tuning_scheme) != "unityWeight")
    prescaling_shown = complexity_shown and (
        service.is_all_interval(inputs.tuning_scheme) or _f.alt_complexity)
    weight_unit = f"({service.weight_annotation(inputs.tuning_scheme)})"
    return replace(
        draft, show_captions=_f.captions, show_mnemonics=_f.mnemonics, show_equiv=_f.equiv,
        show_presets=_f.presets, show_counts=_f.counts, show_ptext=_f.ptext, show_charts=_f.charts,
        show_ranges=_f.ranges, show_symbols=show_symbols, ctrl_symbol_h=SYMBOL_H if show_symbols else 0,
        show_header_symbols=_f.header_symbols, show_units=_f.units, show_cell_units=_f.cell_units,
        show_domain_units=_f.domain_units, show_temp=_f.temp, show_form=_f.form,
        show_form_controls=_f.form_controls, show_form_tiles=_f.form_tiles, show_tuning=_f.tuning,
        show_optimization=_f.optimization, show_weighting=show_weighting,
        show_alt_complexity=_f.alt_complexity, _complexity_shown=complexity_shown,
        _prescaling_shown=prescaling_shown, weight_unit=weight_unit,
        complexity_unit=f"({service.complexity_annotation(inputs.tuning_scheme)})",
        damage_unit=f"¢{weight_unit}", _lbox_show=_f.lbox and complexity_shown,
        _cbox_show=_f.cbox and complexity_shown, show_detempering=_f.detempering,
        show_interest=_f.interest, gridded=_f.gridded, show_quantities=_f.quantities,
        _decimals=_f.decimals, show_ebk=_f.ebk, show_interval_ratios=_f.interval_ratios,
        show_interval_vectors=_f.interval_vectors, show_math=show_math,
        custom_weights_active=(inputs.custom_weights is not None
                               and not service.is_all_interval(inputs.tuning_scheme)
                               and not show_math))


def resolve_superspace_dims(inputs, draft):
    elements = inputs.state.domain_basis
    r = len(inputs.state.mapping)
    row_draft = inputs.pending_mapping_row is not None or draft.ghost_row
    show_nonstandard_domain = inputs.settings.get("nonstandard_domain", False)
    show_superspace = (show_nonstandard_domain
                       and service.domain_has_nonprimes(elements)
                       and inputs.nonprime_approach != "nonprime-based")
    return replace(
        draft, d=inputs.state.d, r=r, row_draft=row_draft, r_shown=r + (1 if row_draft else 0),
        elements=elements, dL=service.superspace_dimension(elements),
        rL=service.superspace_rank(inputs.state), superspace_primes=service.superspace_primes(elements),
        show_nonstandard_domain=show_nonstandard_domain, show_superspace=show_superspace,
        show_superspace_generators=show_superspace and inputs.nonprime_approach == "prime-based")


def resolve_prescaler_and_domain_labels(inputs, draft):
    _p = _resolve_prescaler_labels(inputs.state, inputs.tuning_scheme, inputs.custom_prescaler,
                                   draft.show_equiv, draft.show_superspace)
    return replace(
        draft, _scheme_prescaler=_p.scheme_prescaler, _realized_prescaler=_p.realized,
        prescaler_symbol=_p.symbol, prescaler_equivalence=_p.equivalence,
        prescaling_symbols=_p.prescaling_symbols, col_labels=_p.col_labels, row_labels=_p.row_labels,
        effective_captions=_p.effective_captions,
        show_identity_objects=inputs.settings.get("identity_objects", False),
        standard_domain=service.is_standard_domain(draft.elements),
        domain_label="b" if service.domain_has_nonprimes(draft.elements) else "p",
        domain_can_shrink=service.can_shrink_domain(inputs.state))

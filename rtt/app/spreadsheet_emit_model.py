from __future__ import annotations

from dataclasses import dataclass, replace

from rtt.app.spreadsheet_constants import DASH
from rtt.app.spreadsheet_text import pending_token


def pending_col_token(resolved, group: str):
    return pending_token([token for token, _ in resolved.column_ids[group]])


def voice(cells, tile, index, cents) -> None:
    if cents is None:
        return
    cells[-1] = replace(cells[-1], audio=(tile, int(index), float(cents)))


def element_cell_kind(text: str) -> str:
    return "element_ratio" if "/" in text else "element_cell"


def _element_draft_kind(resolved, pending_element) -> str:
    if not resolved.flags.nonstandard_domain:
        return "prime"
    return element_cell_kind(pending_element) if pending_element else "element_ratio"


def dash_or_str(v) -> str:
    return DASH if v is None else str(v)


@dataclass(frozen=True)
class EmitResult:
    cells: tuple = ()
    lines: tuple = ()
    blocks: tuple = ()
    region_panels: tuple = ()
    extra: object = None


@dataclass(frozen=True)
class BuildContext:
    state: object
    settings: object
    collapsed: object
    row_order: tuple
    column_order: tuple
    tuning_scheme: object
    target_spec: object
    range_mode: str
    nonprime_approach: str
    pending_element: object
    pending_mapping_row: object
    tuning_optimized: bool
    targets_in_use: bool
    custom_prescaler: object
    custom_weights: object
    held_basis_ratios: object
    superspace_generator_tuning: object
    generator_tuning: object
    target_override: object


def build_context(builder) -> BuildContext:
    inp = builder.inputs
    return BuildContext(
        state=inp.state,
        settings=inp.settings,
        collapsed=inp.collapsed,
        row_order=inp.row_order,
        column_order=inp.column_order,
        tuning_scheme=inp.tuning_scheme,
        target_spec=inp.target_spec,
        range_mode=inp.range_mode,
        nonprime_approach=inp.nonprime_approach,
        pending_element=inp.pending_element,
        pending_mapping_row=inp.pending_mapping_row,
        tuning_optimized=inp.tuning_optimized,
        targets_in_use=inp.targets_in_use,
        custom_prescaler=inp.custom_prescaler,
        custom_weights=inp.custom_weights,
        held_basis_ratios=inp.held_basis_ratios,
        superspace_generator_tuning=inp.superspace_generator_tuning,
        generator_tuning=inp.generator_tuning,
        target_override=inp.target_override,
    )


def draft_open(resolved) -> bool:
    return bool(
        (resolved.scalars.comma_draft and not resolved.ghosts.comma)
        or (resolved.scalars.row_draft and not resolved.ghosts.row)
        or (resolved.scalars.element_draft and not resolved.ghosts.element)
        or resolved.targets.pending is not None
        or resolved.held.pending is not None
        or resolved.interest.pending is not None
    )

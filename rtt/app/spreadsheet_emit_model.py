from __future__ import annotations

from dataclasses import dataclass, replace


def voice(cells, tile, idx, cents) -> None:
    if cents is None:
        return
    cells[-1] = replace(cells[-1], audio=(tile, int(idx), float(cents)))


def element_cell_kind(text: str) -> str:
    return "elementratio" if "/" in text else "elementcell"


@dataclass(frozen=True)
class EmitResult:
    cells: tuple = ()
    lines: tuple = ()
    blocks: tuple = ()
    region_boxes: tuple = ()
    extra: object = None


@dataclass(frozen=True)
class BuildContext:
    state: object
    settings: object
    collapsed: object
    tuning_scheme: object
    target_spec: object
    range_mode: str
    nonprime_approach: str
    pending_element: object
    pending_mapping_row: object
    preview_remove: object
    tuning_optimized: bool
    targets_in_use: bool
    custom_prescaler: object
    custom_weights: object
    held_basis_ratios: object
    superspace_generator_tuning: object
    generator_tuning: object
    target_override: object


def build_context(builder) -> BuildContext:
    return BuildContext(
        state=builder.state,
        settings=builder.settings,
        collapsed=builder.collapsed,
        tuning_scheme=builder.tuning_scheme,
        target_spec=builder.target_spec,
        range_mode=builder.range_mode,
        nonprime_approach=builder.nonprime_approach,
        pending_element=builder.pending_element,
        pending_mapping_row=builder.pending_mapping_row,
        preview_remove=builder.preview_remove,
        tuning_optimized=builder.tuning_optimized,
        targets_in_use=builder.targets_in_use,
        custom_prescaler=builder.custom_prescaler,
        custom_weights=builder.custom_weights,
        held_basis_ratios=builder.held_basis_ratios,
        superspace_generator_tuning=builder.superspace_generator_tuning,
        generator_tuning=builder.generator_tuning,
        target_override=builder.target_override,
    )

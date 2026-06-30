from __future__ import annotations

from dataclasses import dataclass, replace


def voice(cells, tile, index, cents) -> None:
    if cents is None:
        return
    cells[-1] = replace(cells[-1], audio=(tile, int(index), float(cents)))


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
    inp = builder.inputs
    return BuildContext(
        state=inp.state,
        settings=inp.settings,
        collapsed=inp.collapsed,
        tuning_scheme=inp.tuning_scheme,
        target_spec=inp.target_spec,
        range_mode=inp.range_mode,
        nonprime_approach=inp.nonprime_approach,
        pending_element=inp.pending_element,
        pending_mapping_row=inp.pending_mapping_row,
        preview_remove=inp.preview_remove,
        tuning_optimized=inp.tuning_optimized,
        targets_in_use=inp.targets_in_use,
        custom_prescaler=inp.custom_prescaler,
        custom_weights=inp.custom_weights,
        held_basis_ratios=inp.held_basis_ratios,
        superspace_generator_tuning=inp.superspace_generator_tuning,
        generator_tuning=inp.generator_tuning,
        target_override=inp.target_override,
    )

from __future__ import annotations

from rtt.app import editor_layout
from rtt.app.editor_document import INITIAL_MAPPING, Document
from rtt.app.editor_intervals import IntervalOps
from rtt.app.editor_session import SessionOps
from rtt.app.editor_settings_ops import ShowSettingsOps
from rtt.app.editor_structure import StructureOps
from rtt.app.editor_tuning import TuningOps
from rtt.app.editor_view import TuningView

__all__ = ["INITIAL_MAPPING", "Editor"]


class Editor:
    def __init__(self) -> None:
        self._doc = Document()
        self._view = TuningView(self._doc)
        self._structure = StructureOps(self._doc)
        self._tuning = TuningOps(self._doc, self._view, self._structure)
        self._intervals = IntervalOps(self._doc, self._view)
        self._show = ShowSettingsOps(self._doc, self._structure)
        self._session = SessionOps(self._doc)

    @property
    def state(self):
        return self._doc.state

    @state.setter
    def state(self, new_state) -> None:
        self._doc.state = new_state

    @property
    def tuning_scheme(self):
        return self._doc.tuning_scheme

    @property
    def settings(self) -> dict[str, bool]:
        return self._doc.settings

    @property
    def collapsed(self) -> set[str]:
        return self._doc.collapsed

    @property
    def target_family(self) -> str:
        return self._doc.target_family

    @property
    def target_limit(self) -> int | None:
        return self._doc.target_limit

    @property
    def target_override(self) -> tuple[str, ...] | None:
        return self._doc.target_override

    @property
    def range_mode(self) -> str:
        return self._doc.range_mode

    @property
    def generator_tuning(self) -> tuple[float, ...] | None:
        return self._doc.generator_tuning

    @property
    def manual_tuning(self) -> bool:
        return self._doc.manual_tuning

    @property
    def custom_prescaler(self):
        return self._doc.custom_prescaler

    @property
    def custom_weights(self) -> tuple[float, ...] | None:
        return self._doc.custom_weights

    @property
    def projection_basis(self) -> tuple[str, ...]:
        return self._doc.projection_basis

    @property
    def held_vectors(self) -> list[tuple[int, ...]]:
        return self._doc.held_vectors

    @property
    def interest_vectors(self) -> list[tuple[int, ...]]:
        return self._doc.interest_vectors

    @interest_vectors.setter
    def interest_vectors(self, vectors) -> None:
        self._doc.interest_vectors = vectors

    @property
    def nonprime_basis_approach(self) -> str:
        return self._doc.nonprime_basis_approach

    @nonprime_basis_approach.setter
    def nonprime_basis_approach(self, approach: str) -> None:
        self._doc.nonprime_basis_approach = approach

    @property
    def target_spec(self) -> str:
        return self._doc.target_spec

    @property
    def superspace_generator_tuning(self) -> tuple[float, ...] | None:
        return self._doc.pending.superspace_generator_tuning

    @property
    def pending_comma(self) -> list[int | None] | None:
        return self._doc.pending.pending_comma

    @pending_comma.setter
    def pending_comma(self, value) -> None:
        self._doc.pending.pending_comma = value

    @property
    def pending_interest(self) -> list[int | None] | None:
        return self._doc.pending.pending_interest

    @property
    def pending_held(self) -> list[int | None] | None:
        return self._doc.pending.pending_held

    @property
    def pending_target(self) -> list[int | None] | None:
        return self._doc.pending.pending_target

    @property
    def pending_element(self) -> str | None:
        return self._doc.pending.pending_element

    @property
    def pending_mapping_row(self) -> list[int | None] | None:
        return self._doc.pending.pending_mapping_row

    @pending_mapping_row.setter
    def pending_mapping_row(self, value) -> None:
        self._doc.pending.pending_mapping_row = value

    @property
    def _undo_stack(self):
        return self._doc.history.undo_stack

    @property
    def can_undo(self) -> bool:
        return self._doc.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self._doc.history.can_redo

    @property
    def can_reset(self) -> bool:
        return self._doc.can_reset

    @property
    def can_expand(self) -> bool:
        return self._structure.can_expand

    @property
    def basis_is_nonstandard(self) -> bool:
        return self._structure.basis_is_nonstandard

    @property
    def can_shrink(self) -> bool:
        return self._structure.can_shrink

    @property
    def can_remove_domain_element(self) -> bool:
        return self._structure.can_remove_domain_element

    @property
    def can_add_mapping_row(self) -> bool:
        return self._structure.can_add_mapping_row

    @property
    def can_remove_mapping_row(self) -> bool:
        return self._structure.can_remove_mapping_row

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        return self._view.displayed_tuning_scheme_name

    @property
    def tuning_is_optimized(self) -> bool:
        return self._view.tuning_is_optimized

    @property
    def displayed_prescaler_name(self) -> str | None:
        return self._view.displayed_prescaler_name

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        return self._view.unchanged_ratios

    @property
    def targets_in_use(self) -> bool:
        return self._view.targets_in_use

    @property
    def displayed_projection_scheme_name(self) -> str | None:
        return self._view.displayed_projection_scheme_name

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        return self._view.effective_generator_tuning()

    def optimum_generator_tuning(self) -> tuple[float, ...]:
        return self._view.optimum_generator_tuning()

    def optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        return self._view.optimum_superspace_generator_tuning()

    def displayed_retuning_map(self) -> tuple[float, ...] | None:
        return self._view.displayed_retuning_map()

    def current_targets(self) -> list[str]:
        return self._doc.current_targets()

    def list_vectors(self, name: str) -> list[tuple[int, ...]]:
        return self._intervals.list_vectors(name)

    def layout(self, prev_ids=None, preview_remove=None):
        return editor_layout.build(self._doc, self._view, prev_ids, preview_remove)

    def capture_for_preview(self) -> tuple:
        return self._session.capture_for_preview()

    def restore_for_preview(self, token: tuple) -> None:
        self._session.restore_for_preview(token)

    def undo(self) -> None:
        self._session.undo()

    def redo(self) -> None:
        self._session.redo()

    def reset(self) -> None:
        self._session.reset()

    def serialize(self) -> dict:
        return self._session.serialize()

    def load(self, data: dict) -> None:
        self._session.load(data)

    def set_show(self, key: str, value: bool) -> None:
        self._show.set_show(key, value)

    def set_all_show(self, value: bool, keys=None) -> None:
        self._show.set_all_show(value, keys)

    def disable_hidden_settings(self, chapter: int) -> None:
        self._show.disable_hidden_settings(chapter)

    def toggle_collapsed(self, item: str) -> None:
        self._show.toggle_collapsed(item)

    def set_collapsed(self, items) -> None:
        self._show.set_collapsed(items)

    def edit_mapping(self, mapping) -> None:
        self._structure.edit_mapping(mapping)

    def edit_comma_basis(self, comma_basis, domain_basis=None) -> None:
        self._structure.edit_comma_basis(comma_basis, domain_basis)

    def exit_nonstandard_domain(self) -> None:
        self._structure.exit_nonstandard_domain()

    def set_mapping_row(self, i: int, val) -> bool:
        return self._structure.set_mapping_row(i, val)

    def set_comma(self, c: int, vector) -> bool:
        return self._structure.set_comma(c, vector)

    def canonicalize_mapping(self) -> None:
        self._structure.canonicalize_mapping()

    def set_mapping_form(self, form: str) -> None:
        self._structure.set_mapping_form(form)

    def edit_form_matrix(self, form_rows) -> bool:
        return self._structure.edit_form_matrix(form_rows)

    def try_edit_form_matrix_text(self, text: str) -> bool:
        return self._structure.try_edit_form_matrix_text(text)

    def canonicalize_comma_basis(self) -> None:
        self._structure.canonicalize_comma_basis()

    def set_comma_basis_form(self, form: str) -> None:
        self._structure.set_comma_basis_form(form)

    def try_edit_mapping_text(self, text: str) -> bool:
        return self._structure.try_edit_mapping_text(text)

    def try_edit_comma_basis_text(self, text: str) -> bool:
        return self._structure.try_edit_comma_basis_text(text)

    def expand(self) -> None:
        self._structure.expand()

    def shrink(self) -> None:
        self._structure.shrink()

    def add_mapping_row(self) -> None:
        self._structure.add_mapping_row()

    def set_pending_mapping_row(self, values) -> None:
        self._structure.set_pending_mapping_row(values)

    def cancel_pending_mapping_row(self) -> None:
        self._structure.cancel_pending_mapping_row()

    def remove_mapping_row(self, i: int) -> None:
        self._structure.remove_mapping_row(i)

    def add_mapping_row_to(self, source: int, target: int) -> None:
        self._structure.add_mapping_row_to(source, target)

    def add_comma_to(self, source: int, target: int) -> None:
        self._structure.add_comma_to(source, target)

    def add_comma(self) -> None:
        self._structure.add_comma()

    def set_pending_comma(self, values) -> None:
        self._structure.set_pending_comma(values)

    def cancel_pending_comma(self) -> None:
        self._structure.cancel_pending_comma()

    def remove_comma(self, index: int = -1) -> None:
        self._structure.remove_comma(index)

    def add_element(self) -> None:
        self._structure.add_element()

    def set_pending_element(self, text) -> None:
        self._structure.set_pending_element(text)

    def remove_element(self) -> None:
        self._structure.remove_element()

    def remove_domain_element(self, index: int) -> None:
        self._structure.remove_domain_element(index)

    def set_domain_element(self, index: int, text) -> None:
        self._structure.set_domain_element(index, text)

    def add_interest(self) -> None:
        self._intervals.add_interest()

    def set_pending_interest(self, values) -> None:
        self._intervals.set_pending_interest(values)

    def cancel_pending_interest(self) -> None:
        self._intervals.cancel_pending_interest()

    def remove_interest(self, i: int) -> None:
        self._intervals.remove_interest(i)

    def set_interest_vectors(self, vectors) -> None:
        self._intervals.set_interest_vectors(vectors)

    def add_held(self) -> None:
        self._intervals.add_held()

    def set_pending_held(self, values) -> None:
        self._intervals.set_pending_held(values)

    def cancel_pending_held(self) -> None:
        self._intervals.cancel_pending_held()

    def remove_held(self, i: int) -> None:
        self._intervals.remove_held(i)

    def set_held_vectors(self, vectors) -> None:
        self._intervals.set_held_vectors(vectors)

    def set_target_spec(self, spec: str) -> None:
        self._intervals.set_target_spec(spec)

    def set_target_override_text(self, text: str) -> bool:
        return self._intervals.set_target_override_text(text)

    def set_target_override_vectors(self, vectors) -> None:
        self._intervals.set_target_override_vectors(vectors)

    def add_target(self) -> None:
        self._intervals.add_target()

    def set_pending_target(self, values) -> None:
        self._intervals.set_pending_target(values)

    def cancel_pending_target(self) -> None:
        self._intervals.cancel_pending_target()

    def remove_target(self, i: int) -> None:
        self._intervals.remove_target(i)

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        return self._intervals.move_interval(src_list, src_idx, dst_list, dst_idx)

    def add_interest_to(self, source: int, target: int) -> None:
        self._intervals.add_interest_to(source, target)

    def add_held_to(self, source: int, target: int) -> None:
        self._intervals.add_held_to(source, target)

    def add_target_to(self, source: int, target: int) -> None:
        self._intervals.add_target_to(source, target)

    def set_range_mode(self, mode: str) -> None:
        self._intervals.set_range_mode(mode)

    def back_to_scheme(self) -> None:
        self._tuning.back_to_scheme()

    def set_generator_tuning_text(self, text: str) -> bool:
        return self._tuning.set_generator_tuning_text(text)

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        self._tuning.set_generator_tuning_component(i, cents)

    def nudge_generator_tuning_component(self, i: int, steps: int) -> None:
        self._tuning.nudge_generator_tuning_component(i, steps)

    def flip_generator(self, i: int) -> None:
        self._tuning.flip_generator(i)

    def set_superspace_generator_tuning_text(self, text: str) -> bool:
        return self._tuning.set_superspace_generator_tuning_text(text)

    def set_superspace_generator_tuning_component(self, i: int, cents: float) -> None:
        self._tuning.set_superspace_generator_tuning_component(i, cents)

    def nudge_superspace_generator_tuning_component(self, i: int, steps: int) -> None:
        self._tuning.nudge_superspace_generator_tuning_component(i, steps)

    def try_edit_projection_text(self, text: str) -> bool:
        return self._tuning.try_edit_projection_text(text)

    def try_edit_embedding_text(self, text: str) -> bool:
        return self._tuning.try_edit_embedding_text(text)

    def set_tuning_scheme(self, name: str) -> None:
        self._tuning.set_tuning_scheme(name)

    def set_established_projection(self, name: str | None) -> None:
        self._tuning.set_established_projection(name)

    def set_unchanged_basis(self, ratios) -> None:
        self._tuning.set_unchanged_basis(ratios)

    def set_projection_matrix(self, projection) -> bool:
        return self._tuning.set_projection_matrix(projection)

    def set_embedding_matrix(self, embedding) -> bool:
        return self._tuning.set_embedding_matrix(embedding)

    def set_complexity_prescaler(self, prescaler: str) -> None:
        self._tuning.set_complexity_prescaler(prescaler)

    def set_complexity_norm_power(self, power: float) -> None:
        self._tuning.set_complexity_norm_power(power)

    def set_optimization_power(self, power: float) -> None:
        self._tuning.set_optimization_power(power)

    def set_weight_slope(self, slope: str) -> None:
        self._tuning.set_weight_slope(slope)

    def set_nonprime_basis_approach(self, approach: str) -> None:
        self._tuning.set_nonprime_basis_approach(approach)

    def set_complexity_name(self, name: str) -> None:
        self._tuning.set_complexity_name(name)

    def set_custom_prescaler_entry(self, i: int, j: int, value: float) -> None:
        self._tuning.set_custom_prescaler_entry(i, j, value)

    def set_custom_prescaler_text(self, text: str) -> bool:
        return self._tuning.set_custom_prescaler_text(text)

    def set_diminuator_replaced(self, replaced: bool) -> None:
        self._tuning.set_diminuator_replaced(replaced)

    def set_all_interval(self, all_interval: bool) -> None:
        self._tuning.set_all_interval(all_interval)

    def set_custom_weight_entry(self, i: int, value: float) -> None:
        self._tuning.set_custom_weight_entry(i, value)

    def set_custom_weights(self, weights) -> None:
        self._tuning.set_custom_weights(weights)

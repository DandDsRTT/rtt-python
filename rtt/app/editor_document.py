from __future__ import annotations

from rtt.app import service
from rtt.app.editor_history import History
from rtt.app.editor_intervals import _IntervalCommands, _IntervalQueries
from rtt.app.editor_pending import PendingEdits
from rtt.app.editor_session import _SessionCommands
from rtt.app.editor_settings_ops import _ShowCommands
from rtt.app.editor_state import _Doc, initial_doc
from rtt.app.editor_structure import _StructureCommands, _StructureQueries
from rtt.app.editor_tuning import _TuningCommands
from rtt.app.editor_view import _TuningQueries
from rtt.app.service.state import TemperamentState


class Document(
    _StructureCommands,
    _StructureQueries,
    _IntervalCommands,
    _IntervalQueries,
    _TuningCommands,
    _ShowCommands,
    _SessionCommands,
    _TuningQueries,
):
    def __init__(self) -> None:
        self.history = History()
        self.pending = PendingEdits()
        self.nonprime_basis_approach: str = ""
        self.preferred_form: dict[str, str] = {}
        self.restore(initial_doc())

    def capture(self) -> _Doc:
        return _Doc(
            state=self._state,
            tuning_scheme=self.tuning_scheme,
            target_family=self.target_family,
            target_limit=self.target_limit,
            interest_vectors=tuple(self.interest_vectors),
            held_vectors=tuple(self.held_vectors),
            range_mode=self.range_mode,
            generator_tuning=self.generator_tuning,
            manual_tuning=self.manual_tuning,
            custom_prescaler=self.custom_prescaler,
            custom_weights=self.custom_weights,
            target_override=self.target_override,
            projection_basis=self.projection_basis,
            settings=tuple(sorted(self.settings.items())),
            collapsed=frozenset(self.collapsed),
            preferred_form=tuple(sorted(self.preferred_form.items())),
        )

    def restore(self, document: _Doc) -> None:
        self._state = document.state
        self.tuning_scheme = document.tuning_scheme
        self.target_family = document.target_family
        self.target_limit = document.target_limit
        self.interest_vectors = [tuple(m) for m in document.interest_vectors]
        self.held_vectors = [tuple(m) for m in document.held_vectors]
        self.range_mode = document.range_mode
        self.generator_tuning = document.generator_tuning
        self.manual_tuning = document.manual_tuning
        self.custom_prescaler = document.custom_prescaler
        self.custom_weights = document.custom_weights
        self.target_override = document.target_override
        self.projection_basis = document.projection_basis
        self.settings = dict(document.settings)
        self.collapsed = set(document.collapsed)
        self.preferred_form = dict(document.preferred_form)
        self.pending.reset()

    @property
    def state(self) -> TemperamentState:
        return self._state

    @state.setter
    def state(self, new_state: TemperamentState) -> None:
        if new_state.dimensionality != self._state.dimensionality:
            self.target_limit = None
            self.target_override = None
            self.held_vectors = []
            self.interest_vectors = []
            self.custom_prescaler = None
            self.invalidate_custom_weights()
        if not service.domain_has_nonprimes(new_state.domain_basis):
            self.nonprime_basis_approach = ""
        if (
            new_state.mapping != self._state.mapping
            or new_state.domain_basis != self._state.domain_basis
        ):
            self.pending.superspace_generator_tuning = None
            self.projection_basis = ()
        self._state = new_state

    @property
    def real_comma_basis(self) -> tuple[tuple[int, ...], ...]:
        return self.state.comma_basis if self.state.nullity else ()

    @property
    def target_spec(self) -> str:
        if self.target_limit is not None:
            return f"{self.target_limit}-{self.target_family}"
        return self.target_family

    @property
    def can_reset(self) -> bool:
        return self.capture() != initial_doc()

    def snapshot(self) -> None:
        self.history.record(self.capture())
        self.pending.nudging_generator = None

    def apply_state(self, state: TemperamentState) -> None:
        self.snapshot()
        self.pending.clear_drafts()
        old_mapping = self._state.mapping
        self.state = state
        self.drop_stale_manual(old_mapping)

    def drop_stale_manual(self, old_mapping) -> None:
        if self.generator_tuning is not None and self.state.mapping != old_mapping:
            self.generator_tuning = None
            self.manual_tuning = False

    def current_targets(self) -> list[str]:
        if self.target_override is not None:
            return list(self.target_override)
        return list(service.target_interval_set(self.target_spec, self.state.domain_basis))

    def displayed_target_weights(self) -> tuple[float, ...]:
        return tuple(
            service.interval_weights(
                self.state.mapping,
                self.tuning_scheme,
                self.current_targets(),
                prescaler_override=self.custom_prescaler,
                domain_basis=self.state.domain_basis,
            )
        )

    def apply_all_interval(self, all_interval: bool) -> None:
        slope = "simplicity-weight" if all_interval else "unity-weight"
        scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)
        self.tuning_scheme = service.scheme_with_targets(
            scheme, "{}" if all_interval else self.target_spec
        )
        self.reconcile_custom_weights()

    def exit_all_interval_if_hidden(self, had_all_interval: bool) -> None:
        if (
            had_all_interval
            and not self.settings["all_interval"]
            and service.is_all_interval(self.tuning_scheme)
        ):
            self.apply_all_interval(False)

    def reconcile_custom_weights(self) -> None:
        applies = self.settings["custom_weights"] and not service.is_all_interval(
            self.tuning_scheme
        )
        if applies and self.custom_weights is None:
            self.custom_weights = tuple(self.displayed_target_weights())
        elif not applies:
            self.custom_weights = None

    def invalidate_custom_weights(self) -> None:
        self.custom_weights = None
        self.reconcile_custom_weights()

    def custom_weights_deviate(self) -> bool:
        return not service.is_all_interval(self.tuning_scheme) and service.weights_deviate(
            self.custom_weights, self.displayed_target_weights()
        )

    def reset_to_basic_tuning(self) -> None:
        self.tuning_scheme = service.scheme_with_power(
            service.scheme_with_complexity(self.tuning_scheme, "lp"), float("inf")
        )
        self.custom_prescaler = None

    def undo(self) -> None:
        if self.history.can_undo:
            self.history.push_redo(self.capture())
            self.restore(self.history.pop_undo())

    def redo(self) -> None:
        if self.history.can_redo:
            self.history.push_undo(self.capture())
            self.restore(self.history.pop_redo())

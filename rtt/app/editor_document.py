from __future__ import annotations

import functools
import math
from dataclasses import dataclass

from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app.editor_history import History
from rtt.app.editor_pending import PendingEdits
from rtt.app.service.state import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))
INITIAL_COLLAPSED: frozenset[str] = frozenset()


def _same_cents_map(a, b) -> bool:
    return len(a) == len(b) and all(
        service.cents(x) == service.cents(y) for x, y in zip(a, b, strict=False)
    )


@dataclass(frozen=True)
class _Doc:
    state: TemperamentState
    tuning_scheme: object
    target_family: str
    target_limit: int | None
    interest_vectors: tuple[tuple[int, ...], ...]
    held_vectors: tuple[tuple[int, ...], ...]
    range_mode: str
    generator_tuning: tuple[float, ...] | None
    manual_tuning: bool
    custom_prescaler: tuple | None
    custom_weights: tuple[float, ...] | None
    target_override: tuple[str, ...] | None
    projection_basis: tuple[str, ...]
    settings: tuple[tuple[str, bool], ...]
    collapsed: frozenset[str]
    preferred_form: tuple[tuple[str, str], ...]


def prescaler_is_solvable(p) -> bool:
    if not p:
        return False
    is_matrix = isinstance(p[0], (tuple, list))
    if is_matrix:
        for i, row in enumerate(p):
            for j, x in enumerate(row):
                if not math.isfinite(x) or (i == j and x <= 0):
                    return False
        return True
    return all(math.isfinite(x) and x > 0 for x in p)


def weights_are_solvable(w) -> bool:
    return bool(w) and all(math.isfinite(x) and x > 0 for x in w)


@functools.lru_cache(maxsize=1)
def initial_doc() -> _Doc:
    state = service.from_mapping(INITIAL_MAPPING)
    return _Doc(
        state=state,
        tuning_scheme=service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME),
        target_family=service.DEFAULT_TARGET_SPEC,
        target_limit=None,
        interest_vectors=(),
        held_vectors=(),
        range_mode="monotone",
        generator_tuning=None,
        manual_tuning=False,
        custom_prescaler=None,
        custom_weights=None,
        target_override=None,
        projection_basis=(),
        settings=tuple(sorted(show_settings.defaults().items())),
        collapsed=INITIAL_COLLAPSED,
        preferred_form=(),
    )


class Document:
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

    def restore(self, doc: _Doc) -> None:
        self._state = doc.state
        self.tuning_scheme = doc.tuning_scheme
        self.target_family = doc.target_family
        self.target_limit = doc.target_limit
        self.interest_vectors = [tuple(m) for m in doc.interest_vectors]
        self.held_vectors = [tuple(m) for m in doc.held_vectors]
        self.range_mode = doc.range_mode
        self.generator_tuning = doc.generator_tuning
        self.manual_tuning = doc.manual_tuning
        self.custom_prescaler = doc.custom_prescaler
        self.custom_weights = doc.custom_weights
        self.target_override = doc.target_override
        self.projection_basis = doc.projection_basis
        self.settings = dict(doc.settings)
        self.collapsed = set(doc.collapsed)
        self.preferred_form = dict(doc.preferred_form)
        self.pending.reset()

    @property
    def state(self) -> TemperamentState:
        return self._state

    @state.setter
    def state(self, new_state: TemperamentState) -> None:
        if new_state.d != self._state.d:
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
        return self.state.comma_basis if self.state.n else ()

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

    def turn_off_custom_weights(self) -> None:
        self.settings["custom_weights"] = False
        self.custom_weights = None

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

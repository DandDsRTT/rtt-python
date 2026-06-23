from __future__ import annotations

import re
from fractions import Fraction

from rtt.app import service
from rtt.app.editor_document import Document
from rtt.app.editor_view import TuningView


class IntervalOps:
    MOVE_LISTS = ("targets", "held", "interest", "commas", "unchanged")

    def __init__(self, doc: Document, view: TuningView) -> None:
        self.doc = doc
        self.pending = doc.pending
        self.view = view

    def _feed_draft(self, values, commit) -> list[int | None] | None:
        draft = list(values)
        if any(v is None for v in draft):
            return draft
        self.doc.snapshot()
        commit(tuple(int(v) for v in draft))
        return None

    def add_interest(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_interest = [None] * self.doc.state.d

    def set_pending_interest(self, values) -> None:
        self.pending.pending_interest = self._feed_draft(values, self.doc.interest_vectors.append)

    def cancel_pending_interest(self) -> None:
        self.pending.pending_interest = None

    def remove_interest(self, i: int) -> None:
        self.doc.snapshot()
        del self.doc.interest_vectors[i]

    def set_interest_vectors(self, vectors) -> None:
        self.doc.snapshot()
        self.doc.interest_vectors = [tuple(int(x) for x in m) for m in vectors]

    def add_held(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_held = [None] * self.doc.state.d

    def set_pending_held(self, values) -> None:
        self.pending.pending_held = self._feed_draft(values, self.doc.held_vectors.append)

    def cancel_pending_held(self) -> None:
        self.pending.pending_held = None

    def remove_held(self, i: int) -> None:
        self.doc.snapshot()
        del self.doc.held_vectors[i]

    def set_held_vectors(self, vectors) -> None:
        self.doc.snapshot()
        self.doc.held_vectors = [tuple(int(x) for x in m) for m in vectors]

    def set_target_spec(self, spec: str) -> None:
        self.doc.snapshot()
        match = re.match(r"(\d*)-?(TILT|OLD)", spec)
        n, family = (match.group(1), match.group(2)) if match else ("", self.doc.target_family)
        self.doc.target_family = family
        self.doc.target_limit = int(n) if n else None
        self.doc.target_override = None
        self.doc.invalidate_custom_weights()
        if not service.is_all_interval(self.doc.tuning_scheme):
            self.doc.tuning_scheme = service.scheme_with_targets(
                self.doc.tuning_scheme, self.doc.target_spec
            )

    def set_target_override_text(self, text: str) -> bool:
        vectors = service.parse_comma_basis(text)
        if vectors is None:
            return False
        self.doc.snapshot()
        self.doc.target_override = service.comma_ratios(vectors, self.doc.state.domain_basis)
        self.doc.invalidate_custom_weights()
        return True

    def set_target_override_vectors(self, vectors) -> None:
        self.doc.snapshot()
        self.doc.target_override = service.comma_ratios(
            [tuple(int(x) for x in m) for m in vectors], self.doc.state.domain_basis
        )
        self.doc.invalidate_custom_weights()

    def add_target(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_target = [None] * self.doc.state.d

    def set_pending_target(self, values) -> None:
        def commit(vector):
            targets = self.doc.current_targets()
            targets.append(service.comma_ratios([vector], self.doc.state.domain_basis)[0])
            self.doc.target_override = tuple(targets)
            self.doc.invalidate_custom_weights()

        self.pending.pending_target = self._feed_draft(values, commit)

    def cancel_pending_target(self) -> None:
        self.pending.pending_target = None

    def remove_target(self, i: int) -> None:
        targets = self.doc.current_targets()
        del targets[i]
        self.doc.snapshot()
        self.doc.target_override = tuple(targets)
        self.doc.invalidate_custom_weights()

    def _list_vectors(self, name: str) -> list[tuple[int, ...]]:
        state = self.doc.state
        if name == "targets":
            return [
                tuple(v)
                for v in service.target_interval_vectors(
                    self.doc.current_targets(), state.d, state.domain_basis
                )
            ]
        if name == "held":
            return [tuple(v) for v in self.doc.held_vectors]
        if name == "interest":
            return [tuple(v) for v in self.doc.interest_vectors]
        if name == "unchanged":
            return list(service.unchanged_interval_basis(state, self.view.unchanged_ratios) or ())
        return [tuple(v) for v in state.comma_basis]

    def _peek_vector(self, name: str, i: int) -> tuple[int, ...] | None:
        vectors = self._list_vectors(name)
        return vectors[i] if 0 <= i < len(vectors) else None

    def _move_feasible(self, src: str, dst: str, vector: tuple[int, ...]) -> bool:
        state = self.doc.state
        if src not in self.MOVE_LISTS or dst not in self.MOVE_LISTS:
            return False
        if dst == "unchanged":
            return False
        if "targets" in (src, dst) and service.is_all_interval(self.doc.tuning_scheme):
            return False
        if src == "commas" and state.n == 0:
            return False
        if dst == "commas":
            domain_basis = state.domain_basis if len(vector) == state.d else None
            extended = service.from_comma_basis(
                (*self.doc.real_comma_basis, tuple(vector)), domain_basis
            )
            if extended.n <= state.n:
                return False
        return True

    def _take_from(self, name: str, i: int) -> None:
        if name == "targets":
            targets = self.doc.current_targets()
            del targets[i]
            self.doc.target_override = tuple(targets)
        elif name == "held":
            del self.doc.held_vectors[i]
        elif name == "interest":
            del self.doc.interest_vectors[i]
        elif name == "unchanged":
            pass
        else:
            self.doc.state = service.remove_comma(self.doc.state, i)

    def _put_into(self, name: str, i: int, vector: tuple[int, ...]) -> None:
        if name == "targets":
            targets = self.doc.current_targets()
            targets.insert(i, service.comma_ratios([vector], self.doc.state.domain_basis)[0])
            self.doc.target_override = tuple(targets)
        elif name == "held":
            self.doc.held_vectors.insert(i, tuple(vector))
        elif name == "interest":
            self.doc.interest_vectors.insert(i, tuple(vector))
        else:
            state = self.doc.state
            domain_basis = state.domain_basis if len(vector) == state.d else None
            self.doc.state = service.from_comma_basis(
                (*self.doc.real_comma_basis, tuple(vector)), domain_basis
            )

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        vector = self._peek_vector(src_list, src_idx)
        if vector is None or not self._move_feasible(src_list, dst_list, vector):
            return False
        if src_list == dst_list and (src_list in ("commas", "unchanged") or src_idx == dst_idx):
            return False
        self.doc.snapshot()
        if "commas" in (src_list, dst_list):
            self.pending.clear_drafts()
        if "targets" in (src_list, dst_list):
            self.doc.invalidate_custom_weights()
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)
        return True

    def _combine_interval_vectors(self, vectors: list, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(vectors) and 0 <= target < len(vectors)):
            return
        self.doc.snapshot()
        vectors[target] = tuple(
            a + b for a, b in zip(vectors[target], vectors[source], strict=False)
        )

    def add_interest_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.doc.interest_vectors, source, target)

    def add_held_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.doc.held_vectors, source, target)

    def add_target_to(self, source: int, target: int) -> None:
        targets = self.doc.current_targets()
        if source == target or not (0 <= source < len(targets) and 0 <= target < len(targets)):
            return
        product = Fraction(targets[source]) * Fraction(targets[target])
        self.doc.snapshot()
        targets[target] = f"{product.numerator}/{product.denominator}"
        self.doc.target_override = tuple(targets)
        self.doc.invalidate_custom_weights()

    def set_range_mode(self, mode: str) -> None:
        self.doc.snapshot()
        self.doc.range_mode = mode

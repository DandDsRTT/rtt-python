from __future__ import annotations

import re
from fractions import Fraction

from rtt.app import service
from rtt.app.editor_state import blank_draft, comma_ratios_in_domain


class _IntervalCommands:
    MOVE_LISTS = ("targets", "held", "interest", "commas", "unchanged")

    def _feed_draft(self, values, commit) -> list[int | None] | None:
        draft = list(values)
        if any(v is None for v in draft):
            return draft
        self.snapshot()
        commit(tuple(int(v) for v in draft))
        return None

    def add_interest(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_interest = blank_draft(self.state)

    def set_pending_interest(self, values) -> None:
        self.pending.pending_interest = self._feed_draft(values, self.interest_vectors.append)

    def cancel_pending_interest(self) -> None:
        self.pending.pending_interest = None

    def remove_interest(self, i: int) -> None:
        self.snapshot()
        del self.interest_vectors[i]

    def set_interest_vectors(self, vectors) -> None:
        self.snapshot()
        self.interest_vectors = [tuple(int(x) for x in m) for m in vectors]

    def add_held(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_held = blank_draft(self.state)

    def set_pending_held(self, values) -> None:
        self.pending.pending_held = self._feed_draft(values, self.held_vectors.append)

    def cancel_pending_held(self) -> None:
        self.pending.pending_held = None

    def remove_held(self, i: int) -> None:
        self.snapshot()
        del self.held_vectors[i]

    def set_held_vectors(self, vectors) -> None:
        self.snapshot()
        self.held_vectors = [tuple(int(x) for x in m) for m in vectors]

    def set_target_spec(self, spec: str) -> None:
        self.snapshot()
        match = re.match(r"(\d*)-?(TILT|OLD)", spec)
        n, family = (match.group(1), match.group(2)) if match else ("", self.target_family)
        self.target_family = family
        self.target_limit = int(n) if n else None
        self.target_override = None
        self.invalidate_custom_weights()
        if not service.is_all_interval(self.tuning_scheme):
            self.tuning_scheme = service.scheme_with_targets(self.tuning_scheme, self.target_spec)

    def set_target_override_text(self, text: str) -> bool:
        vectors = service.parse_comma_basis(text)
        if vectors is None:
            return False
        self.snapshot()
        self.target_override = comma_ratios_in_domain(self.state, vectors)
        self.invalidate_custom_weights()
        return True

    def set_target_override_vectors(self, vectors) -> None:
        self.snapshot()
        self.target_override = comma_ratios_in_domain(
            self.state, [tuple(int(x) for x in m) for m in vectors]
        )
        self.invalidate_custom_weights()

    def add_target(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_target = blank_draft(self.state)

    def set_pending_target(self, values) -> None:
        def commit(vector):
            targets = self.current_targets()
            targets.append(comma_ratios_in_domain(self.state, [vector])[0])
            self.target_override = tuple(targets)
            self.invalidate_custom_weights()

        self.pending.pending_target = self._feed_draft(values, commit)

    def cancel_pending_target(self) -> None:
        self.pending.pending_target = None

    def remove_target(self, i: int) -> None:
        targets = self.current_targets()
        del targets[i]
        self.snapshot()
        self.target_override = tuple(targets)
        self.invalidate_custom_weights()

    def list_vectors(self, name: str) -> list[tuple[int, ...]]:
        state = self.state
        if name == "targets":
            return [
                tuple(v)
                for v in service.target_interval_vectors(
                    self.current_targets(), state.d, state.domain_basis
                )
            ]
        if name == "held":
            return [tuple(v) for v in self.held_vectors]
        if name == "interest":
            return [tuple(v) for v in self.interest_vectors]
        if name == "unchanged":
            return list(service.unchanged_interval_basis(state, self.unchanged_ratios) or ())
        return [tuple(v) for v in state.comma_basis]

    def _peek_vector(self, name: str, i: int) -> tuple[int, ...] | None:
        vectors = self.list_vectors(name)
        return vectors[i] if 0 <= i < len(vectors) else None

    def _move_feasible(self, src: str, dst: str, vector: tuple[int, ...]) -> bool:
        state = self.state
        if src not in self.MOVE_LISTS or dst not in self.MOVE_LISTS:
            return False
        if dst == "unchanged":
            return False
        if "targets" in (src, dst) and service.is_all_interval(self.tuning_scheme):
            return False
        if src == "commas" and state.n == 0:
            return False
        if dst == "commas":
            domain_basis = state.domain_basis if len(vector) == state.d else None
            extended = service.from_comma_basis(
                (*self.real_comma_basis, tuple(vector)), domain_basis
            )
            if extended.n <= state.n:
                return False
        return True

    def _take_from(self, name: str, i: int) -> None:
        if name == "targets":
            targets = self.current_targets()
            del targets[i]
            self.target_override = tuple(targets)
        elif name == "held":
            del self.held_vectors[i]
        elif name == "interest":
            del self.interest_vectors[i]
        elif name == "unchanged":
            pass
        else:
            self.state = service.remove_comma(self.state, i)

    def _put_into(self, name: str, i: int, vector: tuple[int, ...]) -> None:
        if name == "targets":
            targets = self.current_targets()
            targets.insert(i, comma_ratios_in_domain(self.state, [vector])[0])
            self.target_override = tuple(targets)
        elif name == "held":
            self.held_vectors.insert(i, tuple(vector))
        elif name == "interest":
            self.interest_vectors.insert(i, tuple(vector))
        else:
            state = self.state
            domain_basis = state.domain_basis if len(vector) == state.d else None
            self.state = service.from_comma_basis(
                (*self.real_comma_basis, tuple(vector)), domain_basis
            )

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        vector = self._peek_vector(src_list, src_idx)
        if vector is None or not self._move_feasible(src_list, dst_list, vector):
            return False
        if src_list == dst_list and (src_list in ("commas", "unchanged") or src_idx == dst_idx):
            return False
        self.snapshot()
        if "commas" in (src_list, dst_list):
            self.pending.clear_drafts()
        if "targets" in (src_list, dst_list):
            self.invalidate_custom_weights()
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)
        return True

    def _combine_interval_vectors(self, vectors: list, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(vectors) and 0 <= target < len(vectors)):
            return
        self.snapshot()
        vectors[target] = tuple(
            a + b for a, b in zip(vectors[target], vectors[source], strict=False)
        )

    def add_interest_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.interest_vectors, source, target)

    def add_held_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.held_vectors, source, target)

    def add_target_to(self, source: int, target: int) -> None:
        targets = self.current_targets()
        if source == target or not (0 <= source < len(targets) and 0 <= target < len(targets)):
            return
        product = Fraction(targets[source]) * Fraction(targets[target])
        self.snapshot()
        targets[target] = f"{product.numerator}/{product.denominator}"
        self.target_override = tuple(targets)
        self.invalidate_custom_weights()

    def set_range_mode(self, mode: str) -> None:
        self.snapshot()
        self.range_mode = mode

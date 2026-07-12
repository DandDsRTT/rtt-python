from __future__ import annotations

import re

from rtt.app import editor_predicates, service
from rtt.app.editor_state import blank_draft, comma_ratios_in_domain

INTERVAL_GROUP_LIST = {
    "comma": "commas",
    "target": "targets",
    "held": "held",
    "interest": "interest",
}


class _IntervalQueries:
    def list_vectors(self, name: str) -> list[tuple[int, ...]]:
        return editor_predicates.list_vectors(self._solve(), name)


class _IntervalCommands:
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
        self.rederive_custom_weights()
        if not service.is_all_interval(self.tuning_scheme):
            self.tuning_scheme = service.scheme_with_targets(self.tuning_scheme, self.target_spec)

    def set_target_override_text(self, text: str) -> bool:
        vectors = service.parse_comma_basis(text)
        if vectors is None:
            return False
        self.snapshot()
        self.target_override = comma_ratios_in_domain(self.state, vectors)
        self.rederive_custom_weights()
        return True

    def set_target_override_vectors(self, vectors) -> None:
        self.snapshot()
        self.target_override = comma_ratios_in_domain(
            self.state, [tuple(int(x) for x in m) for m in vectors]
        )
        self.rederive_custom_weights()

    def add_target(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_target = blank_draft(self.state)

    def set_pending_target(self, values) -> None:
        def commit(vector):
            targets = self.current_targets()
            targets.append(comma_ratios_in_domain(self.state, [vector])[0])
            self.target_override = tuple(targets)
            self.rederive_custom_weights()

        self.pending.pending_target = self._feed_draft(values, commit)

    def cancel_pending_target(self) -> None:
        self.pending.pending_target = None

    def remove_target(self, i: int) -> None:
        targets = self.current_targets()
        del targets[i]
        self.snapshot()
        self.target_override = tuple(targets)
        self.rederive_custom_weights()

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
            domain_basis = state.domain_basis if len(vector) == state.dimensionality else None
            self.state = service.from_comma_basis(
                (*self.real_comma_basis, tuple(vector)), domain_basis
            )

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        if "generators" in (src_list, dst_list):
            rows = [list(row) for row in self.state.mapping]
            target = min(dst_idx, len(rows) - 1)
            if src_list != dst_list or not 0 <= src_idx < len(rows) or src_idx == target:
                return False
            rows.insert(target, rows.pop(src_idx))
            self.edit_mapping(rows)
            return True
        s = self._solve()
        vector = editor_predicates.peek_vector(editor_predicates.list_vectors(s, src_list), src_idx)
        if vector is None or not editor_predicates.move_feasible(s, src_list, dst_list, vector):
            return False
        if src_list == dst_list and (src_list in ("commas", "unchanged") or src_idx == dst_idx):
            return False
        self.snapshot()
        if "commas" in (src_list, dst_list):
            self.pending.clear_drafts()
        if "targets" in (src_list, dst_list):
            self.rederive_custom_weights()
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)
        return True

    def combine_intervals(
        self, source_group: str, source: int, target_group: str, target: int
    ) -> None:
        if (source_group, source) == (target_group, target):
            return
        solve = self._solve()
        source_vector = editor_predicates.peek_vector(
            editor_predicates.list_vectors(solve, INTERVAL_GROUP_LIST[source_group]), source
        )
        target_vectors = editor_predicates.list_vectors(solve, INTERVAL_GROUP_LIST[target_group])
        if source_vector is None or not (0 <= target < len(target_vectors)):
            return
        combined = tuple(a + b for a, b in zip(target_vectors[target], source_vector, strict=False))
        self.snapshot()
        if target_group == "comma":
            old_mapping = self.state.mapping
            self.pending.clear_drafts()
            commas = [list(comma) for comma in self.state.comma_basis]
            commas[target] = list(combined)
            self.state = service.from_comma_basis(commas, self.state.domain_basis)
            self.drop_stale_manual(old_mapping)
        elif target_group == "target":
            targets = self.current_targets()
            targets[target] = comma_ratios_in_domain(self.state, [combined])[0]
            self.target_override = tuple(targets)
            self.rederive_custom_weights()
        elif target_group == "held":
            self.held_vectors[target] = tuple(combined)
        else:
            self.interest_vectors[target] = tuple(combined)

    def add_interest_to(self, source: int, target: int) -> None:
        self.combine_intervals("interest", source, "interest", target)

    def add_held_to(self, source: int, target: int) -> None:
        self.combine_intervals("held", source, "held", target)

    def add_target_to(self, source: int, target: int) -> None:
        self.combine_intervals("target", source, "target", target)

    def set_range_mode(self, mode: str) -> None:
        self.snapshot()
        self.range_mode = mode

from __future__ import annotations

import ast
import json
from pathlib import Path

from tools._quality_common import Violation
from tools.quality_metrics import (
    bag_cross_file,
    class_surface,
    demeter_chains,
    explanatory_comment_blocks,
    oversized_classes,
    reach_through_by_handle,
)

BASELINE_PATH = Path(__file__).with_name("quality_baseline.json")
SPREADSHEET_GLOB = "rtt/app/spreadsheet*.py"


def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text())


def reach_through_violations(
    trees: list[tuple[Path, ast.Module]], baseline: dict
) -> list[Violation]:
    counts = reach_through_by_handle(trees)
    found: list[Violation] = []
    total = sum(counts.values())
    total_floor = baseline["reach_through_total"]
    if total > total_floor:
        found.append(_reach_total_violation(total, total_floor))
    for handle, floor in sorted(baseline.get("reach_through_by_handle", {}).items()):
        live = counts.get(handle, 0)
        if live > floor:
            found.append(_reach_handle_violation(handle, live, floor))
    return found


def _reach_total_violation(total: int, floor: int) -> Violation:
    return Violation(
        "rtt/app",
        1,
        f"injected-handle reach-throughs rose to {total} (ratchet floor {floor}); a class "
        "reaches self.<injected_handle>.<member> — inject the member or narrow the handle",
    )


def _reach_handle_violation(handle: str, live: int, floor: int) -> Violation:
    return Violation(
        "rtt/app",
        1,
        f"reach-throughs via self.{handle} rose to {live} (per-handle floor {floor}); a "
        "per-handle floor only shrinks — inject the member or narrow the handle",
    )


def demeter_violations(trees: list[tuple[Path, ast.Module]], baseline: dict) -> list[Violation]:
    grandfathered = set(baseline["demeter_chains"])
    found = []
    for entry in sorted(demeter_chains(trees) - grandfathered):
        path, chain = entry.split("::", 1)
        found.append(
            Violation(
                path,
                1,
                f"new depth-3+ reach off an injected handle ({chain}); a 4-hop Law-of-Demeter "
                "chain is banned — ask the handle for what you need, don't walk its internals",
            )
        )
    return found


def bag_violations(trees: list[tuple[Path, ast.Module]], baseline: dict) -> list[Violation]:
    crossing, accumulators = bag_cross_file(trees)
    found = []
    floor = baseline["bag_cross_file_total"]
    if len(crossing) > floor:
        found.append(
            Violation(
                SPREADSHEET_GLOB,
                1,
                f"SimpleNamespace bag cross-file shared attrs rose to {len(crossing)} (ratchet "
                f"floor {floor}); a bag threaded across files is shared mutable state — freeze it",
            )
        )
    for bag in sorted(accumulators - set(baseline["bag_cross_file_accumulators"])):
        found.append(
            Violation(
                SPREADSHEET_GLOB,
                1,
                f"'{bag}' is a new SimpleNamespace cross-file accumulator; threading a mutable bag "
                "across files is banned — pass a frozen value object instead",
            )
        )
    return found


def class_surface_violations(
    trees: list[tuple[Path, ast.Module]], baseline: dict
) -> list[Violation]:
    floors = baseline["class_surface"]
    surface = class_surface(trees)
    found = []
    for name, floor in sorted(floors.items()):
        counts = surface.get(name)
        if counts is None:
            continue
        for kind in ("methods", "attrs"):
            if counts[kind] > floor[kind]:
                found.append(_class_grew(name, kind, counts[kind], floor[kind]))
    for name, counts in sorted(oversized_classes(surface).items()):
        if name not in floors:
            found.append(_new_god_object(name, counts))
    return found


def _new_god_object(name: str, counts: dict) -> Violation:
    return Violation(
        "rtt",
        1,
        f"{name} crosses the class-surface floor ({counts['methods']} methods, {counts['attrs']} "
        "instance attrs); split it before it becomes a god-object, or baseline it deliberately",
    )


def _class_grew(name: str, kind: str, value: int, floor: int) -> Violation:
    return Violation(
        "rtt",
        1,
        f"{name} grew to {value} {kind} (ratchet floor {floor}); a class surface only shrinks",
    )


def comment_violations(files: list[Path], baseline: dict) -> list[Violation]:
    floor = baseline["explanatory_comment_blocks"]
    offenders = [(path, line) for path in files for line in explanatory_comment_blocks(path)]
    if len(offenders) <= floor:
        return []
    return [
        Violation(
            path.as_posix(),
            line,
            "explanatory comment that names no platform constraint; this project documents via "
            "names + tests only (CLAUDE.md) — delete it or name the NiceGUI/Quasar/browser limit",
        )
        for path, line in offenders
    ]

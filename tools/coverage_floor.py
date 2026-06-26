from __future__ import annotations

import json
import math
import sys
from pathlib import Path

BASELINE_PATH = Path(__file__).with_name("coverage_baseline.json")
LOGIC_TIERS = ("rtt/library/", "rtt/app/service/")
_EPSILON = 1e-9


def is_logic_tier(path: str) -> bool:
    posix = Path(path).as_posix()
    return any(posix.startswith(tier) for tier in LOGIC_TIERS)


def file_percents(report: dict) -> dict[str, float]:
    return {
        Path(path).as_posix(): data["summary"]["percent_covered"]
        for path, data in report["files"].items()
        if is_logic_tier(path)
    }


def load_report(path: Path) -> dict:
    return json.loads(path.read_text())


def load_baseline() -> dict[str, float]:
    return json.loads(BASELINE_PATH.read_text())


def floor_violations(percents: dict[str, float], baseline: dict[str, float]) -> list[str]:
    found = []
    for path, floor in sorted(baseline.items()):
        live = percents.get(path)
        if live is not None and live + _EPSILON < floor:
            found.append(
                f"{path} branch coverage fell to {live:.2f}% (per-file floor {floor:.2f}%); "
                "a logic-tier file's coverage only ratchets up — add tests or remove the branch"
            )
    return found


def floored(percent: float) -> float:
    return math.floor(percent * 100) / 100


def write_baseline(percents: dict[str, float]) -> dict[str, float]:
    data = {path: floored(pct) for path, pct in sorted(percents.items())}
    BASELINE_PATH.write_text(json.dumps(data, indent=2) + "\n")
    return data


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--update-baseline"]
    report_path = Path(args[0]) if args else Path("coverage.json")
    percents = file_percents(load_report(report_path))
    if "--update-baseline" in argv:
        write_baseline(percents)
        return 0
    violations = floor_violations(percents, load_baseline())
    for violation in violations:
        print(violation)
    if violations:
        print(f"\n{len(violations)} per-file coverage floor violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

import json

from tools import coverage_floor as cf


def report(percents):
    return {
        "files": {path: {"summary": {"percent_covered": pct}} for path, pct in percents.items()}
    }


def test_file_percents_keeps_only_logic_tier_files():
    data = report(
        {
            "rtt/library/projection.py": 88.0,
            "rtt/app/service/superspace.py": 90.5,
            "rtt/app/app.py": 10.0,
            "rtt/app/spreadsheet.py": 12.0,
        }
    )
    assert cf.file_percents(data) == {
        "rtt/library/projection.py": 88.0,
        "rtt/app/service/superspace.py": 90.5,
    }


def test_floors_at_baseline_pass():
    percents = {"rtt/library/a.py": 88.0, "rtt/app/service/b.py": 90.5}
    assert cf.floor_violations(percents, dict(percents)) == []


def test_a_file_dropping_below_its_floor_fails_only_for_that_file():
    percents = {"rtt/library/a.py": 88.0, "rtt/app/service/b.py": 90.5}
    floors = {"rtt/library/a.py": 88.0, "rtt/app/service/b.py": 91.0}
    violations = cf.floor_violations(percents, floors)
    assert len(violations) == 1
    assert "rtt/app/service/b.py" in violations[0]
    assert "fell to 90.50%" in violations[0]


def test_improvement_above_floor_passes():
    assert cf.floor_violations({"rtt/library/a.py": 95.0}, {"rtt/library/a.py": 88.0}) == []


def test_a_removed_baselined_file_is_skipped_not_flagged():
    assert cf.floor_violations({"rtt/library/a.py": 90.0}, {"rtt/library/gone.py": 99.0}) == []


def test_main_update_baseline_then_passes(tmp_path, monkeypatch):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(report({"rtt/library/a.py": 88.0, "rtt/app/x.py": 1.0})))
    monkeypatch.setattr(cf, "BASELINE_PATH", tmp_path / "coverage_baseline.json")
    assert cf.main(["coverage_floor", str(report_path), "--update-baseline"]) == 0
    assert json.loads((tmp_path / "coverage_baseline.json").read_text()) == {
        "rtt/library/a.py": 88.0
    }
    assert cf.main(["coverage_floor", str(report_path)]) == 0


def test_main_returns_nonzero_when_a_file_regresses(tmp_path, monkeypatch):
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(report({"rtt/library/a.py": 80.0})))
    (tmp_path / "coverage_baseline.json").write_text(json.dumps({"rtt/library/a.py": 88.0}))
    monkeypatch.setattr(cf, "BASELINE_PATH", tmp_path / "coverage_baseline.json")
    assert cf.main(["coverage_floor", str(report_path)]) == 1

"""Tests for opskit4.py — plant a CONDITIONAL story, verify the drill
finds the true path; verify every architectural contract."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from opskit4 import (
    PLAYBOOKS,
    STEP_LIBRARY,
    Config,
    OpsKitError,
    Playbook,
    Severity,
    build_context,
    conditional_drill,
    load_config,
    materialise_custom_playbooks,
    run_playbook,
    write_jsonl,
)

CFG = Config()


@pytest.fixture()
def surge_csv(tmp_path: Path) -> Path:
    """Calm 5/day then surge 12/day. Surge driven by service='payments',
    and WITHIN payments by severity='P2' — a true conditional path."""
    p = tmp_path / "inc.csv"
    end = datetime(2026, 7, 6, 12, 0)
    rows = []
    n = 1
    for off in range(56, -1, -1):
        day = end - timedelta(days=off)
        per_day = 12 if off <= 7 else 5
        for i in range(per_day):
            if off <= 7 and i % 2 == 0:
                # all surge rows are payments; WITHIN them, 2/3 are P2 —
                # service explains 100% of the delta, severity only ~67%
                svc, sev = "payments", ("P2" if i % 3 != 0 else "P3")
            else:
                svc, sev = "cards", "P3"
            rows.append([f"I-{n:04d}", day.strftime("%Y-%m-%d 10:00:00"),
                         sev, svc, "owner" if i else ""])
            n += 1
    rows.append(list(rows[0]))
    rows.append(list(rows[1]))
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["incident_id", "opened_at", "severity", "service", "owner"])
        w.writerows(rows)
    return p


class TestConditionalDrill:
    def test_finds_true_conditional_path(self, surge_csv: Path) -> None:
        ctx = build_context(surge_csv, CFG)
        path = conditional_drill(ctx, CFG)
        assert path, "drill returned nothing"
        # level 1 must be the service driver
        assert path[0].column == "service"
        assert path[0].value == "payments"
        # contribution must be a real share of the parent delta
        assert 0 < abs(path[0].contribution) <= 1.5
        # level 2 (within payments) must be severity P2
        if len(path) > 1:
            assert path[1].column == "severity"
            assert path[1].value == "P2"

    def test_no_time_column_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "no_time.csv"
        p.write_text("a,b\nx,1\ny,2\n", encoding="utf-8")
        ctx = build_context(p, CFG)
        assert conditional_drill(ctx, CFG) == []


class TestArchitecturalContracts:
    def test_dependency_violation_raises_at_load(self) -> None:
        bad = Playbook("bad", "Bad", "wrong order",
                       (STEP_LIBRARY["volume_change"], STEP_LIBRARY["shape"]))
        with pytest.raises(OpsKitError, match="requires"):
            bad.validate()

    def test_builtin_playbooks_all_validate(self) -> None:
        for pb in PLAYBOOKS.values():
            pb.validate()   # must not raise

    def test_qident_rejects_unknown_column(self, surge_csv: Path) -> None:
        ctx = build_context(surge_csv, CFG)
        with pytest.raises(OpsKitError, match="does not exist"):
            ctx.qident("ghost")

    def test_steps_are_pure(self, surge_csv: Path) -> None:
        """Running a step twice must produce identical results — no state."""
        ctx = build_context(surge_csv, CFG)
        first = STEP_LIBRARY["duplicates"].run(ctx, CFG)
        second = STEP_LIBRARY["duplicates"].run(ctx, CFG)
        assert first == second


class TestConfig:
    def test_unknown_threshold_key_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "opskit.toml"
        f.write_text("[thresholds]\nsparkle = 3\n", encoding="utf-8")
        with pytest.raises(OpsKitError, match="unknown keys"):
            load_config(f)

    def test_threshold_override_applies(self, tmp_path: Path) -> None:
        f = tmp_path / "opskit.toml"
        f.write_text("[thresholds]\ndrill_threshold = 0.5\n", encoding="utf-8")
        cfg, _ = load_config(f)
        assert cfg.drill_threshold == 0.5

    def test_custom_playbook_from_toml(self) -> None:
        raw = {"claims-review": {"title": "Claims", "description": "d",
                                 "steps": ["shape", "missing"]}}
        books = materialise_custom_playbooks(raw)
        assert books["claims-review"].steps[0].key == "shape"

    def test_custom_playbook_unknown_step_raises(self) -> None:
        raw = {"broken": {"steps": ["shape", "teleport"]}}
        with pytest.raises(OpsKitError, match="unknown steps"):
            materialise_custom_playbooks(raw)


class TestOutputs:
    def test_jsonl_is_valid_and_versioned(self, surge_csv: Path,
                                          tmp_path: Path) -> None:
        ctx = build_context(surge_csv, CFG)
        findings = run_playbook(PLAYBOOKS["data-quality"], ctx, CFG)
        out = tmp_path / "f.jsonl"
        write_jsonl(findings, out)
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == len(findings)
        for line in lines:
            rec = json.loads(line)
            assert rec["schema"] == "opskit.finding/v1"
            assert rec["severity"] in ("INFO", "NOTABLE", "CRITICAL")

    def test_sustained_shift_collapses(self, surge_csv: Path) -> None:
        ctx = build_context(surge_csv, CFG)
        findings = run_playbook(PLAYBOOKS["weekly-review"], ctx, CFG)
        anomaly_crit = [f for f in findings if f.step == "anomaly_days"
                        and f.severity is Severity.CRITICAL]
        assert len(anomaly_crit) == 1
        assert "SUSTAINED SHIFT" in anomaly_crit[0].text

    def test_empty_dataset_is_critical(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("a,b,opened_at\n", encoding="utf-8")
        ctx = build_context(p, CFG)
        findings = run_playbook(PLAYBOOKS["data-quality"], ctx, CFG)
        assert any(f.severity is Severity.CRITICAL and "ZERO" in f.text
                   for f in findings)


class TestMetricDrill:
    def test_sum_metric_drill_finds_planted_driver(self, surge_csv: Path,
                                                   tmp_path: Path) -> None:
        # rebuild surge fixture with an amount column: payments rows carry
        # big amounts in the surge week
        import csv as _csv
        from datetime import datetime as _dt
        from datetime import timedelta as _td
        p = tmp_path / "amt.csv"
        end = _dt(2026, 7, 6, 12, 0)
        rows = []
        n = 1
        for off in range(56, -1, -1):
            day = end - _td(days=off)
            for i in range(8):
                if off <= 7 and i % 2 == 0:
                    svc, amt = "payments", 900.0
                else:
                    svc, amt = "cards", 100.0
                rows.append([f"I-{n:04d}", day.strftime("%Y-%m-%d 10:00:00"),
                             "P2", svc, f"{amt:.2f}"])
                n += 1
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["id", "opened_at", "severity", "service", "amount"])
            w.writerows(rows)
        from opskit4 import Metric
        cfg = Config(metric="sum:amount")
        ctx = build_context(p, cfg)
        path = conditional_drill(ctx, cfg, Metric("sum", "amount"))
        assert path and path[0].column == "service"
        assert path[0].value == "payments"
        # REGRESSION GUARD: the recursion must carry the metric. Level-2
        # values must be rupee-scale sums computed INSIDE payments, not
        # row counts dressed as money.
        if len(path) > 1:
            assert path[1].cur > 500, (
                "level-2 value looks like a count, not a sum — "
                "the recursive call dropped the metric")

    def test_avg_metric_refuses_drill(self, surge_csv: Path) -> None:
        from opskit4 import Metric
        ctx = build_context(surge_csv, Config())
        assert conditional_drill(ctx, Config(), Metric("avg", "x")) == []

    def test_invalid_metric_string_raises(self, surge_csv: Path) -> None:
        from opskit4 import resolve_metric
        ctx = build_context(surge_csv, Config(metric="sparkle:amount"))
        with pytest.raises(OpsKitError, match="Unknown metric kind"):
            resolve_metric(ctx, Config(metric="sparkle:amount"))

    def test_metric_on_non_numeric_column_raises(self, surge_csv: Path) -> None:
        from opskit4 import resolve_metric
        cfg = Config(metric="sum:service")
        ctx = build_context(surge_csv, cfg)
        with pytest.raises(OpsKitError, match="not numeric"):
            resolve_metric(ctx, cfg)

    def test_metric_on_missing_column_raises(self, surge_csv: Path) -> None:
        from opskit4 import resolve_metric
        cfg = Config(metric="sum:ghost")
        ctx = build_context(surge_csv, cfg)
        with pytest.raises(OpsKitError, match="does not exist"):
            resolve_metric(ctx, cfg)

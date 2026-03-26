#!/usr/bin/env python3

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT_DIR / "runs" / "ftbug" / "route-only"
REPORT_PATH = RUNS_ROOT / "compare_results.json"
CASES = ["truth", "fixed", "old", "slope-only", "point-only"]
METRICS = {
    "rivqdown": {
        "filename": ".rivqdown.csv",
        "epsilon_abs": 1e-8,
        "unit": "m^3/min",
    },
    "rivystage": {
        "filename": ".rivystage.csv",
        "epsilon_abs": 1e-10,
        "unit": "m",
    },
}
MIN_RIV_SLOPE = 4e-4
OUTLET_RIVER = 6


def parse_series_file(path: Path) -> dict[str, Any]:
    times: list[float] = []
    values: list[list[float]] = []
    saw_header = False

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue

            parts = line.split()
            if not saw_header:
                if parts and parts[0] == "Time_min":
                    saw_header = True
                continue

            row = [float(part) for part in parts]
            times.append(row[0])
            values.append(row[1:])

    if not saw_header:
        raise ValueError(f"Did not find Time_min header in {path}")
    if not values:
        raise ValueError(f"No data rows found in {path}")

    ncols = len(values[0])
    for idx, row in enumerate(values, start=1):
        if len(row) != ncols:
            raise ValueError(f"Inconsistent column count in {path} at data row {idx}")

    return {"times": times, "values": values, "n_rivers": ncols}


def parse_diagriv(path: Path) -> dict[str, Any]:
    slopes_by_river: dict[int, list[float]] = {}
    qdown_by_river: dict[int, list[tuple[float, float]]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 5:
                raise ValueError(f"Unexpected .diagriv format in {path}: {line}")

            time_val = float(parts[0])
            river = int(parts[1])
            bedslope = float(parts[2])
            qdown = float(parts[4])
            slopes_by_river.setdefault(river, []).append(bedslope)
            qdown_by_river.setdefault(river, []).append((time_val, qdown))

    if not slopes_by_river:
        raise ValueError(f"No data rows found in {path}")

    representative_slopes: dict[int, float] = {}
    max_slope_variation: dict[int, float] = {}
    for river, series in slopes_by_river.items():
        representative_slopes[river] = series[0]
        max_slope_variation[river] = max(abs(value - series[0]) for value in series)

    return {
        "bedslope_by_river": representative_slopes,
        "bedslope_max_variation": max_slope_variation,
        "qdown_by_river": qdown_by_river,
    }


def ensure_aligned(metric_name: str, metric_series: dict[str, dict[str, Any]]) -> None:
    reference = metric_series[CASES[0]]
    reference_times = reference["times"]
    reference_rivers = reference["n_rivers"]

    for case in CASES[1:]:
        current = metric_series[case]
        if current["n_rivers"] != reference_rivers:
            raise ValueError(
                f"{metric_name}: river count mismatch for {case}: "
                f"{current['n_rivers']} != {reference_rivers}"
            )
        if len(current["times"]) != len(reference_times):
            raise ValueError(
                f"{metric_name}: timestep count mismatch for {case}: "
                f"{len(current['times'])} != {len(reference_times)}"
            )
        for idx, (lhs, rhs) in enumerate(zip(current["times"], reference_times), start=1):
            if not math.isclose(lhs, rhs, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(
                    f"{metric_name}: time mismatch at row {idx} for {case}: {lhs} != {rhs}"
                )


def compute_pairwise_diff(
    series_a: dict[str, Any], series_b: dict[str, Any], epsilon: float
) -> dict[str, Any]:
    max_abs_diff = -1.0
    max_abs_meta: dict[str, Any] | None = None
    max_rel_diff = -1.0
    max_rel_meta: dict[str, Any] | None = None

    for time_idx, (row_a, row_b) in enumerate(zip(series_a["values"], series_b["values"])):
        time_min = series_a["times"][time_idx]
        for river_idx, (value_a, value_b) in enumerate(zip(row_a, row_b), start=1):
            abs_diff = abs(value_a - value_b)
            if abs_diff > max_abs_diff:
                max_abs_diff = abs_diff
                max_abs_meta = {
                    "time_min": time_min,
                    "river": river_idx,
                    "case_a_value": value_a,
                    "case_b_value": value_b,
                }

            if abs(value_b) > epsilon:
                rel_diff = abs_diff / abs(value_b)
                if rel_diff > max_rel_diff:
                    max_rel_diff = rel_diff
                    max_rel_meta = {
                        "time_min": time_min,
                        "river": river_idx,
                        "case_a_value": value_a,
                        "case_b_value": value_b,
                    }

    result = {
        "max_abs_diff": max_abs_diff,
        "max_abs_location": max_abs_meta,
        "relative_denominator_case": "case_b",
        "relative_denominator_threshold": epsilon,
    }
    if max_rel_meta is not None:
        result["max_rel_diff"] = max_rel_diff
        result["max_rel_location"] = max_rel_meta
    else:
        result["max_rel_diff"] = None
        result["max_rel_location"] = None
    return result


def compute_bedslope_pairwise(
    case_a: str, case_b: str, diagriv_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    slopes_a = diagriv_data[case_a]["bedslope_by_river"]
    slopes_b = diagriv_data[case_b]["bedslope_by_river"]
    rivers = sorted(slopes_a)
    max_abs_diff = -1.0
    at_river = None
    for river in rivers:
        diff = abs(slopes_a[river] - slopes_b[river])
        if diff > max_abs_diff:
            max_abs_diff = diff
            at_river = river
    return {
        "max_abs_diff": max_abs_diff,
        "river": at_river,
        "case_a_value": slopes_a[at_river] if at_river is not None else None,
        "case_b_value": slopes_b[at_river] if at_river is not None else None,
    }


def fmt_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6e}"


def main() -> int:
    metric_series: dict[str, dict[str, dict[str, Any]]] = {}
    diagriv_data: dict[str, dict[str, Any]] = {}

    for metric_name, config in METRICS.items():
        metric_series[metric_name] = {}
        for case in CASES:
            path = RUNS_ROOT / case / "output" / "ftbug.out" / config["filename"]
            metric_series[metric_name][case] = parse_series_file(path)
        ensure_aligned(metric_name, metric_series[metric_name])

    for case in CASES:
        diagriv_path = RUNS_ROOT / case / "output" / "ftbug.out" / ".diagriv"
        diagriv_data[case] = parse_diagriv(diagriv_path)

    pairwise_metrics: dict[str, dict[str, Any]] = {}
    noise_floor: dict[str, Any] = {}
    criteria: dict[str, Any] = {}

    for metric_name, config in METRICS.items():
        pairwise_metrics[metric_name] = {}
        for case_a, case_b in itertools.permutations(CASES, 2):
            key = f"{case_a}__vs__{case_b}"
            pairwise_metrics[metric_name][key] = compute_pairwise_diff(
                metric_series[metric_name][case_a],
                metric_series[metric_name][case_b],
                config["epsilon_abs"],
            )

        fixed_truth = pairwise_metrics[metric_name]["fixed__vs__truth"]["max_abs_diff"]
        point_fixed = pairwise_metrics[metric_name]["point-only__vs__fixed"]["max_abs_diff"]
        noise_value = max(fixed_truth, point_fixed, config["epsilon_abs"])
        noise_floor[metric_name] = {
            "epsilon_abs": config["epsilon_abs"],
            "noise": noise_value,
            "components": {
                "diff_fixed_truth": fixed_truth,
                "diff_point_only_fixed": point_fixed,
            },
            "unit": config["unit"],
        }

    criteria_definitions = {
        "A": {
            "label": "Slope is main pollution channel",
            "pair": ("old", "slope-only"),
            "comparator": "<=",
            "factor": 10.0,
        },
        "B": {
            "label": "Fix is correct",
            "pair": ("fixed", "truth"),
            "comparator": "<=",
            "factor": 10.0,
        },
        "C": {
            "label": "@point doesn't affect solver",
            "pair": ("point-only", "fixed"),
            "comparator": "<=",
            "factor": 10.0,
        },
        "D": {
            "label": "Bug impact is significant",
            "pair": ("old", "fixed"),
            "comparator": ">=",
            "factor": 100.0,
        },
    }

    for criterion_id, definition in criteria_definitions.items():
        case_a, case_b = definition["pair"]
        per_metric: dict[str, Any] = {}
        passed = True
        for metric_name in METRICS:
            diff_value = pairwise_metrics[metric_name][f"{case_a}__vs__{case_b}"]["max_abs_diff"]
            threshold = definition["factor"] * noise_floor[metric_name]["noise"]
            if definition["comparator"] == "<=":
                metric_passed = diff_value <= threshold
            else:
                metric_passed = diff_value >= threshold
            passed = passed and metric_passed
            per_metric[metric_name] = {
                "diff": diff_value,
                "threshold": threshold,
                "comparator": definition["comparator"],
                "passed": metric_passed,
            }
        criteria[criterion_id] = {
            "label": definition["label"],
            "passed": passed,
            "per_metric": per_metric,
        }

    bedslope_summary: dict[str, Any] = {}
    for case in CASES:
        slopes = diagriv_data[case]["bedslope_by_river"]
        bedslope_summary[case] = {
            "bedslope_by_river": {str(river): slope for river, slope in sorted(slopes.items())},
            "max_time_variation": max(diagriv_data[case]["bedslope_max_variation"].values()),
        }

    bedslope_pairwise = {}
    for case_a, case_b in itertools.combinations(CASES, 2):
        key = f"{case_a}__vs__{case_b}"
        bedslope_pairwise[key] = compute_bedslope_pairwise(case_a, case_b, diagriv_data)

    truth_outlet_slope = diagriv_data["truth"]["bedslope_by_river"][OUTLET_RIVER]
    old_outlet_slope = diagriv_data["old"]["bedslope_by_river"][OUTLET_RIVER]
    qdown_truth_final = metric_series["rivqdown"]["truth"]["values"][-1][OUTLET_RIVER - 1]
    qdown_old_final = metric_series["rivqdown"]["old"]["values"][-1][OUTLET_RIVER - 1]
    predicted_ratio = math.sqrt(old_outlet_slope / truth_outlet_slope)
    actual_ratio = qdown_old_final / qdown_truth_final

    criteria["E"] = {
        "label": "Truth case QrivDown is physically reasonable",
        "passed": math.isfinite(qdown_truth_final) and qdown_truth_final > 0.0,
        "truth_case_final_qrivdown": qdown_truth_final,
    }
    criteria["F"] = {
        "label": "Outlet QrivDown ratio matches Manning prediction",
        "passed": 0.16 <= actual_ratio <= 0.24,
        "predicted_ratio": predicted_ratio,
        "actual_ratio": actual_ratio,
        "acceptable_range": [0.16, 0.24],
        "outlet_river": OUTLET_RIVER,
        "truth_outlet_bedslope": truth_outlet_slope,
        "old_outlet_bedslope": old_outlet_slope,
        "min_riv_slope": MIN_RIV_SLOPE,
        "qdown_old_final": qdown_old_final,
        "qdown_truth_final": qdown_truth_final,
    }

    all_passed = all(item["passed"] for item in criteria.values())
    report = {
        "root_dir": str(ROOT_DIR),
        "runs_root": str(RUNS_ROOT),
        "cases": CASES,
        "timesteps": len(metric_series["rivqdown"]["truth"]["times"]),
        "n_rivers": metric_series["rivqdown"]["truth"]["n_rivers"],
        "metrics": pairwise_metrics,
        "noise_floor": noise_floor,
        "bedslope_summary": bedslope_summary,
        "bedslope_pairwise": bedslope_pairwise,
        "criteria": criteria,
        "all_passed": all_passed,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("FTBUG 5-case comparison summary")
    print("")
    print("Noise floor")
    print("metric       noise         epsilon_abs")
    for metric_name in METRICS:
        print(
            f"{metric_name:<12} "
            f"{noise_floor[metric_name]['noise']:.6e} "
            f"{noise_floor[metric_name]['epsilon_abs']:.6e}"
        )

    print("")
    print("Required comparisons (max abs diff / max rel diff)")
    print("metric       pair                       abs_diff      rel_diff")
    pairs_to_show = [
        ("old", "slope-only"),
        ("fixed", "truth"),
        ("point-only", "fixed"),
        ("old", "fixed"),
    ]
    for metric_name in METRICS:
        for case_a, case_b in pairs_to_show:
            entry = pairwise_metrics[metric_name][f"{case_a}__vs__{case_b}"]
            print(
                f"{metric_name:<12} "
                f"{case_a + ' vs ' + case_b:<26} "
                f"{entry['max_abs_diff']:.6e} "
                f"{fmt_value(entry['max_rel_diff'])}"
            )

    print("")
    print("BedSlope verification (solver-used slopes from .diagriv)")
    print("case         R1           R2           R3           R4           R5           R6")
    for case in CASES:
        slopes = bedslope_summary[case]["bedslope_by_river"]
        print(
            f"{case:<12} "
            f"{float(slopes['1']):.6e} "
            f"{float(slopes['2']):.6e} "
            f"{float(slopes['3']):.6e} "
            f"{float(slopes['4']):.6e} "
            f"{float(slopes['5']):.6e} "
            f"{float(slopes['6']):.6e}"
        )

    print("")
    print("Manning check")
    print(f"outlet river: R{OUTLET_RIVER}")
    print(f"truth outlet BedSlope: {truth_outlet_slope:.6e}")
    print(f"old outlet BedSlope:   {old_outlet_slope:.6e}")
    print(f"predicted ratio:       {predicted_ratio:.6f}")
    print(f"actual ratio:          {actual_ratio:.6f}")
    print(f"truth final QrivDown:  {qdown_truth_final:.6e}")
    print(f"old final QrivDown:    {qdown_old_final:.6e}")

    print("")
    print("Acceptance criteria")
    for criterion_id in ["A", "B", "C", "D", "E", "F"]:
        criterion = criteria[criterion_id]
        status = "PASS" if criterion["passed"] else "FAIL"
        print(f"{criterion_id}: {status} - {criterion['label']}")
        if criterion_id in {"A", "B", "C", "D"}:
            for metric_name in METRICS:
                metric_entry = criterion["per_metric"][metric_name]
                print(
                    f"  {metric_name}: diff={metric_entry['diff']:.6e} "
                    f"{metric_entry['comparator']} {metric_entry['threshold']:.6e}"
                )
        elif criterion_id == "E":
            print(f"  truth final QrivDown={criterion['truth_case_final_qrivdown']:.6e}")
        else:
            print(
                f"  predicted={criterion['predicted_ratio']:.6f}, "
                f"actual={criterion['actual_ratio']:.6f}, "
                f"range=[{criterion['acceptable_range'][0]:.2f}, {criterion['acceptable_range'][1]:.2f}]"
            )

    print("")
    print(f"JSON report: {REPORT_PATH}")
    print(f"Overall result: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - top-level script guard
        print(f"compare_ftbug.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

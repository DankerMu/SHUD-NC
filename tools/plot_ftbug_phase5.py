#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT_DIR / "runs" / "ftbug" / "route-only"
REPORT_PATH = RUNS_ROOT / "compare_results.json"
OUTPUT_DIR = ROOT_DIR / "testdata" / "ftbug"

METRIC_FILES = {
    "rivqdown": ".rivqdown.csv",
    "rivystage": ".rivystage.csv",
}

CASE_ORDER = ["truth", "fixed", "old", "slope-only", "point-only"]
CASE_STYLES = {
    "truth": {
        "label": "truth",
        "color": "black",
        "linestyle": "-",
        "linewidth": 2.3,
        "zorder": 5,
    },
    "fixed": {
        "label": "fixed",
        "color": "tab:blue",
        "linestyle": "-",
        "linewidth": 1.8,
        "zorder": 4,
    },
    "old": {
        "label": "old",
        "color": "tab:red",
        "linestyle": "-",
        "linewidth": 1.8,
        "zorder": 3,
    },
    "slope-only": {
        "label": "slope-only",
        "color": "darkorange",
        "linestyle": "--",
        "linewidth": 1.9,
        "zorder": 2,
    },
    "point-only": {
        "label": "point-only",
        "color": "cyan",
        "linestyle": "--",
        "linewidth": 1.9,
        "zorder": 1,
    },
}

QDOWN_REPRESENTATIVE_RIVERS = [
    (0, "R1 (headwater)"),
    (2, "R3 (confluence)"),
    (5, "R6 (outlet)"),
]
QDOWN_RAW_STYLES = {
    "truth": {
        "label": "truth",
        "color": "black",
        "linestyle": "-",
        "linewidth": 3.0,
        "zorder": 5,
    },
    "fixed": {
        "label": "fixed",
        "color": "tab:blue",
        "linestyle": "--",
        "linewidth": 1.5,
        "zorder": 6,
    },
    "old": {
        "label": "old",
        "color": "tab:red",
        "linestyle": "-",
        "linewidth": 3.0,
        "zorder": 2,
    },
    "slope-only": {
        "label": "slope-only",
        "color": "darkorange",
        "linestyle": "--",
        "linewidth": 1.5,
        "zorder": 3,
    },
    "point-only": {
        "label": "point-only",
        "color": "cyan",
        "linestyle": ":",
        "linewidth": 1.0,
        "zorder": 7,
    },
}
QDOWN_DIFF_STYLES = {
    "old-truth": {
        "label": "old - truth",
        "color": "tab:red",
        "linestyle": "-",
        "linewidth": 2.0,
        "zorder": 2,
    },
    "fixed-truth": {
        "label": "fixed - truth",
        "color": "tab:blue",
        "linestyle": "-",
        "linewidth": 1.5,
        "zorder": 3,
    },
    "slope-only-truth": {
        "label": "slope-only - truth",
        "color": "darkorange",
        "linestyle": "--",
        "linewidth": 1.5,
        "zorder": 4,
    },
    "point-only-truth": {
        "label": "point-only - truth",
        "color": "cyan",
        "linestyle": ":",
        "linewidth": 1.0,
        "zorder": 5,
    },
}
QDOWN_RAW_PLOT_ORDER = ["old", "slope-only", "truth", "fixed", "point-only"]
QDOWN_DIFF_PLOT_ORDER = ["old-truth", "fixed-truth", "slope-only-truth", "point-only-truth"]
RELATIVE_DIFF_REFERENCE = 0.01

HIGHLIGHT_PAIRS = {
    ("old", "slope-only"): {"label": "old ≡ slope-only", "color": "#2ca02c"},
    ("point-only", "fixed"): {"label": "point-only ≡ fixed", "color": "#1f77b4"},
    ("fixed", "truth"): {"label": "fixed ≈ truth", "color": "#9467bd"},
    ("old", "fixed"): {"label": "old ≠ fixed", "color": "#d62728"},
}

MIN_RIV_SLOPE = 4e-4
FIG_DPI = 150


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": FIG_DPI,
            "savefig.dpi": FIG_DPI,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": ":",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_series_file(path: Path) -> dict[str, Any]:
    times: list[float] = []
    values: list[list[float]] = []
    columns: list[str] = []
    saw_header = False

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if not saw_header:
                if parts and parts[0] == "Time_min":
                    columns = parts[1:]
                    saw_header = True
                continue

            row = [float(item) for item in parts]
            times.append(row[0])
            values.append(row[1:])

    if not saw_header:
        raise ValueError(f"Did not find Time_min header in {path}")
    if not values:
        raise ValueError(f"No data rows found in {path}")

    array = np.asarray(values, dtype=float)
    return {
        "times": np.asarray(times, dtype=float),
        "values": array,
        "columns": columns,
        "n_rivers": array.shape[1],
    }


def parse_diagriv_bedslopes(path: Path) -> dict[str, Any]:
    slopes_by_river: dict[int, list[float]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(f"Unexpected .diagriv format in {path}: {line}")

            river = int(parts[1])
            bedslope = float(parts[2])
            slopes_by_river.setdefault(river, []).append(bedslope)

    if not slopes_by_river:
        raise ValueError(f"No rows found in {path}")

    bedslope_by_river: dict[int, float] = {}
    max_time_variation = 0.0
    for river, series in slopes_by_river.items():
        reference = series[0]
        bedslope_by_river[river] = reference
        max_time_variation = max(max_time_variation, max(abs(value - reference) for value in series))

    return {
        "bedslope_by_river": bedslope_by_river,
        "max_time_variation": max_time_variation,
    }


def load_metric_series(metric_name: str, cases: list[str]) -> dict[str, dict[str, Any]]:
    filename = METRIC_FILES[metric_name]
    result: dict[str, dict[str, Any]] = {}
    for case in cases:
        path = RUNS_ROOT / case / "output" / "ftbug.out" / filename
        result[case] = parse_series_file(path)
    ensure_aligned(metric_name, result, cases)
    return result


def load_bedslope_summary(cases: list[str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for case in cases:
        path = RUNS_ROOT / case / "output" / "ftbug.out" / ".diagriv"
        summary[case] = parse_diagriv_bedslopes(path)
    return summary


def ensure_aligned(metric_name: str, series_by_case: dict[str, dict[str, Any]], cases: list[str]) -> None:
    reference = series_by_case[cases[0]]
    ref_times = reference["times"]
    ref_shape = reference["values"].shape

    for case in cases[1:]:
        current = series_by_case[case]
        if current["values"].shape != ref_shape:
            raise ValueError(
                f"{metric_name}: shape mismatch for {case}: {current['values'].shape} != {ref_shape}"
            )
        if not np.allclose(current["times"], ref_times, rtol=0.0, atol=1e-12):
            raise ValueError(f"{metric_name}: timestep mismatch for {case}")


def river_labels(n_rivers: int) -> list[str]:
    return [f"R{idx}" for idx in range(1, n_rivers + 1)]


def nice_days_ticks(max_days: float) -> np.ndarray:
    upper = max(1, math.ceil(max_days))
    if upper <= 5:
        step = 1
    elif upper <= 10:
        step = 2
    else:
        step = 5
    ticks = np.arange(0, upper + 0.01, step, dtype=float)
    if ticks[-1] < max_days:
        ticks = np.append(ticks, upper)
    return ticks


def format_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "0"
    abs_value = abs(value)
    if abs_value >= 1e4 or abs_value < 1e-3:
        return f"{value:.1e}"
    if abs_value >= 100:
        return f"{value:.0f}"
    if abs_value >= 1:
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{value:.4f}".rstrip("0").rstrip(".")


def format_relative_annotation(value: float) -> str:
    if value >= 0.01:
        return f"{value:.2%}"
    if value >= 1e-4:
        return f"{value:.3%}"
    return f"{value:.2e}"


def min_positive_value(*arrays: np.ndarray, fallback: float = 1e-12) -> float:
    minima: list[float] = []
    for array in arrays:
        positive = np.asarray(array, dtype=float)
        positive = positive[positive > 0.0]
        if positive.size:
            minima.append(float(np.min(positive)))
    if not minima:
        return fallback
    return min(minima)


def add_shared_legend(fig: plt.Figure) -> None:
    handles = [
        Line2D([0], [0], color=CASE_STYLES[case]["color"], linestyle=CASE_STYLES[case]["linestyle"],
               linewidth=CASE_STYLES[case]["linewidth"], label=CASE_STYLES[case]["label"])
        for case in CASE_ORDER
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.5, 0.985),
    )


def add_qdown_shared_legend(fig: plt.Figure) -> None:
    handles = [
        Line2D(
            [0],
            [0],
            color=QDOWN_RAW_STYLES[case]["color"],
            linestyle=QDOWN_RAW_STYLES[case]["linestyle"],
            linewidth=QDOWN_RAW_STYLES[case]["linewidth"],
            label=QDOWN_RAW_STYLES[case]["label"],
        )
        for case in CASE_ORDER
    ]
    handles.extend(
        Line2D(
            [0],
            [0],
            color=QDOWN_DIFF_STYLES[key]["color"],
            linestyle=QDOWN_DIFF_STYLES[key]["linestyle"],
            linewidth=QDOWN_DIFF_STYLES[key]["linewidth"],
            label=QDOWN_DIFF_STYLES[key]["label"],
        )
        for key in QDOWN_DIFF_PLOT_ORDER
    )
    handles.extend(
        [
            Line2D([0], [0], color="0.35", linestyle="--", linewidth=1.2, label="noise floor"),
            Line2D([0], [0], color="0.35", linestyle=":", linewidth=1.2, label="1% reference"),
        ]
    )
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=6,
        frameon=False,
        bbox_to_anchor=(0.5, 0.972),
        columnspacing=1.3,
        handlelength=2.8,
    )


def plot_qrivdown_five_case_figure(
    series_by_case: dict[str, dict[str, Any]], noise_floor: float, output_path: Path
) -> None:
    reference = series_by_case[CASE_ORDER[0]]
    times_days = reference["times"] / (60.0 * 24.0)
    n_rivers = reference["n_rivers"]
    x_limit = math.ceil(float(times_days[-1]))
    x_ticks = nice_days_ticks(float(times_days[-1]))
    safe_noise_floor = max(float(noise_floor), 1e-12)

    for river_idx, title in QDOWN_REPRESENTATIVE_RIVERS:
        if river_idx >= n_rivers:
            raise ValueError(f"Representative river {title} is missing; only found {n_rivers} rivers")

    fig, axes = plt.subplots(3, 3, figsize=(18, 14), sharex=True)

    for col_idx, (river_idx, title) in enumerate(QDOWN_REPRESENTATIVE_RIVERS):
        raw_ax = axes[0, col_idx]
        abs_ax = axes[1, col_idx]
        rel_ax = axes[2, col_idx]

        raw_series = {
            case: np.asarray(series_by_case[case]["values"][:, river_idx], dtype=float)
            for case in CASE_ORDER
        }
        truth = raw_series["truth"]
        truth_abs = np.abs(truth)
        abs_diff_series = {
            "old-truth": np.abs(raw_series["old"] - truth),
            "fixed-truth": np.abs(raw_series["fixed"] - truth),
            "slope-only-truth": np.abs(raw_series["slope-only"] - truth),
            "point-only-truth": np.abs(raw_series["point-only"] - truth),
        }
        rel_diff_series = {
            key: np.divide(
                values,
                truth_abs,
                out=np.zeros_like(values),
                where=truth_abs > 0.0,
            )
            for key, values in abs_diff_series.items()
        }

        raw_ymax = max(float(np.max(values)) for values in raw_series.values())
        raw_ymin = min_positive_value(*raw_series.values(), fallback=safe_noise_floor)
        for case in QDOWN_RAW_PLOT_ORDER:
            style = QDOWN_RAW_STYLES[case]
            raw_ax.plot(
                times_days,
                raw_series[case],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                zorder=style["zorder"],
            )
        raw_ax.set_title(title)
        raw_ax.set_yscale("log", nonpositive="clip")
        raw_ax.set_ylim(raw_ymin * 0.8, raw_ymax * 1.2)

        abs_ymax = max(max(float(np.max(values)) for values in abs_diff_series.values()), safe_noise_floor)
        abs_ymin = min_positive_value(
            np.asarray([safe_noise_floor], dtype=float),
            *abs_diff_series.values(),
            fallback=safe_noise_floor,
        )
        for key in QDOWN_DIFF_PLOT_ORDER:
            style = QDOWN_DIFF_STYLES[key]
            abs_ax.plot(
                times_days,
                abs_diff_series[key],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                zorder=style["zorder"],
            )
        abs_ax.axhline(safe_noise_floor, color="0.35", linestyle="--", linewidth=1.2, zorder=1)
        abs_ax.set_yscale("log", nonpositive="clip")
        abs_ax.set_ylim(abs_ymin * 0.8, abs_ymax * 1.2)

        rel_ymax = max(
            max(float(np.max(values)) for values in rel_diff_series.values()),
            RELATIVE_DIFF_REFERENCE,
        )
        rel_ymin = min_positive_value(
            np.asarray([RELATIVE_DIFF_REFERENCE], dtype=float),
            *rel_diff_series.values(),
            fallback=1e-12,
        )
        for key in QDOWN_DIFF_PLOT_ORDER:
            style = QDOWN_DIFF_STYLES[key]
            rel_ax.plot(
                times_days,
                rel_diff_series[key],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                zorder=style["zorder"],
            )
        rel_ax.axhline(RELATIVE_DIFF_REFERENCE, color="0.35", linestyle=":", linewidth=1.2, zorder=1)
        rel_ax.set_yscale("log", nonpositive="clip")
        rel_ax.set_ylim(rel_ymin * 0.8, rel_ymax * 1.2)
        rel_ax.text(
            0.03,
            0.97,
            "\n".join(
                [
                    f"max old: {format_relative_annotation(float(np.max(rel_diff_series['old-truth'])))}",
                    f"max fixed: {format_relative_annotation(float(np.max(rel_diff_series['fixed-truth'])))}",
                ]
            ),
            transform=rel_ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
        )

        for row_ax in (raw_ax, abs_ax, rel_ax):
            row_ax.set_xlim(0.0, x_limit)
            row_ax.set_xticks(x_ticks)
            row_ax.grid(True, which="major", alpha=0.28)
            row_ax.grid(True, which="minor", alpha=0.12)

    axes[0, 0].set_ylabel("QrivDown (m$^3$/day)")
    axes[1, 0].set_ylabel(r"|$\Delta Q$| (m$^3$/day)")
    axes[2, 0].set_ylabel(r"Relative |$\Delta Q / Q$|")

    fig.suptitle("QrivDown: 5-case Ablation - Raw + Absolute + Relative Differences", fontsize=16, y=0.994)
    fig.supxlabel("Time (days)", y=0.035)
    add_qdown_shared_legend(fig)
    fig.tight_layout(rect=(0.04, 0.05, 1.0, 0.88))
    fig.savefig(output_path, dpi=FIG_DPI)
    plt.close(fig)


def plot_time_series_grid(
    metric_name: str,
    series_by_case: dict[str, dict[str, Any]],
    title: str,
    ylabel: str,
    output_path: Path,
    log_y: bool,
) -> None:
    reference = series_by_case[CASE_ORDER[0]]
    times_days = reference["times"] / (60.0 * 24.0)
    n_rivers = reference["n_rivers"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 10), sharex=True)
    axes_flat = axes.ravel()

    for river_idx in range(n_rivers):
        ax = axes_flat[river_idx]
        ymax = 0.0
        ymin_positive = np.inf

        for case in CASE_ORDER:
            values = series_by_case[case]["values"][:, river_idx]
            style = CASE_STYLES[case]
            ax.plot(
                times_days,
                values,
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=style["linewidth"],
                zorder=style["zorder"],
            )
            ymax = max(ymax, float(np.max(values)))
            positive = values[values > 0]
            if positive.size:
                ymin_positive = min(ymin_positive, float(np.min(positive)))

        ax.set_title(f"River R{river_idx + 1}")
        ax.set_xlim(0.0, math.ceil(float(times_days[-1])))
        ax.set_xticks(nice_days_ticks(float(times_days[-1])))
        ax.grid(True, which="major", alpha=0.28)

        if log_y:
            ax.set_yscale("log", nonpositive="clip")
            if np.isfinite(ymin_positive) and ymax > 0.0:
                ax.set_ylim(ymin_positive * 0.8, ymax * 1.2)
        else:
            ax.set_ylim(0.0, ymax * 1.08 if ymax > 0 else 1.0)

    for extra_ax in axes_flat[n_rivers:]:
        extra_ax.set_visible(False)

    fig.suptitle(title, fontsize=16, y=0.995)
    fig.supxlabel("Time (days)", y=0.03)
    fig.supylabel(ylabel, x=0.04)
    add_shared_legend(fig)
    fig.tight_layout(rect=(0.04, 0.04, 1.0, 0.93))
    fig.savefig(output_path, dpi=FIG_DPI)
    plt.close(fig)


def build_pairwise_matrix(metric_report: dict[str, Any], cases: list[str], field: str) -> np.ndarray:
    matrix = np.zeros((len(cases), len(cases)), dtype=float)
    for row_idx, case_a in enumerate(cases):
        for col_idx, case_b in enumerate(cases):
            if case_a == case_b:
                matrix[row_idx, col_idx] = 0.0
                continue
            value = metric_report[f"{case_a}__vs__{case_b}"].get(field)
            matrix[row_idx, col_idx] = 0.0 if value is None else float(value)
    return matrix


def highlight_pairs(ax: plt.Axes, cases: list[str]) -> None:
    for (case_a, case_b), info in HIGHLIGHT_PAIRS.items():
        for row_case, col_case in [(case_a, case_b), (case_b, case_a)]:
            row_idx = cases.index(row_case)
            col_idx = cases.index(col_case)
            ax.add_patch(
                Rectangle(
                    (col_idx - 0.5, row_idx - 0.5),
                    1.0,
                    1.0,
                    fill=False,
                    edgecolor=info["color"],
                    linewidth=2.2,
                )
            )


def plot_heatmap_panel(
    ax: plt.Axes,
    matrix: np.ndarray,
    cases: list[str],
    title: str,
    cmap: str = "YlOrRd",
) -> Any:
    image = ax.imshow(matrix, cmap=cmap, aspect="equal")
    ax.set_title(title)
    ax.set_xticks(np.arange(len(cases)))
    ax.set_yticks(np.arange(len(cases)))
    ax.set_xticklabels(cases, rotation=35, ha="right")
    ax.set_yticklabels(cases)
    ax.set_xlabel("case_b")
    ax.set_ylabel("case_a")
    ax.set_xticks(np.arange(-0.5, len(cases), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(cases), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    vmax = float(np.nanmax(matrix)) if np.isfinite(np.nanmax(matrix)) else 0.0
    threshold = 0.55 * vmax if vmax > 0 else 0.0
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            value = matrix[row_idx, col_idx]
            text_color = "white" if value >= threshold and vmax > 0 else "black"
            ax.text(
                col_idx,
                row_idx,
                format_value(float(value)),
                ha="center",
                va="center",
                color=text_color,
                fontsize=8,
                fontweight="semibold" if row_idx != col_idx else "normal",
            )

    highlight_pairs(ax, cases)
    return image


def plot_pairwise_heatmaps(report: dict[str, Any], output_path: Path) -> None:
    cases = report["cases"]
    metric_data = report["metrics"]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    panels = [
        ("rivqdown", "max_abs_diff", "QrivDown max abs diff (m$^3$/min)"),
        ("rivystage", "max_abs_diff", "Stage max abs diff (m)"),
        ("rivqdown", "max_rel_diff", "QrivDown max relative diff"),
        ("rivystage", "max_rel_diff", "Stage max relative diff"),
    ]

    for ax, (metric_name, field, panel_title) in zip(axes.ravel(), panels):
        matrix = build_pairwise_matrix(metric_data[metric_name], cases, field)
        image = plot_heatmap_panel(ax, matrix, cases, panel_title)
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        colorbar.ax.tick_params(labelsize=8)

    legend_handles = [
        Patch(facecolor="none", edgecolor=info["color"], linewidth=2.2, label=info["label"])
        for info in HIGHLIGHT_PAIRS.values()
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 0.01),
    )
    fig.suptitle("Pairwise Differences Across 5 Cases", fontsize=16, y=0.99)
    fig.text(
        0.5,
        0.955,
        "Rows are case_a, columns are case_b. Relative diff uses case_b as denominator.",
        ha="center",
        va="top",
        fontsize=10,
    )
    fig.tight_layout(rect=(0.02, 0.06, 1.0, 0.93))
    fig.savefig(output_path, dpi=FIG_DPI)
    plt.close(fig)


def plotting_floor(values: list[float]) -> float:
    positive = [value for value in values if value > 0]
    if not positive:
        return 1e-12
    return min(positive) / 3.0


def plot_acceptance_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    criteria_ids = ["A", "B", "C", "D"]
    metrics = [("rivqdown", "", -0.18), ("rivystage", "//", 0.18)]
    groups = np.arange(len(criteria_ids), dtype=float)
    width = 0.30

    positives: list[float] = []
    for criterion_id in criteria_ids:
        criterion = report["criteria"][criterion_id]
        for metric_name, _, _ in metrics:
            entry = criterion["per_metric"][metric_name]
            positives.extend(
                [
                    float(entry["diff"]),
                    float(entry["threshold"]),
                    float(report["noise_floor"][metric_name]["noise"]),
                ]
            )
    floor = plotting_floor(positives)

    ymax = 0.0
    for group_idx, criterion_id in enumerate(criteria_ids):
        criterion = report["criteria"][criterion_id]
        for metric_name, hatch, offset in metrics:
            entry = criterion["per_metric"][metric_name]
            actual = float(entry["diff"])
            threshold = float(entry["threshold"])
            noise = float(report["noise_floor"][metric_name]["noise"])
            bar_top = max(actual, floor)
            bar_height = max(bar_top - floor, floor * 0.25)
            x = groups[group_idx] + offset
            color = "#2ca02c" if entry["passed"] else "#d62728"

            ax.bar(
                x,
                bar_height,
                width=width,
                bottom=floor,
                color=color,
                edgecolor="black",
                hatch=hatch,
                linewidth=0.9,
                zorder=3,
            )
            ax.hlines(threshold, x - width / 2.0, x + width / 2.0, color="black", linewidth=2.0, zorder=4)
            ax.scatter(x, noise, s=36, facecolors="white", edgecolors="black", linewidths=1.0, zorder=5)
            ymax = max(ymax, bar_top, threshold, noise)

            if actual == 0.0:
                ax.text(x, floor * 1.28, "0", ha="center", va="bottom", fontsize=8)

    ax.set_yscale("log")
    ax.set_ylim(floor, ymax * 2.5)
    ax.set_xticks(groups)
    ax.set_xticklabels(criteria_ids)
    ax.set_title("Criteria A-D: Actual Diff vs Threshold")
    ax.set_ylabel("Difference (log scale)")
    ax.grid(True, which="major", axis="y", alpha=0.3)
    ax.text(
        0.01,
        0.98,
        "Green/red bars = actual diff, black ticks = threshold, white dots = noise floor\nZero diffs are shown at the plotting floor for visibility.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9, "edgecolor": "#cccccc"},
    )

    legend_handles = [
        Patch(facecolor="#2ca02c", edgecolor="black", label="PASS"),
        Patch(facecolor="#d62728", edgecolor="black", label="FAIL"),
        Patch(facecolor="white", edgecolor="black", label="QrivDown"),
        Patch(facecolor="white", edgecolor="black", hatch="//", label="River stage"),
        Line2D([0], [0], color="black", linewidth=2.0, label="Threshold"),
        Line2D(
            [0],
            [0],
            marker="o",
            markersize=6,
            markerfacecolor="white",
            markeredgecolor="black",
            linewidth=0,
            label="Noise floor",
        ),
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=False, ncol=2)


def plot_bedslope_panel(ax: plt.Axes, bedslope_summary: dict[str, dict[str, Any]], cases: list[str]) -> None:
    rivers = sorted(bedslope_summary[cases[0]]["bedslope_by_river"])
    positions = np.arange(len(rivers), dtype=float)
    width = 0.15

    for case_idx, case in enumerate(cases):
        offset = (case_idx - (len(cases) - 1) / 2.0) * width
        values = [bedslope_summary[case]["bedslope_by_river"][river] for river in rivers]
        style = CASE_STYLES[case]
        ax.bar(
            positions + offset,
            values,
            width=width,
            color=style["color"],
            edgecolor="black",
            linewidth=0.8,
            label=style["label"],
            alpha=0.92,
        )

    ax.axhline(MIN_RIV_SLOPE, color="gray", linestyle="--", linewidth=1.6, label="MINRIVSLOPE = 4e-4")
    ax.set_yscale("log")
    ax.set_title("BedSlope Used by Solver (.diagriv)")
    ax.set_ylabel("BedSlope")
    ax.set_xticks(positions)
    ax.set_xticklabels(river_labels(len(rivers)))
    ax.legend(loc="upper left", ncol=3, frameon=False)
    ax.grid(True, which="major", axis="y", alpha=0.3)


def build_summary_text(report: dict[str, Any]) -> str:
    criteria = report["criteria"]
    q_noise = report["noise_floor"]["rivqdown"]["noise"]
    stage_noise = report["noise_floor"]["rivystage"]["noise"]

    def pair(metric: str, case_a: str, case_b: str) -> float:
        return float(report["metrics"][metric][f"{case_a}__vs__{case_b}"]["max_abs_diff"])

    lines = [
        f"Overall: {'PASS' if report['all_passed'] else 'FAIL'}",
        "",
        "Criteria A-F",
        f"A {'PASS' if criteria['A']['passed'] else 'FAIL'}  old vs slope-only",
        f"   qdown={criteria['A']['per_metric']['rivqdown']['diff']:.1e}  stage={criteria['A']['per_metric']['rivystage']['diff']:.1e}",
        f"B {'PASS' if criteria['B']['passed'] else 'FAIL'}  fixed vs truth",
        f"   qdown={criteria['B']['per_metric']['rivqdown']['diff']:.1e}  stage={criteria['B']['per_metric']['rivystage']['diff']:.1e}",
        f"C {'PASS' if criteria['C']['passed'] else 'FAIL'}  point-only vs fixed",
        f"   qdown={criteria['C']['per_metric']['rivqdown']['diff']:.1e}  stage={criteria['C']['per_metric']['rivystage']['diff']:.1e}",
        f"D {'PASS' if criteria['D']['passed'] else 'FAIL'}  old vs fixed",
        f"   qdown={criteria['D']['per_metric']['rivqdown']['diff']:.1e}  stage={criteria['D']['per_metric']['rivystage']['diff']:.1e}",
        f"E {'PASS' if criteria['E']['passed'] else 'FAIL'}  truth final QrivDown={criteria['E']['truth_case_final_qrivdown']:.3f}",
        f"F {'PASS' if criteria['F']['passed'] else 'FAIL'}  actual={criteria['F']['actual_ratio']:.3f}, predicted={criteria['F']['predicted_ratio']:.3f}",
        f"   range=[{criteria['F']['acceptable_range'][0]:.2f}, {criteria['F']['acceptable_range'][1]:.2f}]",
        "",
        "Noise floor",
        f"QrivDown  {q_noise:.2e} m^3/min",
        f"Stage     {stage_noise:.2e} m",
        "",
        "Key max abs diffs",
        f"old vs slope-only : q={pair('rivqdown', 'old', 'slope-only'):.1e}, y={pair('rivystage', 'old', 'slope-only'):.1e}",
        f"point vs fixed    : q={pair('rivqdown', 'point-only', 'fixed'):.1e}, y={pair('rivystage', 'point-only', 'fixed'):.1e}",
        f"fixed vs truth    : q={pair('rivqdown', 'fixed', 'truth'):.1e}, y={pair('rivystage', 'fixed', 'truth'):.1e}",
        f"old vs fixed      : q={pair('rivqdown', 'old', 'fixed'):.1e}, y={pair('rivystage', 'old', 'fixed'):.1e}",
    ]
    return "\n".join(lines)


def plot_summary_text(ax: plt.Axes, report: dict[str, Any]) -> None:
    ax.set_title("Key Numbers")
    ax.axis("off")
    ax.text(
        0.02,
        0.98,
        build_summary_text(report),
        ha="left",
        va="top",
        fontsize=9.5,
        family="monospace",
        bbox={"boxstyle": "round", "facecolor": "#f8f8f8", "edgecolor": "#cccccc"},
    )


def plot_acceptance_dashboard(
    report: dict[str, Any], bedslope_summary: dict[str, dict[str, Any]], output_path: Path
) -> None:
    fig = plt.figure(figsize=(16, 10))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.25, 1.0], height_ratios=[1.0, 1.0])
    ax_accept = fig.add_subplot(grid[:, 0])
    ax_bedslope = fig.add_subplot(grid[0, 1])
    ax_text = fig.add_subplot(grid[1, 1])

    plot_acceptance_panel(ax_accept, report)
    plot_bedslope_panel(ax_bedslope, bedslope_summary, report["cases"])
    plot_summary_text(ax_text, report)

    fig.suptitle("Acceptance Criteria Summary Dashboard", fontsize=16, y=0.995)
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.96))
    fig.savefig(output_path, dpi=FIG_DPI)
    plt.close(fig)


def main() -> int:
    configure_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report = load_report(REPORT_PATH)
    cases = report.get("cases", CASE_ORDER)
    metric_series = {metric_name: load_metric_series(metric_name, cases) for metric_name in METRIC_FILES}
    bedslope_summary = load_bedslope_summary(cases)

    plot_qrivdown_five_case_figure(
        metric_series["rivqdown"],
        float(report["noise_floor"]["rivqdown"]["noise"]),
        OUTPUT_DIR / "fig13_qdown_5case.png",
    )
    plot_time_series_grid(
        "rivystage",
        metric_series["rivystage"],
        "River Stage: 5-case Ablation Comparison",
        "Water depth (m)",
        OUTPUT_DIR / "fig14_stage_5case.png",
        log_y=False,
    )
    plot_pairwise_heatmaps(report, OUTPUT_DIR / "fig15_pairwise_diff.png")
    plot_acceptance_dashboard(report, bedslope_summary, OUTPUT_DIR / "fig16_acceptance_summary.png")

    print(f"Saved {OUTPUT_DIR / 'fig13_qdown_5case.png'}")
    print(f"Saved {OUTPUT_DIR / 'fig14_stage_5case.png'}")
    print(f"Saved {OUTPUT_DIR / 'fig15_pairwise_diff.png'}")
    print(f"Saved {OUTPUT_DIR / 'fig16_acceptance_summary.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

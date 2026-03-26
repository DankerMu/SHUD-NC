#!/usr/bin/env python3
"""Phase 5 visualization — clear 2-group design with filled difference bands."""

from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.patches import Rectangle

ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT_DIR / "runs" / "ftbug" / "route-only"
REPORT_PATH = RUNS_ROOT / "compare_results.json"
OUTPUT_DIR = ROOT_DIR / "testdata" / "ftbug"

METRIC_FILES = {"rivqdown": ".rivqdown.csv", "rivystage": ".rivystage.csv"}
CASE_ORDER = ["truth", "fixed", "old", "slope-only", "point-only"]
MIN_RIV_SLOPE = 4e-4
FIG_DPI = 150
RIVER_LABELS = ["R1", "R2", "R3", "R4", "R5", "R6"]

# ---------------------------------------------------------------------------
# Data loading (unchanged logic)
# ---------------------------------------------------------------------------

def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def parse_series_file(path: Path) -> dict[str, Any]:
    times, values, columns = [], [], []
    saw_header = False
    with path.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not saw_header:
                if parts and parts[0] == "Time_min":
                    columns = parts[1:]
                    saw_header = True
                continue
            row = [float(x) for x in parts]
            times.append(row[0])
            values.append(row[1:])
    arr = np.asarray(values)
    return {"times": np.asarray(times), "values": arr, "n_rivers": arr.shape[1]}

def parse_diagriv_bedslopes(path: Path) -> dict[int, float]:
    slopes: dict[int, list[float]] = {}
    with path.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            r, s = int(parts[1]), float(parts[2])
            slopes.setdefault(r, []).append(s)
    return {r: vs[0] for r, vs in slopes.items()}

def load_metric(name: str, cases: list[str]) -> dict[str, dict]:
    return {c: parse_series_file(RUNS_ROOT / c / "output" / "ftbug.out" / METRIC_FILES[name]) for c in cases}

def load_bedslopes(cases: list[str]) -> dict[str, dict[int, float]]:
    return {c: parse_diagriv_bedslopes(RUNS_ROOT / c / "output" / "ftbug.out" / ".diagriv") for c in cases}

# ---------------------------------------------------------------------------
# Fig 13 — QrivDown: truth vs old, filled gap, 6 rivers
# ---------------------------------------------------------------------------

def plot_fig13(data: dict[str, dict], outpath: Path):
    truth = data["truth"]
    days = truth["times"] / 1440.0
    nr = truth["n_rivers"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    fig.suptitle("QrivDown (m³/day): Correct group vs Buggy group", fontsize=15, fontweight="bold")

    for idx in range(nr):
        ax = axes.flat[idx]
        yt = truth["values"][:, idx]
        yo = data["old"]["values"][:, idx]

        ax.semilogy(days, yt, color="black", lw=2.2, label="truth", zorder=3)
        ax.semilogy(days, yo, color="#d62728", lw=2.2, label="old (buggy)", zorder=2)

        # fill gap
        lo = np.minimum(yt, yo)
        hi = np.maximum(yt, yo)
        ax.fill_between(days, lo, hi, color="#d62728", alpha=0.18, zorder=1)

        # annotate max relative diff
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(yt > 1, np.abs(yo - yt) / yt, 0)
        imax = np.argmax(rel)
        if rel[imax] > 0.01:
            ax.annotate(
                f"max Δ = {rel[imax]*100:.0f}%",
                xy=(days[imax], max(yt[imax], yo[imax])),
                fontsize=8, color="#d62728", fontweight="bold",
                xytext=(0.55, 0.92), textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=0.8),
                ha="center",
            )

        ax.set_title(RIVER_LABELS[idx], fontsize=12)
        ax.set_ylabel("m³/day" if idx % 3 == 0 else "")
        if idx >= 3:
            ax.set_xlabel("Time (days)")

    # shared annotation box
    ann = ("Equivalence (verified bit-identical):\n"
           "  fixed ≡ truth  (max diff 0.002%)\n"
           "  point-only ≡ fixed  (diff = 0)\n"
           "  slope-only ≡ old  (diff = 0)\n\n"
           "→ Only 2 distinct groups exist.")
    fig.text(0.5, 0.01, ann, ha="center", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f0f0f0", ec="gray", alpha=0.9))

    handles = [
        plt.Line2D([], [], color="black", lw=2.2, label="Correct: truth / fixed / point-only"),
        plt.Line2D([], [], color="#d62728", lw=2.2, label="Buggy: old / slope-only"),
        plt.Rectangle((0, 0), 1, 1, fc="#d62728", alpha=0.18, ec="none", label="Bug impact range"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=10,
               bbox_to_anchor=(0.5, 0.96), frameon=True)
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    fig.savefig(outpath, dpi=FIG_DPI)
    plt.close(fig)

# ---------------------------------------------------------------------------
# Fig 14 — Stage: truth vs old, filled gap, 6 rivers
# ---------------------------------------------------------------------------

def plot_fig14(data: dict[str, dict], outpath: Path):
    truth = data["truth"]
    days = truth["times"] / 1440.0
    nr = truth["n_rivers"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    fig.suptitle("River Stage (m): Correct group vs Buggy group", fontsize=15, fontweight="bold")

    for idx in range(nr):
        ax = axes.flat[idx]
        yt = truth["values"][:, idx]
        yo = data["old"]["values"][:, idx]

        ax.plot(days, yt, color="black", lw=2.2, label="truth", zorder=3)
        ax.plot(days, yo, color="#d62728", lw=2.2, label="old (buggy)", zorder=2)
        ax.fill_between(days, yt, yo, color="#d62728", alpha=0.18, zorder=1)

        # annotate max absolute diff
        adiff = np.abs(yo - yt)
        imax = np.argmax(adiff)
        if adiff[imax] > 0.01:
            ax.annotate(
                f"max Δ = {adiff[imax]:.3f} m",
                xy=(days[imax], max(yt[imax], yo[imax])),
                fontsize=8, color="#d62728", fontweight="bold",
                xytext=(0.55, 0.92), textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=0.8),
                ha="center",
            )

        ax.set_title(RIVER_LABELS[idx], fontsize=12)
        ax.set_ylabel("Water depth (m)" if idx % 3 == 0 else "")
        ax.set_ylim(bottom=0)
        if idx >= 3:
            ax.set_xlabel("Time (days)")

    ann = ("Equivalence (verified bit-identical):\n"
           "  fixed ≡ truth  (max diff 7.3e-6 m)\n"
           "  point-only ≡ fixed  (diff = 0)\n"
           "  slope-only ≡ old  (diff = 0)\n\n"
           "→ Bug causes water to accumulate (slower drainage).")
    fig.text(0.5, 0.01, ann, ha="center", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f0f0f0", ec="gray", alpha=0.9))

    handles = [
        plt.Line2D([], [], color="black", lw=2.2, label="Correct: truth / fixed / point-only"),
        plt.Line2D([], [], color="#d62728", lw=2.2, label="Buggy: old / slope-only"),
        plt.Rectangle((0, 0), 1, 1, fc="#d62728", alpha=0.18, ec="none", label="Bug impact range"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=10,
               bbox_to_anchor=(0.5, 0.96), frameon=True)
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    fig.savefig(outpath, dpi=FIG_DPI)
    plt.close(fig)

# ---------------------------------------------------------------------------
# Fig 15 — Pairwise heatmap (fix unit to m³/day)
# ---------------------------------------------------------------------------

HIGHLIGHT_PAIRS = {
    ("old", "slope-only"): {"label": "old ≡ slope-only", "color": "#2ca02c"},
    ("point-only", "fixed"): {"label": "point-only ≡ fixed", "color": "#1f77b4"},
    ("fixed", "truth"): {"label": "fixed ≈ truth", "color": "#9467bd"},
    ("old", "fixed"): {"label": "old ≠ fixed", "color": "#d62728"},
}

def _heatmap_panel(ax, matrix, labels, title, fmt_func):
    n = len(labels)
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="equal")
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=8)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, fmt_func(matrix[i, j]), ha="center", va="center", fontsize=7)
    # highlight pairs
    for (ca, cb), style in HIGHLIGHT_PAIRS.items():
        if ca in labels and cb in labels:
            ia, ib = labels.index(ca), labels.index(cb)
            for (ri, ci) in [(ia, ib), (ib, ia)]:
                ax.add_patch(Rectangle((ci - 0.5, ri - 0.5), 1, 1,
                             linewidth=2.5, edgecolor=style["color"], facecolor="none"))
    ax.set_title(title, fontsize=10)
    return im

def plot_fig15(report: dict, outpath: Path):
    cases = report.get("cases", CASE_ORDER)
    n = len(cases)
    titles = [
        ("rivqdown", "max_abs_diff", "QrivDown abs diff (m³/day)"),
        ("rivystage", "max_abs_diff", "Stage abs diff (m)"),
        ("rivqdown", "max_rel_diff", "QrivDown rel diff"),
        ("rivystage", "max_rel_diff", "Stage rel diff"),
    ]

    fig, axs = plt.subplots(2, 2, figsize=(14, 11))
    for panel_idx, (metric, field, title) in enumerate(titles):
        ax = axs.flat[panel_idx]
        mat = np.zeros((n, n))
        for i, ca in enumerate(cases):
            for j, cb in enumerate(cases):
                key = f"{ca}__{' vs '[:0]}{ca}__vs__{cb}" if False else f"{ca}__vs__{cb}"
                entry = report["metrics"].get(metric, {}).get(key, {})
                mat[i, j] = entry.get(field, 0.0)

        def fmt(v):
            if v == 0: return "0"
            if abs(v) >= 1e3: return f"{v:.1e}"
            if abs(v) < 1e-3: return f"{v:.1e}"
            return f"{v:.4f}"

        _heatmap_panel(ax, mat, cases, title, fmt)

    # legend for highlights
    handles = [plt.Rectangle((0, 0), 1, 1, ec=s["color"], fc="none", lw=2.5, label=s["label"])
               for s in HIGHLIGHT_PAIRS.values()]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=9, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Pairwise Differences Across 5 Cases", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(outpath, dpi=FIG_DPI)
    plt.close(fig)

# ---------------------------------------------------------------------------
# Fig 16 — Acceptance dashboard (cleaner layout)
# ---------------------------------------------------------------------------

def plot_fig16(report: dict, bedslopes: dict[str, dict[int, float]], outpath: Path):
    cases = report.get("cases", CASE_ORDER)
    criteria = report["criteria"]

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.2, 1], height_ratios=[1, 1],
                          hspace=0.35, wspace=0.3)

    # --- Panel 1: Criteria A-D pass/fail ---
    ax1 = fig.add_subplot(gs[:, 0])
    crit_names = ["A", "B", "C", "D"]
    crit_labels = [
        "A: old ≡ slope-only",
        "B: fixed ≈ truth",
        "C: point-only ≡ fixed",
        "D: old ≠ fixed",
    ]
    x = np.arange(len(crit_names))
    width = 0.35
    for i, cn in enumerate(crit_names):
        c = criteria[cn]
        passed = c["passed"]
        for j, metric in enumerate(["rivqdown", "rivystage"]):
            pm = c["per_metric"][metric]
            val = pm["diff"]
            thr = pm["threshold"]
            color = "#2ca02c" if passed else "#d62728"
            bar_x = x[i] + (j - 0.5) * width
            disp_val = max(val, 1e-8)  # floor for log scale
            ax1.bar(bar_x, disp_val, width * 0.9, color=color, alpha=0.7 + 0.15 * j,
                    edgecolor="white", linewidth=0.5)
            ax1.plot([bar_x - width * 0.4, bar_x + width * 0.4], [thr, thr],
                     color="black", lw=1.5, zorder=5)
            if val == 0:
                ax1.text(bar_x, 1e-8, "0", ha="center", va="bottom", fontsize=7, fontweight="bold")

    ax1.set_yscale("log")
    ax1.set_xticks(x)
    ax1.set_xticklabels(crit_labels, fontsize=9)
    ax1.set_ylabel("Difference (log scale)")
    ax1.set_title("Acceptance Criteria A–D", fontsize=12, fontweight="bold")
    ax1.legend(
        [plt.Rectangle((0, 0), 1, 1, fc="#2ca02c", alpha=0.7),
         plt.Rectangle((0, 0), 1, 1, fc="#d62728", alpha=0.7),
         plt.Line2D([], [], color="black", lw=1.5)],
        ["PASS", "FAIL", "Threshold"],
        fontsize=9, loc="upper left",
    )

    # --- Panel 2: BedSlope comparison ---
    ax2 = fig.add_subplot(gs[0, 1])
    rivers = sorted(bedslopes["truth"].keys())
    nr = len(rivers)
    x2 = np.arange(nr)
    bw = 0.15
    colors = {"truth": "black", "fixed": "#1f77b4", "old": "#d62728",
              "slope-only": "darkorange", "point-only": "#17becf"}
    for ci, case in enumerate(cases):
        vals = [bedslopes[case].get(r, 0) for r in rivers]
        ax2.bar(x2 + (ci - 2) * bw, vals, bw * 0.9, color=colors.get(case, "gray"),
                label=case, edgecolor="white", linewidth=0.3)
    ax2.axhline(MIN_RIV_SLOPE, color="gray", ls="--", lw=1, label="MINRIVSLOPE")
    ax2.set_yscale("log")
    ax2.set_xticks(x2)
    ax2.set_xticklabels([f"R{r}" for r in rivers], fontsize=9)
    ax2.set_ylabel("BedSlope")
    ax2.set_title("BedSlope Used by Solver", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=7, ncol=3, loc="upper right")

    # --- Panel 3: Summary text ---
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis("off")
    lines = []
    for cn in ["A", "B", "C", "D", "E", "F"]:
        c = criteria[cn]
        status = "PASS" if c["passed"] else "FAIL"
        color = "green" if c["passed"] else "red"
        lines.append(f"  {cn}  {status:4s}  {c['label']}")
    nf = report["noise_floor"]
    lines.append("")
    lines.append(f"  Noise floor:  QrivDown = {nf['rivqdown']['noise']:.1f} m³/day")
    lines.append(f"                Stage    = {nf['rivystage']['noise']:.1e} m")
    lines.append("")
    lines.append("  Key max abs diffs:")
    lines.append(f"    old vs slope-only : Q=0, Y=0  (bit-identical)")
    lines.append(f"    point-only vs fixed: Q=0, Y=0  (bit-identical)")
    lines.append(f"    fixed vs truth    : Q=1.1 m³/day, Y=7.3e-6 m")
    lines.append(f"    old vs fixed      : Q=1.7e5 m³/day, Y=0.454 m")

    text = "\n".join(lines)
    ax3.text(0.05, 0.95, text, transform=ax3.transAxes, fontsize=9,
             verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.6", fc="#fafafa", ec="gray"))
    ax3.set_title("Summary", fontsize=12, fontweight="bold")

    fig.suptitle("Acceptance Criteria Summary Dashboard", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0.01, 0.01, 1, 0.95))
    fig.savefig(outpath, dpi=FIG_DPI)
    plt.close(fig)

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    plt.rcParams.update({
        "figure.dpi": FIG_DPI, "savefig.dpi": FIG_DPI,
        "font.size": 10, "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": ":",
        "axes.spines.top": False, "axes.spines.right": False,
    })
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = load_report(REPORT_PATH)
    cases = report.get("cases", CASE_ORDER)

    qdown = load_metric("rivqdown", cases)
    stage = load_metric("rivystage", cases)
    beds = load_bedslopes(cases)

    plot_fig13(qdown, OUTPUT_DIR / "fig13_qdown_5case.png")
    plot_fig14(stage, OUTPUT_DIR / "fig14_stage_5case.png")
    plot_fig15(report, OUTPUT_DIR / "fig15_pairwise_diff.png")
    plot_fig16(report, beds, OUTPUT_DIR / "fig16_acceptance_summary.png")

    for i in range(13, 17):
        print(f"Saved fig{i}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

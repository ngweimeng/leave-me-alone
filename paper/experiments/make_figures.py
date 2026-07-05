"""Render the paper's figures from ``paper/results/results.json``.

Outputs PDF (vector, for LaTeX) into ``paper/figures/``:
  - fig_scaling.pdf       : solve time vs problem size, per solver (log-y).
  - fig_alpha.pdf         : adjacency weight vs schedule shape (saturates).
  - fig_max_stretch.pdf   : max-stretch cap vs schedule shape (true dial).
  - fig_leverage.pdf      : longest achievable break across countries.

Usage:  python paper/experiments/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "paper" / "results" / "results.json"
FIGDIR = ROOT / "paper" / "figures"

# Consistent, colorblind-friendly palette and markers per solver.
STYLE = {
    "Xpress": ("#0072B2", "o"),
    "Gurobi": ("#D55E00", "s"),
    "SCIP": ("#009E73", "^"),
    "OR-Tools (CP-SAT)": ("#CC79A7", "D"),
}

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
    }
)


def fig_scaling(data: dict) -> None:
    sc = data["scaling"]
    horizons = sc["horizons"]
    xs = [h["num_variables"] for h in horizons]

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for solver in sc["solvers"]:
        color, marker = STYLE.get(solver, ("gray", "x"))
        px, py = [], []
        for h, x in zip(horizons, xs):
            s = h["solvers"].get(solver, {})
            if s.get("ok") and s.get("time_best_s") is not None:
                px.append(x)
                py.append(s["time_best_s"] * 1000.0)  # ms
        if px:
            ax.plot(px, py, marker=marker, color=color, label=solver, markersize=4.5)
    ax.set_xlabel("Number of variables")
    ax.set_ylabel("Best solve time (ms)")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="upper left")
    fig.savefig(str(FIGDIR / "fig_scaling.pdf"))
    plt.close(fig)
    print("wrote fig_scaling.pdf")


def fig_alpha(data: dict) -> None:
    rows = data["alpha_sensitivity"]["rows"]
    alphas = [r["alpha"] for r in rows]
    stretches = [r["num_stretches"] for r in rows]
    longest = [r["longest_stretch"] for r in rows]

    fig, ax1 = plt.subplots(figsize=(4.2, 3.0))
    x = list(range(len(alphas)))
    ax1.bar(
        [i - 0.2 for i in x],
        stretches,
        width=0.4,
        color="#0072B2",
        label="# break stretches",
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(a) for a in alphas])
    ax1.set_xlabel(r"Adjacency weight $\alpha$")
    ax1.set_ylabel("Number of break stretches", color="#0072B2")
    ax1.tick_params(axis="y", labelcolor="#0072B2")

    ax2 = ax1.twinx()
    ax2.bar(
        [i + 0.2 for i in x],
        longest,
        width=0.4,
        color="#D55E00",
        label="longest stretch",
    )
    ax2.set_ylabel("Longest stretch (days)", color="#D55E00")
    ax2.tick_params(axis="y", labelcolor="#D55E00")
    ax2.grid(False)
    fig.savefig(str(FIGDIR / "fig_alpha.pdf"))
    plt.close(fig)
    print("wrote fig_alpha.pdf")


def fig_max_stretch(data: dict) -> None:
    rows = data["max_stretch"]["rows"]
    labels = [
        "none" if r["max_stretch"] is None else str(r["max_stretch"]) for r in rows
    ]
    longest = [r["longest_stretch"] for r in rows]
    nstretch = [r["num_stretches"] for r in rows]

    fig, ax1 = plt.subplots(figsize=(4.2, 3.0))
    x = list(range(len(labels)))
    ax1.bar(
        [i - 0.2 for i in x],
        longest,
        width=0.4,
        color="#0072B2",
        label="longest stretch",
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_xlabel("Max-stretch cap $K$ (days)")
    ax1.set_ylabel("Longest stretch (days)", color="#0072B2")
    ax1.tick_params(axis="y", labelcolor="#0072B2")

    ax2 = ax1.twinx()
    ax2.bar(
        [i + 0.2 for i in x],
        nstretch,
        width=0.4,
        color="#D55E00",
        label="# stretches",
    )
    ax2.set_ylabel("Number of break stretches", color="#D55E00")
    ax2.tick_params(axis="y", labelcolor="#D55E00")
    ax2.grid(False)
    fig.savefig(str(FIGDIR / "fig_max_stretch.pdf"))
    plt.close(fig)
    print("wrote fig_max_stretch.pdf")


def fig_leverage(data: dict) -> None:
    rows = sorted(
        data["holiday_leverage"]["rows"],
        key=lambda r: r["longest_stretch"],
        reverse=True,
    )
    countries = [r["country"] for r in rows]
    longest = [r["longest_stretch"] for r in rows]

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.bar(countries, longest, color="#009E73")
    ax.set_xlabel("Country")
    ax.set_ylabel("Longest continuous break (days)")
    fig.savefig(str(FIGDIR / "fig_leverage.pdf"))
    plt.close(fig)
    print("wrote fig_leverage.pdf")


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(RESULTS.read_text())
    fig_scaling(data)
    fig_alpha(data)
    fig_max_stretch(data)
    fig_leverage(data)


if __name__ == "__main__":
    main()

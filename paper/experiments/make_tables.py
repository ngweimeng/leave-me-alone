"""Generate LaTeX table bodies from ``paper/results/results.json``.

Writes \\input-able fragments into ``paper/tables/`` so the numbers in the
paper are never hand-copied:
  - tab_comparison.tex : per-solver time/objective on the canonical instance.
  - tab_scaling.tex    : solve time vs horizon, with size-cap markers.
  - tab_alpha.tex      : adjacency-weight sensitivity.
  - tab_leverage.tex   : holiday leverage across countries.

Usage:  python paper/experiments/make_tables.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "paper" / "results" / "results.json"
TABDIR = ROOT / "paper" / "tables"


def _ms(x: float | None) -> str:
    return "---" if x is None else f"{x * 1000.0:.1f}"


def _esc(s: str) -> str:
    return s.replace("&", r"\&").replace("_", r"\_")


def _join(rows: list[str]) -> str:
    r"""Join row bodies (no trailing ``\\``) with a separator between them.

    A fragment that ends with ``\\`` immediately before ``\bottomrule`` in the
    \input-ing file triggers a "Misplaced \noalign" error (TeX's ``\\``
    look-ahead runs off the end of the inputted file). So we emit ``\\`` only
    *between* rows; ``main.tex`` supplies the final terminator after ``\input``.
    """
    return " \\\\\n".join(rows)


def tab_comparison(data: dict) -> str:
    rows = data["solver_comparison"]["rows"]
    lines = []
    for r in rows:
        obj = "---" if r["objective"] is None else f"{r['objective']:.1f}"
        lines.append(
            f"{_esc(r['solver'])} & {r['num_variables']} & "
            f"{r['num_constraints']} & {obj} & {_ms(r['time_best_s'])} & "
            f"{_ms(r['time_median_s'])}"
        )
    return _join(lines)


def tab_scaling(data: dict) -> str:
    sc = data["scaling"]
    solvers = sc["solvers"]
    lines = []
    for h in sc["horizons"]:
        cells = [f"{_esc(h['label'])}", str(h["days"]), str(h["num_variables"])]
        for s in solvers:
            entry = h["solvers"].get(s, {})
            if entry.get("ok"):
                t = _ms(entry["time_best_s"])
                # A '~' prefix flags a horizon not proved optimal in every run.
                if entry.get("proved_optimal") is False:
                    t = r"$\sim$" + t
                cells.append(t)
            else:
                # Mark a size-cap / license failure distinctly.
                cells.append(r"\textemdash")
        lines.append(" & ".join(cells))
    return _join(lines)


def tab_alpha(data: dict) -> str:
    rows = data["alpha_sensitivity"]["rows"]
    lines = []
    for r in rows:
        dist = ", ".join(str(x) for x in r["stretch_lengths"][:8])
        lines.append(
            f"{r['alpha']:.1f} & {r['num_break_days']} & {r['num_leave_days']} & "
            f"{r['num_stretches']} & {r['longest_stretch']} & {dist}"
        )
    return _join(lines)


def tab_max_stretch(data: dict) -> str:
    rows = data["max_stretch"]["rows"]
    lines = []
    for r in rows:
        cap = "none" if r["max_stretch"] is None else str(r["max_stretch"])
        dist = ", ".join(str(x) for x in r["stretch_lengths"][:8])
        lines.append(
            f"{cap} & {r['num_break_days']} & {r['num_leave_days']} & "
            f"{r['num_stretches']} & {r['longest_stretch']} & {dist}"
        )
    return _join(lines)


def tab_leverage(data: dict) -> str:
    rows = sorted(
        data["holiday_leverage"]["rows"],
        key=lambda r: r["longest_stretch"],
        reverse=True,
    )
    lines = []
    for r in rows:
        lines.append(
            f"{_esc(r['country'])} & {r['num_holidays']} & "
            f"{r['baseline_break_days']} & {r['num_break_days']} & "
            f"{r['extra_break_days']} & {r['longest_stretch']}"
        )
    return _join(lines)


def main() -> None:
    TABDIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(RESULTS.read_text())
    (TABDIR / "tab_comparison.tex").write_text(tab_comparison(data) + "\n")
    (TABDIR / "tab_scaling.tex").write_text(tab_scaling(data) + "\n")
    (TABDIR / "tab_alpha.tex").write_text(tab_alpha(data) + "\n")
    (TABDIR / "tab_max_stretch.tex").write_text(tab_max_stretch(data) + "\n")
    (TABDIR / "tab_leverage.tex").write_text(tab_leverage(data) + "\n")
    print("wrote 5 table fragments to", TABDIR)


if __name__ == "__main__":
    main()

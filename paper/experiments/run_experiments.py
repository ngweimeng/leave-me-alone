"""Reproducible experiment harness for the Leave-Me-Alone paper.

Runs every measurement the paper reports by calling the *same* solver layer the
Streamlit app uses (``app.services.solvers``). Output is a single JSON file
(``paper/results/results.json``) consumed by ``make_figures.py`` and the LaTeX
tables. Nothing here is hand-tuned: re-running regenerates all numbers.

Experiments
-----------
1. solver_comparison : one canonical instance, every backend; time + objective
                       + variable/constraint counts + schedule divergence.
2. scaling           : solve time vs horizon length (90 d .. 4 y); exposes the
                       Gurobi (2000) and Xpress (5000) free-license caps.
3. alpha_sensitivity : how the adjacency weight alpha reshapes the schedule
                       (break count, longest stretch) on a fixed instance ---
                       and why it saturates (alpha is a threshold, not a dial).
3b. max_stretch      : the max-stretch cap as the genuine length control that
                       alpha is not; sweeps the four UI preset caps.
4. holiday_leverage  : break-days-per-PTO-day across countries with different
                       public-holiday calendars.

Usage:  python paper/experiments/run_experiments.py [--repeats N]
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

# Make the project importable when run from anywhere.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.holiday_service import get_public_holiday_map  # noqa: E402
from app.services.solvers import (  # noqa: E402
    LeaveProblem,
    SolverConfig,
    available_solver_names,
    get_solver,
    run_benchmark,
    schedules_diverge,
)

RESULTS_DIR = ROOT / "paper" / "results"

# A canonical, reproducible instance used across several experiments.
CANON_COUNTRY = "US"
CANON_YEAR = 2026
CANON_PTO = 15
CANON_ALPHA = 1.5  # the "Recommended (Balanced Mix)" preset


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _date_range(start: date, end: date) -> list[date]:
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _holidays_for_years(country: str, years: range) -> list[date]:
    out: list[date] = []
    for y in years:
        out.extend(d for d, _name in get_public_holiday_map(country, y))
    return out


def _year_problem(country: str, year: int, pto: int, alpha: float) -> LeaveProblem:
    start, end = date(year, 1, 1), date(year, 12, 31)
    return LeaveProblem.of(
        date_range=_date_range(start, end),
        holidays=_holidays_for_years(country, range(year, year + 1)),
        leave_available=pto,
        adjacency_weight=alpha,
    )


def _is_optimal_status(status: str) -> bool:
    """Normalize each backend's 'proved optimal' status string."""
    s = (status or "").lower()
    # Xpress: 'mip_optimal' / 'optimal'; SCIP: 'optimal'; Gurobi: 'OPTIMAL';
    # CP-SAT: 'OPTIMAL' (vs 'FEASIBLE' when only a time-limited solution).
    return "optimal" in s


def _stretch_stats(break_days: list[date]) -> dict:
    """Number of separate break stretches and the longest one (in days)."""
    if not break_days:
        return {"num_stretches": 0, "longest_stretch": 0, "stretch_lengths": []}
    days = sorted(break_days)
    lengths, cur = [], 1
    for prev, nxt in zip(days, days[1:]):
        if (nxt - prev).days == 1:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)
    return {
        "num_stretches": len(lengths),
        "longest_stretch": max(lengths),
        "stretch_lengths": sorted(lengths, reverse=True),
    }


def _pick_reference_solver() -> str:
    """A backend with no size cap that always proves optimality (prefer SCIP)."""
    names = available_solver_names()
    return "SCIP" if "SCIP" in names else names[0]


def _timed_solve(
    name: str,
    problem: LeaveProblem,
    repeats: int,
    time_limit_s: float | None = None,
) -> dict:
    """Solve repeatedly; report best (min) wall time to reduce noise."""
    # threads=None lets each engine use its own default (matching how the app
    # deploys them). This matters for CP-SAT, whose strength is a parallel
    # portfolio of strategies; pinning it to one thread cripples it.
    cfg = SolverConfig(
        mip_gap=0.0, threads=None, verbose=False, time_limit_s=time_limit_s
    )
    times, last, proved = [], None, 0
    for _ in range(repeats):
        last = get_solver(name, cfg).solve(problem)
        times.append(last.stats.solve_time_s)
        proved += 1 if _is_optimal_status(last.stats.status) else 0
    s = last.stats
    stretch = _stretch_stats(last.solution.break_days)
    return {
        "solver": name,
        "status": s.status,
        "objective": s.objective,
        "time_best_s": min(times),
        "time_median_s": statistics.median(times),
        "proved_runs": proved,
        "total_runs": repeats,
        "num_variables": s.num_variables,
        "num_constraints": s.num_constraints,
        "num_break_days": s.num_break_days,
        "num_leave_days": s.num_leave_days,
        **stretch,
    }


# --------------------------------------------------------------------------- #
# Experiment 1 — solver comparison on a canonical instance
# --------------------------------------------------------------------------- #
def exp_solver_comparison(repeats: int) -> dict:
    problem = _year_problem(CANON_COUNTRY, CANON_YEAR, CANON_PTO, CANON_ALPHA)
    names = available_solver_names()
    rows = [_timed_solve(n, problem, repeats) for n in names]

    bench = run_benchmark(problem, SolverConfig(mip_gap=0.0, threads=None))
    signatures = {
        r.result.stats.solver: list(r.leave_signature)
        for r in bench
        if r.result.solution.found
    }
    return {
        "instance": {
            "country": CANON_COUNTRY,
            "year": CANON_YEAR,
            "pto": CANON_PTO,
            "alpha": CANON_ALPHA,
            "horizon_days": len(problem.date_range),
            "num_holidays": len(problem.holidays),
        },
        "rows": rows,
        "diverge": schedules_diverge(bench),
        "leave_signatures": signatures,
    }


# --------------------------------------------------------------------------- #
# Experiment 2 — scaling vs horizon length
# --------------------------------------------------------------------------- #
def exp_scaling(repeats: int, time_limit_s: float = 10.0) -> dict:
    # (label, number of days). PTO scales at ~25 days/year of horizon.
    horizons = [
        ("3 months", 90),
        ("6 months", 182),
        ("1 year", 365),
        ("2 years", 730),
        ("3 years", 1095),
        ("4 years", 1460),
    ]
    names = available_solver_names()
    start = date(2026, 1, 1)
    out = []
    for label, days in horizons:
        end = start + timedelta(days=days - 1)
        years = range(start.year, end.year + 1)
        pto = max(1, round(25 * days / 365))
        problem = LeaveProblem.of(
            date_range=_date_range(start, end),
            holidays=_holidays_for_years(CANON_COUNTRY, years),
            leave_available=pto,
            adjacency_weight=CANON_ALPHA,
        )
        entry = {
            "label": label,
            "days": days,
            "pto": pto,
            "num_variables": problem.num_variables,
            "solvers": {},
        }
        for n in names:
            try:
                # A time limit bounds wall-clock; a backend that hits it is
                # recorded as not having *proved* optimality. Repeats capture
                # proof-time variance (notably for CP-SAT's parallel portfolio).
                r = _timed_solve(n, problem, repeats, time_limit_s=time_limit_s)
                entry["solvers"][n] = {
                    "time_best_s": r["time_best_s"],
                    "time_median_s": r["time_median_s"],
                    "objective": r["objective"],
                    "status": r["status"],
                    "proved_runs": r["proved_runs"],
                    "total_runs": r["total_runs"],
                    "proved_optimal": r["proved_runs"] == r["total_runs"],
                    "num_constraints": r["num_constraints"],
                    "ok": r["objective"] is not None,
                }
            except Exception as exc:
                # Free-license size caps surface here (Gurobi/Xpress).
                entry["solvers"][n] = {
                    "time_best_s": None,
                    "time_median_s": None,
                    "objective": None,
                    "status": f"CAP: {type(exc).__name__}",
                    "proved_runs": 0,
                    "total_runs": repeats,
                    "proved_optimal": False,
                    "num_constraints": None,
                    "ok": False,
                }
        out.append(entry)
    return {"horizons": out, "solvers": names, "time_limit_s": time_limit_s}


# --------------------------------------------------------------------------- #
# Experiment 3 — adjacency-weight (alpha) sensitivity
# --------------------------------------------------------------------------- #
def exp_alpha_sensitivity(repeats: int) -> dict:
    # The four UI presets plus alpha=0 (no adjacency reward) as a baseline.
    alphas = [0.0, 1.5, 2.0, 4.0, 8.0]
    name = _pick_reference_solver()  # uncapped, always proves optimality
    rows = []
    for a in alphas:
        problem = _year_problem(CANON_COUNTRY, CANON_YEAR, CANON_PTO, a)
        r = _timed_solve(name, problem, repeats)
        rows.append(
            {
                "alpha": a,
                "num_break_days": r["num_break_days"],
                "num_leave_days": r["num_leave_days"],
                "num_stretches": r["num_stretches"],
                "longest_stretch": r["longest_stretch"],
                "stretch_lengths": r["stretch_lengths"],
            }
        )
    return {"solver": name, "rows": rows, "pto": CANON_PTO, "year": CANON_YEAR}


# --------------------------------------------------------------------------- #
# Experiment 3b — max-stretch cap (the actual shape control)
# --------------------------------------------------------------------------- #
def exp_max_stretch(repeats: int) -> dict:
    # The cap values behind the four UI presets; None = uncapped ("Extended").
    caps = [4, 6, 9, None]
    name = _pick_reference_solver()
    rows = []
    for cap in caps:
        problem = LeaveProblem.of(
            date_range=_date_range(date(CANON_YEAR, 1, 1), date(CANON_YEAR, 12, 31)),
            holidays=_holidays_for_years(
                CANON_COUNTRY, range(CANON_YEAR, CANON_YEAR + 1)
            ),
            leave_available=CANON_PTO,
            adjacency_weight=CANON_ALPHA,
            max_stretch=cap,
        )
        r = _timed_solve(name, problem, repeats)
        rows.append(
            {
                "max_stretch": cap,
                "num_break_days": r["num_break_days"],
                "num_leave_days": r["num_leave_days"],
                "num_stretches": r["num_stretches"],
                "longest_stretch": r["longest_stretch"],
                "stretch_lengths": r["stretch_lengths"],
            }
        )
    return {
        "solver": name,
        "rows": rows,
        "pto": CANON_PTO,
        "year": CANON_YEAR,
        "country": CANON_COUNTRY,
    }


# --------------------------------------------------------------------------- #
# Experiment 4 — holiday leverage across countries
# --------------------------------------------------------------------------- #
def exp_holiday_leverage(repeats: int) -> dict:
    countries = ["US", "GB", "DE", "IN", "JP", "SG", "BR", "FR"]
    name = _pick_reference_solver()
    rows = []
    for c in countries:
        problem = _year_problem(c, CANON_YEAR, CANON_PTO, CANON_ALPHA)
        r = _timed_solve(name, problem, repeats)
        # Break days attributable beyond the no-PTO baseline (weekends+holidays).
        baseline_breaks = sum(
            1 for d in problem.date_range if problem.is_fixed_break(d)
        )
        # How many public holidays fall on a weekday (a weekend holiday is
        # "wasted" — it would have been a break anyway). This, not the raw
        # holiday count, drives how much structure PTO can exploit.
        weekday_holidays = sum(
            1 for d in problem.holidays if d.weekday() < 5 and d in problem.date_range
        )
        rows.append(
            {
                "country": c,
                "num_holidays": len(problem.holidays),
                "weekday_holidays": weekday_holidays,
                "baseline_break_days": baseline_breaks,
                "num_break_days": r["num_break_days"],
                "num_leave_days": r["num_leave_days"],
                "extra_break_days": r["num_break_days"] - baseline_breaks,
                "num_stretches": r["num_stretches"],
                "longest_stretch": r["longest_stretch"],
            }
        )
    return {"solver": name, "pto": CANON_PTO, "year": CANON_YEAR, "rows": rows}


# --------------------------------------------------------------------------- #
def _solver_versions() -> dict:
    out = {}
    try:
        import xpress

        out["Xpress"] = getattr(xpress, "__version__", "unknown")
    except Exception:
        pass
    try:
        import gurobipy

        out["Gurobi"] = ".".join(map(str, gurobipy.gurobi.version()))
    except Exception:
        pass
    try:
        import pyscipopt

        out["SCIP (pyscipopt)"] = getattr(pyscipopt, "__version__", "unknown")
    except Exception:
        pass
    try:
        import ortools

        out["OR-Tools"] = getattr(ortools, "__version__", "unknown")
    except Exception:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument(
        "--scaling-time-limit",
        type=float,
        default=10.0,
        help="Per-solver wall-clock cap in the scaling experiment (seconds).",
    )
    args = ap.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Available solvers: {available_solver_names()}")
    print(f"Repeats per timing: {args.repeats}")

    results = {
        "meta": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor() or platform.machine(),
            "repeats": args.repeats,
            "solver_versions": _solver_versions(),
        },
        "solver_comparison": exp_solver_comparison(args.repeats),
        "scaling": exp_scaling(args.repeats, time_limit_s=args.scaling_time_limit),
        "alpha_sensitivity": exp_alpha_sensitivity(args.repeats),
        "max_stretch": exp_max_stretch(args.repeats),
        "holiday_leverage": exp_holiday_leverage(args.repeats),
    }

    out_path = RESULTS_DIR / "results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

from datetime import timedelta

from app.services.solvers import (
    LeaveProblem,
    SolverConfig,
    get_solver,
    run_benchmark,
    schedules_diverge,
)


def _build_date_range(start, end):
    date_range = []
    cur = start
    while cur <= end:
        date_range.append(cur)
        cur += timedelta(days=1)
    return date_range


def _build_problem(
    start,
    end,
    public_holidays,
    leave_available,
    adjacency_weight,
    prebooked_days,
    max_stretch=None,
):
    return LeaveProblem.of(
        date_range=_build_date_range(start, end),
        holidays=public_holidays or [],
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=prebooked_days or [],
        max_stretch=max_stretch,
    )


def run_optimizer(
    start,
    end,
    public_holidays=None,
    blocked_days=None,
    leave_available=0,
    adjacency_weight: float = 1.0,
    prebooked_days=None,
    max_stretch=None,
    solver_name: str = "Xpress",
    config: SolverConfig | None = None,
):
    """Adapter between UI and the optimization model.

    Solves with the chosen backend and returns a result dict for the UI.
    """
    if public_holidays is None:
        public_holidays = []
    if prebooked_days is None:
        prebooked_days = []

    problem = _build_problem(
        start,
        end,
        public_holidays,
        leave_available,
        adjacency_weight,
        prebooked_days,
        max_stretch,
    )
    result = get_solver(solver_name, config).solve(problem)
    solution = result.solution

    return {
        "break_days": solution.break_days,
        "leave_days": solution.leave_days,
        "start": start,
        "end": end,
        "public_holidays": public_holidays,
        "prebooked_days": prebooked_days,
        "num_break_days": len(solution.break_days),
        "num_leave_days": len(solution.leave_days),
        "solver": result.stats.solver,
        "stats": result.stats,
    }


def benchmark_optimizer(
    start,
    end,
    public_holidays=None,
    leave_available=0,
    adjacency_weight: float = 1.0,
    prebooked_days=None,
    max_stretch=None,
    solver_names=None,
    config: SolverConfig | None = None,
):
    """Solve the same problem with multiple backends and compare.

    Returns the per-solver rows, whether their schedules diverge, and the
    primary result dict (first successful backend) for the UI to render.
    """
    problem = _build_problem(
        start,
        end,
        public_holidays,
        leave_available,
        adjacency_weight,
        prebooked_days,
        max_stretch,
    )
    rows = run_benchmark(problem, config=config, solver_names=solver_names)

    primary = None
    for row in rows:
        if row.result.solution.found:
            sol = row.result.solution
            primary = {
                "break_days": sol.break_days,
                "leave_days": sol.leave_days,
                "start": start,
                "end": end,
                "public_holidays": public_holidays or [],
                "prebooked_days": prebooked_days or [],
                "num_break_days": len(sol.break_days),
                "num_leave_days": len(sol.leave_days),
                "solver": row.result.stats.solver,
                "stats": row.result.stats,
            }
            break

    return {
        "rows": rows,
        "diverge": schedules_diverge(rows),
        "primary": primary,
    }

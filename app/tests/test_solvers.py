from datetime import date, timedelta

import pytest

from app.services.solvers import (
    LeaveProblem,
    SolverConfig,
    available_solver_classes,
    available_solver_names,
    get_solver,
    run_benchmark,
)


def _problem(days=31, leave=5, weight=1.5):
    start = date(2025, 1, 1)
    dr = [start + timedelta(days=i) for i in range(days)]
    return LeaveProblem.of(
        dr, {date(2025, 1, 1)}, leave_available=leave, adjacency_weight=weight
    )


def test_problem_validation():
    with pytest.raises(ValueError):
        LeaveProblem.of([], [], leave_available=5)
    with pytest.raises(ValueError):
        LeaveProblem.of([date(2025, 1, 1)], [], leave_available=-1)


def test_at_least_one_solver_available():
    assert len(available_solver_classes()) >= 1


@pytest.mark.parametrize("name", available_solver_names())
def test_each_available_solver_solves(name):
    result = get_solver(name, SolverConfig()).solve(_problem())
    assert result.solution.found
    # Budget is respected.
    assert result.stats.num_leave_days <= 5
    assert result.stats.objective is not None


def test_unknown_solver_raises():
    with pytest.raises(ValueError):
        get_solver("NotASolver")


def test_prebooked_days_are_forced():
    start = date(2025, 1, 1)
    dr = [start + timedelta(days=i) for i in range(31)]
    forced = date(2025, 1, 15)  # a weekday
    problem = LeaveProblem.of(dr, [], leave_available=5, prebooked_days={forced})
    name = available_solver_names()[0]
    result = get_solver(name).solve(problem)
    assert forced in result.solution.leave_days


def test_benchmark_all_solvers_agree_on_objective():
    rows = run_benchmark(_problem(), SolverConfig())
    objectives = [r.result.stats.objective for r in rows if r.result.solution.found]
    # Every backend should reach the same optimum for a model this small.
    # Compare with a tolerance: solvers differ by floating-point rounding
    # (e.g. SCIP returns 29.0000000000000007 where others return 29.0).
    assert objectives, "no solver produced a solution"
    assert max(objectives) - min(objectives) < 1e-6

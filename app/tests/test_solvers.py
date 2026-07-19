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


def _longest_stretch(break_days):
    if not break_days:
        return 0
    days = sorted(break_days)
    longest = cur = 1
    for prev, nxt in zip(days, days[1:]):
        cur = cur + 1 if (nxt - prev).days == 1 else 1
        longest = max(longest, cur)
    return longest


@pytest.mark.parametrize("name", available_solver_names())
def test_max_stretch_caps_break_length(name):
    # A horizon with no forced holiday run longer than the cap: every break
    # stretch the solver builds must respect max_stretch.
    start = date(2025, 1, 1)
    dr = [start + timedelta(days=i) for i in range(120)]
    problem = LeaveProblem.of(dr, [], leave_available=20, max_stretch=4)
    result = get_solver(name, SolverConfig()).solve(problem)
    assert result.solution.found
    assert _longest_stretch(result.solution.break_days) <= 4


def test_max_stretch_stays_feasible_with_long_holiday_run():
    # A block of public holidays longer than the cap is a *forced* run; the
    # cap must not make the model infeasible (windows that are all fixed breaks
    # are skipped). The forced run may exceed the cap; leave must not extend it.
    start = date(2025, 6, 2)  # a Monday
    dr = [start + timedelta(days=i) for i in range(30)]
    holiday_block = {start + timedelta(days=i) for i in range(5)}  # Mon–Fri
    problem = LeaveProblem.of(dr, holiday_block, leave_available=5, max_stretch=3)
    name = available_solver_names()[0]
    result = get_solver(name).solve(problem)
    assert result.solution.found  # feasible despite the 5+-day forced run


def test_invalid_max_stretch_raises():
    with pytest.raises(ValueError):
        LeaveProblem.of([date(2025, 1, 1)], [], leave_available=5, max_stretch=0)


def test_benchmark_all_solvers_agree_on_objective():
    rows = run_benchmark(_problem(), SolverConfig())
    objectives = [
        r.result.stats.objective
        for r in rows
        if r.result.solution.found and r.result.stats.objective is not None
    ]
    # Every backend should reach the same optimum for a model this small.
    # Compare with a tolerance: solvers differ by floating-point rounding
    # (e.g. SCIP returns 29.0000000000000007 where others return 29.0).
    assert objectives, "no solver produced a solution"
    assert max(objectives) - min(objectives) < 1e-6

"""Tests for household PTO coordination (Consensus Planning Protocol).

The scenarios are hermetic (no external holiday data): three full weeks starting
on a Monday, no public holidays, so weekends are the only *fixed* breaks and the
gains come purely from the coordinator lining up leave.
"""

from datetime import date, timedelta

import pytest

from app.services.consensus_service import Member, coordinate
from app.services.solvers import (
    LeaveProblem,
    SolverConfig,
    available_solver_names,
    get_solver,
)

_DEFAULT_SOLVER = available_solver_names()[0]

# Three full weeks Mon 2025-01-06 .. Sun 2025-01-26.
_START = date(2025, 1, 6)
_HORIZON = [_START + timedelta(days=i) for i in range(21)]


def _member(name, leave, prebooked=None, solver=_DEFAULT_SOLVER):
    return Member(
        name=name,
        problem=LeaveProblem.of(
            _HORIZON,
            [],
            leave_available=leave,
            adjacency_weight=1.0,
            prebooked_days=prebooked or [],
        ),
        solver_name=solver,
    )


# --- the per-day price hook on the oracle -------------------------------------


def test_empty_prices_leave_objective_unchanged():
    """A problem with no day-prices solves identically to the base model."""
    base = LeaveProblem.of(_HORIZON, [], leave_available=5, adjacency_weight=1.0)
    priced = base.with_prices({})  # empty -> has_prices is False
    assert not priced.has_prices
    r_base = get_solver(_DEFAULT_SOLVER).solve(base)
    r_priced = get_solver(_DEFAULT_SOLVER).solve(priced)
    assert r_base.stats.objective == pytest.approx(r_priced.stats.objective)


@pytest.mark.parametrize("name", available_solver_names())
def test_positive_day_price_pulls_a_break_onto_that_day(name):
    """A large price on one free weekday makes every backend take it off."""
    target = date(2025, 1, 8)  # a Wednesday, not otherwise attractive
    # Budget 0: with no price the day cannot be a break; a big price makes the
    # reward for breaking there exceed... nothing, but leave budget is 0, so use
    # budget 1 and a price big enough to beat any competing single day.
    problem = LeaveProblem.of(
        _HORIZON, [], leave_available=1, adjacency_weight=1.0
    ).with_prices({target: 100.0})
    result = get_solver(name, SolverConfig()).solve(problem)
    assert target in result.solution.break_days


# --- the coordinator ----------------------------------------------------------


def test_coordinate_requires_two_members():
    with pytest.raises(ValueError):
        coordinate([_member("solo", 5)])


def test_coordination_never_worse_than_baseline():
    """Core guarantee: the returned plan is >= the uncoordinated baseline."""
    a = _member("A", 6, prebooked={_START})
    b = _member("B", 6, prebooked={_START + timedelta(days=14)})
    result = coordinate([a, b], togetherness_bonus=2.0, rho=1.0, max_iters=30)
    assert result.togetherness >= result.baseline_togetherness


def test_coordination_strictly_improves_togetherness():
    """With misaligned prebooked weeks but spare budget, coordination wins."""
    a = _member("A", 6, prebooked={_START})
    b = _member("B", 6, prebooked={_START + timedelta(days=14)})
    result = coordinate([a, b], togetherness_bonus=3.0, rho=1.0, max_iters=40)
    assert result.gain > 0


def test_every_member_stays_budget_feasible():
    a = _member("A", 6, prebooked={_START})
    b = _member("B", 6, prebooked={_START + timedelta(days=14)})
    result = coordinate([a, b], togetherness_bonus=3.0, rho=1.0, max_iters=40)
    budgets = {"A": 6, "B": 6}
    for m in result.members:
        assert len(m.leave_days) <= budgets[m.name]


def test_prebooked_days_survive_coordination():
    """Private prebooked (e.g. medical) days remain forced through the loop."""
    forced_a = _START
    forced_b = _START + timedelta(days=14)
    a = _member("A", 6, prebooked={forced_a})
    b = _member("B", 6, prebooked={forced_b})
    result = coordinate([a, b], togetherness_bonus=3.0, rho=1.0, max_iters=40)
    by_name = {m.name: m for m in result.members}
    assert forced_a in by_name["A"].leave_days
    assert forced_b in by_name["B"].leave_days


def test_shared_off_days_are_the_intersection_of_breaks():
    a = _member("A", 6, prebooked={_START})
    b = _member("B", 6, prebooked={_START + timedelta(days=14)})
    result = coordinate([a, b], togetherness_bonus=3.0, rho=1.0, max_iters=40)
    break_sets = [m.break_days for m in result.members]
    expected = sorted(set.intersection(*break_sets))
    assert result.shared_off_days == expected


def test_three_members_coordinate():
    """CPP is not limited to couples; a 3-person household also coordinates."""
    a = _member("A", 6, prebooked={_START})
    b = _member("B", 6, prebooked={_START + timedelta(days=7)})
    c = _member("C", 6, prebooked={_START + timedelta(days=14)})
    result = coordinate([a, b, c], togetherness_bonus=3.0, rho=1.0, max_iters=40)
    assert result.togetherness >= result.baseline_togetherness
    assert len(result.members) == 3

"""
Leave Optimization Model (Linear Programming)

This module defines an optimization model that determines which days a user
should take leave in order to maximize total break time. Break time includes:

- Weekends
- Public holidays
- Leave days chosen by the model

The model respects several constraints:

1. Leave budget:
   - The user cannot exceed the number of leave days available.

2. Prebooked leave:
   - Certain dates may already be locked in as leave days.

3. Break-day logic:
   - Weekends and public holidays are automatically break days.
   - Weekdays become break days only if leave is allocated.

4. Adjacency bonus:
   - Consecutive break days are rewarded using adjacency_weight, encouraging
     longer continuous vacations.

The core solver `solve_leave_lp()` returns:
- break_days: all days off (weekends + holidays + allocated leave)
- leave_days: days where the solver assigns leave
"""

from datetime import date
from typing import Optional
import warnings
import xpress as xp

# Suppress Xpress license warnings
warnings.filterwarnings("ignore", category=UserWarning, module="xpress")


def solve_leave_lp(
    date_range: list[date],
    holidays: set[date],
    leave_available: int,
    adjacency_weight: float = 1.0,
    prebooked_days: Optional[set[date]] = None,
) -> tuple[list[date], list[date]]:
    """
    Solve a leave allocation optimization problem.

    Args:
        date_range: Ordered list of dates to evaluate.
        holidays: Set of public holidays (treated automatically as break days).
        leave_available: Maximum number of leave days available.
        adjacency_weight: Bonus weight for consecutive break days (higher = longer breaks).
        prebooked_days: Dates already locked in as leave.

    Returns:
        (break_days, leave_days):
            break_days → all break days (weekends + holidays + allocated leave)
            leave_days → dates where the solver assigns leave
    """

    # ------------------------------
    # Input Validation
    # ------------------------------
    if not date_range:
        raise ValueError("Date range cannot be empty")

    if leave_available < 0:
        raise ValueError("Leave available cannot be negative")

    # ------------------------------
    # Create Optimization Model
    # ------------------------------
    model = xp.problem()

    # Decision variables:
    # leave_vars[d] = 1 → take leave on date d
    # break_vars[d] = 1 → date d is a break day
    leave_vars = {d: xp.var(vartype=xp.binary) for d in date_range}
    break_vars = {d: xp.var(vartype=xp.binary) for d in date_range}

    # adjacency_vars[d] = 1 → break[d] AND break[d+1]
    adjacency_vars = {
        date_range[i]: xp.var(vartype=xp.binary) for i in range(len(date_range) - 1)
    }

    # Register variables
    model.addVariable(leave_vars)
    model.addVariable(break_vars)
    model.addVariable(adjacency_vars)

    # ==============================================================
    #                           CONSTRAINTS
    # ==============================================================

    # --------------------------------------------------------------
    # 1. Prebooked leave must be respected
    #
    # If the user already booked leave on certain days, the optimizer is
    # forced to set leave_vars[d] = 1 for those dates.
    # --------------------------------------------------------------
    if prebooked_days:
        for d in prebooked_days:
            if d in leave_vars:
                model.addConstraint(leave_vars[d] == 1)

    # --------------------------------------------------------------
    # 2. Leave budget constraint
    #
    # Ensures the solver cannot assign more leave days than the user has.
    #
    #     sum(leave_vars[d]) ≤ leave_available
    # --------------------------------------------------------------
    model.addConstraint(xp.Sum(leave_vars[d] for d in date_range) <= leave_available)

    # --------------------------------------------------------------
    # 3. Break day logic
    #
    # Weekends and public holidays are automatically break days.
    # Weekdays become break days only when leave is taken.
    #
    # weekend/holiday → break_vars[d] = 1
    # weekday         → break_vars[d] ≤ leave_vars[d]
    # --------------------------------------------------------------
    for d in date_range:
        is_weekend_or_holiday = (d.weekday() >= 5) or (d in holidays)

        if is_weekend_or_holiday:
            model.addConstraint(break_vars[d] == 1)
        else:
            model.addConstraint(break_vars[d] <= leave_vars[d])

    # --------------------------------------------------------------
    # 4. Adjacency logic
    #
    # adjacency_vars[d] = 1 when:
    #       break[d] = 1 AND break[d+1] = 1
    #
    # Linearized AND constraints:
    #       adj[d] ≤ break[d]
    #       adj[d] ≤ break[d+1]
    #       adj[d] ≥ break[d] + break[d+1] - 1
    #
    # This rewards continuous vacation stretches.
    # --------------------------------------------------------------
    for i in range(len(date_range) - 1):
        d1 = date_range[i]
        d2 = date_range[i + 1]
        adj = adjacency_vars[d1]

        model.addConstraint(adj <= break_vars[d1])
        model.addConstraint(adj <= break_vars[d2])
        model.addConstraint(adj >= break_vars[d1] + break_vars[d2] - 1)

    # ==============================================================
    #                            OBJECTIVE
    # ==============================================================
    # Maximize:
    #   total break days
    # + adjacency bonus for longer continuous vacations
    #
    # Higher adjacency_weight → longer, more consolidated breaks
    # --------------------------------------------------------------
    model.setObjective(
        xp.Sum(break_vars[d] for d in date_range)
        + adjacency_weight * xp.Sum(adjacency_vars[d] for d in adjacency_vars),
        sense=xp.maximize,
    )

    # Solve model
    model.solve()

    # Extract final solution
    break_days = [d for d in date_range if model.getSolution(break_vars[d]) > 0.5]
    leave_days = [d for d in date_range if model.getSolution(leave_vars[d]) > 0.5]

    return break_days, leave_days

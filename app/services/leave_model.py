"""
Leave Optimization Model (Linear Programming)

This is a lightweight, robust optimization model designed for FICO Xpress
Community Edition (≤5000 variables/constraints), supporting:

- Weekends and public holidays automatically as break days
- Leave-days selected by the solver
- Prebooked leave days (forced)
- A leave budget constraint
- Adjacency bonus to encourage longer break stretches

IMPORTANT:
min_stretch and max_stretch are *not implemented as LP constraints* to keep
the model extremely small and avoid Xpress solver limits. Instead, presets
should influence `adjacency_weight` (higher → prefers longer blocks).

This version is intentionally SIMPLE and SAFE.
"""

from datetime import date
from typing import Optional
import warnings
import xpress as xp

warnings.filterwarnings("ignore", category=UserWarning, module="xpress")


def solve_leave_lp(
    date_range: list[date],
    holidays: set[date],
    leave_available: int,
    adjacency_weight: float = 1.0,
    prebooked_days: Optional[set[date]] = None,
    min_stretch: Optional[int] = None,
    max_stretch: Optional[int] = None,
) -> tuple[list[date], list[date]]:
    """Solve the leave optimization model."""

    if not date_range:
        raise ValueError("date_range cannot be empty")
    if leave_available < 0:
        raise ValueError("leave_available cannot be negative")

    # ------------------------------
    # Create Model
    # ------------------------------
    model = xp.problem()

    # Decision variables
    leave_vars = {d: xp.var(vartype=xp.binary) for d in date_range}
    break_vars = {d: xp.var(vartype=xp.binary) for d in date_range}
    adjacency_vars = {
        date_range[i]: xp.var(vartype=xp.binary) for i in range(len(date_range) - 1)
    }

    model.addVariable(leave_vars)
    model.addVariable(break_vars)
    model.addVariable(adjacency_vars)

    # ------------------------------
    # Constraints
    # ------------------------------

    # Prebooked leave = 1
    if prebooked_days:
        for d in prebooked_days:
            if d in leave_vars:
                model.addConstraint(leave_vars[d] == 1)

    # Leave budget
    model.addConstraint(xp.Sum(leave_vars[d] for d in date_range) <= leave_available)

    # Break-day logic
    for d in date_range:
        if d.weekday() >= 5 or d in holidays:
            model.addConstraint(break_vars[d] == 1)
        else:
            model.addConstraint(break_vars[d] <= leave_vars[d])

    # Adjacency logic
    for i in range(len(date_range) - 1):
        d1 = date_range[i]
        d2 = date_range[i + 1]
        adj = adjacency_vars[d1]

        model.addConstraint(adj <= break_vars[d1])
        model.addConstraint(adj <= break_vars[d2])
        model.addConstraint(adj >= break_vars[d1] + break_vars[d2] - 1)

    # ------------------------------
    # Objective
    # ------------------------------
    objective = xp.Sum(break_vars[d] for d in date_range)
    objective += adjacency_weight * xp.Sum(adjacency_vars[d] for d in adjacency_vars)

    model.setObjective(objective, sense=xp.maximize)

    # ------------------------------
    # Solve
    # ------------------------------
    model.solve()

    # Correct way to test MIP success:
    # mipsols = number of feasible integer solutions
    mipsols = model.getAttrib("mipsols")

    if mipsols == 0:
        # No feasible MIP solution
        print("⚠️ Xpress: No feasible MIP solution. Status:", model.getProbStatus())
        return [], []

    # ------------------------------
    # Extract solution
    # ------------------------------
    break_days = [d for d in date_range if model.getSolution(break_vars[d]) > 0.5]

    leave_days = [d for d in date_range if model.getSolution(leave_vars[d]) > 0.5]

    return break_days, leave_days

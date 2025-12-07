"""
Leave optimization model using linear programming.

This module defines a linear     # 3. Break day logic
    for d in date_range:
        is_weekend_or_holiday = (d.weekday() >= 5) or (d in holidays)

        if is_weekend_or_holiday:
            # Automatically a break day
            model.addConstraint(break_vars[d] == 1)
        else:
            # Only a break if leave is taken
            model.addConstraint(break_vars[d] <= leave_vars[d])

    # 4. Adjacency logic: adj = break[i] AND break[i+1] model that allocates leave days to
maximize total break time (weekends + holidays + leave) while respecting
constraints such as:
- leave budget
- blocked days
- pre-booked leave days
- adjacency bonus for longer continuous breaks
"""

from datetime import date
from typing import List, Set, Optional, Tuple
import warnings
import xpress as xp

# Suppress Xpress license warnings
warnings.filterwarnings("ignore", category=UserWarning, module="xpress")


def solve_leave_lp(
    date_range: List[date],
    holidays: Set[date],
    leave_available: int,
    adjacency_weight: float = 1.0,
    prebooked_days: Optional[Set[date]] = None,
) -> Tuple[List[date], List[date]]:
    """
    Solve a leave allocation optimization problem.

    Args:
        date_range: Ordered list of dates to consider.
        holidays: Set of public holidays (always treated as break days).
        leave_available: Maximum number of leave days available.
        adjacency_weight: Weight applied to consecutive break-day bonuses.
        prebooked_days: Optional set of dates already confirmed as leave.

    Returns:
        A tuple of:
            break_days: All break days (weekends, holidays, and allocated leave).
            leave_days: Dates where the solver allocated leave.
    """

    # ------------------------------
    # Validate inputs
    # ------------------------------
    if not date_range:
        raise ValueError("Date range cannot be empty")

    if leave_available < 0:
        raise ValueError("Leave available cannot be negative")

    # ------------------------------
    # Create optimization model
    # ------------------------------
    model = xp.problem()

    # Decision Variables
    leave_vars = {d: xp.var(vartype=xp.binary) for d in date_range}
    break_vars = {d: xp.var(vartype=xp.binary) for d in date_range}

    # Adjacency variable: 1 when day[i] and day[i+1] are both break days
    adjacency_vars = {
        date_range[i]: xp.var(vartype=xp.binary) for i in range(len(date_range) - 1)
    }

    # Add variables to model
    model.addVariable(leave_vars)
    model.addVariable(break_vars)
    model.addVariable(adjacency_vars)

    # ------------------------------
    # Constraints
    # ------------------------------

    # 1. Prebooked leave must be respected
    if prebooked_days:
        for d in prebooked_days:
            if d in leave_vars:
                model.addConstraint(leave_vars[d] == 1)

    # 2. Leave budget
    model.addConstraint(xp.Sum(leave_vars[d] for d in date_range) <= leave_available)

    # 3. Break day logic
    for d in date_range:
        is_weekend_or_holiday = (d.weekday() >= 5) or (d in holidays)

        if is_weekend_or_holiday:
            # Automatically a break day
            model.addConstraint(break_vars[d] == 1)
        else:
            # Only a break if leave is taken
            model.addConstraint(break_vars[d] <= leave_vars[d])

    # 5. Adjacency logic: adj = break[i] AND break[i+1]
    for i in range(len(date_range) - 1):
        d1 = date_range[i]
        d2 = date_range[i + 1]
        adj = adjacency_vars[d1]

        model.addConstraint(adj <= break_vars[d1])
        model.addConstraint(adj <= break_vars[d2])
        model.addConstraint(adj >= break_vars[d1] + break_vars[d2] - 1)

    # ------------------------------
    # Objective: Maximize total break days + adjacency bonus
    # ------------------------------
    model.setObjective(
        xp.Sum(break_vars[d] for d in date_range)
        + adjacency_weight * xp.Sum(adjacency_vars[d] for d in adjacency_vars),
        sense=xp.maximize,
    )

    # ------------------------------
    # Solve
    # ------------------------------
    model.solve()

    # ------------------------------
    # Extract solution
    # ------------------------------
    break_days = [d for d in date_range if model.getSolution(break_vars[d]) > 0.5]
    leave_days = [d for d in date_range if model.getSolution(leave_vars[d]) > 0.5]

    return break_days, leave_days

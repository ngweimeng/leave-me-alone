"""
Leave Optimization Model — backward-compatibility shim.

The model now lives in :mod:`app.services.solvers`, where it can be solved by
any backend (Xpress, Gurobi, OR-Tools). This module preserves the original
``solve_leave_lp`` entry point so existing callers and tests keep working; it
delegates to the Xpress backend by default.

Vacation "style" is controlled entirely through ``adjacency_weight``
(higher → the solver prefers longer continuous blocks).
"""

from datetime import date
from typing import Optional

from app.services.solvers import LeaveProblem
from app.services.solvers.xpress_solver import XpressSolver


def solve_leave_lp(
    date_range: list[date],
    holidays: set[date],
    leave_available: int,
    adjacency_weight: float = 1.0,
    prebooked_days: Optional[set[date]] = None,
) -> tuple[list[date], list[date]]:
    """Solve the leave model with the Xpress backend (legacy entry point)."""
    problem = LeaveProblem.of(
        date_range=date_range,
        holidays=holidays,
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=prebooked_days,
    )
    result = XpressSolver().solve(problem)
    return result.solution.break_days, result.solution.leave_days

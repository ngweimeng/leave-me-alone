from datetime import date, timedelta
from typing import Iterable, Optional, Dict, List
from app.services.leave_model import solve_leave_lp


def run_optimizer(
    start: date,
    end: date,
    public_holidays: Optional[Iterable[date]] = None,
    leave_available: int = 0,
    adjacency_weight: float = 1.0,
    prebooked_days: Optional[Iterable[date]] = None,
) -> Dict[str, List[date]]:
    """
    Compute the optimal leave schedule between two dates.

    Parameters:
        start (date):
            Start of the date range (inclusive).
        end (date):
            End of the date range (inclusive).
        public_holidays (Iterable[date], optional):
            Dates that are already considered break days.
        leave_available (int):
            Maximum number of leave days the user can allocate.
        adjacency_weight (float):
            Extra reward for consecutive break days in the objective function.
        prebooked_days (Iterable[date], optional):
            Days the user has already committed to taking as leave.

    Returns:
        dict:
            {
                "break_days": [...],   # all days off (weekends, holidays, leave)
                "leave_days": [...],   # days where leave is allocated
                "year": 2025
            }
    """

    # Normalize None to empty lists
    public_holidays = list(public_holidays or [])
    prebooked_days = list(prebooked_days or [])

    # --------------------------------------------------------------
    # Build full date range (inclusive): start → end
    # --------------------------------------------------------------
    date_range = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # --------------------------------------------------------------
    # Call the underlying LP model
    # --------------------------------------------------------------
    break_days, leave_days = solve_leave_lp(
        date_range=date_range,
        holidays=set(public_holidays),
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=set(prebooked_days),
    )

    # --------------------------------------------------------------
    # Standard response used by UI / API components
    # --------------------------------------------------------------
    return {
        "break_days": break_days,
        "leave_days": leave_days,
        "year": start.year,
    }

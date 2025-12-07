from datetime import timedelta
from app.services.leave_model import solve_leave_lp


def run_optimizer(
    start,
    end,
    public_holidays=None,
    blocked_days=None,
    leave_available=0,
    adjacency_weight: float = 1.0,
    prebooked_days=None,
):
    """Run the leave optimizer.

    Accepts both the older positional names (`ph`, `blocked`) and the newer,
    explicit keyword names used by the UI (`public_holidays`, `blocked_days`).
    """
    if public_holidays is None:
        public_holidays = []
    if blocked_days is None:
        blocked_days = []
    if prebooked_days is None:
        prebooked_days = []

    # Build full date range
    date_range = []
    d = start
    while d <= end:
        date_range.append(d)
        d += timedelta(days=1)

    break_days, leave_days = solve_leave_lp(
        date_range,
        set(public_holidays),
        set(blocked_days),
        leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=set(prebooked_days),
    )

    return {
        "break_days": break_days,
        "leave_days": leave_days,
        "year": start.year,
    }

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
    min_stretch=None,
    max_stretch=None,
):
    """Adapter between UI and the optimization model."""

    if public_holidays is None:
        public_holidays = []
    if prebooked_days is None:
        prebooked_days = []

    # Build complete date range
    date_range = []
    cur = start
    while cur <= end:
        date_range.append(cur)
        cur += timedelta(days=1)

    break_days, leave_days = solve_leave_lp(
        date_range=date_range,
        holidays=set(public_holidays),
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        prebooked_days=set(prebooked_days),
        min_stretch=min_stretch,
        max_stretch=max_stretch,
    )

    return {
        "break_days": break_days,
        "leave_days": leave_days,
        "start": start,
        "end": end,
        "public_holidays": public_holidays,
        "prebooked_days": prebooked_days,
        "num_break_days": len(break_days),
        "num_leave_days": len(leave_days),
    }

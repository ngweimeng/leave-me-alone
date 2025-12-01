from datetime import timedelta
from app.services.leave_model import solve_leave_lp

def run_optimizer(start, end, ph, blocked, leave_available, adjacency_weight: float = 1.0):
    date_range = []
    d = start
    while d <= end:
        date_range.append(d)
        d += timedelta(days=1)

    break_days, leave_days = solve_leave_lp(
        date_range, set(ph), set(blocked), leave_available, adjacency_weight=adjacency_weight
    )

    return {
        "break_days": break_days,
        "leave_days": leave_days,
        "year": start.year,
    }

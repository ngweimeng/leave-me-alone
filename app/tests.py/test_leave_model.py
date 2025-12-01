from datetime import date, timedelta
from app.services.leave_model import solve_leave_lp

def test_leave_solver_runs():
    start = date(2025, 1, 1)
    end = date(2025, 1, 10)
    dates = [start + timedelta(days=i) for i in range((end-start).days + 1)]

    break_days, leave_days = solve_leave_lp(dates, set(), set(), 2)
    assert isinstance(break_days, list)

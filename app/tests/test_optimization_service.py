from datetime import date
from app.services.optimization_service import run_optimizer


def test_run_optimizer():
    result = run_optimizer(
        start=date(2025, 1, 1),
        end=date(2025, 1, 5),
        public_holidays=[],
        leave_available=1,
    )
    assert "break_days" in result
    assert "leave_days" in result
    assert isinstance(result["break_days"], list)
    assert isinstance(result["leave_days"], list)

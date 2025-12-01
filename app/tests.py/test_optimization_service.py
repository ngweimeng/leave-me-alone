from datetime import date
from app.services.optimization_service import run_optimizer

def test_run_optimizer():
    result = run_optimizer(
        start=date(2025,1,1),
        end=date(2025,1,5),
        ph=[],
        blocked=[],
        leave_available=1
    )
    assert "break_days" in result

from dataclasses import dataclass
from datetime import date
from typing import List


@dataclass
class LeaveOptimizationRequest:
    country: str
    year: int
    leave_available: int
    adjacency_weight: float
    start: date
    end: date
    prebooked_days: List[date]
    min_stretch: int | None = None
    max_stretch: int | None = None

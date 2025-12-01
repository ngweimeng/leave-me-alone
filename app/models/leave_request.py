from pydantic import BaseModel
from datetime import date
from typing import List

class LeaveOptimizationRequest(BaseModel):
    country: str
    year: int
    leave_available: int
    adjacency_weight: float = 1.0
    start: date
    end: date
    blocked_days: List[date]

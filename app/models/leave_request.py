from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class LeaveOptimizationRequest:
    country: str
    year: int
    leave_available: int
    adjacency_weight: float
    start: date
    end: date
    prebooked_days: List[date]
    # Cap on continuous break length (None = no cap). Set by the style preset.
    max_stretch: Optional[int] = None

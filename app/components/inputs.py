import streamlit as st
from datetime import date
from typing import Optional
import pandas as pd
from app.models.leave_request import LeaveOptimizationRequest


def render_inputs(
    leave_available: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    **kwargs,
) -> LeaveOptimizationRequest:
    """Return a LeaveOptimizationRequest built from provided values or session state.

    This function no longer renders the PTO number input. PTO should be
    collected in the main UI (Step 1) and provided via the `leave_available`
    argument (or stored in `st.session_state['leave_available_total']`).
    """
    # Accept start/end provided via kwargs (defensive)
    if start is None and "start" in kwargs:
        start = kwargs.get("start")
    if end is None and "end" in kwargs:
        end = kwargs.get("end")

    # If timeframe not provided, default to current calendar year
    if start is None or end is None:
        start = date(date.today().year, 1, 1)
        end = date(date.today().year, 12, 31)

    adjacency_weight = 1.0
    blocked_days = []

    year_val = start.year

    # If leave_available not provided, try to read from session state
    if leave_available is None:
        leave_available = int(st.session_state.get("leave_available_total", 0))

    return LeaveOptimizationRequest(
        country="",
        year=year_val,
        leave_available=int(leave_available),
        adjacency_weight=adjacency_weight,
        start=start,
        end=end,
        blocked_days=blocked_days,
        prebooked_days=[],
    )

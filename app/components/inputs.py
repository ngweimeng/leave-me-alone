import streamlit as st
from datetime import date
import pandas as pd

from app.services.holiday_service import (
    get_all_supported_countries,
    get_supported_country_map,
    get_public_holiday_map,
)
from app.models.leave_request import LeaveOptimizationRequest

def render_inputs() -> LeaveOptimizationRequest:
    st.subheader("Input Parameters")

    # Display full country names but keep the selectbox value as the
    # country code (used by the holiday loader). `format_func` shows the
    # friendly name while the option value remains the code.
    country_map = get_supported_country_map()
    country = st.selectbox(
        "Country",
        options=list(sorted(country_map.keys())),
        format_func=lambda c: country_map.get(c, c),
    )
    year = st.number_input("Year", value=date.today().year)

    # Display public holidays for the selected country/year so the user can
    # review which days are automatically considered breaks.
    try:
        ph_list = get_public_holiday_map(country, year)
    except Exception:
        ph_list = []

    # Show the friendly country name in the expander title (fallback to code)
    with st.expander(f"Public Holidays — {country_map.get(country, country)} {year}"):
        if not ph_list:
            st.info("No public holidays found for the selected country/year.")
        else:
            df_ph = pd.DataFrame(ph_list, columns=["date", "name"])
            st.table(df_ph)
    leave_available = st.slider("Available leave days", 0, 40, 10)

    # Preset vacation styles. Each preset maps to an `adjacency_weight`
    # controlling how strongly the optimizer prefers contiguous break days.
    PRESETS = {
        "Recommended (Balanced Mix)": {
            "weight": 1.0,
            "desc": "A smart blend of short breaks and longer vacations.",
        },
        "Long Weekends": {
            "weight": 1.8,
            "desc": "More 3–4 day weekends throughout the year.",
        },
        "Mini Breaks": {
            "weight": 1.2,
            "desc": "Several shorter 5–6 day breaks spread across the year.",
        },
        "Week-long Breaks": {
            "weight": 2.5,
            "desc": "Focused on 7–9 day breaks for more substantial time off.",
        },
        "Extended Vacations": {
            "weight": 4.0,
            "desc": "Longer 10–15 day vacations for deeper relaxation.",
        },
    }

    preset = st.radio(
        "Vacation Style",
        options=list(PRESETS.keys()),
        index=0,
        help="Choose a preset that matches how you like to take time off.",
    )

    adjacency_weight = float(PRESETS[preset]["weight"])
    st.caption(PRESETS[preset]["desc"])

    col1, col2 = st.columns(2)
    start = col1.date_input("Start date", value=date(year, 1, 1))
    end = col2.date_input("End date", value=date(year, 12, 31))

    blocked_days = st.multiselect("Block off days you already plan to take leave", [])

    return LeaveOptimizationRequest(
        country=country,
        year=year,
        leave_available=leave_available,
        adjacency_weight=adjacency_weight,
        start=start,
        end=end,
        blocked_days=blocked_days,
    )

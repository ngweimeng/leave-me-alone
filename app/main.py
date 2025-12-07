import sys
from pathlib import Path

# Add the project root to Python path to enable 'app' package imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import calendar
from datetime import date, datetime, timedelta
from typing import List, Tuple

import streamlit as st

from app.models.leave_request import LeaveOptimizationRequest
from app.components.results_display import show_results
from app.services.holiday_service import (
    get_public_holiday_map,
    get_supported_country_map,
)
from app.services.optimization_service import run_optimizer
from app.state.session_manager import SessionManager


# Global session manager
ses = SessionManager()


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _format_range(start: date, end: date) -> str:
    """Format a date range safely for UI."""
    return f"{start.strftime('%b %d, %Y')} → {end.strftime('%b %d, %Y')}"


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


# -------------------------------------------------------------------
# Step Rendering Functions
# -------------------------------------------------------------------
def init() -> None:
    """Initialize page layout and header."""
    st.set_page_config(page_title="Leave Optimizer", page_icon="🌴", layout="wide")
    # st.sidebar.title("Navigation")

    st.title("🌴 Leave Optimizer — Maximize Your Break")
    st.subheader("Step 1 — Enter PTO Days")

    st.markdown(
        "Specify the total number of paid time-off days available. "
        "The optimizer will strategically allocate them within the selected timeframe."
    )


def render_pto_input() -> int:
    """Step 1: PTO input widget."""
    leave_available = st.number_input(
        "Number of paid time off days",
        min_value=0,
        max_value=365,
        value=int(st.session_state.get("leave_available_total", 10)),
        step=1,
        help="Enter how many paid time-off days you have.",
        key="leave_available_total",
    )

    if leave_available == 0:
        st.warning("You entered **0** PTO days. At least 1 is required to optimize.")

    st.markdown("---")
    return int(leave_available)


def render_timeframe_selection() -> Tuple[date, date]:
    """Step 2: Select timeframe."""
    st.subheader("Step 2 — Select Optimization Timeframe")
    st.markdown("Define the period within which PTO days will be optimized.")

    tf_option = st.radio(
        "Timeframe selection",
        options=[
            f"Calendar Year {date.today().year}",
            f"Calendar Year {date.today().year + 1}",
            "12-Month Period (Custom)",
        ],
    )

    if tf_option.startswith("Calendar Year"):
        year = int(tf_option.split()[-1])
        start, end = date(year, 1, 1), date(year, 12, 31)

    else:
        col_month, col_year = st.columns(2)

        month_name = col_month.selectbox(
            "Start month",
            list(calendar.month_name)[1:],
            index=date.today().month - 1,
        )
        year_sel = col_year.selectbox(
            "Start year", [date.today().year, date.today().year + 1]
        )

        month_idx = list(calendar.month_name).index(month_name)
        start = date(year_sel, month_idx, 1)

        end_month_idx = ((month_idx + 10) % 12) + 1
        end_year = year_sel + ((month_idx + 11) // 12)
        last_day = calendar.monthrange(end_year, end_month_idx)[1]
        end = date(end_year, end_month_idx, last_day)

    st.markdown(f"**Selected timeframe:** {_format_range(start, end)}")
    st.markdown("---")
    return start, end


def render_public_holidays(user_input) -> List[date]:
    """Step 3: Select public holidays."""
    st.subheader("Step 3 — Select Public Holidays")
    st.markdown(
        "Choose which public holidays to include in the optimization. Selected holidays will be treated as non-working days."
    )

    country_map = get_supported_country_map()

    ph_country = st.selectbox(
        "Country (for public holidays)",
        options=sorted(country_map.keys()),
        format_func=lambda c: country_map.get(c, c),
    )
    user_input.country = ph_country

    # Fetch holiday candidates
    ph_candidates = []
    try:
        for year in range(user_input.start.year, user_input.end.year + 1):
            ph_candidates += get_public_holiday_map(ph_country, year)
    except Exception as e:
        st.warning(f"⚠️ Could not load holidays for {ph_country}: {str(e)}")
        ph_candidates = []

    # Filter to timeframe
    ph_candidates = [
        (d, n) for d, n in ph_candidates if user_input.start <= d <= user_input.end
    ]

    selected_dates: List[date] = []
    expander_title = f"Public Holidays — {ph_country} ({_format_range(user_input.start, user_input.end)}) — {len(ph_candidates)} found"

    with st.expander(expander_title):
        if not ph_candidates:
            st.info("No public holidays found for the selected period.")
        else:
            import pandas as pd

            df = pd.DataFrame(ph_candidates, columns=["date", "name"])
            df["date"] = df["date"].apply(lambda d: d.isoformat())
            df["include"] = True

            edited = st.data_editor(df, num_rows="fixed", width="stretch")

            if edited is not None:
                for _, row in edited.iterrows():
                    if bool(row["include"]):
                        selected_dates.append(
                            datetime.fromisoformat(row["date"]).date()
                        )

    st.markdown("---")
    return selected_dates


def render_style_preset(user_input) -> None:
    """Step 4: Choose vacation style preset."""
    st.subheader("Step 4 — Select Vacation Style")
    st.markdown(
        "Choose a vacation preference to guide how PTO days are distributed throughout the timeframe."
    )

    style = st.radio("Vacation Style", list(PRESETS.keys()), index=0)
    st.caption(PRESETS[style]["desc"])

    user_input.adjacency_weight = PRESETS[style]["weight"]

    st.markdown("---")


def render_prebooked_days(user_input) -> None:
    """Step 5: Allow user to add pre-booked days."""
    st.subheader("Step 5 — Add Pre-booked Vacation Days (optional)")

    st.markdown(
        "Specify individual dates or a date range for vacation days that have already been scheduled. These will be excluded from optimization."
    )

    add_col, show_col = st.columns([1, 2])

    with add_col:
        # Toggle between single day and date range
        input_mode = st.radio(
            "Input mode",
            ["Single Day", "Date Range"],
            horizontal=True,
            key="prebook_mode",
        )

        if input_mode == "Single Day":
            new_pre = st.date_input(
                "Select date", value=user_input.start, key="new_pre_single"
            )
            if st.button("Add Day", use_container_width=True):
                ses.add_prebooked(new_pre)
                st.rerun()
        else:
            col_start, col_end = st.columns(2)
            with col_start:
                range_start = st.date_input(
                    "Start", value=user_input.start, key="pre_range_start"
                )
            with col_end:
                range_end = st.date_input(
                    "End", value=user_input.start, key="pre_range_end"
                )

            if st.button("Add Range", use_container_width=True):
                if range_end < range_start:
                    st.error("End date must be after start date")
                else:
                    # Add all days in the range
                    current = range_start
                    while current <= range_end:
                        ses.add_prebooked(current)
                        current += timedelta(days=1)
                    st.rerun()

    with show_col:
        prebooked = ses.get_prebooked()
        if not prebooked:
            st.caption("No pre-booked days added.")
        else:
            st.markdown(f"**Pre-booked days ({len(prebooked)}):**")

            # Group consecutive days for better display
            if prebooked:
                sorted_days = sorted(prebooked)
                display_items = []

                i = 0
                while i < len(sorted_days):
                    start_day = sorted_days[i]
                    end_day = start_day

                    # Find consecutive days
                    while i + 1 < len(sorted_days) and sorted_days[
                        i + 1
                    ] == sorted_days[i] + timedelta(days=1):
                        i += 1
                        end_day = sorted_days[i]

                    if start_day == end_day:
                        display_items.append((start_day, None))
                    else:
                        display_items.append((start_day, end_day))
                    i += 1

                for idx, item in enumerate(display_items):
                    col_left, col_right = st.columns([3, 1])
                    if item[1] is None:
                        # Single day
                        col_left.write(item[0].isoformat())
                        if col_right.button("✕", key=f"rm_pre_{idx}"):
                            ses.remove_prebooked(item[0])
                            st.rerun()
                    else:
                        # Date range
                        col_left.write(f"{item[0].isoformat()} → {item[1].isoformat()}")
                        if col_right.button("✕", key=f"rm_pre_{idx}"):
                            # Remove all days in this range
                            current = item[0]
                            while current <= item[1]:
                                ses.remove_prebooked(current)
                                current += timedelta(days=1)
                            st.rerun()

    user_input.prebooked_days = list(ses.get_prebooked())
    st.markdown("---")


def render_other_time_off(user_input) -> None:
    """Step 6: Add other non-PTO time off."""
    st.subheader("Step 6 — Add other non-PTO Time Off")

    st.markdown(
        "Add company-wide days off or missing public holidays so they won’t count against your PTO."
    )

    col_date, col_label, col_add = st.columns([2, 3, 1])
    with col_date:
        oth_date = st.date_input("Date", value=user_input.start, key="oth_date")
    with col_label:
        label = st.text_input("Label (optional)", key="oth_label")
    with col_add:
        if st.button("Add Other Time Off"):
            ses.add_other_time_off((oth_date, label or "Other"))

    items = ses.get_other_time_off()
    if not items:
        st.caption("No additional time off added.")
    else:
        st.markdown("**Additional Time Off:**")
        for i, (d, lbl) in enumerate(items):
            col_left, col_right = st.columns([6, 1])
            col_left.write(f"{d.isoformat()} — {lbl}")
            if col_right.button("Remove", key=f"rm_oth_{i}"):
                ses.remove_other_time_off((d, lbl))

    st.markdown("---")


def render_optimize_button(user_input, selected_ph_dates: List[date]) -> None:
    """Step 7: Optimize button and processing."""
    prebook_count = len(user_input.prebooked_days)
    total_pto = int(st.session_state.get("leave_available_total", 0))
    remaining = max(total_pto - prebook_count, 0)

    if remaining == 0:
        st.warning("No remaining PTO after accounting for pre-booked days.")
    else:
        st.info(f"Remaining PTO: {remaining} (out of {total_pto})")

    if st.button("Optimize Break"):
        if remaining <= 0:
            st.error("At least 1 PTO day is required to optimize.")
            return

        additional_off = [d for d, _ in ses.get_other_time_off()]
        public_holidays = list({d: True for d in (selected_ph_dates + additional_off)})

        result = run_optimizer(
            start=user_input.start,
            end=user_input.end,
            public_holidays=public_holidays,
            leave_available=remaining,
            adjacency_weight=user_input.adjacency_weight,
            prebooked_days=user_input.prebooked_days,
        )

        st.success("✅ Optimization Completed!")
        show_results(result)


# -------------------------------------------------------------------
# Main App
# -------------------------------------------------------------------


def main() -> None:
    init()

    leave_available = render_pto_input()
    start, end = render_timeframe_selection()

    user_input = LeaveOptimizationRequest(
        country="",
        year=start.year,
        leave_available=leave_available,
        adjacency_weight=1.0,
        start=start,
        end=end,
        prebooked_days=[],
    )

    selected_ph_dates = render_public_holidays(user_input)
    render_style_preset(user_input)
    render_prebooked_days(user_input)
    render_other_time_off(user_input)
    render_optimize_button(user_input, selected_ph_dates)


if __name__ == "__main__":
    main()

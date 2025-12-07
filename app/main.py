import calendar
from datetime import date, datetime
from typing import List, Tuple

import streamlit as st

from app.components.inputs import render_inputs
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
    try:
        return f"{start.strftime('%b %d, %Y')} → {end.strftime('%b %d, %Y')}"
    except Exception:
        return f"{start} → {end}"


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
    st.sidebar.title("Navigation")

    st.title("🌴 Leave Optimizer — Maximize Your Break")
    st.subheader("Step 1 — Enter Your Days")

    st.markdown(
        "Tell us how many paid time-off (PTO) days you have. "
        "The optimizer will help you maximize them between your selected dates."
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
    st.subheader("Step 2 — Select Your Timeframe")
    st.markdown("Choose the period you want to optimize.")

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
    st.subheader("Step 3 — Public Holidays")

    try:
        country_map = get_supported_country_map()
    except Exception:
        country_map = {}

    ph_country = st.selectbox(
        "Country (for public holidays)",
        options=sorted(country_map.keys()) if country_map else ["AW"],
        format_func=lambda c: country_map.get(c, c),
    )
    user_input.country = ph_country

    # Fetch holiday candidates
    ph_candidates = []
    try:
        for year in range(user_input.start.year, user_input.end.year + 1):
            ph_candidates += get_public_holiday_map(ph_country, year)
    except Exception:
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

            try:
                edited = st.data_editor(df, num_rows="fixed", width="stretch")
            except Exception:
                edited = st.experimental_data_editor(df, num_rows="fixed")

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
    st.subheader("Step 4 — Choose Your Style")

    style = st.radio("Vacation Style", list(PRESETS.keys()), index=0)
    st.caption(PRESETS[style]["desc"])

    try:
        user_input.adjacency_weight = PRESETS[style]["weight"]
    except Exception:
        pass

    st.markdown("---")


def render_prebooked_days(user_input) -> None:
    """Step 5: Allow user to add pre-booked days."""
    st.subheader("Step 5 — Pre-booked Vacation Days (optional)")

    add_col, show_col = st.columns([1, 2])

    with add_col:
        new_pre = st.date_input("Add a day", value=user_input.start, key="new_pre")
        if st.button("Add pre-booked day"):
            ses.add_prebooked(new_pre)

    with show_col:
        prebooked = ses.get_prebooked()
        if not prebooked:
            st.caption("No pre-booked days added.")
        else:
            st.markdown("**Current pre-booked days:**")
            for i, d in enumerate(prebooked):
                col_left, col_right = st.columns([3, 1])
                col_left.write(d.isoformat())
                if col_right.button("Remove", key=f"rm_pre_{i}"):
                    ses.remove_prebooked(d)

    user_input.prebooked_days = list(ses.get_prebooked())
    st.markdown("---")


def render_other_time_off(user_input) -> None:
    """Step 6: Add other non-PTO time off."""
    st.subheader("Step 6 — Other Additional Time Off (optional)")

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
            blocked_days=user_input.blocked_days,
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
        blocked_days=[],
        prebooked_days=[],
    )

    selected_ph_dates = render_public_holidays(user_input)
    render_style_preset(user_input)
    render_prebooked_days(user_input)
    render_other_time_off(user_input)
    render_optimize_button(user_input, selected_ph_dates)


if __name__ == "__main__":
    main()

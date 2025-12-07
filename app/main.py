import calendar
from datetime import date, datetime
from typing import List, Tuple

import streamlit as st

from app.components.inputs import render_inputs
from app.models.leave_request import LeaveOptimizationRequest
from app.components.results_display import show_results
from app.services.holiday_service import get_public_holiday_map, get_supported_country_map
from app.services.optimization_service import run_optimizer
from app.state.session_manager import SessionManager

# Instantiate a global session manager to centralize session access in UI helpers
ses = SessionManager()


def _format_range(start: date, end: date) -> str:
    try:
        return f"{start.strftime('%b %d, %Y')} → {end.strftime('%b %d, %Y')}"
    except Exception:
        return f"{start} → {end}"


PRESETS = {
    "Recommended (Balanced Mix)": {"weight": 1.0, "desc": "A smart blend of short breaks and longer vacations."},
    "Long Weekends": {"weight": 1.8, "desc": "More 3–4 day weekends throughout the year."},
    "Mini Breaks": {"weight": 1.2, "desc": "Several shorter 5–6 day breaks spread across the year."},
    "Week-long Breaks": {"weight": 2.5, "desc": "Focused on 7–9 day breaks for more substantial time off."},
    "Extended Vacations": {"weight": 4.0, "desc": "Longer 10–15 day vacations for deeper relaxation."},
}


def init() -> None:
    """Initialize the page and render the header.

    Combines page config (sidebar) and the top-of-page header content.
    """
    st.set_page_config(page_title="Leave Optimizer", page_icon="🌴", layout="wide")
    st.sidebar.title("Navigation")

    st.title("🌴 Leave Optimizer — Maximize Your Break")
    st.subheader("Step 1 — Enter Your Days")
    st.markdown(
        "**Required**\n\n"
        "Tell us how many paid time-off (PTO) days you have. "
        "The optimizer will help you use them efficiently from today until the end of the year."
    )


def render_pto_input() -> int:
    """Render the Step 1 PTO number input and return the selected value.

    The value is stored in `st.session_state['leave_available_total']` by the
    `st.number_input` widget so it persists across reruns.
    """
    leave_available = st.number_input(
        "Number of paid time off days",
        min_value=0,
        max_value=365,
        value=int(st.session_state.get("leave_available_total", 10)),
        step=1,
        help="Enter how many paid time-off days you have available.",
        key="leave_available_total",
    )

    if leave_available == 0:
        st.warning(
            "You entered **0** paid time-off days. "
            "You need at least one day to run the optimizer."
        )

    return int(leave_available)


def render_timeframe_selection() -> Tuple[date, date]:
    st.subheader("Step 2 — Select Your Timeframe")
    st.markdown(
        "Select the time period you want to plan for. Your holidays and company days will automatically adjust to show only what's relevant for your selected timeframe."
    )

    tf_option = st.radio(
        "Timeframe selection",
        options=[
            f"Calendar Year {date.today().year}",
            f"Calendar Year {date.today().year + 1}",
            "12-Month Period (Custom)",
        ],
    )

    if tf_option.startswith("Calendar Year"):
        sel_year = int(tf_option.split()[-1])
        start = date(sel_year, 1, 1)
        end = date(sel_year, 12, 31)
    else:
        colm, coly = st.columns(2)
        month_name = colm.selectbox(
            "Start month",
            options=list(calendar.month_name)[1:],
            index=date.today().month - 1,
        )
        year_options = [date.today().year, date.today().year + 1]
        year_sel = coly.selectbox("Start year", options=year_options, index=0)
        month_idx = list(calendar.month_name).index(month_name)
        start = date(year_sel, month_idx, 1)
        end_month_index = ((month_idx + 11 - 1) % 12) + 1
        end_year = year_sel + ((month_idx + 11 - 1) // 12)
        last_day = calendar.monthrange(end_year, end_month_index)[1]
        end = date(end_year, end_month_index, last_day)

    st.markdown(f"**Selected timeframe:** {_format_range(start, end)}")
    return start, end


def _render_public_holidays(user_input) -> List[date]:
    st.subheader("Step 3 — Public Holidays")
    st.markdown(
        "**Required**\n\n"
        "Add public holidays for the selected timeframe by confirming your country below and choosing which holidays to include."
    )

    country_map = {}
    try:
        country_map = get_supported_country_map()
    except Exception:
        country_map = {}

    ph_country = st.selectbox(
        "Country (for public holidays)",
        options=list(sorted(country_map.keys())) if country_map else ["AW"],
        format_func=lambda c: country_map.get(c, c) if country_map else c,
    )

    user_input.country = ph_country

    # collect candidates
    ph_candidates: List[Tuple[date, str]] = []
    try:
        for y in range(user_input.start.year, user_input.end.year + 1):
            ph_candidates.extend(get_public_holiday_map(ph_country, y))
    except Exception:
        ph_candidates = []

    ph_candidates = [(d, n) for (d, n) in ph_candidates if (d >= user_input.start and d <= user_input.end)]

    expander_title = f"Public Holidays — {ph_country} ({_format_range(user_input.start, user_input.end)}) — {len(ph_candidates)} found"

    selected_ph_dates: List[date] = []
    with st.expander(expander_title, expanded=False):
        if not ph_candidates:
            st.info("No public holidays found for the selected country/timeframe")
        else:
            import pandas as _pd  # local import to keep module-level imports small

            df_ph = _pd.DataFrame(ph_candidates, columns=["date", "name"]).copy()
            df_ph["date"] = df_ph["date"].apply(lambda d: d.isoformat())
            df_ph["include"] = True

            key = "selected_public_holidays"
            if key not in st.session_state:
                st.session_state[key] = [f"{d.isoformat()} — {name}" for (d, name) in ph_candidates]

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Select all", key="ph_select_all"):
                    st.session_state[key] = [f"{d.isoformat()} — {name}" for (d, name) in ph_candidates]
            with col2:
                if st.button("Clear all", key="ph_clear_all"):
                    st.session_state[key] = []

            try:
                edited = st.data_editor(df_ph, num_rows="fixed", width="stretch")
            except Exception:
                edited = st.experimental_data_editor(df_ph, num_rows="fixed", width="stretch")

            if edited is not None and not edited.empty:
                for _, row in edited.iterrows():
                    try:
                        if bool(row.get("include", False)):
                            selected_ph_dates.append(datetime.fromisoformat(str(row["date"])).date())
                    except Exception:
                        continue

    return selected_ph_dates


def _render_style_and_preset(user_input) -> None:
    st.subheader("Step 4 — Choose Your Style")
    st.markdown(
        "Select how you'd like to distribute your time off. This affects the length and frequency of your breaks throughout the year."
    )

    style_choice = st.radio("Vacation Style", options=list(PRESETS.keys()), index=0)
    st.caption(PRESETS[style_choice]["desc"])

    try:
        user_input.adjacency_weight = float(PRESETS[style_choice]["weight"])
    except Exception:
        pass


def _render_prebooked_days(user_input) -> None:
    st.subheader("Step 5 — Pre-booked Vacation Days (optional)")
    # Use SessionManager to encapsulate prebooked days state
    add_col, show_col = st.columns([1, 2])
    with add_col:
        new_pre = st.date_input("Pick a pre-booked day to add", value=user_input.start, key="new_prebook_date")
        if st.button("Add pre-booked day", key="add_prebooked_day"):
            ses.add_prebooked(new_pre)
    with show_col:
        prebooked = ses.get_prebooked()
        if not prebooked:
            st.caption("No pre-booked days added. Use the picker to add one.")
        else:
            st.markdown("**Current pre-booked days:**")
            for i, d in enumerate(list(prebooked)):
                c1, c2 = st.columns([3, 1])
                c1.write(d.strftime("%Y-%m-%d"))
                if c2.button("Remove", key=f"remove_pre_{i}_{d.isoformat()}"):
                    ses.remove_prebooked(d)

    try:
        user_input.prebooked_days = ses.get_prebooked()
    except Exception:
        user_input.prebooked_days = []


def _render_optimize_button(user_input, selected_ph_dates: List[date]) -> None:
    # Recompute effective remaining PTO after prebooked days
    prebook_count = len(user_input.prebooked_days) if getattr(user_input, "prebooked_days", None) else 0
    total_pTO = int(st.session_state.get("leave_available_total", 0))
    effective_remaining = max(total_pTO - prebook_count, 0)

    if effective_remaining < 0:
        st.error(
            f"You have {abs(effective_remaining)} more pre-booked day(s) than your available PTO. Please increase your PTO or remove pre-booked days."
        )
    elif effective_remaining == 0:
        st.warning(
            f"No remaining PTO after accounting for pre-booked days ({prebook_count}). Consider increasing PTO or removing pre-booked days."
        )
    else:
        st.info(f"Leave available after accounting for pre-booked days ({prebook_count}): {effective_remaining} day(s) — Total: {total_pTO}")

    if st.button("Optimize Break"):
        if effective_remaining <= 0:
            st.error("Please enter at least 1 paid time-off day (after pre-booked days) to continue.")
            return

        additional_off_dates = [d for (d, lbl) in ses.get_other_time_off()]
        public_holidays = (selected_ph_dates or []) + additional_off_dates
        # dedupe
        public_holidays = list({d: True for d in public_holidays}.keys())

        result = run_optimizer(
            start=user_input.start,
            end=user_input.end,
            public_holidays=public_holidays,
            blocked_days=user_input.blocked_days,
            leave_available=effective_remaining,
            adjacency_weight=user_input.adjacency_weight,
            prebooked_days=user_input.prebooked_days,
        )

        st.success("✅ Optimization Completed!")
        show_results(result)


def _render_other_time_off(user_input) -> None:
    st.header("Step 6 — Other Additional Time Off (optional)")
    st.markdown("Add company-wide days off, personal days off (birthday), or other non-pto time off.")
    col_date, col_label, col_add = st.columns([2, 3, 1])
    with col_date:
        other_date = st.date_input("Date", value=user_input.start, key="other_time_off_date")
    with col_label:
        other_label = st.text_input("Label (optional)", key="other_time_off_label")
    with col_add:
        if st.button("Add", key="add_other_time_off"):
            entry = (other_date, other_label or "Other")
            ses.add_other_time_off(entry)

    other_items = ses.get_other_time_off()
    if not other_items:
        st.caption("No additional time off added.")
    else:
        st.markdown("**Additional Time Off:**")
        for i, (d, lbl) in enumerate(list(other_items)):
            c1, c2 = st.columns([6, 1])
            c1.write(f"{d.isoformat()} — {lbl}")
            if c2.button("Remove", key=f"remove_other_{i}_{d.isoformat()}"):
                ses.remove_other_time_off((d, lbl))


def main() -> None:
    init()

    # Step 1 — PTO input
    leave_available = render_pto_input()

    # Step 2 — Timeframe
    start, end = render_timeframe_selection()

    # Create the user input request model
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

    # Step 3 — Public holidays
    selected_ph_dates = _render_public_holidays(user_input)

    # Step 4 — Style
    _render_style_and_preset(user_input)

    # Step 5 — Pre-booked days UI (separate from optimize button)
    # This updates `user_input.prebooked_days` via SessionManager
    _render_prebooked_days(user_input)

    # Step 5b — Run optimizer (separate control)
    _render_optimize_button(user_input, selected_ph_dates)

    # Step 6 — Other time off
    _render_other_time_off(user_input)


if __name__ == "__main__":
    main()

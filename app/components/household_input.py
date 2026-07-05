"""Streamlit input form for the household (couple/family) coordination flow.

Collects a roster of people, each with their own private inputs — name,
country (→ holidays), PTO budget, vacation style, and optional prebooked days —
and turns them into :class:`~app.services.consensus_service.Member` objects for
the consensus coordinator. This keeps all Streamlit/`session_state` handling out
of the service layer (per the repo's services-must-not-import-streamlit rule).
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.services.consensus_service import Member
from app.services.holiday_service import (
    get_public_holiday_map,
    get_supported_country_map,
)
from app.services.solvers import LeaveProblem

# Reuse the same style presets as the solo flow, expressed as stretch caps.
_STYLE_CAPS = {
    "Long Weekends (≤4d)": 4,
    "Mini Breaks (≤6d)": 6,
    "Week-Long (≤9d)": 9,
    "Extended (no cap)": None,
}


def _date_range(start: date, end: date) -> list[date]:
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _holidays_in_span(country: str, start: date, end: date) -> set[date]:
    """Public holidays for ``country`` intersected with the horizon."""
    span_lo, span_hi = start, end
    found: set[date] = set()
    for year in range(start.year, end.year + 1):
        try:
            for d, _ in get_public_holiday_map(country, year):
                if span_lo <= d <= span_hi:
                    found.add(d)
        except Exception:
            # Unknown/unsupported country code — treat as no holidays.
            pass
    return found


def render_household_input(start: date, end: date, solver_name: str) -> list[Member]:
    """Render the household roster editor and return the built members.

    Args:
        start, end: Shared planning horizon (all members share the calendar
            span; their *holidays* still differ by country).
        solver_name: Backend each member's private oracle should use.

    Returns:
        A list of :class:`Member`. May be shorter than the roster if a row is
        incomplete; the caller decides whether there are enough to coordinate.
    """
    country_map = get_supported_country_map()
    country_codes = sorted(country_map.keys())
    # Seed the two default rows with *different* countries so the very first
    # run demonstrates a togetherness gain (identical calendars have nothing to
    # coordinate). Fall back gracefully if these codes aren't supported.
    seed_a = "US" if "US" in country_map else country_codes[0]
    seed_b = (
        "GB" if "GB" in country_map else country_codes[min(1, len(country_codes) - 1)]
    )

    st.markdown(
        "Add each person in the household. Everyone shares the same date range, "
        "but keeps their **own** country holidays, PTO budget and style — none "
        "of which is shared with the others. The optimizer only lines up the "
        "days you can all be off **together**."
    )

    if "household_roster" not in st.session_state:
        st.session_state["household_roster"] = pd.DataFrame(
            [
                {
                    "Name": "Person 1",
                    "Country": seed_a,
                    "PTO": 10,
                    "Style": list(_STYLE_CAPS.keys())[1],
                },
                {
                    "Name": "Person 2",
                    "Country": seed_b,
                    "PTO": 10,
                    "Style": list(_STYLE_CAPS.keys())[1],
                },
            ]
        )

    edited = st.data_editor(
        st.session_state["household_roster"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Name": st.column_config.TextColumn("Name", required=True),
            "Country": st.column_config.SelectboxColumn(
                "Country", options=country_codes, required=True
            ),
            "PTO": st.column_config.NumberColumn(
                "PTO days", min_value=0, max_value=365, step=1, required=True
            ),
            "Style": st.column_config.SelectboxColumn(
                "Vacation style", options=list(_STYLE_CAPS.keys()), required=True
            ),
        },
        key="household_roster_editor",
    )
    st.session_state["household_roster"] = edited
    st.caption(
        "Country codes follow ISO-2 (e.g. US, GB, SG, DE). "
        "Add or remove rows with the ± controls."
    )

    horizon = _date_range(start, end)
    members: list[Member] = []

    for idx, row in edited.iterrows():
        name = str(row.get("Name") or "").strip()
        country = str(row.get("Country") or "").strip()
        if not name or not country:
            continue  # skip incomplete rows

        pto = int(row.get("PTO") or 0)
        style = row.get("Style") or list(_STYLE_CAPS.keys())[1]
        max_stretch = _STYLE_CAPS.get(style)

        prebooked = _render_prebooked(name, idx, start, end)

        problem = LeaveProblem.of(
            date_range=horizon,
            holidays=_holidays_in_span(country, start, end),
            leave_available=pto,
            adjacency_weight=1.0,
            prebooked_days=prebooked,
            max_stretch=max_stretch,
        )
        members.append(Member(name=name, problem=problem, solver_name=solver_name))

    return members


def _render_prebooked(name: str, idx, start: date, end: date) -> list[date]:
    """Optional per-person prebooked-day picker, tucked in an expander."""
    key = f"household_prebooked_{idx}"
    store = st.session_state.setdefault(key, [])

    with st.expander(f"🔒 {name}'s pre-booked days (optional) — {len(store)} set"):
        picked = st.date_input(
            "Add a pre-booked day (e.g. medical, commitment)",
            value=start,
            min_value=start,
            max_value=end,
            key=f"{key}_input",
        )
        cols = st.columns([1, 1, 3])
        if cols[0].button("Add", key=f"{key}_add"):
            if isinstance(picked, date) and picked not in store:
                store.append(picked)
                st.rerun()
        if store and cols[1].button("Clear", key=f"{key}_clear"):
            store.clear()
            st.rerun()
        if store:
            st.write(", ".join(sorted(d.isoformat() for d in store)))

    return list(store)

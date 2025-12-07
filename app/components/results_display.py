import streamlit as st
import pandas as pd
from datetime import timedelta, date, datetime
from typing import List, Dict, Any, Iterable
from app.components.calendar_heatmap import render_calendar_heatmap


# ----------------------------------------------------
# Break Type Label
# ----------------------------------------------------
def classify_break(days: int) -> str:
    if days <= 4:
        return "Long Weekend"
    elif days <= 9:
        return "Week Break"
    return "Extended Break"


def _coerce_to_dates(values: Iterable[Any]) -> List[date]:
    """Convert iterable values into a clean list[date]."""
    out: List[date] = []
    for v in values or []:
        if isinstance(v, date) and not isinstance(v, datetime):
            out.append(v)
        elif isinstance(v, datetime):
            out.append(v.date())
        elif isinstance(v, str):
            try:
                out.append(date.fromisoformat(v))
            except Exception:
                continue
    return out


# ----------------------------------------------------
# Render Break Cards (3 columns)
# ----------------------------------------------------
def render_break_cards(
    break_periods: List[Dict[str, Any]],
    public_holidays: List[date],
):
    st.subheader("🌴 Your Optimized Breaks")

    # Load CSS once
    st.markdown(
        """
<style>
.break-card {
    background: white;
    padding: 18px 20px;
    border-radius: 16px;
    margin-bottom: 18px;
    box-shadow: 0 2px 6px rgba(0,0,0,.07);
    border: 1px solid #eee;
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
}
.break-header {
    font-size: 18px;
    font-weight: 600;
}
.days-off {
    color: #6a5acd;
    font-weight: 600;
    margin-top: 4px;
}
.badge {
    display: inline-block;
    background: #e5f7ec;
    color: #137a3f;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    margin-top: 6px;
    font-weight: 600;
}
.stats {
    margin-top: 12px;
    font-size: 14px;
    line-height: 1.4;
}
.bar {
    margin-top: 14px;
    height: 6px;
    background: #f6e9ff;
    border-radius: 4px;
}
</style>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)

    for i, p in enumerate(break_periods):
        col = cols[i % 3]

        start = p["Start"].strftime("%b %d")
        end = p["End"].strftime("%b %d")

        total = p["Days"]
        pto = p["PTO Used"]

        # Count public holidays inside this break
        holiday_count = sum(1 for d in public_holidays if p["Start"] <= d <= p["End"])

        badge = classify_break(total)

        html = f"""
<div class="break-card">
  <div class="break-header">{start} – {end}</div>
  <div class="days-off">{total} days off</div>
  <div class="badge">{badge}</div>

  <div class="stats">
    🗓 <strong>{pto}</strong> PTO<br>
    ⭐ <strong>{holiday_count}</strong> Public Holidays
  </div>

  <div class="bar"></div>
</div>
"""

        col.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------
# Main Results Rendering
# ----------------------------------------------------
def show_results(result: Dict[str, Any], prebook_pto_count: int = 0):
    # Convert incoming values to real date objects
    break_days: List[date] = sorted(_coerce_to_dates(result.get("break_days", [])))
    leave_days: List[date] = _coerce_to_dates(result.get("leave_days", []))
    public_holidays: List[date] = _coerce_to_dates(result.get("public_holidays", []))
    prebooked_days: List[date] = _coerce_to_dates(result.get("prebooked_days", []))

    # Merge prebooked days into break_days for display
    all_break_days = sorted(set(break_days + prebooked_days))

    # leave_days from optimizer now includes ALL PTO days (prebooked + optimized)
    # since we pass the full budget to the optimizer
    all_leave_days = leave_days
    total_pto_used = len(leave_days)

    break_periods: List[Dict[str, Any]] = []

    # Build continuous break periods
    if all_break_days:
        start = all_break_days[0]
        end = all_break_days[0]

        # leave_days already includes all PTO days (both prebooked and optimized)
        all_pto_days_set = set(leave_days)

        pto_count = 1 if start in all_pto_days_set else 0

        for d in all_break_days[1:]:
            if d == end + timedelta(days=1):
                end = d
                if d in all_pto_days_set:
                    pto_count += 1
            else:
                break_periods.append(
                    {
                        "Start": start,
                        "End": end,
                        "Days": (end - start).days + 1,
                        "PTO Used": pto_count,
                    }
                )
                start, end = d, d
                pto_count = 1 if d in all_pto_days_set else 0

        break_periods.append(
            {
                "Start": start,
                "End": end,
                "Days": (end - start).days + 1,
                "PTO Used": pto_count,
            }
        )

    # Remove pure Sat–Sun weekend-only breaks
    filtered: List[Dict[str, Any]] = []
    for p in break_periods:
        if p["Days"] == 2 and p["Start"].weekday() == 5 and p["End"].weekday() == 6:
            continue
        filtered.append(p)

    # -------------------------------
    # Summary + Cards + Calendar
    # -------------------------------
    if filtered:
        total_break_days = sum(p["Days"] for p in filtered)

        # Summary
        st.subheader("📊 Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Break Days", total_break_days)
        col2.metric("PTO Used", total_pto_used)
        col3.metric("Break Periods", len(filtered))

        # Cards
        render_break_cards(filtered, public_holidays=public_holidays)

        # Calendar View
        # Pick year (from first break day or current year)
        if all_break_days:
            year = all_break_days[0].year
        else:
            year = date.today().year

        try:
            render_calendar_heatmap(
                all_break_days,
                all_leave_days,
                year,
                holiday_map={d: d.strftime("%b %d") for d in public_holidays},
            )
        except Exception as e:
            st.error(f"Calendar rendering failed: {e}")
    else:
        st.info("No break periods found.")

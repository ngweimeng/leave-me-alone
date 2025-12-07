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
def show_results(result: Dict[str, Any]):
    # Convert incoming values to real date objects
    break_days: List[date] = sorted(_coerce_to_dates(result.get("break_days", [])))
    leave_days: List[date] = _coerce_to_dates(result.get("leave_days", []))
    public_holidays: List[date] = _coerce_to_dates(result.get("public_holidays", []))

    break_periods: List[Dict[str, Any]] = []

    # Build continuous break periods
    if break_days:
        start = break_days[0]
        end = break_days[0]
        pto_count = 1 if start in leave_days else 0

        for d in break_days[1:]:
            if d == end + timedelta(days=1):
                end = d
                if d in leave_days:
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
                pto_count = 1 if d in leave_days else 0

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
        col2.metric("PTO Used", len(leave_days))
        col3.metric("Break Periods", len(filtered))

        # Cards
        render_break_cards(filtered, public_holidays=public_holidays)

        # Calendar View
        # Pick year (from first break day or current year)
        if break_days:
            year = break_days[0].year
        else:
            year = date.today().year

        try:
            render_calendar_heatmap(
                break_days,
                leave_days,
                year,
                holiday_map={d: d.strftime("%b %d") for d in public_holidays},
            )
        except Exception as e:
            st.error(f"Calendar rendering failed: {e}")
    else:
        st.info("No break periods found.")

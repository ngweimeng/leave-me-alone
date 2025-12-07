import streamlit as st
import pandas as pd
from app.components.calendar_heatmap import render_calendar_heatmap


def show_results(result):
    # Keep DataFrames for display, but pass raw lists to the heatmap renderer
    leave_days_df = pd.DataFrame({"Leave Days": result["leave_days"]})
    break_days_df = pd.DataFrame({"Break Days": result["break_days"]})

    st.subheader("Recommended Leave Days")
    st.table(leave_days_df)

    st.subheader("Total Break Period")
    st.write(f"**{len(result['break_days'])} days**")

    # Render a visual calendar heatmap of the recommended break days.
    try:
        render_calendar_heatmap(
            result["break_days"], result["leave_days"], result.get("year")
        )
    except Exception:
        # Don't fail the whole results display if the heatmap renderer has issues.
        st.info("Break calendar unavailable.")

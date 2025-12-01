import streamlit as st
import pandas as pd
from app.components.calendar_heatmap import render_calendar_heatmap

def show_results(result):
    st.success("Optimization complete!")

    # Keep DataFrames for display, but pass raw lists to the heatmap renderer
    leave_days_df = pd.DataFrame({"Leave Days": result["leave_days"]})
    break_days_df = pd.DataFrame({"Break Days": result["break_days"]})

    st.subheader("Recommended Leave Days")
    st.table(leave_days_df)

    st.subheader("Total Break Period")
    st.write(f"**{len(result['break_days'])} days**")

    st.subheader("Break Calendar")
    st.write(result["break_days"])

    # `render_calendar_heatmap` expects iterables of dates (lists/sets),
    # not pandas DataFrames. Pass the raw lists from the result dict.
    render_calendar_heatmap(result["break_days"], result["leave_days"], result["year"])

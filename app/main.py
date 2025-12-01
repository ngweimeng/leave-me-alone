import sys
import pathlib

# Ensure project root is on sys.path so `app` package imports work when
# running `streamlit run app/main.py` from the project root or other contexts.
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st
from datetime import date
from app.components.inputs import render_inputs
from app.components.results_display import show_results
from app.services.holiday_service import load_public_holidays
from app.services.optimization_service import run_optimizer


st.set_page_config(
    page_title="Leave Optimizer",
    page_icon="🌴",
    layout="wide"
)

st.sidebar.title("Navigation")

# --- Page content (merged from `app/pages/1_Optimize.py`) ---
st.title("🌴 Leave Optimizer — Maximize Your Break")

st.write("""
Welcome! This tool helps you **maximize your holiday break** using:
- 🇨🇳 Public Holidays (auto-loaded via the `holidays` library)
- 🗓️ Your available leave days
- ⛔ Days you want to block off
- 🧮 LP Optimization via **FICO Xpress**

Fill in the inputs below and click **Optimize Break** to get your personalized plan.
""")

# Collect Inputs
user_input = render_inputs()

st.markdown("---")

if st.button("Optimize Break"):
    ph = load_public_holidays(user_input.country, user_input.year)

    result = run_optimizer(
        user_input.start,
        user_input.end,
        ph,
        user_input.blocked_days,
        user_input.leave_available,
        adjacency_weight=user_input.adjacency_weight,
    )

    st.success("Optimization Completed!")
    show_results(result)


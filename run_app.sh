#!/bin/bash
# Script to run the Leave Me Alone Streamlit app
# This ensures the app runs from the correct directory

cd "$(dirname "$0")"
source .venv/bin/activate
streamlit run app/main.py

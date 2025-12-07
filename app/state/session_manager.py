import streamlit as st
from datetime import date
from typing import List, Tuple


class SessionManager:
    """Encapsulates access to Streamlit session state keys used by the app.

    Keys managed:
    - 'leave_available_total' (int)
    - 'prebooked_days' (List[date])
    - 'other_time_off' (List[Tuple[date,str]])
    - 'selected_public_holidays' (List[str])

    Provide simple add/remove/get helpers to centralize session mutations.
    """

    def get_leave_available(self) -> int:
        return int(st.session_state.get("leave_available_total", 0))

    def set_leave_available(self, value: int) -> None:
        st.session_state["leave_available_total"] = int(value)

    # Prebooked days
    def get_prebooked(self) -> List[date]:
        return list(st.session_state.get("prebooked_days", []))

    def add_prebooked(self, d: date) -> None:
        if "prebooked_days" not in st.session_state:
            st.session_state["prebooked_days"] = []
        if d not in st.session_state["prebooked_days"]:
            st.session_state["prebooked_days"].append(d)

    def remove_prebooked(self, d: date) -> None:
        if "prebooked_days" in st.session_state and d in st.session_state["prebooked_days"]:
            st.session_state["prebooked_days"].remove(d)

    # Other time off
    def get_other_time_off(self) -> List[Tuple[date, str]]:
        return list(st.session_state.get("other_time_off", []))

    def add_other_time_off(self, entry: Tuple[date, str]) -> None:
        if "other_time_off" not in st.session_state:
            st.session_state["other_time_off"] = []
        if entry not in st.session_state["other_time_off"]:
            st.session_state["other_time_off"].append(entry)

    def remove_other_time_off(self, entry: Tuple[date, str]) -> None:
        if "other_time_off" in st.session_state and entry in st.session_state["other_time_off"]:
            st.session_state["other_time_off"].remove(entry)

    # Selected public holidays placeholder (stores the display strings)
    def get_selected_public_holidays(self) -> List[str]:
        return list(st.session_state.get("selected_public_holidays", []))

    def set_selected_public_holidays(self, values: List[str]) -> None:
        st.session_state["selected_public_holidays"] = list(values)

"""Tests for the household-input helpers (the UI → service glue).

These cover the pure, Streamlit-free parts of the household flow: holiday
resolution per country and the style→stretch mapping. The rendering itself
needs a Streamlit runtime and is exercised manually / via the demo.
"""

from datetime import date

from app.components.household_input import _STYLE_CAPS, _holidays_in_span


def test_holidays_in_span_filters_to_horizon():
    # US New Year's Day 2025 is in span; Christmas is out of a Jan-only window.
    got = _holidays_in_span("US", date(2025, 1, 1), date(2025, 1, 31))
    assert date(2025, 1, 1) in got
    assert date(2025, 12, 25) not in got


def test_holidays_in_span_differs_by_country():
    # UK has a Boxing Day (Dec 26) holiday the US federal calendar lacks.
    span_lo, span_hi = date(2025, 12, 1), date(2025, 12, 31)
    gb = _holidays_in_span("GB", span_lo, span_hi)
    us = _holidays_in_span("US", span_lo, span_hi)
    assert date(2025, 12, 26) in gb
    assert date(2025, 12, 26) not in us


def test_holidays_in_span_unknown_country_is_empty():
    assert _holidays_in_span("ZZ", date(2025, 1, 1), date(2025, 12, 31)) == set()


def test_style_caps_match_expected_length_controls():
    # The four presets map to the stretch caps used by the solo flow (+ no-cap).
    assert set(_STYLE_CAPS.values()) == {4, 6, 9, None}

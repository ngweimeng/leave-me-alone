"""
Utility functions for mapping country codes to readable names and fetching
public holidays using the `holidays` library.
"""

import holidays
import pycountry
from typing import Dict, List, Tuple


# -------------------------------------------------------------------
# Country Name Resolution
# -------------------------------------------------------------------
def _get_country_name(code: str) -> str:
    """
    Convert a 2-letter or 3-letter ISO country code into a readable name.

    Examples:
        "US"  → "United States"
        "FRA" → "France"
        "SG"  → "Singapore"

    If a code is unrecognized, the function returns the code itself.
    """
    try:
        code_upper = code.upper()

        # pycountry distinguishes lookup format by code length
        country = (
            pycountry.countries.get(alpha_2=code_upper)
            if len(code_upper) == 2
            else pycountry.countries.get(alpha_3=code_upper)
        )

        return country.name if country else code
    except Exception:
        # Defensive fallback
        return code


# -------------------------------------------------------------------
# Country Mapping Construction
# -------------------------------------------------------------------
def _build_country_map() -> Dict[str, str]:
    """
    Build a mapping of supported holiday country codes → readable country names.

    Why deduplication is needed:
        The `holidays` library sometimes includes BOTH:
            - a 2-letter ISO code (e.g., "US")
            - a 3-letter ISO code (e.g., "USA")
        for the same country.

        Since ISO-2 codes are canonical and shorter, we keep only the
        2-letter version when duplicates exist.

    Returns:
        {
            "US": "United States",
            "SG": "Singapore",
            "FRA": "France",
            ...
        }
    """
    supported_codes = list(holidays.list_supported_countries().keys())

    # Convert once to lowercase for comparison convenience
    lower_codes = {code.lower() for code in supported_codes}

    # Identify all 2-letter codes available
    iso2_codes = {code for code in lower_codes if len(code) == 2}

    # Determine which 3-letter codes should be removed
    redundant_3letter_codes = set()
    for code in supported_codes:
        if len(code) != 3:
            continue

        try:
            country = pycountry.countries.get(alpha_3=code.upper())
            if not country:
                continue

            alpha2_lower = getattr(country, "alpha_2", "").lower()

            # If ISO-2 exists, we prefer that version and drop the ISO-3
            if alpha2_lower in iso2_codes:
                redundant_3letter_codes.add(code.lower())

        except Exception:
            # Continue gracefully (bad code or lookup failure)
            pass

    # Create final map: readable name only for non-redundant codes
    return {
        code: _get_country_name(code)
        for code in sorted(supported_codes)
        if code.lower() not in redundant_3letter_codes
    }


# Cached at import time for efficiency
COUNTRY_MAP: Dict[str, str] = _build_country_map()


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------
def get_supported_country_map() -> Dict[str, str]:
    """
    Return a mapping of available holiday country codes → readable names.

    Used for:
    - populating dropdowns
    - displaying country names in UI
    - validating user selections

    Example:
        {
            "SG": "Singapore",
            "US": "United States",
            "DE": "Germany"
        }
    """
    return COUNTRY_MAP


def get_public_holiday_map(country: str, year: int) -> List[Tuple]:
    """
    Return sorted public holidays for a given country and year.

    Args:
        country: ISO-2 or ISO-3 country code (e.g., "SG", "US", "FRA")
        year: Gregorian calendar year

    Returns:
        List of (date, holiday_name) sorted chronologically:
            [
                (date(2025, 1, 1), "New Year's Day"),
                (date(2025, 2, 10), "Chinese New Year"),
                ...
            ]
    """
    holiday_items = holidays.country_holidays(country, years=year).items()
    return sorted(holiday_items)

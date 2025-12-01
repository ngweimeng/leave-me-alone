import holidays

def get_all_supported_countries():
    """Return country codes supported by the holidays library."""
    return sorted(list(holidays.list_supported_countries().keys()))


def get_supported_country_map():
    """Return a mapping of country code -> full country name for supported countries.

    This can be used by UIs to display friendly country names while keeping the
    underlying country code for API/logic calls.
    """
    codes_map = holidays.list_supported_countries()

    # Attempt to map ISO codes to human-friendly country names using
    # `pycountry` if available. If not installed, fall back to returning
    # the code itself as the display name.
    try:
        import pycountry

        result = {}
        for code in sorted(codes_map.keys()):
            name = None
            try:
                if len(code) == 2:
                    country = pycountry.countries.get(alpha_2=code.upper())
                else:
                    country = pycountry.countries.get(alpha_3=code.upper())
                if country is not None:
                    name = getattr(country, 'name', None)
            except Exception:
                name = None

            result[code] = name or code
        return result
    except Exception:
        # pycountry not available — return codes as-is
        return {c: c for c in sorted(codes_map.keys())}

def load_public_holidays(country: str, year: int):
    ph = holidays.country_holidays(country, years=year)
    return sorted(list(ph.keys()))


def get_public_holiday_map(country: str, year: int):
    """Return a list of (date, name) tuples for the given country/year.

    This is useful for UI display while `load_public_holidays` still
    returns only the dates (used by the optimizer).
    """
    ph = holidays.country_holidays(country, years=year)
    # `ph` maps date -> name (or names). Return sorted list of tuples.
    items = sorted(ph.items())
    return items

from app.services.holiday_service import get_supported_country_map


def test_country_list_not_empty():
    assert len(get_supported_country_map()) > 10

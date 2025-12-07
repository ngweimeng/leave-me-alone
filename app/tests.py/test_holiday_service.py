from app.services.holiday_service import get_all_supported_countries


def test_country_list_not_empty():
    assert len(get_all_supported_countries()) > 10

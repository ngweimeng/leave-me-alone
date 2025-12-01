def validate_dates(start, end):
    if end < start:
        raise ValueError("End date cannot be before start date")

from datetime import timedelta


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

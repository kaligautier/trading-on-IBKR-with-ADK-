"""Weekday freshness, with an explicit as-of date for historical replay."""

from datetime import date, timedelta


def is_fresh(observed_on: date | None, as_of: date, max_weekdays: int = 3) -> bool:
    if observed_on is None or observed_on > as_of:
        return False
    age = sum(
        (observed_on + timedelta(days=offset)).weekday() < 5
        for offset in range(1, (as_of - observed_on).days + 1)
    )
    return age <= max_weekdays

"""Date contracts shared by market providers."""

from datetime import datetime, timezone


def require_current_fundamentals(curr_date: str | None) -> None:
    """Snapshots lack publication history; never label them point-in-time data."""
    if (
        curr_date
        and datetime.strptime(curr_date, "%Y-%m-%d").date()
        != datetime.now(timezone.utc).date()
    ):
        raise ValueError(
            "Historical fundamentals unavailable: provider has no point-in-time disclosure data"
        )

"""Calendar-aware market horizon value object."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class CalendarHorizon:
    """Find a calendar reference date relative to a market observation."""

    label: str
    days: int = 0
    months: int = 0
    years: int = 0
    year_to_date: bool = False

    def __post_init__(self) -> None:
        if self.year_to_date:
            if self.days or self.months or self.years:
                raise ValueError("YTD cannot include a rolling duration")
            return
        if self.days + self.months + self.years <= 0:
            raise ValueError("A calendar horizon must be positive")

    def target_date(self, observed_on: date) -> date:
        if self.year_to_date:
            return date(observed_on.year - 1, 12, 31)
        shifted = self._subtract_months(observed_on)
        return shifted - timedelta(days=self.days)

    def _subtract_months(self, observed_on: date) -> date:
        months_to_subtract = self.months + (self.years * 12)
        month_index = observed_on.year * 12 + observed_on.month - 1
        target_year, target_month_index = divmod(month_index - months_to_subtract, 12)
        target_month = target_month_index + 1
        target_day = min(observed_on.day, monthrange(target_year, target_month)[1])
        return date(target_year, target_month, target_day)

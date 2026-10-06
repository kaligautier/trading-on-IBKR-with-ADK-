"""Compute indicators from collected observations without contacting providers."""

import math
from datetime import date
from decimal import Decimal, InvalidOperation

from app.config.constants import (
    CHANGE_DECIMAL_PLACES,
    DECIMAL_REFERENCE_MAX_WEEKDAYS,
    FALLING_TREND,
    HORIZONS,
    MIN_PERCENTILE_OBSERVATIONS,
    PERCENTILE_HORIZON,
    PRICE_DECIMAL_PLACES,
    RISING_TREND,
    STABLE_TREND,
    SUCCESS,
    YTD_HORIZON_LABEL,
)
from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)
from app.models.calendar_horizon import CalendarHorizon
from app.models.market_assets import HorizonResult, Trend
from app.models.step_01_external_market_data import (
    ExternalMarketAsset,
    ExternalMarketData,
)
from app.models.step_02_trend_market_data import (
    TrendMarketAsset,
    TrendMarketData,
)
from app.services.data_freshness import is_fresh
from app.utils.error import InvalidInputError


class MarketDataTrendService:
    """Enrich collected observations with horizons, YTD direction and percentile."""

    def define_trend(self, external_market_data: ExternalMarketData) -> TrendMarketData:
        assets = {
            key: self._enrich_asset(asset)
            for key, asset in external_market_data.assets.items()
        }
        return TrendMarketData(assets=assets)

    def _enrich_asset(self, asset: ExternalMarketAsset) -> TrendMarketAsset:
        history = self._validated_history(asset)
        if asset.status == SUCCESS:
            indicators = self._build_result(asset.symbol, history)
        else:
            indicators = {"status": "error", "error": asset.error}

        enriched_asset = TrendMarketAsset.model_validate(
            {**asset.model_dump(exclude={"observations"}), **indicators}
        )
        if enriched_asset.status == SUCCESS:
            ytd = enriched_asset.horizons.get(YTD_HORIZON_LABEL)
            enriched_asset.trend = ytd.trend if ytd is not None else None
        return enriched_asset

    @staticmethod
    def _validated_history(asset: ExternalMarketAsset) -> ClosingPriceHistory:
        """Validate the external snapshot before calculating indicators."""
        if asset.status == "error":
            if asset.observations or not asset.error:
                raise InvalidInputError(
                    "Failed collection requires an error and no observations",
                    details={"symbol": asset.symbol},
                )
            return ClosingPriceHistory(())
        if asset.error or not asset.observations:
            raise InvalidInputError(
                "Successful collection requires observations and no error",
                details={"symbol": asset.symbol},
            )
        if any(
            observation.observed_on > asset.retrieved_at.date()
            for observation in asset.observations
        ):
            raise InvalidInputError(
                "Provider returned a future observation",
                details={"symbol": asset.symbol},
            )
        try:
            return ClosingPriceHistory(
                tuple(
                    ClosingPrice(
                        observation.observed_on,
                        Decimal(observation.value)
                        if isinstance(observation.value, str)
                        else observation.value,
                    )
                    for observation in asset.observations
                )
            )
        except (ValueError, InvalidOperation) as error:
            raise InvalidInputError(
                "Invalid observation history",
                details={"symbol": asset.symbol, "cause_type": type(error).__name__},
            ) from error

    def _build_result(self, symbol: str, closing_prices: ClosingPriceHistory) -> dict:
        current_price = closing_prices.latest
        if current_price is None:
            return {"status": "error", "error": f"No data for {symbol}"}

        current = float(current_price.value)
        if current_price.observed_on > date.today():
            return {"status": "error", "error": "future_observation"}
        if not math.isfinite(current):
            return {"status": "error", "error": f"NaN current price for {symbol}"}

        horizons = self._compute_horizons(closing_prices, current_price)
        percentile, history_points = self._compute_percentile(
            closing_prices, current_price
        )
        return {
            "status": SUCCESS,
            "symbol": symbol,
            "value": str(current_price.value)
            if isinstance(current_price.value, Decimal)
            else round(current, PRICE_DECIMAL_PLACES),
            "horizons": horizons,
            "observed_on": current_price.observed_on.isoformat(),
            "percentile_3y": percentile,
            "history_points_3y": history_points,
        }

    @staticmethod
    def _compute_percentile(
        closing_prices: ClosingPriceHistory, current_price: ClosingPrice
    ) -> tuple[float | None, int]:
        window_start = PERCENTILE_HORIZON.target_date(current_price.observed_on)
        reference_values = [
            price.value
            for price in closing_prices.prices
            if window_start <= price.observed_on < current_price.observed_on
        ]
        history_points = len(reference_values)
        if history_points < MIN_PERCENTILE_OBSERVATIONS:
            return None, history_points

        current_value = float(current_price.value)
        rank = 0.0
        for reference_value in reference_values:
            if reference_value < current_value:
                rank += 1.0
            elif reference_value == current_value:
                # Equal values count as half an observation (midrank).
                rank += 0.5
        return rank / history_points, history_points

    def _compute_horizons(
        self,
        closing_prices: ClosingPriceHistory,
        current_price: ClosingPrice,
    ) -> dict:
        horizons = {}
        for horizon in HORIZONS:
            reference_price = closing_prices.on_or_before(
                horizon.target_date(current_price.observed_on)
            )
            horizons[horizon.label] = self._compute_single_horizon(
                current_price, reference_price, horizon
            )
        return horizons

    def _compute_single_horizon(
        self,
        current_price: ClosingPrice,
        reference_price: ClosingPrice | None,
        horizon: CalendarHorizon,
    ):
        if reference_price is None:
            return None

        if isinstance(current_price.value, Decimal):
            target = horizon.target_date(current_price.observed_on)
            if not is_fresh(
                reference_price.observed_on,
                target,
                max_weekdays=DECIMAL_REFERENCE_MAX_WEEKDAYS,
            ):
                return None
            percent = round(
                float(self._percent_change(current_price.value, reference_price.value)),
                CHANGE_DECIMAL_PLACES,
            )
            return HorizonResult(
                percent,
                str(reference_price.value),
                self._classify_trend(current_price.value, reference_price.value),
            ).to_dict()

        current = float(current_price.value)
        past = float(reference_price.value)
        if math.isnan(past):
            return None

        percent = round(self._percent_change(current, past), CHANGE_DECIMAL_PLACES)
        trend = self._classify_trend(current_price.value, reference_price.value)
        return HorizonResult(
            percent, round(past, PRICE_DECIMAL_PLACES), trend
        ).to_dict()

    @staticmethod
    def _percent_change(current: float, past: float) -> float:
        if not past:
            return 0.0
        return (current - past) / past * 100

    @staticmethod
    def _classify_trend(current: float | Decimal, reference: float | Decimal) -> Trend:
        """Compare observed values directly, independently of percentage rounding."""
        if current > reference:
            return RISING_TREND
        if current < reference:
            return FALLING_TREND
        return STABLE_TREND

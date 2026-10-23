"""Canonical queries and endpoint/filter-bound keyset positions."""

import base64
import hashlib
import json
import re
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

View = Literal["history", "latest", "recommendations"]
RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    created_at: AwareDatetime
    id: UUID
    scope: str = Field(pattern=r"^[a-f0-9]{64}$")

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode()

    @classmethod
    def decode(cls, token: str) -> Self:
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", token) or len(token) > 512:
                raise ValueError()
            raw = base64.b64decode(token, altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(raw).decode() != token:
                raise ValueError()
            return cls.model_validate_json(raw)
        except ValueError:
            raise ValueError("Invalid pagination token") from None


class AnalysisSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    view: View
    ticker: str | None
    ratings: tuple[str, ...] | None
    page_size: int = Field(ge=1, le=100)
    cursor: Cursor | None = None

    @property
    def scope(self) -> str:
        filters = [self.view, self.ticker, self.ratings]
        return hashlib.sha256(json.dumps(filters).encode()).hexdigest()

    @classmethod
    def from_parameters(
        cls,
        view: View,
        ticker: str | None,
        rating: str | None,
        page_size: int,
        page_token: str,
    ) -> Self:
        if ticker is not None:
            ticker = ticker.strip().upper()
            if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,31}", ticker):
                raise ValueError("Invalid ticker")
        if rating is None and view == "recommendations":
            rating = "Buy,Overweight"
        ratings = None
        if rating is not None:
            values = {value.strip().lower() for value in rating.split(",")}
            if not values or not values.issubset({value.lower() for value in RATINGS}):
                raise ValueError("Invalid rating")
            ratings = tuple(value for value in RATINGS if value.lower() in values)
        query = cls(view=view, ticker=ticker, ratings=ratings, page_size=page_size)
        if page_token:
            cursor = Cursor.decode(page_token)
            if cursor.scope != query.scope:
                raise ValueError("Pagination token does not match this query")
            return query.model_copy(update={"cursor": cursor})
        return query

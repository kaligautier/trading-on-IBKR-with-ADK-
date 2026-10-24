"""Atomic intake and public status; review stays outside the public API."""

from typing import Protocol
from uuid import UUID

from app.domain.suggestions import Suggestion, SuggestionInput


class SuggestionStore(Protocol):
    async def submit(self, request: SuggestionInput) -> Suggestion: ...

    async def get(self, suggestion_id: UUID) -> Suggestion | None: ...

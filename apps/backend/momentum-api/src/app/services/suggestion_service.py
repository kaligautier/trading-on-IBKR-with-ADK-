"""Validate public input before atomic intake in Momentum's own store."""

from uuid import UUID

from app.domain.suggestions import Suggestion, SuggestionInput
from app.ports.suggestions import SuggestionStore


class SuggestionService:
    def __init__(self, store: SuggestionStore):
        self.store = store

    async def submit(self, symbol: str, reason: str, caller: str) -> Suggestion:
        return await self.store.submit(SuggestionInput(symbol, reason, caller))

    async def get(self, suggestion_id: UUID) -> Suggestion | None:
        return await self.store.get(suggestion_id)

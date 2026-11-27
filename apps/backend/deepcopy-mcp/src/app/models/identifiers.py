"""Identifiers shared by domain models and API contracts."""

from typing import Annotated

from pydantic import Field

AccountId = Annotated[str, Field(pattern=r"^[A-Z0-9]{1,20}$")]
Symbol = Annotated[str, Field(pattern=r"^[A-Z0-9.\-]{1,12}$")]
Page = Annotated[int, Field(ge=0, le=1000)]

"""Common policy for validated public API response models."""

from pydantic import BaseModel, ConfigDict


class PublicResponse(BaseModel):
    """Allow additive API changes without leaking undeclared fields."""

    model_config = ConfigDict(extra="ignore")

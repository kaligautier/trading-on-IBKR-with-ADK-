"""Uvicorn factory entry point with JSON application logs."""

import logging

from app.application import create_app

logging.basicConfig(level=logging.INFO, format="%(message)s")

__all__ = ["create_app"]

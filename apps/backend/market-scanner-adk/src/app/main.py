"""
Application entry point.

This module creates the FastAPI application instance and configures logging.
"""

from app.application import create_app
from app.utils.logger import config_logger

config_logger()

app = create_app()

"""Uvicorn factory entry point with JSON application logs."""

import logging

from fastapi import FastAPI

from app.application import create_app as build_app


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return build_app()

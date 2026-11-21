"""Bundled report v3 JSON schema, shared by the mapper and the contract route."""

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

REPORT_SCHEMA = json.loads(files("app.schemas").joinpath("report-v3.json").read_text())
REPORT_VALIDATOR = Draft202012Validator(REPORT_SCHEMA, format_checker=FormatChecker())

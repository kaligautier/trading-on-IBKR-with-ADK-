"""Strong representation tags and conditional GET/HEAD precedence."""

import hashlib
import re

ENTITY_TAG = r'(?:W/)?"[\x21\x23-\x7e\x80-\xff]*"'


def representation_tag(body: bytes) -> str:
    return '"' + hashlib.sha256(body).hexdigest() + '"'


def tags(value: str) -> list[str]:
    if value.strip() == "*":
        return ["*"]
    if not re.fullmatch(rf"\s*{ENTITY_TAG}(?:\s*,\s*{ENTITY_TAG})*\s*", value):
        raise ValueError("Malformed conditional header")
    return re.findall(ENTITY_TAG, value)


def precondition(tag: str, match: str | None, none: str | None) -> int | None:
    if match is not None:
        values = tags(match)
        if "*" not in values and tag not in values:
            return 412
    if none is not None:
        values = tags(none)
        if "*" in values or any(value.removeprefix("W/") == tag for value in values):
            return 304
    return None

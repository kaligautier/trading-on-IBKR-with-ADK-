"""Representation and identity-coding selection (RFC 9110, section 12.5)."""

import re

HTTP_WORD = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
QUALITY = re.compile(r"(?:0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?)\Z")


def split_quoted(value: str, separator: str) -> list[str]:
    """Split HTTP lists without treating quoted delimiters as separators."""
    parts, start, quoted, escaped = [], 0, False, False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == separator and not quoted:
            parts.append(value[start:index].strip())
            start = index + 1
    if quoted or escaped:
        return []
    return [*parts, value[start:].strip()]


def weighted(value: str) -> tuple[str, dict[str, str], float] | None:
    parts = split_quoted(value, ";")
    if not parts:
        return None
    params: dict[str, str] = {}
    quality = 1.0
    for part in parts[1:]:
        key, sep, raw = part.partition("=")
        key, raw = key.strip().lower(), raw.strip()
        if not sep or not re.fullmatch(HTTP_WORD, key) or key in params:
            return None
        if key == "q":
            if not QUALITY.fullmatch(raw):
                return None
            quality = float(raw)
        elif not re.fullmatch(HTTP_WORD + r'|"(?:[^"\\\r\n]|\\[^\r\n])*"', raw):
            return None
        params[key] = raw
    params.pop("q", None)
    return parts[0].lower(), params, quality


def accepts(value: str | None, media_type: str) -> bool:
    if value is None:
        return True
    candidates: list[tuple[int, float]] = []
    major = media_type.split("/")[0]
    for entry in split_quoted(value, ","):
        parsed = weighted(entry)
        if parsed is None:
            continue
        media, params, quality = parsed
        if media_type == "application/json":
            # RFC 8259 section 11: charset has no effect on application/json.
            params.pop("charset", None)
        # No representation parameters are advertised by this API.
        if params:
            continue
        if media in ("*/*", f"{major}/*", media_type):
            specificity = 2 if media == media_type else int(media != "*/*")
            candidates.append((specificity, quality))
    return bool(candidates) and max(candidates)[1] > 0


def accepts_identity(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    qualities: dict[str, float] = {}
    for entry in split_quoted(value, ","):
        parsed = weighted(entry)
        if parsed is not None and not parsed[1]:
            qualities[parsed[0]] = parsed[2]
    if "identity" in qualities:
        return qualities["identity"] > 0
    return qualities.get("*", 1) > 0

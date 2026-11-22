"""HTTP policy follows wire semantics, including refusal and precedence cases."""

import json

import pytest

from app.dto.response.error_response import error_bytes
from app.presentation.http.conditional import precondition, representation_tag
from app.presentation.http.negotiation import accepts, accepts_identity
from app.utils.error import AppError, ErrorCode


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("*/*", True),
        ("text/html", False),
        ("application/*;q=0.5", True),
        ("application/json;q=0", False),
        ("application/json;q=0, */*;q=1", False),
        ("application/*;q=0, */*;q=1", False),
        ('application/json;profile="a,b", application/json;q=0.2', True),
        ("application/json;q=1.1", False),
        ("application/json;q=.5", False),
        ("application/json;q=0.001", True),
        ("application/json;q=0.0000", False),
        ("APPLICATION/JSON;Q=1", True),
        ("application/json;profile=unknown", False),
        ("application/json;charset=utf-8", True),
        ('APPLICATION/JSON;CHARSET="UTF-8"', True),
        ("application/json;charset=iso-8859-1", True),
        ("application/*;charset=utf-8", True),
        ("application/json;charset=utf-8;q=0, */*;q=1", False),
        ("application/json;q=0;charset=utf-8, application/*;q=1", False),
        ("application/json;charset=utf-8;q=0.5, */*;q=0", True),
        ("application/json;charset=utf-8;profile=unknown", False),
        ("application/json;charset=utf-8;charset=utf-8", False),
    ],
)
def test_accept(value: str | None, expected: bool) -> None:
    assert accepts(value, "application/json") is expected


def test_json_charset_tolerance_does_not_apply_to_other_media_types():
    assert not accepts("text/plain;charset=utf-8", "text/plain")
    assert not accepts(
        "application/problem+json;charset=utf-8", "application/problem+json"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("gzip", True),
        ("*;q=0", False),
        ("identity;q=0, *;q=1", False),
        ("identity;q=0.1,*;q=0", True),
    ],
)
def test_identity(value: str | None, expected: bool) -> None:
    assert accepts_identity(value) is expected


def test_exact_bytes_have_strong_tags() -> None:
    assert representation_tag(b"{}") == representation_tag(b"{}")
    assert representation_tag(b"{}") != representation_tag(b"{ }")
    assert representation_tag(b"{}").startswith('"')


@pytest.mark.parametrize(
    ("match", "none", "expected"),
    [
        (None, None, None),
        ("*", None, None),
        ('"different"', None, 412),
        ('W/"same"', None, 412),
        ('"same", "other"', None, None),
        (None, "*", 304),
        (None, 'W/"same"', 304),
        ('"bad"', '"same"', 412),
        ('"same"', '"other"', None),
        (None, '"a,b", "same"', 304),
    ],
)
def test_preconditions(
    match: str | None, none: str | None, expected: int | None
) -> None:
    assert precondition('"same"', match, none) == expected


@pytest.mark.parametrize("value", ["same", '"bad', '*,"same"', '"a" trailing'])
def test_malformed_condition(value: str) -> None:
    with pytest.raises(ValueError):
        precondition('"same"', value, None)


def test_error_body_has_only_the_aip_193_fields() -> None:
    body = json.loads(error_bytes(AppError(ErrorCode.INVALID_ARGUMENT)))
    error = body["error"]
    assert set(body) == {"error"}
    assert set(error) == {"code", "message", "status", "details"}
    assert (error["code"], error["status"]) == (400, "INVALID_ARGUMENT")
    assert error["message"] == "The request parameters or headers are invalid."
    assert [item["@type"].rsplit(".", 1)[1] for item in error["details"]] == [
        "ErrorInfo",
        "Help",
    ]


def test_etags_use_literal_backslashes_not_quoted_string_escaping() -> None:
    assert precondition('"same"', None, '"a\\", "same"') == 304


@pytest.mark.parametrize("condition", [', "same",', ',, W/"same", ,'])
def test_empty_etag_list_elements_are_ignored(condition):
    assert precondition('"same"', None, condition) == 304


def test_public_error_codes_and_distinct_not_found_codes():
    for code in (
        ErrorCode.UNAUTHENTICATED,
        ErrorCode.INVALID_STORED_ANALYSIS,
        ErrorCode.ANALYSIS_NOT_FOUND,
        ErrorCode.NOT_FOUND,
    ):
        details = json.loads(error_bytes(AppError(code)))["error"]["details"]
        assert details[0]["reason"] == code.name

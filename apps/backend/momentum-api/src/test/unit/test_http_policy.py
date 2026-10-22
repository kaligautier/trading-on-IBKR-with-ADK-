"""HTTP policy follows wire semantics, including refusal and precedence cases."""

import json

import pytest

from app.presentation.http.conditional import precondition, representation_tag
from app.presentation.http.negotiation import accepts, accepts_identity
from app.presentation.http.problems import APIError, problem_bytes


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
    ],
)
def test_accept(value: str | None, expected: bool) -> None:
    assert accepts(value, "application/json") is expected


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


def test_problem_has_stable_type_and_matching_status() -> None:
    problem = json.loads(problem_bytes(APIError(400, "invalid-argument")))
    assert problem["status"] == 400
    assert problem["code"] == "INVALID_ARGUMENT"
    assert problem["type"].startswith("https://github.com/kaligautier/")
    assert "instance" not in problem


def test_etags_use_literal_backslashes_not_quoted_string_escaping() -> None:
    assert precondition('"same"', None, '"a\\", "same"') == 304


@pytest.mark.parametrize("condition", [', "same",', ',, W/"same", ,'])
def test_empty_etag_list_elements_are_ignored(condition):
    assert precondition('"same"', None, condition) == 304


def test_public_problem_codes_and_distinct_not_found_types():
    assert (
        json.loads(problem_bytes(APIError(401, "invalid-token")))["code"]
        == "UNAUTHENTICATED"
    )
    assert (
        json.loads(problem_bytes(APIError(500, "invalid-stored-data")))["code"]
        == "INVALID_STORED_ANALYSIS"
    )
    assert (
        json.loads(problem_bytes(APIError(404, "analysis-not-found")))["code"]
        == "ANALYSIS_NOT_FOUND"
    )
    assert json.loads(problem_bytes(APIError(404, "not-found")))["code"] == "NOT_FOUND"

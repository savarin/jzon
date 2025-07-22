"""
JSON specification compliance tests for valid JSON inputs.

Validates that properly formatted JSON strings parse successfully and produce
the expected Python objects.
"""

import pytest

import jzon

from .conftest import JsonTestCase


def test_json_spec_compliance(json_pass_cases: list[JsonTestCase]) -> None:
    """
    Validates JSON strings that must parse successfully per specification.

    Tests standards compliance for valid JSON structures including complex
    nested documents, deep arrays, and simple objects.
    """
    for case in json_pass_cases:
        # Should not raise any exceptions
        result = jzon.loads(case.input_data)

        # Verify we get some result (exact validation comes later)
        assert result is not None or case.input_data.strip() == "null"


def test_basic_json_values(basic_json_values: list[JsonTestCase]) -> None:
    """
    Validates parsing of fundamental JSON value types.

    Covers all JSON primitive types and basic container structures
    to ensure core parsing functionality works correctly.
    """
    for case in basic_json_values:
        if case.should_fail:
            with pytest.raises(jzon.JSONDecodeError):
                jzon.loads(case.input_data)
        else:
            result = jzon.loads(case.input_data)
            if case.expected_output is not None:
                assert result == case.expected_output


def test_empty_containers() -> None:
    """
    Validates parsing of empty JSON containers.
    """
    assert jzon.loads("[]") == []
    assert jzon.loads("{}") == {}
    assert jzon.loads(" [] ") == []  # With whitespace
    assert jzon.loads(" {} ") == {}  # With whitespace


def test_whitespace_handling() -> None:
    """
    Validates proper handling of JSON whitespace.
    """
    # Leading/trailing whitespace should be ignored
    assert jzon.loads(" null ") is None
    assert jzon.loads("\n\ttrue\n") is True
    assert jzon.loads("\r\n42\r\n") == 42

    # Whitespace in containers
    assert jzon.loads("[ 1 , 2 , 3 ]") == [1, 2, 3]
    assert jzon.loads('{ "key" : "value" }') == {"key": "value"}

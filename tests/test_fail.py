"""
JSON specification failure tests ensuring standards compliance.

Validates that invalid JSON strings properly raise JSONDecodeError exceptions
with appropriate error messages and position information.
"""

import sys

import pytest

import jzon

from .conftest import JsonTestCase


def test_json_spec_failures(json_fail_cases: list[JsonTestCase]) -> None:
    """
    Validates JSON strings that must fail parsing per specification.

    Tests all 33 JSON_checker failure cases to ensure strict standards
    compliance and proper error handling for malformed JSON.
    """
    for case in json_fail_cases:
        if case.skip_reason:
            pytest.skip(case.skip_reason)

        with pytest.raises(jzon.JSONDecodeError) as exc_info:
            jzon.loads(case.input_data)

        # Ensure error contains position information
        assert exc_info.value.pos >= 0
        assert exc_info.value.lineno >= 1
        assert exc_info.value.colno >= 1


def test_non_string_keys_dict_encoding() -> None:
    """
    Validates dictionary encoding rejects non-serializable key types.
    """
    data = {"a": 1, (1, 2): 2}

    with pytest.raises(TypeError, match=r"keys must be.*not tuple"):
        jzon.dumps(data)


def test_module_not_serializable() -> None:
    """
    Validates modules raise proper TypeError during encoding.
    """
    with pytest.raises(
        TypeError, match=r"Object of type module is not JSON serializable"
    ):
        jzon.dumps(sys)


def test_nested_non_serializable_error_context() -> None:
    """
    Validates error context is preserved in nested non-serializable objects.
    """
    # Test nested list context
    with pytest.raises(TypeError) as exc_info:
        jzon.dumps([1, [2, 3, sys]])

    # Should have context notes showing nesting path
    assert hasattr(exc_info.value, "__notes__")

    # Test nested tuple context
    with pytest.raises(TypeError) as exc_info:
        jzon.dumps((1, (2, 3, sys)))

    # Test nested dict context
    with pytest.raises(TypeError) as exc_info:
        jzon.dumps({"a": {"b": sys}})


@pytest.mark.parametrize(
    "input_data,expected_msg,expected_pos",
    [
        ("", "Expecting value", 0),
        ("[", "Expecting value", 1),
        ("[42", "Expecting ',' delimiter", 3),
        ("[42,", "Expecting value", 4),
        ('["', "Unterminated string starting at", 1),
        ('["spam', "Unterminated string starting at", 1),
        ('["spam"', "Expecting ',' delimiter", 7),
        ('["spam",', "Expecting value", 8),
        ("{", "Expecting property name enclosed in double quotes", 1),
        ('{"', "Unterminated string starting at", 1),
        ('{"spam', "Unterminated string starting at", 1),
        ('{"spam"', "Expecting ':' delimiter", 7),
        ('{"spam":', "Expecting value", 8),
        ('{"spam":42', "Expecting ',' delimiter", 10),
        (
            '{"spam":42,',
            "Expecting property name enclosed in double quotes",
            11,
        ),
        ('"', "Unterminated string starting at", 0),
        ('"spam', "Unterminated string starting at", 0),
    ],
)
def test_truncated_input_error_positions(
    input_data: str, expected_msg: str, expected_pos: int
) -> None:
    """
    Validates precise error positioning for truncated JSON inputs.
    """
    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.loads(input_data)

    err = exc_info.value
    assert err.msg == expected_msg
    assert err.pos == expected_pos
    assert err.lineno == 1
    assert err.colno == expected_pos + 1


@pytest.mark.parametrize(
    "input_data,expected_msg,expected_pos",
    [
        ("[,", "Expecting value", 1),
        ('{"spam":[}', "Expecting value", 9),
        ("[42:", "Expecting ',' delimiter", 3),
        ('[42 "spam"', "Expecting ',' delimiter", 4),
        ("[42,]", "Illegal trailing comma before end of array", 3),
        ('{"spam":[42}', "Expecting ',' delimiter", 11),
        ('["]', "Unterminated string starting at", 1),
        ('["spam":', "Expecting ',' delimiter", 7),
        ('["spam",]', "Illegal trailing comma before end of array", 7),
        ("{:", "Expecting property name enclosed in double quotes", 1),
        ("{,", "Expecting property name enclosed in double quotes", 1),
        ("{42", "Expecting property name enclosed in double quotes", 1),
        ("[{]", "Expecting property name enclosed in double quotes", 2),
        ('{"spam",', "Expecting ':' delimiter", 7),
        ('{"spam"}', "Expecting ':' delimiter", 7),
        ('[{"spam"]', "Expecting ':' delimiter", 8),
        ('{"spam":}', "Expecting value", 8),
        ('[{"spam":]', "Expecting value", 9),
        ('{"spam":42 "ham"', "Expecting ',' delimiter", 11),
        ('[{"spam":42]', "Expecting ',' delimiter", 11),
        ('{"spam":42,}', "Illegal trailing comma before end of object", 10),
        ('{"spam":42 , }', "Illegal trailing comma before end of object", 11),
        ("[123  , ]", "Illegal trailing comma before end of array", 6),
    ],
)
def test_unexpected_data_error_positions(
    input_data: str, expected_msg: str, expected_pos: int
) -> None:
    """
    Validates precise error positioning for unexpected JSON data.
    """
    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.loads(input_data)

    err = exc_info.value
    assert err.msg == expected_msg
    assert err.pos == expected_pos
    assert err.lineno == 1
    assert err.colno == expected_pos + 1


@pytest.mark.parametrize(
    "input_data,expected_msg,expected_pos",
    [
        ("[]]", "Extra data", 2),
        ("{}}", "Extra data", 2),
        ("[],[]", "Extra data", 2),
        ("{},{}", "Extra data", 2),
        ('42,"spam"', "Extra data", 2),
        ('"spam",42', "Extra data", 6),
    ],
)
def test_extra_data_error_positions(
    input_data: str, expected_msg: str, expected_pos: int
) -> None:
    """
    Validates precise error positioning for extra data after valid JSON.
    """
    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.loads(input_data)

    err = exc_info.value
    assert err.msg == expected_msg
    assert err.pos == expected_pos
    assert err.lineno == 1
    assert err.colno == expected_pos + 1


@pytest.mark.parametrize(
    "input_data,expected_line,expected_col,expected_pos",
    [
        ("!", 1, 1, 0),
        (" !", 1, 2, 1),
        ("\n!", 2, 1, 1),
        ("\n  \n\n     !", 4, 6, 10),
    ],
)
def test_line_column_calculation(
    input_data: str, expected_line: int, expected_col: int, expected_pos: int
) -> None:
    """
    Validates accurate line and column number calculation for multi-line JSON.
    """
    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.loads(input_data)

    err = exc_info.value
    assert err.msg == "Expecting value"
    assert err.pos == expected_pos
    assert err.lineno == expected_line
    assert err.colno == expected_col

    # Verify string representation format
    expected_str = (
        f"Expecting value at line {expected_line}, column {expected_col}"
    )
    assert expected_str in str(err)

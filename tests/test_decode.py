"""
JSON decoding functionality tests.

Validates core parsing capabilities including type conversion, custom hooks,
and proper handling of various JSON input formats.
"""

import decimal
from collections import OrderedDict
from io import StringIO
from typing import Any

import pytest

import jzon


def test_decimal_parsing() -> None:
    """
    Validates decimal.Decimal parsing via parse_float hook.
    """
    rval = jzon.loads("1.1", parse_float=decimal.Decimal)
    assert isinstance(rval, decimal.Decimal)
    assert rval == decimal.Decimal("1.1")  # type: ignore[unreachable]


def test_float_parsing() -> None:
    """
    Validates integer to float conversion via parse_int hook.
    """
    rval = jzon.loads("1", parse_int=float)
    assert isinstance(rval, float)
    assert rval == 1.0


@pytest.mark.parametrize("invalid_digit", ["1\uff10", "0.\uff10", "0e\uff10"])
def test_nonascii_digits_rejected(invalid_digit: str) -> None:
    """
    Validates rejection of non-ASCII digits per JSON specification.

    JSON specifies only ASCII digits are allowed in numeric literals.
    """
    with pytest.raises(jzon.JSONDecodeError):
        jzon.loads(invalid_digit)


def test_bytes_input_handling() -> None:
    """
    Validates proper handling of bytes input.
    """
    # This should raise TypeError for bytes input
    with pytest.raises(TypeError):
        jzon.loads(b"1")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "constant,expected",
    [
        ("Infinity", "INFINITY"),
        ("-Infinity", "-INFINITY"),
        ("NaN", "NAN"),
    ],
)
def test_parse_constant_hook(constant: str, expected: str) -> None:
    """
    Validates parse_constant hook for handling special numeric values.
    """
    result = jzon.loads(constant, parse_constant=str.upper)
    assert result == expected


@pytest.mark.parametrize(
    "invalid_constant",
    ["nan", "NAN", "naN", "infinity", "INFINITY", "inFiniTy"],
)
def test_constant_invalid_case_rejected(invalid_constant: str) -> None:
    """
    Validates rejection of improperly cased constant values.
    """
    with pytest.raises(jzon.JSONDecodeError):
        jzon.loads(invalid_constant)


def test_empty_containers() -> None:
    """
    Validates parsing of empty JSON containers.
    """
    assert jzon.loads("{}") == {}
    assert jzon.loads("[]") == []
    assert jzon.loads('""') == ""


def test_object_pairs_hook() -> None:
    """
    Validates object_pairs_hook for custom object construction.
    """
    s = '{"xkd":1, "kcw":2, "art":3, "hxm":4, "qrt":5, "pad":6, "hoy":7}'
    expected_pairs = [
        ("xkd", 1),
        ("kcw", 2),
        ("art", 3),
        ("hxm", 4),
        ("qrt", 5),
        ("pad", 6),
        ("hoy", 7),
    ]

    # Normal parsing should create dict
    assert jzon.loads(s) == eval(s)

    # With hook should preserve pairs
    assert jzon.loads(s, object_pairs_hook=lambda x: x) == expected_pairs

    # Test with file-like object
    assert (
        jzon.load(StringIO(s), object_pairs_hook=lambda x: x) == expected_pairs
    )

    # Test OrderedDict construction
    od = jzon.loads(s, object_pairs_hook=OrderedDict)
    assert od == OrderedDict(expected_pairs)
    assert isinstance(od, OrderedDict)

    # object_pairs_hook takes priority over object_hook
    result = jzon.loads(
        s, object_pairs_hook=OrderedDict, object_hook=lambda x: None
    )
    assert result == OrderedDict(expected_pairs)

    # Test empty object literals
    assert jzon.loads("{}", object_pairs_hook=OrderedDict) == OrderedDict()

    nested_result = jzon.loads('{"empty": {}}', object_pairs_hook=OrderedDict)
    expected_nested: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict(
        [("empty", OrderedDict())]
    )
    assert nested_result == expected_nested


def test_decoder_optimizations() -> None:
    """
    Validates parsing with various whitespace patterns.
    """
    rval = jzon.loads('{   "key"    :    "value"    ,  "k":"v"    }')
    assert rval == {"key": "value", "k": "v"}


def test_keys_reuse() -> None:
    """
    Validates string key reuse optimization for repeated keys.
    """
    s = '[{"a_key": 1, "b_\xe9": 2}, {"a_key": 3, "b_\xe9": 4}]'
    rval = jzon.loads(s)
    # Extract keys from dictionaries for comparison
    dict0 = rval[0]  # type: ignore[index]
    dict1 = rval[1]  # type: ignore[index]
    (a, b), (c, d) = sorted(dict0), sorted(dict1)

    # Keys should be reused (same string objects)
    assert a is c
    assert b is d


def test_extra_data_rejection() -> None:
    """
    Validates rejection of extra data after valid JSON.
    """
    with pytest.raises(jzon.JSONDecodeError, match="Extra data"):
        jzon.loads("[1, 2, 3]5")


def test_invalid_escape_rejection() -> None:
    """
    Validates rejection of invalid escape sequences.
    """
    with pytest.raises(jzon.JSONDecodeError, match="escape"):
        jzon.loads('["abc\\y"]')


@pytest.mark.parametrize("invalid_value", [1, 3.14, [], {}, None])
def test_invalid_input_type_rejection(invalid_value: Any) -> None:
    """
    Validates rejection of non-string input types.
    """
    with pytest.raises(TypeError, match="the JSON object must be str"):
        jzon.loads(invalid_value)


def test_utf8_bom_rejection() -> None:
    """
    Validates rejection of UTF-8 BOM in JSON input.
    """
    bom_json = "[1,2,3]".encode("utf-8-sig").decode("utf-8")

    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.loads(bom_json)
    assert "BOM" in str(exc_info.value)

    with pytest.raises(jzon.JSONDecodeError) as exc_info:
        jzon.load(StringIO(bom_json))
    assert "BOM" in str(exc_info.value)

    # BOM in middle of string should be preserved as character
    bom = "".encode("utf-8-sig").decode("utf-8")
    bom_in_str = f'"{bom}"'
    assert jzon.loads(bom_in_str) == "\ufeff"
    assert jzon.load(StringIO(bom_in_str)) == "\ufeff"


def test_large_integer_limits() -> None:
    """
    Validates handling of very large integer literals.
    """
    maxdigits = 5000

    # Should handle large numbers up to limit
    jzon.loads("1" * maxdigits)

    # Should reject numbers beyond limit
    with pytest.raises(ValueError):
        jzon.loads("1" * (maxdigits + 1))

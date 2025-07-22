"""
Pytest configuration and shared fixtures for jzon tests.

Provides immutable test data fixtures and common utilities following
CLAUDE.md patterns for clean, type-safe test organization.
"""

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass(frozen=True)
class JsonTestCase:
    """
    Immutable container for JSON test case data.

    Holds test input and expected behavior for consistent test execution.
    """

    description: str
    input_data: str
    should_fail: bool = False
    expected_output: Any = None
    skip_reason: str = ""


@pytest.fixture
def json_fail_cases() -> list[JsonTestCase]:
    """
    Provides JSON strings that must fail parsing per JSON specification.

    These 33 test cases from json.org JSON_checker ensure strict standards
    compliance and proper error handling for malformed JSON.
    """
    fail_docs = [
        # https://json.org/JSON_checker/test/fail1.json
        '"A JSON payload should be an object or array, not a string."',
        # https://json.org/JSON_checker/test/fail2.json
        '["Unclosed array"',
        # https://json.org/JSON_checker/test/fail3.json
        '{unquoted_key: "keys must be quoted"}',
        # https://json.org/JSON_checker/test/fail4.json
        '["extra comma",]',
        # https://json.org/JSON_checker/test/fail5.json
        '["double extra comma",,]',
        # https://json.org/JSON_checker/test/fail6.json
        '[   , "<-- missing value"]',
        # https://json.org/JSON_checker/test/fail7.json
        '["Comma after the close"],',
        # https://json.org/JSON_checker/test/fail8.json
        '["Extra close"]]',
        # https://json.org/JSON_checker/test/fail9.json
        '{"Extra comma": true,}',
        # https://json.org/JSON_checker/test/fail10.json
        '{"Extra value after close": true} "misplaced quoted value"',
        # https://json.org/JSON_checker/test/fail11.json
        '{"Illegal expression": 1 + 2}',
        # https://json.org/JSON_checker/test/fail12.json
        '{"Illegal invocation": alert()}',
        # https://json.org/JSON_checker/test/fail13.json
        '{"Numbers cannot have leading zeroes": 013}',
        # https://json.org/JSON_checker/test/fail14.json
        '{"Numbers cannot be hex": 0x14}',
        # https://json.org/JSON_checker/test/fail15.json
        '["Illegal backslash escape: \\x15"]',
        # https://json.org/JSON_checker/test/fail16.json
        "[\\naked]",
        # https://json.org/JSON_checker/test/fail17.json
        '["Illegal backslash escape: \\017"]',
        # https://json.org/JSON_checker/test/fail18.json - SKIPPED (deep nesting allowed)
        '[[[[[[[[[[[[[[[[[[["Too deep"]]]]]]]]]]]]]]]]]]',
        # https://json.org/JSON_checker/test/fail19.json
        '{"Missing colon" null}',
        # https://json.org/JSON_checker/test/fail20.json
        '{"Double colon":: null}',
        # https://json.org/JSON_checker/test/fail21.json
        '{"Comma instead of colon", null}',
        # https://json.org/JSON_checker/test/fail22.json
        '["Colon instead of comma": false]',
        # https://json.org/JSON_checker/test/fail23.json
        '["Bad value", truth]',
        # https://json.org/JSON_checker/test/fail24.json
        "['single quote']",
        # https://json.org/JSON_checker/test/fail25.json
        '["\ttab\tcharacter\tin\tstring\t"]',
        # https://json.org/JSON_checker/test/fail26.json
        '["tab\\   character\\   in\\  string\\  "]',
        # https://json.org/JSON_checker/test/fail27.json
        '["line\nbreak"]',
        # https://json.org/JSON_checker/test/fail28.json
        '["line\\\nbreak"]',
        # https://json.org/JSON_checker/test/fail29.json
        "[0e]",
        # https://json.org/JSON_checker/test/fail30.json
        "[0e+]",
        # https://json.org/JSON_checker/test/fail31.json
        "[0e+-1]",
        # https://json.org/JSON_checker/test/fail32.json
        '{"Comma instead if closing brace": true,',
        # https://json.org/JSON_checker/test/fail33.json
        '["mismatch"}',
        # https://code.google.com/archive/p/simplejson/issues/3
        '["A\u001fZ control characters in string"]',
    ]

    # Cases that are skipped with reasons
    skips = {
        1: "why not have a string payload?",
        18: "spec doesn't specify any nesting limitations",
    }

    return [
        JsonTestCase(
            description=f"fail{idx + 1}.json",
            input_data=doc,
            should_fail=True,
            skip_reason=skips.get(idx + 1, ""),
        )
        for idx, doc in enumerate(fail_docs)
    ]


@pytest.fixture
def json_pass_cases() -> list[JsonTestCase]:
    """
    Provides JSON strings that must parse successfully per JSON specification.

    These test cases validate standards compliance for valid JSON structures.
    """
    return [
        JsonTestCase(
            description="pass1.json - complex nested structure",
            input_data="""[
    "JSON Test Pattern pass1",
    {"object with 1 member":["array with 1 element"]},
    {},
    [],
    -42,
    true,
    false,
    null,
    {
        "integer": 1234567890,
        "real": -9876.543210,
        "e": 0.123456789e-12,
        "E": 1.234567890E+34,
        "":  23456789012E66,
        "zero": 0,
        "one": 1,
        "space": " ",
        "quote": "\\"",
        "backslash": "\\\\",
        "controls": "\\b\\f\\n\\r\\t",
        "slash": "/ & \\/",
        "alpha": "abcdefghijklmnopqrstuvwyz",
        "ALPHA": "ABCDEFGHIJKLMNOPQRSTUVWYZ",
        "digit": "0123456789",
        "0123456789": "digit",
        "special": "`1~!@#$%^&*()_+-={':[,]}|;.</>?",
        "hex": "\\u0123\\u4567\\u89AB\\uCDEF\\uabcd\\uef4A",
        "true": true,
        "false": false,
        "null": null,
        "array":[  ],
        "object":{  },
        "address": "50 St. James Street",
        "url": "https://www.JSON.org/",
        "comment": "// /* <!-- --",
        "# -- --> */": " ",
        " s p a c e d " :[1,2 , 3

,

4 , 5        ,          6           ,7        ],"compact":[1,2,3,4,5,6,7],
        "jsontext": "{\\"object with 1 member\\":[\\"array with 1 element\\"]}"
    }
]""",
            should_fail=False,
        ),
        JsonTestCase(
            description="pass2.json - deep nesting",
            input_data='[[[[[[[[[[[[[[[[[[["Not too deep"]]]]]]]]]]]]]]]]]]]',
            should_fail=False,
        ),
        JsonTestCase(
            description="pass3.json - simple object",
            input_data='{"JSON Test Pattern pass3": {"The outermost value": "must be an object or array.", "In this test": "It is an object."}}',
            should_fail=False,
        ),
    ]


@pytest.fixture
def basic_json_values() -> list[JsonTestCase]:
    """
    Provides basic JSON value test cases for fundamental parsing.

    Covers all JSON primitive types and basic container structures.
    """
    return [
        JsonTestCase("null value", "null", False, None),
        JsonTestCase("true boolean", "true", False, True),
        JsonTestCase("false boolean", "false", False, False),
        JsonTestCase("integer", "42", False, 42),
        JsonTestCase("negative integer", "-17", False, -17),
        JsonTestCase("float", "3.14", False, 3.14),
        JsonTestCase("empty string", '""', False, ""),
        JsonTestCase("simple string", '"hello"', False, "hello"),
        JsonTestCase("empty array", "[]", False, []),
        JsonTestCase("empty object", "{}", False, {}),
        JsonTestCase("simple array", "[1, 2, 3]", False, [1, 2, 3]),
        JsonTestCase(
            "simple object", '{"key": "value"}', False, {"key": "value"}
        ),
    ]

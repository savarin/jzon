"""
JSON specification pass3 test from json.org test suite.

Validates parsing of nested object structure with proper
handling of string keys and values.
"""

import jzon

# from https://json.org/JSON_checker/test/pass3.json
JSON = r"""
{
    "JSON Test Pattern pass3": {
        "The outermost value": "must be an object or array.",
        "In this test": "It is an object."
    }
}
"""


def test_parse() -> None:
    """
    Validates JSON parsing and round-trip encoding for nested objects.

    Tests parser's ability to handle nested object structure with
    string keys and values, ensuring proper reconstruction.
    """
    # Test parsing
    res = jzon.loads(JSON)

    # Test round-trip encoding
    out = jzon.dumps(res)
    assert res == jzon.loads(out)

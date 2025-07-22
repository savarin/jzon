"""
JSON specification pass2 test from json.org test suite.

Validates parsing of deeply nested array structure to ensure
parser can handle significant nesting levels.
"""

import jzon

# from https://json.org/JSON_checker/test/pass2.json
JSON = r"""
[[[[[[[[[[[[[[[[[[["Not too deep"]]]]]]]]]]]]]]]]]]]
"""


def test_parse() -> None:
    """
    Validates JSON parsing and round-trip encoding for deeply nested arrays.

    Tests parser's ability to handle significant nesting depth (19 levels)
    and proper reconstruction through serialization.
    """
    # Test parsing
    res = jzon.loads(JSON)

    # Test round-trip encoding
    out = jzon.dumps(res)
    assert res == jzon.loads(out)

"""
JSON encoding functionality tests.

Validates core serialization capabilities including custom encoders,
skipkeys behavior, and proper handling of various Python data types.
"""

from io import StringIO

import pytest

import jzon


def test_dump() -> None:
    """
    Validates dump to file-like object.
    """
    sio = StringIO()
    jzon.dump({}, sio)
    assert sio.getvalue() == "{}"


def test_dumps() -> None:
    """
    Validates dumps to string.
    """
    assert jzon.dumps({}) == "{}"


def test_dump_skipkeys() -> None:
    """
    Validates skipkeys behavior for non-serializable keys.
    """
    v = {b"invalid_key": False, "valid_key": True}
    with pytest.raises(TypeError):
        jzon.dumps(v)

    s = jzon.dumps(v, skipkeys=True)
    o = jzon.loads(s)
    assert "valid_key" in o  # type: ignore[operator]
    assert b"invalid_key" not in o  # type: ignore[operator]


def test_dump_skipkeys_indent_empty() -> None:
    """
    Validates skipkeys with indent produces empty object.
    """
    v = {b"invalid_key": False}
    assert jzon.dumps(v, skipkeys=True, indent=4) == "{}"


def test_skipkeys_indent() -> None:
    """
    Validates skipkeys behavior with indentation.
    """
    v = {b"invalid_key": False, "valid_key": True}
    assert (
        jzon.dumps(v, skipkeys=True, indent=4) == '{\n    "valid_key": true\n}'
    )


def test_encode_truefalse() -> None:
    """
    Validates boolean key encoding behavior.
    """
    assert (
        jzon.dumps({True: False, False: True}, sort_keys=True)
        == '{"false": true, "true": false}'
    )
    assert (
        jzon.dumps({2: 3.0, 4.0: 5, False: 1, 6: True}, sort_keys=True)
        == '{"false": 1, "2": 3.0, "4.0": 5, "6": true}'
    )


def test_encode_mutated() -> None:
    """
    Validates handling of list mutation during encoding (Issue 16228).
    """
    a = [object()] * 10

    def crasher(obj):
        del a[-1]

    assert jzon.dumps(a, default=crasher) == "[null, null, null, null, null]"


def test_encode_evil_dict() -> None:
    """
    Validates handling of malicious dict implementation (Issue 24094).
    """
    # Create shared list that will be modified
    x_instances: list[object] = []  # Will be populated by X.__hash__

    class D(dict[int, str]):
        def keys(self):
            return x_instances

    class X:
        def __hash__(self):
            if x_instances:
                del x_instances[0]
            return 1337

        def __lt__(self, o):
            return 0

    # Populate after class definitions
    x_instances.extend([X() for i in range(1122)])
    d = D()
    d[1337] = "true.dat"
    assert jzon.dumps(d, sort_keys=True) == '{"1337": "true.dat"}'


@pytest.mark.skip("Large memory test - enable manually if needed")
def test_large_list() -> None:
    """
    Validates encoding of very large lists.

    Note: This test requires significant memory and is skipped by default.
    """
    size_gb = 1  # 1GB test size
    n_items = int(30 * 1024 * 1024 * size_gb)
    items = [1] * n_items
    encoded = jzon.dumps(items)
    assert len(encoded) == n_items * 3
    assert encoded[:1] == "["
    assert encoded[-2:] == "1]"
    assert encoded[1:-2] == "1, " * (n_items - 1)

"""
JSON parsing performance benchmarks comparing jzon against standard libraries.

Compares parsing speed across different JSON data types and sizes:
- Standard library json
- orjson (C-optimized)
- ujson (ultra-fast JSON)
- jzon (our implementation)
"""

import json
from collections.abc import Callable
from typing import Any

import orjson
import pytest
import ujson  # type: ignore[import-untyped]

import jzon
from benchmarks.data_generators import generate_test_data


class TestParsingBenchmarks:
    """Benchmarks for JSON parsing performance across different libraries."""

    @pytest.mark.benchmark(group="small_objects")
    @pytest.mark.parametrize(
        "parser,parse_func",
        [
            ("stdlib_json", json.loads),
            ("orjson", orjson.loads),
            ("ujson", ujson.loads),
            ("jzon", jzon.loads),
        ],
    )
    def test_small_object_parsing(
        self, benchmark: Any, parser: str, parse_func: Callable[[str], Any]
    ) -> None:
        """Benchmarks parsing of small JSON objects (< 1KB)."""
        test_data = generate_test_data("small_object")

        if parser == "orjson":
            # orjson expects bytes for optimal performance
            test_data_bytes = test_data.encode("utf-8")
            result = benchmark(parse_func, test_data_bytes)
        else:
            result = benchmark(parse_func, test_data)

        # Verify parsing worked correctly
        assert isinstance(result, dict)

    @pytest.mark.benchmark(group="large_objects")
    @pytest.mark.parametrize(
        "parser,parse_func",
        [
            ("stdlib_json", json.loads),
            ("orjson", orjson.loads),
            ("ujson", ujson.loads),
            ("jzon", jzon.loads),
        ],
    )
    def test_large_object_parsing(
        self, benchmark: Any, parser: str, parse_func: Callable[[str], Any]
    ) -> None:
        """Benchmarks parsing of large JSON objects (> 10KB)."""
        test_data = generate_test_data("large_object")

        if parser == "orjson":
            test_data_bytes = test_data.encode("utf-8")
            result = benchmark(parse_func, test_data_bytes)
        else:
            result = benchmark(parse_func, test_data)

        assert isinstance(result, dict)

    @pytest.mark.benchmark(group="arrays")
    @pytest.mark.parametrize(
        "parser,parse_func",
        [
            ("stdlib_json", json.loads),
            ("orjson", orjson.loads),
            ("ujson", ujson.loads),
            ("jzon", jzon.loads),
        ],
    )
    def test_array_parsing(
        self, benchmark: Any, parser: str, parse_func: Callable[[str], Any]
    ) -> None:
        """Benchmarks parsing of large arrays with mixed data types."""
        test_data = generate_test_data("mixed_array")

        if parser == "orjson":
            test_data_bytes = test_data.encode("utf-8")
            result = benchmark(parse_func, test_data_bytes)
        else:
            result = benchmark(parse_func, test_data)

        assert isinstance(result, list)

    @pytest.mark.benchmark(group="nested_structures")
    @pytest.mark.parametrize(
        "parser,parse_func",
        [
            ("stdlib_json", json.loads),
            ("orjson", orjson.loads),
            ("ujson", ujson.loads),
            ("jzon", jzon.loads),
        ],
    )
    def test_nested_structure_parsing(
        self, benchmark: Any, parser: str, parse_func: Callable[[str], Any]
    ) -> None:
        """Benchmarks parsing of deeply nested JSON structures."""
        test_data = generate_test_data("nested_structure")

        if parser == "orjson":
            test_data_bytes = test_data.encode("utf-8")
            result = benchmark(parse_func, test_data_bytes)
        else:
            result = benchmark(parse_func, test_data)

        assert isinstance(result, dict)

    @pytest.mark.benchmark(group="string_heavy")
    @pytest.mark.parametrize(
        "parser,parse_func",
        [
            ("stdlib_json", json.loads),
            ("orjson", orjson.loads),
            ("ujson", ujson.loads),
            ("jzon", jzon.loads),
        ],
    )
    def test_string_heavy_parsing(
        self, benchmark: Any, parser: str, parse_func: Callable[[str], Any]
    ) -> None:
        """Benchmarks parsing of JSON with many string escape sequences."""
        test_data = generate_test_data("string_heavy")

        if parser == "orjson":
            test_data_bytes = test_data.encode("utf-8")
            result = benchmark(parse_func, test_data_bytes)
        else:
            result = benchmark(parse_func, test_data)

        assert isinstance(result, dict)

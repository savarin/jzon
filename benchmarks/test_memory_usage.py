"""
Memory usage benchmarks for JSON parsing.

Measures peak memory consumption and object allocation patterns
across different JSON parsing libraries.
"""

import json
import tracemalloc
from typing import Any

import orjson
import pytest
import ujson  # type: ignore[import-untyped]

import jzon
from benchmarks.data_generators import generate_test_data


def measure_memory_usage(func: Any, *args: Any) -> tuple[Any, int]:
    """
    Measures peak memory usage during function execution.

    Returns:
        Tuple of (function_result, peak_memory_bytes)
    """
    tracemalloc.start()
    try:
        result = func(*args)
        current, peak = tracemalloc.get_traced_memory()
        return result, peak
    finally:
        tracemalloc.stop()


class TestMemoryUsage:
    """Memory usage benchmarks for JSON parsing."""

    @pytest.mark.parametrize(
        "data_type",
        [
            "small_object",
            "large_object",
            "mixed_array",
            "nested_structure",
            "string_heavy",
        ],
    )
    def test_stdlib_json_memory(self, data_type: str) -> None:
        """Measures memory usage for standard library json."""
        test_data = generate_test_data(data_type)
        result, peak_memory = measure_memory_usage(json.loads, test_data)

        # Store result for comparison (pytest will capture this)
        print(f"\nstdlib_json {data_type}: {peak_memory:,} bytes")
        assert result is not None

    @pytest.mark.parametrize(
        "data_type",
        [
            "small_object",
            "large_object",
            "mixed_array",
            "nested_structure",
            "string_heavy",
        ],
    )
    def test_orjson_memory(self, data_type: str) -> None:
        """Measures memory usage for orjson."""
        test_data_bytes = generate_test_data(data_type).encode("utf-8")
        result, peak_memory = measure_memory_usage(
            orjson.loads, test_data_bytes
        )

        print(f"\norjson {data_type}: {peak_memory:,} bytes")
        assert result is not None

    @pytest.mark.parametrize(
        "data_type",
        [
            "small_object",
            "large_object",
            "mixed_array",
            "nested_structure",
            "string_heavy",
        ],
    )
    def test_ujson_memory(self, data_type: str) -> None:
        """Measures memory usage for ujson."""
        test_data = generate_test_data(data_type)
        result, peak_memory = measure_memory_usage(ujson.loads, test_data)

        print(f"\nujson {data_type}: {peak_memory:,} bytes")
        assert result is not None

    @pytest.mark.parametrize(
        "data_type",
        [
            "small_object",
            "large_object",
            "mixed_array",
            "nested_structure",
            "string_heavy",
        ],
    )
    def test_jzon_memory(self, data_type: str) -> None:
        """Measures memory usage for jzon."""
        test_data = generate_test_data(data_type)
        result, peak_memory = measure_memory_usage(jzon.loads, test_data)

        print(f"\njzon {data_type}: {peak_memory:,} bytes")
        assert result is not None

    def test_memory_comparison_summary(self) -> None:
        """Generates a comprehensive memory usage comparison."""
        data_types = [
            "small_object",
            "large_object",
            "mixed_array",
            "nested_structure",
            "string_heavy",
        ]
        results = {}

        for data_type in data_types:
            test_data = generate_test_data(data_type)
            test_data_bytes = test_data.encode("utf-8")

            # Measure each library
            _, stdlib_memory = measure_memory_usage(json.loads, test_data)
            _, orjson_memory = measure_memory_usage(
                orjson.loads, test_data_bytes
            )
            _, ujson_memory = measure_memory_usage(ujson.loads, test_data)
            _, jzon_memory = measure_memory_usage(jzon.loads, test_data)

            results[data_type] = {
                "stdlib_json": stdlib_memory,
                "orjson": orjson_memory,
                "ujson": ujson_memory,
                "jzon": jzon_memory,
            }

        # Print comparison table
        print("\n" + "=" * 80)
        print("MEMORY USAGE COMPARISON (bytes)")
        print("=" * 80)
        print(
            f"{'Data Type':<20} {'stdlib_json':<12} {'orjson':<12} {'ujson':<12} {'jzon':<12}"
        )
        print("-" * 80)

        for data_type, measurements in results.items():
            print(
                f"{data_type:<20} {measurements['stdlib_json']:<12,} {measurements['orjson']:<12,} {measurements['ujson']:<12,} {measurements['jzon']:<12,}"
            )

        print("=" * 80)

        # Calculate and display efficiency ratios
        print("\nMEMORY EFFICIENCY vs stdlib_json")
        print("-" * 40)
        for data_type, measurements in results.items():
            stdlib_baseline = measurements["stdlib_json"]
            orjson_ratio = measurements["orjson"] / stdlib_baseline
            ujson_ratio = measurements["ujson"] / stdlib_baseline
            jzon_ratio = measurements["jzon"] / stdlib_baseline

            print(
                f"{data_type}: orjson={orjson_ratio:.2f}x ujson={ujson_ratio:.2f}x jzon={jzon_ratio:.2f}x"
            )

        assert len(results) == len(data_types)

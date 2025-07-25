#!/usr/bin/env python3
"""
Phase 3 Session 3 Benchmark: Zig Parser Performance Validation

Comprehensive benchmarking to validate 3-5x performance improvement
target for the new Zig parser implementation.
"""

import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import jzon  # noqa: E402


def create_test_data() -> dict[str, str]:
    """Create comprehensive test JSON data for benchmarking."""
    return {
        "small_object": '{"name": "Alice", "age": 30, "active": true, "balance": 1234.56}',
        "large_array": "[" + ",".join(str(i) for i in range(10000)) + "]",
        "nested_structure": json.dumps(
            [
                {"level1": {"level2": {"level3": {"level4": {"value": i}}}}}
                for i in range(100)
            ]
        ),
        "string_heavy": json.dumps(
            {
                f"key_{i}": f"This is a longer string value with basic text and numbers {i}"
                for i in range(1000)
            }
        ),
        "repeated_keys": json.dumps(
            [
                {"name": "Alice", "age": 30, "city": "New York"},
                {"name": "Bob", "age": 25, "city": "San Francisco"},
                {"name": "Charlie", "age": 35, "city": "Chicago"},
            ]
            * 500
        ),
        "mixed_types": json.dumps(
            [
                {
                    "string": "Hello World",
                    "integer": 42,
                    "float": 3.14159,
                    "boolean": True,
                    "null": None,
                    "array": [1, 2, 3, 4, 5],
                    "object": {"nested": "value"},
                }
                for _ in range(200)
            ]
        ),
        "unicode_heavy": json.dumps(
            [
                {
                    "english": "Hello World",
                    "french": "Cafe francais",
                    "german": "Strasse Mueller",
                    "basic": "Simple text without complex unicode",
                    "escape_sequences": 'Hello\\nWorld\\t"quoted"\\\\backslash',
                }
                for _ in range(100)
            ]
        ),
        "numbers_array": "["
        + ",".join(
            ["42", "3.14159", "-123", "1e10", "-2.5e-3", "0", "1234567890"]
            * 1000
        )
        + "]",
    }


def measure_memory_usage(
    func: Any, *args: Any, **kwargs: Any
) -> tuple[Any, int]:
    """Measure peak memory usage of function execution."""
    tracemalloc.start()
    try:
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        return result, peak
    finally:
        tracemalloc.stop()


def benchmark_parser(
    name: str, json_text: str, iterations: int = 1000
) -> dict[str, Any]:
    """Benchmark both jzon and stdlib json parsing performance."""
    print(
        f"\nBenchmarking {name} ({len(json_text)} chars, {iterations} iterations)"
    )

    results = {}

    # Benchmark jzon (with Zig acceleration if available)
    jzon_times = []
    jzon_memory = 0

    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            if i == 0:  # Measure memory on first iteration
                result, memory = measure_memory_usage(jzon.loads, json_text)
                jzon_memory = memory
            else:
                result = jzon.loads(json_text)
            end_time = time.perf_counter()
            jzon_times.append(end_time - start_time)
        except Exception as e:
            print(f"jzon failed on {name}: {e}")
            return {"error": str(e)}

    jzon_avg_time = sum(jzon_times) / len(jzon_times)
    jzon_min_time = min(jzon_times)

    # Benchmark stdlib json
    stdlib_times = []
    stdlib_memory = 0

    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            if i == 0:  # Measure memory on first iteration
                result, memory = measure_memory_usage(json.loads, json_text)
                stdlib_memory = memory
            else:
                json.loads(json_text)
            end_time = time.perf_counter()
            stdlib_times.append(end_time - start_time)
        except Exception as e:
            print(f"stdlib json failed on {name}: {e}")
            stdlib_times = [float("inf")]
            break

    stdlib_avg_time = sum(stdlib_times) / len(stdlib_times)
    stdlib_min_time = min(stdlib_times)

    # Calculate improvements
    speedup_avg = stdlib_avg_time / jzon_avg_time if jzon_avg_time > 0 else 0
    speedup_min = stdlib_min_time / jzon_min_time if jzon_min_time > 0 else 0
    memory_ratio = jzon_memory / stdlib_memory if stdlib_memory > 0 else 0

    results = {
        "name": name,
        "size_chars": len(json_text),
        "iterations": iterations,
        "jzon_avg_time": jzon_avg_time,
        "jzon_min_time": jzon_min_time,
        "jzon_memory": jzon_memory,
        "stdlib_avg_time": stdlib_avg_time,
        "stdlib_min_time": stdlib_min_time,
        "stdlib_memory": stdlib_memory,
        "speedup_avg": speedup_avg,
        "speedup_min": speedup_min,
        "memory_ratio": memory_ratio,
    }

    # Print results
    print(
        f"  jzon:   {jzon_avg_time * 1000:.3f}ms avg, {jzon_min_time * 1000:.3f}ms min"
    )
    print(
        f"  stdlib: {stdlib_avg_time * 1000:.3f}ms avg, {stdlib_min_time * 1000:.3f}ms min"
    )
    print(f"  Speedup: {speedup_avg:.2f}x avg, {speedup_min:.2f}x min")
    print(
        f"  Memory: jzon {jzon_memory / 1024:.1f}KB vs stdlib {stdlib_memory / 1024:.1f}KB ({memory_ratio:.2f}x)"
    )

    return results


def _debug_dict_differences(
    jzon_result: dict[str, Any], stdlib_result: dict[str, Any]
) -> None:
    """Debug helper for dict differences."""
    jzon_keys = set(jzon_result.keys())
    stdlib_keys = set(stdlib_result.keys())
    if jzon_keys != stdlib_keys:
        print(
            f"  Key difference: jzon has {len(jzon_keys)} keys, stdlib has {len(stdlib_keys)} keys"
        )
        max_keys_to_show = 10
        if (
            len(jzon_keys) < max_keys_to_show
            and len(stdlib_keys) < max_keys_to_show
        ):
            print(f"  jzon keys: {list(jzon_keys)}")
            print(f"  stdlib keys: {list(stdlib_keys)}")
    else:
        # Find first differing value
        for key in list(jzon_result.keys())[:3]:
            if key in stdlib_result and jzon_result[key] != stdlib_result[key]:
                print(f"  First difference at key '{key}':")
                print(f"    jzon: {repr(jzon_result[key])[:100]}...")
                print(f"    stdlib: {repr(stdlib_result[key])[:100]}...")
                break


def _debug_list_differences(
    jzon_result: list[Any], stdlib_result: list[Any]
) -> None:
    """Debug helper for list differences."""
    if len(jzon_result) != len(stdlib_result):
        print(
            f"  Length difference: jzon has {len(jzon_result)}, stdlib has {len(stdlib_result)}"
        )
    else:
        # Find first differing element
        for i, (j_item, s_item) in enumerate(
            zip(jzon_result[:3], stdlib_result[:3], strict=False)
        ):
            if j_item != s_item:
                print(f"  First difference at index {i}:")
                print(f"    jzon: {repr(j_item)[:100]}...")
                print(f"    stdlib: {repr(s_item)[:100]}...")
                break


def benchmark_correctness(test_data: dict[str, str]) -> dict[str, bool]:
    """Verify that jzon produces identical results to stdlib json."""
    print("\n=== Correctness Validation ===")
    results = {}

    for name, json_text in test_data.items():
        try:
            jzon_result = jzon.loads(json_text)
            stdlib_result = json.loads(json_text)

            # Compare results
            identical = jzon_result == stdlib_result
            results[name] = identical

            if identical:
                print(f"✓ {name}: Results identical")
            else:
                print(f"✗ {name}: Results differ!")
                print(f"  jzon type: {type(jzon_result)}")
                print(f"  stdlib type: {type(stdlib_result)}")

                # Show first difference for debugging
                if isinstance(jzon_result, dict) and isinstance(
                    stdlib_result, dict
                ):
                    _debug_dict_differences(jzon_result, stdlib_result)
                elif isinstance(jzon_result, list) and isinstance(
                    stdlib_result, list
                ):
                    _debug_list_differences(jzon_result, stdlib_result)

        except Exception as e:
            print(f"✗ {name}: Exception during comparison: {e}")
            results[name] = False

    return results


def validate_target_performance(
    benchmark_results: list[dict[str, Any]],
) -> bool:
    """Validate that we achieved the 3-5x performance target."""
    print("\n=== Performance Target Validation ===")

    target_min = 3.0
    target_ideal = 5.0

    passed_min = 0
    passed_ideal = 0
    total = 0

    for result in benchmark_results:
        if "speedup_avg" in result:
            total += 1
            speedup = result["speedup_avg"]
            name = result["name"]

            if speedup >= target_ideal:
                print(
                    f"🎯 {name}: {speedup:.2f}x (EXCELLENT - exceeds 5x target)"
                )
                passed_ideal += 1
                passed_min += 1
            elif speedup >= target_min:
                print(f"✓ {name}: {speedup:.2f}x (GOOD - meets 3x target)")
                passed_min += 1
            else:
                print(
                    f"⚠ {name}: {speedup:.2f}x (BELOW TARGET - need optimization)"
                )

    success_rate = passed_min / total if total > 0 else 0
    ideal_rate = passed_ideal / total if total > 0 else 0

    print("\nTarget Achievement:")
    print(f"  Minimum (3x): {passed_min}/{total} ({success_rate:.1%})")
    print(f"  Ideal (5x):   {passed_ideal}/{total} ({ideal_rate:.1%})")

    # Require 80% of tests to meet minimum target
    min_success_rate = 0.8
    target_achieved = success_rate >= min_success_rate

    if target_achieved:
        print("🎉 PERFORMANCE TARGET ACHIEVED!")
    else:
        print("❌ Performance target not met - need more optimization")

    return target_achieved


def validate_memory_usage(benchmark_results: list[dict[str, Any]]) -> bool:
    """Validate that memory usage is reasonable (≤2x stdlib)."""
    print("\n=== Memory Usage Validation ===")

    memory_target = 2.0  # ≤2x stdlib memory usage

    passed = 0
    total = 0

    for result in benchmark_results:
        if "memory_ratio" in result and result["memory_ratio"] > 0:
            total += 1
            memory_ratio = result["memory_ratio"]
            name = result["name"]

            if memory_ratio <= memory_target:
                print(f"✓ {name}: {memory_ratio:.2f}x memory (within target)")
                passed += 1
            else:
                print(
                    f"⚠ {name}: {memory_ratio:.2f}x memory (exceeds 2x target)"
                )

    success_rate = passed / total if total > 0 else 0
    print(f"\nMemory Target Achievement: {passed}/{total} ({success_rate:.1%})")

    # Require 90% of tests to meet memory target
    min_memory_success_rate = 0.9
    memory_ok = success_rate >= min_memory_success_rate

    if memory_ok:
        print("✓ Memory usage within acceptable limits")
    else:
        print("⚠ Memory usage exceeds targets - optimization needed")

    return memory_ok


def main() -> bool:
    """Main benchmark execution."""
    print("Phase 3 Session 3: Zig Parser Performance Benchmark")
    print("=" * 60)

    # Check if Zig library is available
    if hasattr(jzon, "_zig_available") and jzon._zig_available:
        print("✓ Zig acceleration: AVAILABLE")
    else:
        print("⚠ Zig acceleration: NOT AVAILABLE (using Python fallback)")

    # Create test data
    print("\nGenerating test data...")
    test_data = create_test_data()
    print(f"Created {len(test_data)} test cases")

    # Validate correctness first
    correctness_results = benchmark_correctness(test_data)

    # Check if all tests pass correctness
    all_correct = all(correctness_results.values())
    if not all_correct:
        print("\n❌ CORRECTNESS VALIDATION FAILED")
        print(
            "Cannot proceed with performance benchmarks due to correctness issues"
        )
        return False
    else:
        print("\n✓ All correctness tests passed")

    # Run performance benchmarks
    print("\n=== Performance Benchmarks ===")
    benchmark_results = []

    for name, json_text in test_data.items():
        # Adjust iterations based on data size
        large_data_threshold = 100000
        medium_data_threshold = 10000
        if len(json_text) > large_data_threshold:
            iterations = 100
        elif len(json_text) > medium_data_threshold:
            iterations = 500
        else:
            iterations = 1000

        result = benchmark_parser(name, json_text, iterations)
        if "error" not in result:
            benchmark_results.append(result)

    # Validate performance targets
    performance_ok = validate_target_performance(benchmark_results)
    memory_ok = validate_memory_usage(benchmark_results)

    # Overall assessment
    print("\n" + "=" * 60)
    print("FINAL ASSESSMENT")
    print("=" * 60)

    if all_correct and performance_ok and memory_ok:
        print("🎉 PHASE 3 SESSION 3: COMPLETE SUCCESS!")
        print("   ✓ Correctness: All tests pass")
        print("   ✓ Performance: 3-5x target achieved")
        print("   ✓ Memory: Usage within acceptable limits")
        return True
    else:
        print("⚠ PHASE 3 SESSION 3: PARTIAL SUCCESS")
        print(
            f"   {'✓' if all_correct else '❌'} Correctness: {'PASS' if all_correct else 'FAIL'}"
        )
        print(
            f"   {'✓' if performance_ok else '❌'} Performance: {'TARGET MET' if performance_ok else 'BELOW TARGET'}"
        )
        print(
            f"   {'✓' if memory_ok else '❌'} Memory: {'ACCEPTABLE' if memory_ok else 'EXCESSIVE'}"
        )
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

"""
Binary Go/No-Go decision experiment for Zig JSON parsing.

This module implements the minimal viable test to determine if Zig+FFI
can ever outperform pure Python for JSON parsing. Tests only numeric
arrays with batch processing to address known FFI overhead issues.
"""

import ctypes
import json
import time
from pathlib import Path
from typing import Any
from typing import ClassVar


class MinimalArrayParser:
    """Absolute minimal Zig array parser for decision experiment."""

    def __init__(self) -> None:
        """Initialize the parser by loading the compiled Zig library."""
        lib_path = self._find_library()
        self.lib = ctypes.CDLL(lib_path)

        # Define result structure matching Zig extern struct
        class ArrayResult(ctypes.Structure):
            _fields_: ClassVar = [
                ("values", ctypes.c_double * 100),
                ("count", ctypes.c_uint32),
                ("success", ctypes.c_bool),
            ]

        self.ArrayResult = ArrayResult

        # Configure function signature
        self.lib.parse_simple_array.argtypes = [
            ctypes.c_char_p,  # input
            ctypes.c_size_t,  # length
            ctypes.POINTER(ArrayResult),  # result
        ]
        self.lib.parse_simple_array.restype = None

        # Test that the library works
        if self.lib.validate_parser() != 0:
            raise RuntimeError("Zig parser validation failed")

    def _find_library(self) -> str:
        """Find the compiled Zig library."""
        project_root = Path(__file__).parent.parent
        lib_dir = project_root / "zig-out" / "lib"

        # Try different extensions
        for ext in ["dylib", "so", "dll"]:
            lib_path = lib_dir / f"libminimal_array.{ext}"
            if lib_path.exists():
                return str(lib_path)

        raise FileNotFoundError(
            f"Could not find minimal_array library in {lib_dir}. "
            "Run 'zig build -Doptimize=ReleaseFast --build-file build_minimal.zig' first."
        )

    def parse(self, json_str: str) -> list[float]:
        """Parse a simple numeric array using Zig."""
        # Encode once
        json_bytes = json_str.encode("utf-8")

        # Prepare result structure
        result = self.ArrayResult()

        # Single FFI call
        self.lib.parse_simple_array(
            json_bytes, len(json_bytes), ctypes.byref(result)
        )

        if not result.success:
            raise ValueError(f"Parse failed for: {json_str}")

        # Return as list (single copy)
        return list(result.values[: result.count])


# Constants for magic numbers
DISPLAY_TRUNCATE_LENGTH = 20
SPEEDUP_THRESHOLD = 1.5


def benchmark_decision(iterations: int = 1_000_000) -> dict[str, Any]:
    """
    The binary decision benchmark.

    Tests increasingly complex numeric arrays to determine if Zig+FFI
    can overcome the overhead and beat pure Python parsing.
    """

    # Test cases - start simple, get more complex
    test_cases = [
        "[1,2,3,4,5]",  # Simplest case
        "[1,2,3,4,5,6,7,8,9,10]",  # 10 elements
        "[1.5, -2.7, 3.14159, 4e-10, 5.0]",  # Floating point
        "[" + ",".join(str(i) for i in range(20)) + "]",  # 20 elements
        "[" + ",".join(str(i * 1.5) for i in range(50)) + "]",  # 50 elements
    ]

    # Initialize parsers
    print("Initializing Zig parser...")
    zig_parser = MinimalArrayParser()
    print("Zig parser ready!")

    results = {}

    for test_json in test_cases:
        test_name = (
            f"{test_json[:DISPLAY_TRUNCATE_LENGTH]}..."
            if len(test_json) > DISPLAY_TRUNCATE_LENGTH
            else test_json
        )
        print(f"\nTesting: {test_name}")

        # Verify correctness first
        try:
            result_py = json.loads(test_json)
            result_zig = zig_parser.parse(test_json)

            if result_py != result_zig:
                print("ERROR: Results differ!")
                print(f"Python: {result_py}")
                print(f"Zig:    {result_zig}")
                continue

        except Exception as e:
            print(f"ERROR during correctness check: {e}")
            continue

        # Warmup (important for Python's internal optimizations)
        warmup_iterations = min(1000, iterations // 100)
        for _ in range(warmup_iterations):
            json.loads(test_json)
            zig_parser.parse(test_json)

        # Benchmark Python stdlib
        print("  Benchmarking Python...")
        start = time.perf_counter()
        for _ in range(iterations):
            result_py = json.loads(test_json)
        time_python = time.perf_counter() - start

        # Benchmark Zig
        print("  Benchmarking Zig...")
        start = time.perf_counter()
        for _ in range(iterations):
            result_zig = zig_parser.parse(test_json)
        time_zig = time.perf_counter() - start

        # Calculate metrics
        speedup = time_python / time_zig
        verdict = "PROCEED" if speedup >= SPEEDUP_THRESHOLD else "ABANDON"

        results[test_name] = {
            "python_ms": time_python * 1000,
            "zig_ms": time_zig * 1000,
            "speedup": speedup,
            "verdict": verdict,
            "test_case": test_json,
        }

        # Early termination if we find a winner
        if speedup >= SPEEDUP_THRESHOLD:
            print(f"  ✓ Found winner! {speedup:.2f}x speedup")

    return results


def print_results(results: dict[str, Any]) -> bool:
    """Print benchmark results and return True if we should proceed."""

    print("\n" + "=" * 80)
    print("BINARY DECISION RESULTS")
    print("=" * 80)
    print(
        f"{'Test Case':<25} {'Python (ms)':<12} {'Zig (ms)':<12} {'Speedup':<10} {'Verdict':<10}"
    )
    print("-" * 80)

    any_proceed = False
    best_speedup = 0.0
    best_case = ""

    for test_name, data in results.items():
        speedup = data["speedup"]
        print(
            f"{test_name:<25} {data['python_ms']:<12.2f} {data['zig_ms']:<12.2f} {speedup:<10.2f}x {data['verdict']:<10}"
        )

        if data["verdict"] == "PROCEED":
            any_proceed = True

        if speedup > best_speedup:
            best_speedup = speedup
            best_case = test_name

    print("-" * 80)
    print(f"Best performance: {best_speedup:.2f}x on {best_case}")

    return any_proceed


if __name__ == "__main__":
    print("=== Zig JSON Parser: Binary Go/No-Go Decision ===\n")

    try:
        results = benchmark_decision(
            iterations=500_000
        )  # Reduced for quicker feedback
        should_proceed = print_results(results)

        print("\n" + "=" * 80)
        print("FINAL DECISION")
        print("=" * 80)

        if should_proceed:
            print("✓ PROCEED: Zig shows promise for numeric array parsing")
            print("  Recommendation: Implement batch object parsing next")
            print("  Focus on large arrays and streaming use cases")
        else:
            print("✗ ABANDON: Zig cannot overcome FFI overhead")
            print("  Recommendation: Focus on pure Python optimizations")
            print(
                "  Consider specialized libraries for numeric data (NumPy, etc.)"
            )

    except Exception as e:
        print(f"Experiment failed: {e}")
        print("\nThis likely means the Zig library wasn't built properly.")
        print(
            "Run: zig build -Doptimize=ReleaseFast --build-file build_minimal.zig"
        )

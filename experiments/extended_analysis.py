"""Extended analysis to find the exact threshold where Zig wins."""

import json
import time

from binary_decision import MinimalArrayParser


def test_array_sizes() -> None:
    """Test different array sizes to find the crossover point."""

    parser = MinimalArrayParser()

    # Test various array sizes
    sizes = [5, 10, 20, 30, 40, 50, 75, 100]
    iterations = 100_000

    print("Array Size | Python (ms) | Zig (ms) | Speedup | Winner")
    print("-" * 55)

    for size in sizes:
        # Generate test array with integers to avoid floating point precision issues
        test_json = "[" + ",".join(str(i) for i in range(size)) + "]"

        # Warmup
        for _ in range(100):
            json.loads(test_json)
            parser.parse(test_json)

        # Benchmark Python
        start = time.perf_counter()
        for _ in range(iterations):
            json.loads(test_json)
        time_python = time.perf_counter() - start

        # Benchmark Zig
        start = time.perf_counter()
        for _ in range(iterations):
            parser.parse(test_json)
        time_zig = time.perf_counter() - start

        speedup = time_python / time_zig
        winner = "Zig" if speedup > 1.0 else "Python"

        print(
            f"{size:>9} | {time_python * 1000:>10.2f} | {time_zig * 1000:>8.2f} | {speedup:>7.2f}x | {winner}"
        )


if __name__ == "__main__":
    test_array_sizes()

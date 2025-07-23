# jzon Benchmark Results

Performance comparison of jzon against standard JSON parsing libraries.

## Libraries Tested

- **stdlib_json**: Python standard library `json` module
- **orjson**: High-performance C-optimized JSON library
- **ujson**: Ultra-fast JSON encoder/decoder
- **jzon**: Our implementation with Zig-ready architecture

## Performance Benchmarks

### Parsing Speed (Lower is Better)

| Data Type | stdlib_json | orjson | ujson | jzon | jzon vs stdlib |
|-----------|-------------|--------|--------|------|----------------|
| **Small Objects** | 861 ns | 291 ns | 565 ns | 45,925 ns | **53x slower** |
| **Large Objects** | 27.8 μs | 14.9 μs | 25.2 μs | 2,984 μs | **107x slower** |
| **Arrays** | 9.1 μs | 4.4 μs | 8.3 μs | 1,034 μs | **114x slower** |
| **Nested Structures** | 13.9 ms | 10.4 ms | 13.7 ms | 917 ms | **66x slower** |
| **String Heavy** | 37.3 μs | 11.1 μs | 36.0 μs | 2,374 μs | **64x slower** |

### Memory Usage (Lower is Better)

| Data Type | stdlib_json | orjson | ujson | jzon | jzon vs stdlib |
|-----------|-------------|--------|--------|------|----------------|
| **Small Objects** | 2,040 B | 5,002 B | 1,033 B | 3,443 B | **1.7x more** |
| **Large Objects** | 35,795 B | 208,248 B | 120,127 B | 62,312 B | **1.7x more** |
| **Arrays** | 7,026 B | 47,212 B | 26,899 B | 14,536 B | **2.1x more** |
| **Nested Structures** | 22.5 MB | 58.3 MB | 44.5 MB | 29.6 MB | **1.3x more** |
| **String Heavy** | 23,088 B | 202,106 B | 98,061 B | 28,487 B | **1.2x more** |

## Key Findings

### Performance Analysis

1. **jzon is currently significantly slower** than all compared libraries across all data types
2. **orjson dominates speed**, being 2-3x faster than stdlib_json in most cases
3. **ujson performs similarly to stdlib_json** in most scenarios
4. **jzon's overhead** is particularly noticeable on small objects and arrays

### Memory Analysis

1. **jzon memory usage is reasonable** - typically 1.2-2.1x more than stdlib_json
2. **ujson is most memory efficient** across most data types
3. **orjson uses significantly more memory** (2.5-8.7x more than stdlib_json)
4. **jzon is memory competitive** with stdlib_json for complex structures

## Performance Bottlenecks

Based on the results, jzon's current performance issues likely stem from:

1. **Pure Python implementation** vs C-optimized libraries
2. **Character-by-character tokenization** optimized for correctness over speed
3. **Comprehensive error handling** with position tracking
4. **State machine overhead** in the recursive descent parser

## Next Steps for Optimization

1. **Zig Integration**: Implement hot-path functions in Zig for significant speed improvements
2. **Tokenization Optimization**: Batch character processing where possible
3. **String Processing**: Optimize escape sequence handling
4. **Memory Allocation**: Consider arena allocation patterns

## Running Benchmarks

```bash
# Run parsing performance benchmarks
uv run pytest benchmarks/test_parsing_performance.py --benchmark-only --benchmark-sort=mean

# Run memory usage benchmarks  
uv run pytest benchmarks/test_memory_usage.py -v -s

# Run specific benchmark group
uv run pytest benchmarks/test_parsing_performance.py -k "small_objects" --benchmark-only
```

## Benchmark Environment

- **Platform**: Darwin (macOS)
- **Python**: 3.12.8
- **pytest-benchmark**: 5.1.0
- **Hardware**: Results may vary by system

---

*Note: These benchmarks establish a baseline for measuring future optimizations. The current focus is on correctness and Zig-ready architecture rather than pure Python performance.*
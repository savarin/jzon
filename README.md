# jzon

**High-performance JSON parsing and encoding library with Zig extensions**

Modern JSON processing that threads the needle between Newtonsoft.Json's extensibility, Zig's performance potential, and Python's ergonomic excellence.

## Why Another JSON Library?

### CPython's JSON Limitations

Python's standard library `json` module, while reliable, has fundamental constraints:

- **Performance bottlenecks**: Pure Python parsing with limited optimization opportunities
- **Memory inefficiency**: Creates intermediate objects during parsing, causing GC pressure
- **Limited extensibility**: Hook system exists but is basic and inflexible
- **Poor error reporting**: Vague error messages without precise position information
- **No observability**: Zero insight into parsing performance or hot paths

These limitations become critical in high-throughput applications where JSON processing is a bottleneck.

### Learning from the Best: Newtonsoft.Json

The .NET ecosystem's Newtonsoft.Json introduced key extensibility patterns we incorporate:

- **Comprehensive hook system**: `object_pairs_hook`, `parse_float`, `parse_int` for custom type conversion
- **Precise error handling**: Detailed error messages with exact line/column positioning
- **Configurable parsing**: Extensive customization through immutable configuration objects

### The Performance Imperative: Why Zig?

Zig's strengths align perfectly with our parsing architecture:

- **State machine translation**: Our ParseState enum maps directly to Zig tagged unions
- **Character-level parsing**: Our JsonLexer design translates naturally to Zig string handling
- **Arena allocation readiness**: Memory management patterns designed for Zig's allocator system
- **Compile-time profiling**: Our ProfileContext infrastructure ready for Zig's comptime features

### Modern Python in 2025: Best Practices We Embrace

**Pydantic's Influence:**
- Type-safe configuration with `@dataclass(frozen=True)` and `__post_init__` validation
- Comprehensive type hints throughout the codebase
- Clear error context and position tracking

**FastAPI's Patterns:**
- Hook-based extensibility for custom parsing behavior
- Immutable configuration objects to prevent state bugs

**UV's Philosophy:**
- Developer experience first: `uv sync` and modern tooling
- Performance-conscious design decisions from the start

## Key Features

- **State Machine Parser**: Proper recursive descent parsing with minimal `eval()` fallback (to be removed)
- **Comprehensive Hooks**: `object_pairs_hook`, `parse_float`, `parse_int`, `parse_constant`
- **Precise Error Reporting**: Line/column numbers and character positions
- **Zero-Cost Profiling**: Toggle with `JZON_PROFILE=1` for performance insights
- **Type Safety**: Full MyPy strict compliance with comprehensive type hints
- **Zig-Ready Architecture**: Designed for future Zig extension integration

## Installation & Usage

```bash
# Install with UV (recommended)
uv add jzon

# Or traditional pip
pip install jzon
```

```python
import jzon
from decimal import Decimal
from collections import OrderedDict

# Basic usage (drop-in replacement for json)
data = jzon.loads('{"pi": 3.14, "active": true}')

# Advanced: custom parsing with hooks
result = jzon.loads(
    '{"numbers": [1.1, 2.2], "meta": {"order": 1}}',
    parse_float=Decimal,           # Custom number parsing
    object_pairs_hook=OrderedDict, # Preserve key order
)

# Profiling for optimization
import os
os.environ['JZON_PROFILE'] = '1'

data = jzon.loads(complex_json)
stats = jzon.get_hot_path_stats()

for func, stat in stats.items():
    print(f"{func}: {stat.call_count} calls, {stat.total_time_ns}ns")
```

## Critical Issues for Next Session

**⚠️ IMPORTANT**: Before using jzon in production, please review the critical issues identified in `/logs/20250122-1939-state-machine-architecture-milestone.md` under "Critical Issues Identified for Next Session". Key items include:

1. **Security Risk**: eval() fallback still exists and must be removed
2. **JSON Compliance**: String escape sequence handling incomplete
3. **Dependencies**: Remove unused pandas dependency
4. **Architecture**: JsonView integration decision needed

See the log file for complete analysis and recommended action plan.

## Changelog

### v0.1.0 - 2025-01-22 (commit: 0ea9862)
State machine architecture milestone. Complete recursive descent parser replacing eval()-based parsing. Zero-cost profiling infrastructure with JZON_PROFILE toggle.

## License

MIT License - see LICENSE file for details.

---

*jzon: where JSON parsing meets modern performance expectations.*
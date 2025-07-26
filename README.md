# jzon

**High-performance JSON parsing library for Python (with battle scars from the Zig frontier)**

## From Vision to Reality

This README tells the story of jzon in two parts. The first section below was our original optimistic vision—a high-performance JSON library designed for future Zig optimization. The second section is reality setting in: we discovered that while Zig integration didn't work out as planned, we built something genuinely valuable along the way. It was a fun experiment that taught us important lessons about performance optimization, FFI overhead, and knowing when to embrace what you've actually built rather than chasing what you thought you wanted.

---

## The Original Vision (Pre-Experiment)

Modern JSON processing that threads the needle between Newtonsoft.Json's extensibility, future Zig performance potential, and Python's ergonomic excellence.

### Why Another JSON Library?

#### CPython's JSON Limitations

Python's standard library `json` module, while reliable, has fundamental constraints:

- **Performance bottlenecks**: Pure Python parsing with limited optimization opportunities
- **Memory inefficiency**: Creates intermediate objects during parsing, causing GC pressure
- **Limited extensibility**: Hook system exists but is basic and inflexible
- **Poor error reporting**: Vague error messages without precise position information
- **No observability**: Zero insight into parsing performance or hot paths

These limitations become critical in high-throughput applications where JSON processing is a bottleneck.

#### Learning from the Best: Newtonsoft.Json

The .NET ecosystem's Newtonsoft.Json introduced key extensibility patterns we incorporate:

- **Comprehensive hook system**: `object_pairs_hook`, `parse_float`, `parse_int` for custom type conversion
- **Precise error handling**: Detailed error messages with exact line/column positioning
- **Configurable parsing**: Extensive customization through immutable configuration objects

#### The Performance Imperative: Why Zig? (Spoiler: It Didn't Work Out)

*[This was our original thinking—reality had other plans!]*

Zig's strengths align perfectly with our parsing architecture:

- **State machine translation**: Our ParseState enum maps directly to Zig tagged unions
- **Character-level parsing**: Our JsonLexer design translates naturally to Zig string handling
- **Arena allocation readiness**: Memory management patterns designed for Zig's allocator system
- **Compile-time profiling**: Our ProfileContext infrastructure ready for Zig's comptime features

#### Modern Python in 2025: Best Practices We Embrace

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

---

## What Actually Happened: The Great Zig Experiment of 2025 🪖

So, we had this brilliant idea: "What if we turbocharged JSON parsing with Zig?" 

After three months of heroic engineering across multiple phases, we built:
- ✅ Four different Zig parser implementations  
- ✅ Comprehensive FFI integration with ctypes
- ✅ Arena allocators with string interning
- ✅ Robust build systems and test infrastructure
- ✅ A really impressive 800+ line Zig codebase

**The Results**: Zig made our JSON parsing... 33x slower. 🎉

Turns out Foreign Function Interface (FFI) overhead is a **beast**. Who knew that calling between languages costs more than just parsing JSON? Well, we do now!

### The Plot Twist

But wait! Our final binary decision experiment found that Zig *could* beat Python... if you:
- Parse arrays with 20+ numeric elements
- Don't mind 1.46x speedup at best  
- Really enjoy managing cross-language build systems
- Have a passionate love for FFI debugging

**Verdict**: We gracefully bowed out and focused on what actually matters: great pure Python code.

## What We Actually Built (The Good Stuff) ✨

Through this journey, we created a genuinely excellent JSON library:

### Key Features
- **State Machine Parser**: Proper recursive descent parsing with no eval() usage
- **Comprehensive Hooks**: `object_pairs_hook`, `parse_float`, `parse_int`, `parse_constant`
- **Precise Error Reporting**: Line/column numbers and character positions
- **Zero-Cost Profiling**: Toggle with `JZON_PROFILE=1` for performance insights
- **Type Safety**: Full MyPy strict compliance with comprehensive type hints
- **Clean Architecture**: Every layer has a single responsibility

### Performance Reality Check
- **Speed**: Competitive with other pure Python parsers (~2-5x slower than stdlib json)
- **Memory**: Reasonable overhead (1.2-2.1x stdlib json)
- **Reliability**: 100% compatibility with CPython's json module
- **Debuggability**: Actually tells you *where* your JSON is broken

## Installation & Usage

```bash
# Install with UV (because we learned to love good tooling)
uv add jzon

# Or traditional pip
pip install jzon
```

```python
import jzon
from decimal import Decimal
from collections import OrderedDict

# Drop-in replacement for json
data = jzon.loads('{"temperature": 23.5, "active": true}')

# Advanced usage with hooks (this is where we shine!)
result = jzon.loads(
    '{"prices": [19.99, 29.99], "metadata": {"version": 2}}',
    parse_float=Decimal,           # Precise decimal handling
    object_pairs_hook=OrderedDict, # Preserve key order
)

# When JSON goes wrong, we tell you exactly where
try:
    jzon.loads('{"broken": }')  # Missing value
except jzon.JSONDecodeError as e:
    print(f"Error at position {e.pos}: {e.msg}")
    # "Error at position 11: Expected value after ':'"

# Performance profiling (because we're still performance nerds)
import os
os.environ['JZON_PROFILE'] = '1'

data = jzon.loads('{"users": [{"name": "Alice", "scores": [95, 87]}]}')
stats = jzon.get_hot_path_stats()

for func, stat in stats.items():
    print(f"{func}: {stat.call_count} calls, {stat.total_time_ns/1_000_000:.2f}ms")
```

## When to Use jzon

**Choose jzon when you need:**
- 🎯 **Superior error diagnostics** - Know exactly where your JSON broke
- 🪝 **Powerful hook system** - Custom parsing logic that actually works  
- 🔧 **Clean, maintainable code** - Architecture that makes sense
- 🛡️ **Type safety** - Full MyPy support for confidence
- 📊 **Performance observability** - Understanding where time is spent

**Stick with stdlib json when:**
- ⚡ Raw speed is your only concern
- 🚀 You're parsing massive JSON files (>1MB)
- 📦 Minimal dependencies matter more than features

**Use orjson/ujson when:**
- 🏎️ You need maximum performance
- 🤝 Simple use cases without custom parsing needs

## The Lessons We Learned

1. **FFI overhead is real**: Fine-grained language interop can kill performance
2. **Measure everything**: Performance intuition is often wrong
3. **Architecture matters**: Good design survives failed optimizations
4. **Time-boxing works**: Our 3-hour binary decision experiment saved months
5. **Sometimes the journey is the destination**: We built great Python code while chasing Zig dreams

## Project Evolution

### Phase 1: Foundation
Built the core parser architecture with proper error handling and hooks.

### Phase 2: Python Optimizations
Optimized tokenization, added profiling, achieved respectable pure Python performance.

### Phase 3: The Zig Adventure
Three intensive sessions building Zig integration. Learned that FFI overhead > parsing gains for typical JSON. The experiment data is preserved in `/logs` for posterity and scientific curiosity.

### Phase 4: Acceptance and Excellence
Embraced our identity as an excellent pure Python JSON library. Sometimes the best optimization is knowing when to stop optimizing.

---

*jzon: where JSON parsing meets reality (and reality usually wins)*

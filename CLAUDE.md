# CLAUDE.md

High-performance JSON parsing and encoding library with Zig extensions. Pure Python implementation with optional Zig acceleration, following modern Python patterns with strong typing and clean architecture.

## Architecture & Testing

**Core Principle:** Each abstraction level solves exactly one type of problem. Parsers know tokenization, decoders know JSON semantics, encoders know serialization, extensions know performance optimization.

**Layer Separation:**
- Protocol interfaces: Define clear contracts for parsing and encoding components
- Immutable models: `@dataclass(frozen=True)` for JSON node types and configuration
- Parser layer: Tokenization and syntactic analysis behind typed interfaces
- Decoder/Encoder layer: JSON semantic processing, pure functions where possible
- Extension layer: Zig acceleration modules with no Python dependencies

**Testing Patterns:**
- Standards compliance: All CPython JSON test cases must pass
- Descriptive test names: `test_unicode_escape_sequence_parsing_accuracy`
- Test isolation: Each test independent, clear setup/teardown
- Fixture organization: Use pytest fixtures for JSON test data, factories for edge cases
- Specific assertions: Assert exact parsed values and error positions, not just truthiness

**Dependency Management:**
- Constructor injection: Pass parsing options to constructors, not global state
- Type-safe boundaries: Strong typing between parsing layers and language boundaries
- Resource management: Proper cleanup of Zig-allocated memory and file handles

## Type System

- Comprehensive type hints on all parameters, returns, class attributes
- Type aliases for domain concepts: `JsonValue = str | int | float | bool | None | dict | list`, `type Position = int`
- Protocol classes for interfaces over abstract base classes
- Modern union syntax: `str | None` over `Optional[str]`
- Enums over string literals for constants

## Function Design

- Short focused functions: ideally 20-30 lines, 40 when reasonable, max 50 if formatting spreads low-density code
- Pure functions: Deterministic outputs for given inputs where possible
- Early validation: Guard clauses at function entry
- Post-init validation: Validate inputs in `__post_init__` methods

## Domain Patterns

- Memory management: Use proper context managers for Zig memory allocation
- String processing: Use explicit bounds checking and UTF-8 validation
- Configuration: Use immutable dataclasses with validation in `__post_init__`
- Performance: Zig extensions for hot paths, Python for flexibility

## Quality Standards

- Standards compliance: All CPython JSON test cases must pass
- Security first: Never expose or log secrets, never commit credentials
- Atomic commits with clear rationale explaining why, not just what
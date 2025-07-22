# CLAUDE.md

General instructions and context for Claude Code sessions working on this codebase.

## Codebase Context

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

- Short focused functions: 10-20 lines maximum, single responsibility
- Pure functions: Deterministic outputs for given inputs where possible
- Early validation: Guard clauses at function entry
- Post-init validation: Validate inputs in `__post_init__` methods

## Literary Style

**Core Principle:** Maximize information density while minimizing cognitive burden. Every word either clarifies purpose, provides essential context, or guides action.

**Clarity:**
- Action-oriented descriptions: "Handles", "Orchestrates", "Manages", "Validates"
- Purpose before implementation in docstrings
- Present tense, active voice
- Front-load critical information
- No filler words - every word serves a purpose

**Documentation Voice:**
- Conversational but never casual - like explaining complex ideas to a sharp colleague over coffee
- Problem-first approach: Start with what this solves, not what it is
- Lead with core insight immediately, build complexity gradually

**Error Communication:**
- Error messages as user guidance: `"Invalid JSON at position 42: expected ',' or '}' after object key"`
- Exception chaining: `raise JSONDecodeError("Parse error") from e`
- Include relevant context: position, line/column numbers, surrounding text

## Formatting

**Import Organization:**
- Three-tier grouping: standard library, third-party, local imports (blank lines between)
- Alphabetical ordering within each tier
- Direct imports before from imports within each group

**Docstring Format:**
- Triple quotes on separate lines: `"""\nDocstring content\n"""`
- Comprehensive docstrings for complex functions, brief ones for simple functions
- Structured Args/Returns/Raises sections with colons

**Code Structure:**
- 80-character soft limit with readability exceptions
- Double blank lines around classes, single around functions
- F-strings over .format() or %
- Trailing commas in multi-line structures
- Early returns and guard clauses

## Quality Standards

- Full mypy compliance with strict settings
- Tests alongside implementation, not after
- Atomic commits with clear rationale explaining why, not just what
- Security first: Never expose or log secrets, never commit credentials

## Common Patterns

- Dataclass usage: Explicitly import and use `dataclasses.dataclass`
- Memory management: Use proper context managers for Zig memory allocation
- String processing: Use explicit bounds checking and UTF-8 validation
- Configuration: Use immutable dataclasses with validation in `__post_init__`
- Performance: Zig extensions for hot paths, Python for flexibility

## Development Workflow

1. Write tests alongside implementation, not after
2. Follow established patterns rather than creating new ones
3. Maintain clean boundaries between business logic and infrastructure concerns
4. Make atomic commits with clear messages describing the change and rationale

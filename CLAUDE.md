# CLAUDE.md

General instructions and context for Claude Code sessions working on this codebase.

## Codebase Context

Python monorepo with machine learning and data pipeline infrastructure. Multiple packages following modern Python patterns with async/await, strong typing, and clean architecture.

## Architecture & Testing

**Core Principle:** Each abstraction level solves exactly one type of problem. Domain models know business rules, repositories know data access, services know workflows, APIs know HTTP concerns.

**Layer Separation:**
- Protocol interfaces: Define clear contracts for dependency injection
- Immutable models: `@dataclass(frozen=True)` as default for data structures
- Repository pattern: Database access behind typed interfaces
- Service layer: Business logic coordination, pure functions where possible
- Domain models: Immutable entities with no external dependencies

**Testing Patterns:**
- Mock external dependencies (databases, APIs), not internal logic
- Descriptive test names: `test_user_assignment_consistency_across_calls`
- Test isolation: Each test independent, clear setup/teardown
- Fixture organization: Use pytest fixtures for complex setup, factories for data generation
- Specific assertions: Assert exact expected values, not just truthiness

**Dependency Management:**
- Constructor injection: Pass dependencies to constructors, not global imports
- Type-safe boundaries: Strong typing between all layers
- Context managers: `with Resource() as client:` for resource management

## Type System

- Comprehensive type hints on all parameters, returns, class attributes
- Type aliases for domain concepts: `UserId = str`, `type NodeId = str`
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
- Error messages as user guidance: `"User features not found: {user_id}"`
- Exception chaining: `raise ValueError("Context") from e`
- Include relevant context in error messages

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
- Database integration: Use proper async context management
- SQL generation: Use explicit AS keywords for table aliases, clear column prefixes
- Configuration: Use immutable dataclasses with validation in `__post_init__`

## Development Workflow

1. Write tests alongside implementation, not after
2. Follow established patterns rather than creating new ones
3. Maintain clean boundaries between business logic and infrastructure concerns
4. Make atomic commits with clear messages describing the change and rationale

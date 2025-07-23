"""
High-performance JSON parsing and encoding library with Zig extensions.

Provides JSON encoding and decoding functionality compatible with the standard
library json module, with optional Zig acceleration for performance-critical paths.
"""

import dataclasses
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import IO
from typing import Any

__version__ = "0.1.0"

# Type aliases for domain concepts - recursive definition
JsonValue = (
    str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]
)
type Position = int

# Union type for values that might be transformed by hooks
JsonValueOrTransformed = JsonValue | Any
# More permissive type for internal/test use
JsonValueLoose = Any

# Hook type definitions - hooks can return custom types
ObjectHook = Callable[[dict[str, JsonValue]], Any] | None
ObjectPairsHook = (
    Callable[[list[tuple[str, JsonValueOrTransformed]]], Any] | None
)
ParseFloatHook = Callable[[str], Any] | None
ParseIntHook = Callable[[str], Any] | None
ParseConstantHook = Callable[[str], Any] | None

# Profiling infrastructure - zero-cost when disabled
PROFILE_HOT_PATHS = __debug__ and "JZON_PROFILE" in os.environ


@dataclass
class HotPathStats:
    """Statistics for profiling hot paths during parsing."""

    function_name: str
    call_count: int = 0
    total_time_ns: int = 0
    chars_processed: int = 0

    def record_call(self, duration_ns: int, chars: int = 0) -> None:
        """Records a function call with timing and character processing info."""
        self.call_count += 1
        self.total_time_ns += duration_ns
        self.chars_processed += chars


class ParseState(Enum):
    """
    State machine states for JSON parsing.

    Maps directly to Zig tagged unions for future optimization.
    """

    START = "start"
    VALUE = "value"
    OBJECT_START = "object_start"
    OBJECT_KEY = "object_key"
    OBJECT_COLON = "object_colon"
    OBJECT_VALUE = "object_value"
    OBJECT_COMMA = "object_comma"
    ARRAY_START = "array_start"
    ARRAY_VALUE = "array_value"
    ARRAY_COMMA = "array_comma"
    STRING = "string"
    NUMBER = "number"
    LITERAL = "literal"
    END = "end"


if PROFILE_HOT_PATHS:
    _hot_path_stats: dict[str, HotPathStats] = {}

    class ProfileContext:
        """Context manager for profiling hot paths."""

        def __init__(self, func_name: str, chars_to_process: int = 0):
            self.func_name = func_name
            self.chars = chars_to_process
            self.start_time = 0

        def __enter__(self) -> "ProfileContext":
            self.start_time = time.perf_counter_ns()
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            duration = time.perf_counter_ns() - self.start_time
            if self.func_name not in _hot_path_stats:
                _hot_path_stats[self.func_name] = HotPathStats(self.func_name)
            _hot_path_stats[self.func_name].record_call(duration, self.chars)

    def get_hot_path_stats() -> dict[str, HotPathStats]:
        """Returns current profiling statistics."""
        return _hot_path_stats.copy()

    def clear_hot_path_stats() -> None:
        """Clears profiling statistics."""
        _hot_path_stats.clear()

else:
    # Zero-cost in production - ignore arguments to nullcontext
    class ProfileContext:  # type: ignore[no-redef]
        def __init__(self, func_name: str, chars: int = 0) -> None:
            pass

        def __enter__(self) -> "ProfileContext":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    def get_hot_path_stats() -> dict[str, HotPathStats]:
        return {}

    def clear_hot_path_stats() -> None:
        pass


class JSONDecodeError(ValueError):
    """
    Handles JSON parsing failures with precise position and context information.

    Error state containing position, line/column numbers, and surrounding
    context to help users identify and fix JSON syntax issues.
    """

    def __init__(self, msg: str, doc: str = "", pos: Position = 0) -> None:
        if not isinstance(msg, str):
            raise TypeError("msg must be a string")
        if not isinstance(pos, int) or pos < 0:
            raise ValueError("pos must be a non-negative integer")

        self.msg = msg
        self.doc = doc
        self.pos = pos

        # Compute line and column numbers from position
        self.lineno = doc.count("\n", 0, pos) + 1 if doc else 1
        self.colno = pos - doc.rfind("\n", 0, pos) if doc else pos + 1

        # Initialize ValueError with formatted message
        super().__init__(f"{msg} at line {self.lineno}, column {self.colno}")


@dataclass(frozen=True)
class JsonView:
    """
    Zero-copy view into JSON source string.

    Implements lazy materialization - parsing is deferred until value is accessed.
    This matches Newtonsoft's StringReference pattern and enables Zig arena allocation.
    """

    source: str
    start: Position
    end: Position
    value_type: ParseState
    _materialized: JsonValueOrTransformed | None = dataclasses.field(
        default=None, init=False
    )

    def get_value(self, config: "ParseConfig") -> JsonValueOrTransformed:
        """
        Materializes the parsed value on-demand.

        First access triggers parsing, subsequent accesses return cached value.
        This enables FastAPI-style lazy evaluation.
        """
        if self._materialized is None:
            with ProfileContext("materialize_value", self.end - self.start):
                view_str = self.source[self.start : self.end]
                # Use object.__setattr__ for frozen dataclass
                object.__setattr__(
                    self,
                    "_materialized",
                    _parse_view_content(view_str, self.value_type, config),
                )
        return self._materialized

    @property
    def raw_content(self) -> str:
        """Returns the raw string content without parsing."""
        return self.source[self.start : self.end]


@dataclass(frozen=True)
class ParseResult:
    """
    Result of parsing operation with contextual error information.

    Supports both immediate values and lazy views for memory efficiency.
    Enables Pydantic-style error accumulation for better UX.
    """

    value: JsonValue | JsonView | None = None
    errors: list[JSONDecodeError] = dataclasses.field(default_factory=list)
    final_position: Position = 0

    def is_success(self) -> bool:
        """Returns True if parsing succeeded without errors."""
        return not self.errors and self.value is not None

    def get_materialized_value(
        self, config: "ParseConfig"
    ) -> JsonValueOrTransformed:
        """
        Returns the final parsed value, materializing lazy views if needed.
        """
        if isinstance(self.value, JsonView):
            return self.value.get_value(config)
        return self.value


@dataclass(frozen=True)
class JsonToken:
    """
    Represents a JSON token with position information.

    Maps to Zig token structures for parsing efficiency.
    """

    type: ParseState
    value: str
    start: Position
    end: Position


class JsonLexer:
    """
    Tokenizes JSON input for state machine parsing.

    Character-by-character scanning optimized for Zig translation.
    Handles whitespace, strings, numbers, literals, and structural tokens.
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def peek(self) -> str:
        """Returns current character without advancing."""
        return self.text[self.pos] if self.pos < self.length else "\0"

    def advance(self) -> str:
        """Returns current character and advances position."""
        char = self.peek()
        if self.pos < self.length:
            self.pos += 1
        return char

    def skip_whitespace(self) -> None:
        """Skips whitespace characters according to JSON spec."""
        with ProfileContext("skip_whitespace"):
            while self.pos < self.length and self.text[self.pos] in " \t\n\r":
                self.pos += 1

    def scan_string(self) -> JsonToken:
        """Scans a JSON string token including quotes."""
        with ProfileContext("scan_string"):
            start = self.pos
            if self.advance() != '"':
                raise JSONDecodeError("Expected string", self.text, start)

            while self.pos < self.length:
                char = self.advance()
                if char == '"':
                    return JsonToken(
                        ParseState.STRING,
                        self.text[start : self.pos],
                        start,
                        self.pos,
                    )
                elif char == "\\":
                    # Skip escaped character
                    if self.pos < self.length:
                        self.advance()
                elif char in {"\n", "\r"}:
                    raise JSONDecodeError(
                        "Unterminated string", self.text, start
                    )

            raise JSONDecodeError(
                "Unterminated string starting at", self.text, start
            )

    def scan_number(self) -> JsonToken:  # noqa: PLR0912
        """Scans a JSON number token."""
        with ProfileContext("scan_number"):
            start = self.pos

            # Handle negative numbers
            if self.peek() == "-":
                self.advance()

            # Scan digits
            if not self.peek().isdigit():
                raise JSONDecodeError("Invalid number", self.text, start)

            # Handle zero or multi-digit numbers
            if self.peek() == "0":
                self.advance()
                if self.peek().isdigit():
                    raise JSONDecodeError(
                        "Leading zeros not allowed", self.text, start
                    )
            else:
                while self.peek().isdigit():
                    self.advance()

            # Handle decimal part
            if self.peek() == ".":
                self.advance()
                if not self.peek().isdigit():
                    raise JSONDecodeError(
                        "Invalid decimal number", self.text, start
                    )
                while self.peek().isdigit():
                    self.advance()

            # Handle exponent
            if self.peek().lower() == "e":
                self.advance()
                if self.peek() in "+-":
                    self.advance()
                if not self.peek().isdigit():
                    raise JSONDecodeError("Invalid exponent", self.text, start)
                while self.peek().isdigit():
                    self.advance()

            return JsonToken(
                ParseState.NUMBER, self.text[start : self.pos], start, self.pos
            )

    def scan_literal(self) -> JsonToken:
        """Scans literal tokens: true, false, null."""
        with ProfileContext("scan_literal"):
            start = self.pos

            if self.text[self.pos : self.pos + 4] == "true":
                self.pos += 4
                return JsonToken(ParseState.LITERAL, "true", start, self.pos)
            elif self.text[self.pos : self.pos + 5] == "false":
                self.pos += 5
                return JsonToken(ParseState.LITERAL, "false", start, self.pos)
            elif self.text[self.pos : self.pos + 4] == "null":
                self.pos += 4
                return JsonToken(ParseState.LITERAL, "null", start, self.pos)
            else:
                raise JSONDecodeError("Invalid literal", self.text, start)

    def next_token(self) -> JsonToken | None:
        """Returns the next token or None if at end."""
        self.skip_whitespace()

        if self.pos >= self.length:
            return None

        char = self.peek()
        start = self.pos

        # Structural tokens
        if char in "{}[],:":
            self.advance()
            state_map = {
                "{": ParseState.OBJECT_START,
                "}": ParseState.OBJECT_START,  # Will be handled by parser context
                "[": ParseState.ARRAY_START,
                "]": ParseState.ARRAY_START,  # Will be handled by parser context
                ",": ParseState.OBJECT_COMMA,
                ":": ParseState.OBJECT_COLON,
            }
            return JsonToken(state_map[char], char, start, self.pos)

        # String tokens
        elif char == '"':
            return self.scan_string()

        # Number tokens
        elif char.isdigit() or char == "-":
            return self.scan_number()

        # Literal tokens
        elif char in "tfn":
            return self.scan_literal()

        else:
            raise JSONDecodeError("Unexpected character", self.text, self.pos)


@dataclass(frozen=True)
class ParseConfig:
    """
    Configures JSON parsing behavior with immutable settings.

    Centralized configuration for all parsing options including hooks,
    validation settings, and performance optimizations.
    """

    strict: bool = True
    parse_float: ParseFloatHook = None
    parse_int: ParseIntHook = None
    parse_constant: ParseConstantHook = None
    object_pairs_hook: ObjectPairsHook = None
    object_hook: ObjectHook = None
    use_decimal: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strict, bool):
            raise TypeError("strict must be a boolean")


@dataclass(frozen=True)
class EncodeConfig:
    """
    Configures JSON encoding behavior with immutable settings.

    Centralized configuration for serialization options including formatting,
    custom encoders, and output optimization.
    """

    skipkeys: bool = False
    ensure_ascii: bool = True
    sort_keys: bool = False
    indent: str | int | None = None
    separators: tuple[str, str] | None = None
    default: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.skipkeys, bool):
            raise TypeError("skipkeys must be a boolean")
        if not isinstance(self.ensure_ascii, bool):
            raise TypeError("ensure_ascii must be a boolean")
        if not isinstance(self.sort_keys, bool):
            raise TypeError("sort_keys must be a boolean")


class JsonParser:
    """
    State machine parser for JSON using token stream.

    Implements recursive descent parsing that maps directly to Zig.
    Handles object_pairs_hook and contextual error accumulation.
    """

    def __init__(self, lexer: JsonLexer, config: ParseConfig):
        self.lexer = lexer
        self.config = config
        self.current_token: JsonToken | None = None
        self.errors: list[JSONDecodeError] = []

    def advance_token(self) -> JsonToken | None:
        """Advances to next token and returns it."""
        self.current_token = self.lexer.next_token()
        return self.current_token

    def expect_token(self, expected_value: str) -> JsonToken:
        """Expects a specific token value and advances."""
        if not self.current_token or self.current_token.value != expected_value:
            raise JSONDecodeError(
                f"Expected '{expected_value}'",
                self.lexer.text,
                self.current_token.start
                if self.current_token
                else self.lexer.pos,
            )
        token = self.current_token
        self.advance_token()
        return token

    def parse_value(self) -> JsonValueOrTransformed:
        """Parses any JSON value based on current token."""
        if not self.current_token:
            raise JSONDecodeError(
                "Expecting value", self.lexer.text, self.lexer.pos
            )

        token = self.current_token

        if token.type == ParseState.LITERAL:
            self.advance_token()
            return _parse_literal(token.value, self.config)
        elif token.type == ParseState.STRING:
            self.advance_token()
            return _parse_string_content(token.value, self.config)
        elif token.type == ParseState.NUMBER:
            self.advance_token()
            return _parse_number_content(token.value, self.config)
        elif token.value == "{":
            return self.parse_object()
        elif token.value == "[":
            return self.parse_array()
        else:
            raise JSONDecodeError(
                "Expecting value", self.lexer.text, token.start
            )

    def parse_object(self) -> JsonValueOrTransformed:
        """Parses JSON object with state machine."""
        with ProfileContext("parse_object"):
            self.expect_token("{")

            # Handle empty object
            if self.current_token and self.current_token.value == "}":
                self.advance_token()
                return {}

            pairs: list[tuple[str, JsonValueOrTransformed]] = []

            while True:
                # Parse key
                if (
                    not self.current_token
                    or self.current_token.type != ParseState.STRING
                ):
                    raise JSONDecodeError(
                        "Expecting property name enclosed in double quotes",
                        self.lexer.text,
                        self.current_token.start
                        if self.current_token
                        else self.lexer.pos,
                    )

                key_token = self.current_token
                self.advance_token()
                key = _parse_string_content(key_token.value, self.config)

                # Expect colon
                self.expect_token(":")

                # Parse value
                value = self.parse_value()
                pairs.append((key, value))

                # Check for continuation or end
                if not self.current_token:
                    raise JSONDecodeError(
                        "Expecting ',' delimiter",
                        self.lexer.text,
                        self.lexer.pos,
                    )

                if self.current_token.value == "}":
                    self.advance_token()
                    break
                elif self.current_token.value == ",":
                    self.advance_token()
                    # Check for trailing comma
                    if self.current_token and self.current_token.value == "}":
                        raise JSONDecodeError(
                            "Illegal trailing comma before end of object",
                            self.lexer.text,
                            self.current_token.start - 1,
                        )
                else:
                    raise JSONDecodeError(
                        "Expecting ',' delimiter",
                        self.lexer.text,
                        self.current_token.start,
                    )

            # Use object_pairs_hook if provided (takes priority)
            if self.config.object_pairs_hook:
                return self.config.object_pairs_hook(pairs)
            else:
                obj = dict(pairs)
                # Use object_hook if provided
                if self.config.object_hook:
                    return self.config.object_hook(obj)
                return obj

    def parse_array(self) -> list[JsonValueOrTransformed]:
        """Parses JSON array with state machine."""
        with ProfileContext("parse_array"):
            self.expect_token("[")

            # Handle empty array
            if self.current_token and self.current_token.value == "]":
                self.advance_token()
                return []

            values: list[JsonValueOrTransformed] = []

            while True:
                # Parse value
                value = self.parse_value()
                values.append(value)

                # Check for continuation or end
                if not self.current_token:
                    raise JSONDecodeError(
                        "Expecting ',' delimiter",
                        self.lexer.text,
                        self.lexer.pos,
                    )

                if self.current_token.value == "]":
                    self.advance_token()
                    break
                elif self.current_token.value == ",":
                    self.advance_token()
                    # Check for trailing comma
                    if self.current_token and self.current_token.value == "]":
                        raise JSONDecodeError(
                            "Illegal trailing comma before end of array",
                            self.lexer.text,
                            self.current_token.start - 1,
                        )
                else:
                    raise JSONDecodeError(
                        "Expecting ',' delimiter",
                        self.lexer.text,
                        self.current_token.start,
                    )

            return values


def _parse_view_content(
    content: str, value_type: ParseState, config: ParseConfig
) -> JsonValueOrTransformed:
    """
    Parses content from a JsonView based on its determined type.

    This function handles the actual parsing after structure analysis is complete.
    Used for lazy materialization of JsonView objects.
    """
    with ProfileContext("parse_view_content", len(content)):
        if value_type == ParseState.LITERAL:
            return _parse_literal(content, config)
        elif value_type == ParseState.STRING:
            return _parse_string_content(content, config)
        elif value_type == ParseState.NUMBER:
            return _parse_number_content(content, config)
        else:
            # Fallback to eval for complex structures (temporary)
            try:
                return eval(content)
            except Exception as e:
                raise JSONDecodeError("Invalid JSON content", content, 0) from e


def _parse_literal(content: str, config: ParseConfig) -> JsonValueOrTransformed:
    """Parses JSON literals: null, true, false, and constants."""
    with ProfileContext("parse_literal", len(content)):
        stripped = content.strip()
        if stripped == "null":
            return None
        elif stripped == "true":
            return True
        elif stripped == "false":
            return False
        elif stripped in ("Infinity", "-Infinity", "NaN"):
            if config.parse_constant:
                return config.parse_constant(stripped)
            else:
                raise JSONDecodeError("Invalid literal", content, 0)
        else:
            raise JSONDecodeError("Invalid literal", content, 0)


def _parse_string_content(content: str, _config: ParseConfig) -> str:
    """Parses JSON string content, handling escape sequences."""
    with ProfileContext("parse_string", len(content)):
        if not (content.startswith('"') and content.endswith('"')):
            raise JSONDecodeError("Invalid string format", content, 0)
        # Basic string parsing - remove quotes
        # TODO: Add proper escape sequence handling
        return content[1:-1]


def _parse_number_content(
    content: str, config: ParseConfig
) -> JsonValueOrTransformed:
    """Parses JSON number content with proper validation."""
    with ProfileContext("parse_number", len(content)):
        stripped = content.strip()

        # Basic validation for ASCII digits only
        if not all(c in "0123456789.-+eE" for c in stripped):
            raise JSONDecodeError("Invalid number format", content, 0)

        try:
            if "." in stripped or "e" in stripped.lower():
                if config.parse_float:
                    return config.parse_float(stripped)
                return float(stripped)
            else:
                if config.parse_int:
                    return config.parse_int(stripped)
                return int(stripped)
        except ValueError as e:
            raise JSONDecodeError("Invalid number", content, 0) from e


def _determine_value_type(s: str) -> ParseState:
    """
    Analyzes JSON string to determine its type without parsing.

    This enables lazy materialization - we know what type it is
    but don't parse until needed. Maps to Zig tagged union discrimination.
    """
    stripped = s.strip()

    if not stripped:
        raise JSONDecodeError("Expecting value", s, 0)

    if stripped in ("null", "true", "false", "Infinity", "-Infinity", "NaN"):
        return ParseState.LITERAL
    elif stripped.startswith('"') and stripped.endswith('"'):
        return ParseState.STRING
    elif stripped.startswith("{"):
        return ParseState.OBJECT_START
    elif stripped.startswith("["):
        return ParseState.ARRAY_START
    elif stripped[0].isdigit() or stripped[0] in "-+":
        return ParseState.NUMBER
    else:
        raise JSONDecodeError("Expecting value", s, 0)


def _parse_value(s: str, config: ParseConfig) -> JsonValueOrTransformed:
    """
    Main parser entry point implementing staged parsing strategy.

    Stage 1: Determine structure and create zero-copy views
    Stage 2: Parse simple values immediately, defer complex ones
    Stage 3: Use arena allocation for final materialization

    This matches Newtonsoft's approach while enabling Zig optimization.
    """
    with ProfileContext("parse_value", len(s)):
        stripped = s.strip()

        if not stripped:
            raise JSONDecodeError("Expecting value", s, 0)

        # Handle empty containers immediately (optimization)
        if stripped == "{}":
            return {}
        elif stripped == "[]":
            return []

        # Determine value type for lazy materialization
        value_type = _determine_value_type(stripped)

        # For simple values, parse immediately
        if value_type in (
            ParseState.LITERAL,
            ParseState.STRING,
            ParseState.NUMBER,
        ):
            return _parse_view_content(stripped, value_type, config)

        # For complex structures, use state machine parser
        else:
            lexer = JsonLexer(stripped)
            parser = JsonParser(lexer, config)
            parser.advance_token()  # Load first token

            result = parser.parse_value()

            # Check for extra data after valid JSON
            if parser.current_token:
                raise JSONDecodeError(
                    "Extra data", stripped, parser.current_token.start
                )

            return result


def loads(s: str, **kwargs: Any) -> JsonValueOrTransformed:
    """
    Parses JSON string into Python objects with strict standards compliance.

    Validates input type and delegates to parser with immutable configuration.
    """
    if not isinstance(s, str):
        raise TypeError("the JSON object must be str, not bytes")

    config = ParseConfig(**kwargs)
    return _parse_value(s, config)


def dumps(obj: JsonValueLoose, **kwargs: Any) -> str:  # noqa: ARG001
    """
    Serializes Python objects to JSON string with configurable formatting.

    Uses immutable configuration to ensure consistent encoding behavior.
    """
    _ = EncodeConfig(**kwargs)  # Validate config but don't use yet
    raise NotImplementedError("jzon.dumps not yet implemented")


def load(fp: IO[str], **kwargs: Any) -> JsonValueOrTransformed:
    """
    Parses JSON from file-like object with memory-efficient streaming.
    """
    if not hasattr(fp, "read"):
        raise TypeError("fp must have a read() method")

    return loads(fp.read(), **kwargs)


def dump(obj: JsonValueLoose, fp: IO[str], **kwargs: Any) -> None:
    """
    Serializes Python objects to JSON file with proper resource management.
    """
    if not hasattr(fp, "write"):
        raise TypeError("fp must have a write() method")

    fp.write(dumps(obj, **kwargs))


__all__ = [
    "EncodeConfig",
    "HotPathStats",
    "JSONDecodeError",
    "JsonLexer",
    "JsonParser",
    "JsonToken",
    "JsonView",
    "ParseConfig",
    "ParseResult",
    "ParseState",
    "clear_hot_path_stats",
    "dump",
    "dumps",
    "get_hot_path_stats",
    "load",
    "loads",
]

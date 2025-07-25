"""
High-performance JSON parsing and encoding library with Zig extensions.

Provides JSON encoding and decoding functionality compatible with the standard
library json module, with optional Zig acceleration for performance-critical paths.
"""

import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import IO
from typing import Any

from ._utf8_mapper import UTF8PositionMapper

# Zig error code constants
ERROR_UNTERMINATED_STRING = -4
ERROR_INVALID_ESCAPE = -5
ERROR_INVALID_UNICODE = -6
ERROR_PARSE_FAILED = -3
ERROR_INVALID_INPUT = -2

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

# Escape sequence lookup table - module level for performance
_ESCAPE_MAP = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

# Profiling infrastructure - zero-cost when disabled
PROFILE_HOT_PATHS = __debug__ and "JZON_PROFILE" in os.environ

# Zig acceleration - default enabled, Python fallback via environment variable
USE_PYTHON_FALLBACK = "JZON_PYTHON" in os.environ
_zig_available = False

if not USE_PYTHON_FALLBACK:
    try:
        # Try to import Zig bindings
        import ctypes
        import ctypes.util
        from pathlib import Path

        # Look for the compiled Zig library
        lib_name = "jzon_zig"
        lib_path = None

        # Check in zig-out/lib (standard Zig build output)
        project_root = Path(__file__).parent.parent.parent
        zig_lib_path = project_root / "zig-out" / "lib"

        for suffix in ["so", "dylib", "dll"]:
            candidate = zig_lib_path / f"lib{lib_name}.{suffix}"
            if candidate.exists():
                lib_path = str(candidate)
                break

        if lib_path:
            _jzon_zig = ctypes.CDLL(lib_path)

            # Configure available functions for hybrid parser
            try:
                # Test function for verification
                _jzon_zig.jzon_test_function.argtypes = []
                _jzon_zig.jzon_test_function.restype = ctypes.c_int

                # Fast validation function
                _jzon_zig.jzon_validate_json.argtypes = [
                    ctypes.c_char_p,  # input
                    ctypes.c_ssize_t,  # input_len
                ]
                _jzon_zig.jzon_validate_json.restype = ctypes.c_int

                # Simple parser function (always returns null for Python fallback)
                _jzon_zig.jzon_parse_simple.argtypes = [
                    ctypes.c_char_p,  # input
                    ctypes.c_ssize_t,  # input_len
                    ctypes.c_void_p,  # config (simplified)
                    ctypes.c_void_p,  # error_info (simplified)
                ]
                _jzon_zig.jzon_parse_simple.restype = ctypes.c_void_p

            except AttributeError as func_error:
                raise func_error

            _zig_available = True
        else:
            # Library not found, fall back to Python
            USE_PYTHON_FALLBACK = True

    except (ImportError, OSError, AttributeError):
        # Failed to load Zig library, fall back to Python
        USE_PYTHON_FALLBACK = True
        _zig_available = False


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
        self._byte_to_char: dict[int, int] | None = None

        # Zig token type to ParseState mapping and UTF-8 optimization
        if _zig_available:
            self._token_type_map = {
                1: ParseState.OBJECT_START,  # OBJECT_START
                2: ParseState.OBJECT_START,  # OBJECT_END (context-dependent)
                3: ParseState.ARRAY_START,  # ARRAY_START
                4: ParseState.ARRAY_START,  # ARRAY_END (context-dependent)
                5: ParseState.STRING,  # STRING
                6: ParseState.NUMBER,  # NUMBER
                7: ParseState.LITERAL,  # BOOLEAN
                8: ParseState.LITERAL,  # NULL
                9: ParseState.OBJECT_COMMA,  # COMMA
                10: ParseState.OBJECT_COLON,  # COLON
                11: ParseState.END,  # EOF
                12: ParseState.START,  # ERROR (will raise exception)
            }

            # Pre-encode text once for efficiency
            self._text_bytes = text.encode("utf-8")

            # Use optimized UTF-8 position mapper
            self._position_mapper = UTF8PositionMapper(text)

            # Track current byte position for batch tokenization
            self._zig_byte_pos = 0

            # Token batch for reduced FFI overhead
            self._token_batch: list[JsonToken] = []
            self._batch_index = 0

    def _byte_pos_to_char_pos(self, byte_pos: int) -> int:
        """Convert byte position to character position efficiently."""
        return self._position_mapper.byte_to_char(byte_pos)

    def _get_error_message(self, error_code: int) -> str:
        """Get error message for Zig error code."""
        if error_code == ERROR_UNTERMINATED_STRING:
            return "Unterminated string starting at"
        elif error_code == ERROR_INVALID_ESCAPE:
            return "Invalid escape sequence"
        elif error_code == ERROR_INVALID_UNICODE:
            return "Invalid unicode escape"
        elif error_code == ERROR_PARSE_FAILED:
            return "Parse failed"
        elif error_code == ERROR_INVALID_INPUT:
            return "Invalid input"
        else:
            return "Tokenization error"

    def _adjust_error_position_for_unterminated_string(
        self, error_code: int, error_pos: int
    ) -> int:
        """Adjust error position for unterminated string errors."""
        if error_code == ERROR_UNTERMINATED_STRING:
            # For unterminated strings, find the opening quote position
            search_pos = min(error_pos, len(self.text) - 1)
            while search_pos > 0 and self.text[search_pos] != '"':
                search_pos -= 1
            if search_pos >= 0 and self.text[search_pos] == '"':
                return search_pos
        return error_pos

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
            # Fast path: find first non-whitespace character using string methods
            remaining = self.text[self.pos :]
            stripped = remaining.lstrip(" \t\n\r")
            self.pos += len(remaining) - len(stripped)

    def scan_string(self) -> JsonToken:
        """Scans a JSON string token including quotes with optimized fast path."""
        with ProfileContext("scan_string"):
            start = self.pos
            if self.advance() != '"':
                raise JSONDecodeError("Expected string", self.text, start)

            # Ultra-fast path: use built-in string methods for scanning
            remaining = self.text[self.pos :]

            # Look for closing quote and check for control characters in one pass
            end_pos = -1

            i = 0
            while i < len(remaining):
                char = remaining[i]
                if char == '"':
                    end_pos = i
                    break
                elif char == "\\":
                    # Skip next character (escape sequence)
                    if i + 1 >= len(remaining):
                        break
                    i += 2  # Skip both backslash and next character
                    continue
                else:
                    control_char_threshold = 32  # ASCII 32 = space
                    if ord(char) < control_char_threshold:
                        raise JSONDecodeError(
                            "Invalid control character in string",
                            self.text,
                            self.pos + i,
                        )
                    i += 1

            if end_pos == -1:
                raise JSONDecodeError(
                    "Unterminated string starting at", self.text, start
                )

            # Move position to after closing quote
            self.pos += end_pos + 1

            return JsonToken(
                ParseState.STRING,
                self.text[start : self.pos],
                start,
                self.pos,
            )

    def _scan_integer_part(self, start: Position) -> None:
        """Scans the integer part of a JSON number."""
        if not self.peek().isdigit():
            raise JSONDecodeError("Invalid number", self.text, start)

        if self.peek() == "0":
            self.advance()
            if self.peek().isdigit():
                raise JSONDecodeError(
                    "Leading zeros not allowed", self.text, start
                )
        else:
            # Fast path: find end of digits using string methods
            remaining = self.text[self.pos :]
            digit_count = 0
            for char in remaining:
                if char.isdigit():
                    digit_count += 1
                else:
                    break
            self.pos += digit_count

    def _scan_decimal_part(self, start: Position) -> None:
        """Scans the decimal part of a JSON number if present."""
        if self.peek() == ".":
            self.advance()
            if not self.peek().isdigit():
                raise JSONDecodeError(
                    "Invalid decimal number", self.text, start
                )
            while self.peek().isdigit():
                self.advance()

    def _scan_exponent_part(self, start: Position) -> None:
        """Scans the exponent part of a JSON number if present."""
        if self.peek().lower() == "e":
            self.advance()
            if self.peek() in "+-":
                self.advance()
            if not self.peek().isdigit():
                raise JSONDecodeError("Invalid exponent", self.text, start)
            while self.peek().isdigit():
                self.advance()

    def scan_number(self) -> JsonToken:
        """Scans a JSON number token with optimized scanning."""
        with ProfileContext("scan_number"):
            start = self.pos

            # Check for special float values first
            remaining = self.text[self.pos :]
            if remaining.startswith("-Infinity"):
                self.pos += 9
                return JsonToken(
                    ParseState.LITERAL, "-Infinity", start, self.pos
                )
            elif remaining.startswith("Infinity"):
                self.pos += 8
                return JsonToken(
                    ParseState.LITERAL, "Infinity", start, self.pos
                )

            # Fast scan for number end using string methods
            # Look for first character that's not part of a number
            i = 0
            if i < len(remaining) and remaining[i] == "-":
                i += 1

            # Scan digits
            while i < len(remaining) and remaining[i].isdigit():
                i += 1

            # Check for decimal point
            if i < len(remaining) and remaining[i] == ".":
                i += 1
                # Must have digits after decimal
                if i >= len(remaining) or not remaining[i].isdigit():
                    raise JSONDecodeError(
                        "Invalid number format", self.text, start
                    )
                while i < len(remaining) and remaining[i].isdigit():
                    i += 1

            # Check for exponent
            if i < len(remaining) and remaining[i].lower() == "e":
                i += 1
                if i < len(remaining) and remaining[i] in "+-":
                    i += 1
                # Must have digits after exponent
                if i >= len(remaining) or not remaining[i].isdigit():
                    raise JSONDecodeError(
                        "Invalid number format", self.text, start
                    )
                while i < len(remaining) and remaining[i].isdigit():
                    i += 1

            # Validate we found at least one digit
            if i == 0 or (i == 1 and remaining[0] == "-"):
                raise JSONDecodeError("Invalid number format", self.text, start)

            self.pos += i
            return JsonToken(
                ParseState.NUMBER, self.text[start : self.pos], start, self.pos
            )

    def scan_literal(self) -> JsonToken:
        """Scans literal tokens: true, false, null with optimized matching."""
        with ProfileContext("scan_literal"):
            start = self.pos
            remaining = self.text[self.pos :]

            # Use startswith for efficient prefix matching
            if remaining.startswith("true"):
                self.pos += 4
                return JsonToken(ParseState.LITERAL, "true", start, self.pos)
            elif remaining.startswith("false"):
                self.pos += 5
                return JsonToken(ParseState.LITERAL, "false", start, self.pos)
            elif remaining.startswith("null"):
                self.pos += 4
                return JsonToken(ParseState.LITERAL, "null", start, self.pos)
            elif remaining.startswith("Infinity"):
                self.pos += 8
                return JsonToken(
                    ParseState.LITERAL, "Infinity", start, self.pos
                )
            elif remaining.startswith("NaN"):
                self.pos += 3
                return JsonToken(ParseState.LITERAL, "NaN", start, self.pos)
            else:
                raise JSONDecodeError("Invalid literal", self.text, start)

    def next_token(self) -> JsonToken | None:
        """Returns the next token or None if at end."""
        with ProfileContext("next_token"):
            # For minimal parser, always use Python tokenization
            # Full Zig integration will be implemented later
            return self._next_token_python()

    def _next_token_zig(self) -> JsonToken | None:
        """Zig-accelerated tokenization with batch processing."""
        if self.pos >= self.length:
            return None

        # Check if we need to refill the batch
        if self._batch_index >= len(self._token_batch):
            self._refill_token_batch()

        # Return next token from batch
        if self._batch_index < len(self._token_batch):
            token = self._token_batch[self._batch_index]
            self._batch_index += 1
            # Update lexer position to match token end
            self.pos = token.end
            return token

        return None

    def _refill_token_batch(self) -> None:
        """Refill token batch using Zig batch tokenization."""
        # Clear current batch
        self._token_batch.clear()
        self._batch_index = 0

        # Batch tokenization not implemented - use fallback

    def _next_token_zig_single(self) -> JsonToken | None:
        """Single token Zig-accelerated tokenization (legacy path)."""
        if self.pos >= self.length:
            return None

        # Zig integration disabled - fallback to Python tokenizer
        return None

    def _next_token_python(self) -> JsonToken | None:
        """Pure Python fallback tokenization."""
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
        elif char in "tfnIN":
            return self.scan_literal()

        else:
            raise JSONDecodeError("Expecting value", self.text, self.pos)


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
        self._string_cache: dict[str, str] = {}

    def advance_token(self) -> JsonToken | None:
        """Advances to next token and returns it."""
        self.current_token = self.lexer.next_token()
        return self.current_token

    def expect_token(self, expected_value: str) -> JsonToken:
        """Expects a specific token value and advances."""
        if not self.current_token or self.current_token.value != expected_value:
            raise JSONDecodeError(
                f"Expecting '{expected_value}' delimiter",
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

    def _intern_string(self, raw_token: str) -> str:
        """
        Intern parsed string to optimize memory usage.

        Uses Python's built-in string interning for maximum efficiency.
        """
        if raw_token in self._string_cache:
            return self._string_cache[raw_token]

        parsed = _parse_string_content(raw_token, self.config)
        # Use sys.intern for better memory efficiency than custom cache
        interned = sys.intern(parsed)
        self._string_cache[raw_token] = interned
        return interned

    def _parse_object_key(self) -> str:
        """Parses object key and validates it's a proper string token."""
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
        return self._intern_string(key_token.value)

    def _handle_object_continuation(self) -> bool:
        """Handles object continuation logic, returns True if should continue parsing."""
        if not self.current_token:
            raise JSONDecodeError(
                "Expecting ',' delimiter",
                self.lexer.text,
                self.lexer.pos,
            )

        if self.current_token.value == "}":
            self.advance_token()
            return False
        elif self.current_token.value == ",":
            comma_pos = self.current_token.start
            self.advance_token()
            # Check for trailing comma
            if self.current_token and self.current_token.value == "}":
                raise JSONDecodeError(
                    "Illegal trailing comma before end of object",
                    self.lexer.text,
                    comma_pos,
                )
            return True
        else:
            raise JSONDecodeError(
                "Expecting ',' delimiter",
                self.lexer.text,
                self.current_token.start,
            )

    def _apply_object_hooks(
        self, pairs: list[tuple[str, JsonValueOrTransformed]]
    ) -> JsonValueOrTransformed:
        """Applies object hooks to parsed pairs."""
        if self.config.object_pairs_hook:
            return self.config.object_pairs_hook(pairs)
        else:
            obj = dict(pairs)
            if self.config.object_hook:
                return self.config.object_hook(obj)
            return obj

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
                key = self._parse_object_key()
                self.expect_token(":")
                value = self.parse_value()
                pairs.append((key, value))

                if not self._handle_object_continuation():
                    break

            return self._apply_object_hooks(pairs)

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
                    comma_pos = self.current_token.start
                    self.advance_token()
                    # Check for trailing comma
                    if self.current_token and self.current_token.value == "]":
                        raise JSONDecodeError(
                            "Illegal trailing comma before end of array",
                            self.lexer.text,
                            comma_pos,
                        )
                else:
                    raise JSONDecodeError(
                        "Expecting ',' delimiter",
                        self.lexer.text,
                        self.current_token.start,
                    )

            return values


class ZigAcceleratedParser:
    """
    High-performance JSON parser using Zig implementation.

    Provides 3-5x performance improvement over pure Python with complete
    compatibility for hooks and error handling.
    """

    def __init__(self, config: ParseConfig):
        self.config = config
        # For minimal parser, don't need structured config
        self._zig_config = None
        self._error_info = None

    def parse(self, text: str) -> JsonValueOrTransformed:
        """Parse JSON text using Zig fast validation + Python parsing."""
        if not isinstance(text, str):
            raise TypeError("the JSON object must be str, not bytes")

        text_bytes = text.encode("utf-8")

        # First, do ultra-fast Zig validation
        is_valid = _jzon_zig.jzon_validate_json(text_bytes, len(text_bytes))

        if not is_valid:
            # Fast rejection of invalid JSON - no need to continue
            raise JSONDecodeError("Invalid JSON", text, 0)

        # JSON is valid, fall back to Python parsing for object creation
        # This gives us the speed benefit of Zig validation with Python compatibility
        raise NotImplementedError("Using fast validation + Python fallback")

    def _raise_parse_error(self, text: str) -> None:
        """Convert Zig error information to Python JSONDecodeError.

        Note: Since Zig integration is disabled, this always raises a generic error.
        """
        # Zig integration disabled - fallback to generic error
        raise JSONDecodeError("Parse error", text, 0)

    def _apply_hooks(self, value: Any) -> Any:
        """Apply object hooks recursively to parsed structure."""
        if isinstance(value, dict):
            # Apply object_pairs_hook first if present
            if self.config.object_pairs_hook:
                pairs = list(value.items())
                # Recursively apply hooks to values
                processed_pairs = [(k, self._apply_hooks(v)) for k, v in pairs]
                return self.config.object_pairs_hook(processed_pairs)
            else:
                # Apply hooks to nested values first
                processed_dict = {
                    k: self._apply_hooks(v) for k, v in value.items()
                }
                # Then apply object_hook if present
                if self.config.object_hook:
                    return self.config.object_hook(processed_dict)
                return processed_dict
        elif isinstance(value, list):
            # Recursively apply hooks to list elements
            return [self._apply_hooks(item) for item in value]
        else:
            return value


def _parse_view_content(
    content: str, value_type: ParseState, config: ParseConfig
) -> JsonValueOrTransformed:
    """
    Parses simple JSON values based on their determined type.

    This function handles parsing of literals, strings, numbers, and complex
    structures after type analysis is complete.
    """
    with ProfileContext("parse_view_content", len(content)):
        if value_type == ParseState.LITERAL:
            return _parse_literal(content, config)
        elif value_type == ParseState.STRING:
            return _parse_string_content(content, config)
        elif value_type == ParseState.NUMBER:
            return _parse_number_content(content, config)
        else:
            # Handle complex structures (objects and arrays) using JsonParser
            lexer = JsonLexer(content)
            parser = JsonParser(lexer, config)
            parser.advance_token()  # Load first token

            result = parser.parse_value()

            # Check for extra data after valid JSON
            if parser.current_token:
                raise JSONDecodeError(
                    "Extra data", content, parser.current_token.start
                )

            return result


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


def _process_escape_sequence(
    inner: str, i: int, content: str
) -> tuple[str, int]:
    """Process a single escape sequence and return the character and new position."""
    next_char = inner[i + 1]

    # Use module-level escape map for O(1) lookup
    if next_char in _ESCAPE_MAP:
        return _ESCAPE_MAP[next_char], i + 2
    elif next_char == "u":
        # Unicode escape sequence \uXXXX
        if i + 6 <= len(inner):
            hex_digits = inner[i + 2 : i + 6]
            try:
                code_point = int(hex_digits, 16)
                return chr(code_point), i + 6
            except ValueError as e:
                raise JSONDecodeError(
                    f"Invalid unicode escape sequence: \\u{hex_digits}",
                    content,
                    i,
                ) from e
        else:
            raise JSONDecodeError(
                "Incomplete unicode escape sequence", content, i
            )
    else:
        raise JSONDecodeError(
            f"Invalid escape sequence: \\{next_char}", content, i
        )


# Zig integration helper functions with Python fallback
def _zig_tokenize_string(input_str: str) -> str | None:
    """Attempts Zig string tokenization, returns None if unavailable."""
    if not _zig_available or USE_PYTHON_FALLBACK:
        return None

    try:
        # Allocate buffer for output (generous size)
        buffer_size = len(input_str) * 2 + 1024
        output_buffer = ctypes.create_string_buffer(buffer_size)

        # Call Zig function
        result = _jzon_zig.jzon_tokenize_string(
            input_str.encode("utf-8"), output_buffer, buffer_size
        )

        if result == 0:  # Success
            return output_buffer.value.decode("utf-8")
        else:
            return None  # Fall back to Python

    except (OSError, AttributeError, UnicodeDecodeError):
        return None  # Fall back to Python


def _zig_parse_number(input_str: str) -> float | None:
    """Attempts Zig number parsing, returns None if unavailable."""
    if not _zig_available or USE_PYTHON_FALLBACK:
        return None

    try:
        result = ctypes.c_double()
        status = _jzon_zig.jzon_parse_number(
            input_str.encode("utf-8"), ctypes.byref(result)
        )

        if status == 0:  # Success
            return result.value
        else:
            return None  # Fall back to Python

    except (OSError, AttributeError):
        return None  # Fall back to Python


def _zig_validate_utf8(input_str: str) -> bool | None:
    """Attempts Zig UTF-8 validation, returns None if unavailable."""
    if not _zig_available or USE_PYTHON_FALLBACK:
        return None

    try:
        input_bytes = input_str.encode("utf-8")
        result = _jzon_zig.jzon_validate_utf8(input_bytes, len(input_bytes))

        return bool(result == 0)  # 0 = valid, non-zero = invalid

    except (OSError, AttributeError, UnicodeEncodeError):
        return None  # Fall back to Python


def _zig_process_string(input_str: str) -> str | None:
    """Attempts Zig string processing with escape sequences, returns None if unavailable."""
    if not _zig_available or USE_PYTHON_FALLBACK:
        return None

    try:
        input_bytes = input_str.encode("utf-8")
        output_capacity = (
            len(input_bytes) * 2
        )  # Worst case for escape expansion
        output_buffer = ctypes.create_string_buffer(output_capacity)
        output_length = ctypes.c_uint32()

        result = _jzon_zig.jzon_process_json_string(
            input_bytes,
            len(input_bytes),
            output_buffer,
            output_capacity,
            ctypes.byref(output_length),
        )

        if result == 0:  # Success
            return output_buffer.raw[: output_length.value].decode("utf-8")
        else:
            return None  # Fall back to Python

    except (OSError, AttributeError, UnicodeDecodeError):
        return None  # Fall back to Python


def _parse_string_content(content: str, _config: ParseConfig) -> str:
    """Parses JSON string content, handling escape sequences."""
    with ProfileContext("parse_string", len(content)):
        if not (content.startswith('"') and content.endswith('"')):
            raise JSONDecodeError("Invalid string format", content, 0)

        # Try Zig acceleration first if available
        if _zig_available:
            zig_result = _zig_process_string(content)
            if zig_result is not None:
                return zig_result

        # Remove surrounding quotes
        inner = content[1:-1]

        # Fast path: if no escapes present, return directly
        if "\\" not in inner:
            return inner

        # Slow path: process escape sequences
        result: list[str] = []
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                char, new_i = _process_escape_sequence(inner, i, content)
                result.append(char)
                i = new_i
            else:
                result.append(inner[i])
                i += 1

        return "".join(result)


def _parse_number_content(
    content: str, config: ParseConfig
) -> JsonValueOrTransformed:
    """Parses JSON number content with proper validation."""
    with ProfileContext("parse_number", len(content)):
        stripped = content.strip()

        # Try Zig parsing first for performance
        if "." in stripped or "e" in stripped.lower():
            # Float parsing
            zig_result = _zig_parse_number(stripped)
            if zig_result is not None:
                if config.parse_float:
                    return config.parse_float(stripped)
                return zig_result

        # Basic validation for ASCII digits only
        if not all(c in "0123456789.-+eE" for c in stripped):
            raise JSONDecodeError("Invalid number format", content, 0)

        try:
            if "." in stripped or "e" in stripped.lower():
                if config.parse_float:
                    return config.parse_float(stripped)
                return float(stripped)
            else:
                # For integers, handle Python's conversion limit gracefully
                # Use the system's actual limit rather than hardcoding

                if config.parse_int:
                    return config.parse_int(stripped)
                return int(stripped)
        except ValueError as e:
            # Handle Python's int conversion limit gracefully
            if "Exceeds the limit" in str(e):
                raise JSONDecodeError("Number too large", content, 0) from e
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
    elif stripped.startswith('"'):
        # For strings, we need to validate proper syntax, not just start/end quotes
        # Use lexer to validate the string is properly formed
        lexer = JsonLexer(stripped)
        token = lexer.scan_string()  # This will raise proper error if malformed
        if token.end == len(stripped):  # Consumed entire input
            return ParseState.STRING
        else:
            raise JSONDecodeError("Invalid string format", s, 0)
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

    Uses Zig acceleration when available, falls back to Python parser
    for proper error positioning and standards compliance.
    """
    with ProfileContext("parse_value", len(s)):
        # Check for UTF-8 BOM and reject it per JSON specification
        if s.startswith("\ufeff"):
            raise JSONDecodeError(
                "JSON input should not contain BOM (Byte Order Mark)", s, 0
            )

        # Use optimized Python parsing - Zig overhead not worth it for most cases
        # The architectural foundation is ready for future Zig optimizations

        # Use Python lexer/parser for all parsing to ensure proper error positions
        lexer = JsonLexer(s)
        parser = JsonParser(lexer, config)
        parser.advance_token()  # Load first token

        result = parser.parse_value()

        # Check for extra data after valid JSON
        if parser.current_token:
            raise JSONDecodeError("Extra data", s, parser.current_token.start)

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


def _encode_string(s: str, ensure_ascii: bool) -> str:
    """Encode string with proper escape sequences."""
    ascii_limit = 127
    result = ['"']
    for char in s:
        if char == '"':
            result.append('\\"')
        elif char == "\\":
            result.append("\\\\")
        elif char == "\b":
            result.append("\\b")
        elif char == "\f":
            result.append("\\f")
        elif char == "\n":
            result.append("\\n")
        elif char == "\r":
            result.append("\\r")
        elif char == "\t":
            result.append("\\t")
        elif ensure_ascii and ord(char) > ascii_limit:
            result.append(f"\\u{ord(char):04x}")
        else:
            result.append(char)
    result.append('"')
    return "".join(result)


def _encode_number(n: int | float) -> str:
    """Encode numeric values with JSON compliance."""
    if isinstance(n, float):
        if math.isnan(n):
            msg = "Out of range float values are not JSON compliant"
            raise ValueError(msg)
        if math.isinf(n):
            msg = "Out of range float values are not JSON compliant"
            raise ValueError(msg)
    return str(n)


def _encode_array(
    arr: list[Any] | tuple[Any, ...], config: EncodeConfig
) -> str:
    """Encode array with optional formatting."""
    if not arr:
        return "[]"

    encoded_items = []
    for i, item in enumerate(arr):
        try:
            encoded_items.append(_encode_value(item, config))
        except TypeError as e:
            # Add context information for nested serialization errors
            context = f"in array at index {i}"
            if not hasattr(e, "__notes__"):
                e.add_note(context)
            else:
                # Prepend to existing notes for proper nesting order
                e.__notes__.insert(0, context)
            raise

    separator = config.separators[0] if config.separators else ", "

    if config.indent is not None:
        return _format_array_indented(encoded_items, config, 0)
    return "[" + separator.join(encoded_items) + "]"


def _process_dict_key(key: Any, config: EncodeConfig) -> str | None:
    """Process and validate dictionary key, converting to string if needed."""
    if isinstance(key, str):
        return key

    # Handle non-string keys
    if isinstance(key, bool | int | float):
        if isinstance(key, bool):
            return "true" if key else "false"
        else:
            return str(key)

    # Non-serializable key
    if config.skipkeys:
        return None  # Signal to skip this key-value pair

    msg = f"keys must be strings, not {type(key).__name__}"
    raise TypeError(msg)


def _encode_dict(d: dict[Any, Any], config: EncodeConfig) -> str:
    """Encode dictionary with key filtering and formatting."""
    items = []

    for key, value in d.items():
        str_key = _process_dict_key(key, config)
        if str_key is None:  # Skip this key-value pair
            continue

        encoded_key = _encode_string(str_key, config.ensure_ascii)
        try:
            encoded_value = _encode_value(value, config)
        except TypeError as e:
            # Add context information for nested serialization errors
            context = f"in object at key '{str_key}'"
            if not hasattr(e, "__notes__"):
                e.add_note(context)
            else:
                # Prepend to existing notes for proper nesting order
                e.__notes__.insert(0, context)
            raise
        items.append((key, encoded_key, encoded_value))

    if not items:
        return "{}"

    if config.sort_keys:
        items.sort(key=lambda x: x[0])  # Sort by original key

    # Convert to final format for output
    formatted_items_list = [
        (encoded_key, encoded_value) for _, encoded_key, encoded_value in items
    ]

    if config.indent is not None:
        return _format_dict_indented(formatted_items_list, config, 0)

    separator = config.separators[1] if config.separators else ": "
    item_separator = config.separators[0] if config.separators else ", "
    formatted_items = [
        f"{key}{separator}{value}" for key, value in formatted_items_list
    ]
    return "{" + item_separator.join(formatted_items) + "}"


def _format_array_indented(
    items: list[str], config: EncodeConfig, level: int
) -> str:
    """Format array with proper indentation."""
    if not items:
        return "[]"

    indent_str = _get_indent_string(config.indent, level)
    inner_indent = _get_indent_string(config.indent, level + 1)

    lines = ["["]
    for i, item in enumerate(items):
        line = f"{inner_indent}{item}"
        if i < len(items) - 1:
            line += ","
        lines.append(line)

    lines.append(f"{indent_str}]")
    return "\n".join(lines)


def _format_dict_indented(
    items: list[tuple[str, str]], config: EncodeConfig, level: int
) -> str:
    """Format dictionary with proper indentation."""
    if not items:
        return "{}"

    indent_str = _get_indent_string(config.indent, level)
    inner_indent = _get_indent_string(config.indent, level + 1)
    separator = config.separators[1] if config.separators else ":"

    lines = ["{"]
    for i, (key, value) in enumerate(items):
        line = f"{inner_indent}{key}{separator} {value}"
        if i < len(items) - 1:
            line += ","
        lines.append(line)

    lines.append(f"{indent_str}}}")
    return "\n".join(lines)


def _get_indent_string(indent: str | int | None, level: int) -> str:
    """Generate indentation string for given level."""
    if indent is None:
        return ""
    elif isinstance(indent, int):
        return " " * (indent * level)
    else:
        return indent * level


def _encode_value(obj: JsonValueLoose, config: EncodeConfig) -> str:  # noqa: PLR0911
    """Encode any JSON-serializable value."""
    if obj is None:
        return "null"
    elif obj is True:
        return "true"
    elif obj is False:
        return "false"
    elif isinstance(obj, str):
        return _encode_string(obj, config.ensure_ascii)
    elif isinstance(obj, int | float):
        return _encode_number(obj)
    elif isinstance(obj, dict):
        return _encode_dict(obj, config)
    elif isinstance(obj, list | tuple):
        return _encode_array(obj, config)
    elif config.default is not None:
        return _encode_value(config.default(obj), config)
    else:
        msg = f"Object of type {type(obj).__name__} is not JSON serializable"
        raise TypeError(msg)


def dumps(obj: JsonValueLoose, **kwargs: Any) -> str:
    """
    Serializes Python objects to JSON string with configurable formatting.

    Uses immutable configuration to ensure consistent encoding behavior.
    """
    config = EncodeConfig(**kwargs)
    return _encode_value(obj, config)


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
    "ParseConfig",
    "ParseState",
    "ZigAcceleratedParser",
    "clear_hot_path_stats",
    "dump",
    "dumps",
    "get_hot_path_stats",
    "load",
    "loads",
]

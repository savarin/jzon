"""
High-performance JSON parsing and encoding library with Zig extensions.

Provides JSON encoding and decoding functionality compatible with the standard
library json module, with optional Zig acceleration for performance-critical paths.
"""

import dataclasses
from dataclasses import dataclass
from typing import IO
from typing import Any

__version__ = "0.1.0"

# Type aliases for domain concepts
JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]
# More permissive type for internal/test use
JsonValueLoose = Any
type Position = int


@dataclass(frozen=True)
class JSONDecodeError(ValueError):
    """
    Handles JSON parsing failures with precise position and context information.

    Immutable error state containing position, line/column numbers, and surrounding
    context to help users identify and fix JSON syntax issues.
    """

    msg: str
    doc: str = ""
    pos: Position = 0
    lineno: int = dataclasses.field(init=False)
    colno: int = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.msg, str):
            raise TypeError("msg must be a string")
        if not isinstance(self.pos, int) or self.pos < 0:
            raise ValueError("pos must be a non-negative integer")

        # Compute line and column numbers from position
        lineno = self.doc.count("\n", 0, self.pos) + 1 if self.doc else 1
        colno = (
            self.pos - self.doc.rfind("\n", 0, self.pos)
            if self.doc
            else self.pos + 1
        )

        # Use object.__setattr__ to set fields on frozen dataclass
        object.__setattr__(self, "lineno", lineno)
        object.__setattr__(self, "colno", colno)

        # Initialize ValueError with formatted message
        super().__init__(f"{self.msg} at line {lineno}, column {colno}")


@dataclass(frozen=True)
class ParseConfig:
    """
    Configures JSON parsing behavior with immutable settings.

    Centralized configuration for all parsing options including hooks,
    validation settings, and performance optimizations.
    """

    strict: bool = True
    parse_float: Any = None
    parse_int: Any = None
    parse_constant: Any = None
    object_pairs_hook: Any = None
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


def loads(s: str, **kwargs: Any) -> JsonValue:
    """
    Parses JSON string into Python objects with strict standards compliance.

    Validates input type and delegates to parser with immutable configuration.
    """
    if not isinstance(s, str):
        raise TypeError("the JSON object must be str, not bytes")

    _ = ParseConfig(**kwargs)  # Validate config but don't use yet
    raise NotImplementedError("jzon.loads not yet implemented")


def dumps(obj: JsonValueLoose, **kwargs: Any) -> str:  # noqa: ARG001
    """
    Serializes Python objects to JSON string with configurable formatting.

    Uses immutable configuration to ensure consistent encoding behavior.
    """
    _ = EncodeConfig(**kwargs)  # Validate config but don't use yet
    raise NotImplementedError("jzon.dumps not yet implemented")


def load(fp: IO[str], **kwargs: Any) -> JsonValue:
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
    "JSONDecodeError",
    "ParseConfig",
    "dump",
    "dumps",
    "load",
    "loads",
]

"""Optimized UTF-8 position mapping for efficient byte to character conversion."""

from __future__ import annotations

from typing import Final


class UTF8PositionMapper:
    """Efficient UTF-8 position mapping with checkpoint system.

    Instead of building a full position map for the entire document,
    this mapper creates checkpoints at regular intervals and calculates
    positions incrementally from the nearest checkpoint.
    """

    def __init__(self, text: str, checkpoint_interval: int = 256) -> None:
        """Initialize position mapper with checkpoint system.

        Args:
            text: The text to create position mapping for
            checkpoint_interval: Interval between checkpoints (default 256 chars)
        """
        self.text: Final = text
        self.text_bytes: Final = text.encode("utf-8")
        self.checkpoint_interval: Final = checkpoint_interval
        self.checkpoints: dict[int, int] = {}  # byte_pos -> char_pos
        self._is_ascii_only: bool = True

        # Build checkpoints
        self._build_checkpoints()

    def _build_checkpoints(self) -> None:
        """Build checkpoint mapping at regular character intervals."""
        byte_pos = 0

        for char_pos, char in enumerate(self.text):
            # Store checkpoint at intervals
            if char_pos % self.checkpoint_interval == 0:
                self.checkpoints[byte_pos] = char_pos

            # ASCII character limit constant
            ascii_limit = 127

            # Check if non-ASCII
            if ord(char) > ascii_limit:
                self._is_ascii_only = False

            # Advance byte position
            byte_pos += len(char.encode("utf-8"))

        # Always store final position
        self.checkpoints[byte_pos] = len(self.text)

    def byte_to_char(self, byte_pos: int) -> int:
        """Convert byte position to character position efficiently.

        Args:
            byte_pos: Byte position in UTF-8 encoded text

        Returns:
            Character position in original text
        """
        # Fast path for ASCII-only text
        if self._is_ascii_only:
            return byte_pos

        # Find nearest checkpoint at or before byte_pos
        checkpoint_byte = 0
        checkpoint_char = 0

        for check_byte, check_char in self.checkpoints.items():
            if check_byte <= byte_pos:
                if check_byte > checkpoint_byte:
                    checkpoint_byte = check_byte
                    checkpoint_char = check_char
            else:
                break

        # If exact checkpoint match, return directly
        if checkpoint_byte == byte_pos:
            return checkpoint_char

        # Calculate from checkpoint
        current_byte = checkpoint_byte
        current_char = checkpoint_char

        # Walk forward from checkpoint to target position
        while current_byte < byte_pos and current_char < len(self.text):
            char_byte_len = len(self.text[current_char].encode("utf-8"))
            current_byte += char_byte_len
            current_char += 1

        return current_char

    def char_to_byte(self, char_pos: int) -> int:
        """Convert character position to byte position.

        Args:
            char_pos: Character position in original text

        Returns:
            Byte position in UTF-8 encoded text
        """
        # Fast path for ASCII-only text
        if self._is_ascii_only:
            return char_pos

        # Find checkpoint at or before char_pos
        best_checkpoint_byte = 0
        best_checkpoint_char = 0

        # Check if we have exact checkpoint
        checkpoint_char = (
            char_pos // self.checkpoint_interval
        ) * self.checkpoint_interval
        for byte_pos, check_char in self.checkpoints.items():
            if check_char == checkpoint_char:
                best_checkpoint_byte = byte_pos
                best_checkpoint_char = check_char
                break

        # Calculate from checkpoint
        byte_pos = best_checkpoint_byte
        for i in range(best_checkpoint_char, char_pos):
            if i < len(self.text):
                byte_pos += len(self.text[i].encode("utf-8"))

        return byte_pos

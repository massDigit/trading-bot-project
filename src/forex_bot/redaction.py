"""Masking of secrets, session tokens and account identifiers in any output."""

from __future__ import annotations

import re

# Minimum length for a registered value to be masked by substring replacement.
# Shorter values would cause noisy false positives.
_MIN_SECRET_LENGTH = 3

# Header-like patterns, as a safety net for values that were never registered.
_HEADER_PATTERNS = [
    re.compile(r"(?i)(x-ig-api-key|cst|x-security-token|authorization)(\"?\s*[:=]\s*\"?)([^\s\",}]+)"),
    re.compile(r"(?i)(\"password\"\s*:\s*\")([^\"]*)(\")"),
]


class Redactor:
    """Replaces every registered sensitive value with a stable placeholder."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def register(self, label: str, value: str | None) -> None:
        if value and len(value) >= _MIN_SECRET_LENGTH:
            self._values[value] = label

    def register_many(self, values: dict[str, str]) -> None:
        for label, value in values.items():
            self.register(label, value)

    def mask(self, text: str) -> str:
        # Longest first so that a value containing another one is fully masked.
        for value in sorted(self._values, key=len, reverse=True):
            text = text.replace(value, f"[MASQUÉ:{self._values[value]}]")
        text = _HEADER_PATTERNS[0].sub(r"\1\2[MASQUÉ]", text)
        text = _HEADER_PATTERNS[1].sub(r"\1[MASQUÉ]\3", text)
        return text

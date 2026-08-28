"""Shared utility functions."""

from __future__ import annotations


def hex_readable(data: bytes | int, separator: str = " ") -> str:
    """Format bytes or a single int as readable hex."""
    if isinstance(data, int):
        return f"{data:02X}"
    return separator.join(f"{b:02X}" for b in data)

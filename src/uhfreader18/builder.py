# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""UHFReader18 command, response, and heartbeat builders."""

from __future__ import annotations

from .checksum import crc16
from .constants import HEARTBEAT_LENGTH, HEARTBEAT_MARKER


def _require_byte(name: str, value: int) -> None:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must be between 0 and 255")


def build_command_frame(address: int, command: int, data: bytes = b"") -> bytes:
    """Build one command frame with CRC."""
    _require_byte("address", address)
    _require_byte("command", command)
    if len(data) > 251:
        raise ValueError("data cannot exceed 251 bytes")
    payload = bytes([len(data) + 4, address, command]) + data
    return payload + crc16(payload).to_bytes(2, "little")


def build_response_frame(
    reader_address: int,
    command: int,
    status: int,
    data: bytes = b"",
) -> bytes:
    """Build one response-shaped frame with CRC."""
    _require_byte("reader_address", reader_address)
    _require_byte("command", command)
    _require_byte("status", status)
    if len(data) > 250:
        raise ValueError("data cannot exceed 250 bytes")
    payload = bytes([len(data) + 5, reader_address, command, status]) + data
    return payload + crc16(payload).to_bytes(2, "little")


def build_heartbeat() -> bytes:
    """Build the six-byte heartbeat observed from readers."""
    return bytes([HEARTBEAT_MARKER]) + b"\0" * (HEARTBEAT_LENGTH - 1)


def is_heartbeat(data: bytes) -> bool:
    """Return whether data starts with one complete heartbeat."""
    return (
        len(data) >= HEARTBEAT_LENGTH and data[:HEARTBEAT_LENGTH] == build_heartbeat()
    )

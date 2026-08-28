# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""UHFReader18 response-frame models and validation."""

from __future__ import annotations

from dataclasses import dataclass

from .checksum import crc16
from .constants import MIN_FRAME_LENGTH, Command, FrameError, Status


@dataclass(frozen=True)
class Frame:
    """Parsed and CRC-validated response frame."""

    length: int
    reader_address: int
    command: int
    status: int
    data: bytes
    checksum: int

    @property
    def tag(self) -> str:
        """Return opaque report data as uppercase hex without trailing NULs."""
        return self.data.rstrip(b"\0").hex().upper()

    @property
    def command_name(self) -> str:
        try:
            return Command(self.command).name
        except ValueError:
            return f"UNKNOWN(0x{self.command:02X})"

    @property
    def status_name(self) -> str:
        try:
            return Status(self.status).name
        except ValueError:
            return f"UNKNOWN(0x{self.status:02X})"

    def to_bytes(self) -> bytes:
        payload = (
            bytes([self.length, self.reader_address, self.command, self.status])
            + self.data
        )
        return payload + self.checksum.to_bytes(2, "little")

    def hex_readable(self) -> str:
        return self.to_bytes().hex(" ").upper()


@dataclass(frozen=True)
class Heartbeat:
    """Reader heartbeat message."""

    raw: bytes

    def hex_readable(self) -> str:
        return self.raw.hex(" ").upper()


def validate_frame(raw: bytes) -> Frame:
    """Parse one complete response frame and verify length and CRC."""
    if not raw:
        raise FrameError("Empty frame")
    length = raw[0]
    if length < MIN_FRAME_LENGTH:
        raise FrameError(f"Length too small: {length} (minimum {MIN_FRAME_LENGTH})")
    expected = length + 1
    if len(raw) != expected:
        raise FrameError(
            f"Length mismatch: length byte says {length} (total {expected}), "
            f"got {len(raw)} bytes"
        )
    received = int.from_bytes(raw[-2:], "little")
    computed = crc16(raw[:-2])
    if received != computed:
        raise FrameError(
            f"CRC mismatch: received 0x{received:04X}, computed 0x{computed:04X}"
        )
    return Frame(length, raw[1], raw[2], raw[3], raw[4:-2], received)

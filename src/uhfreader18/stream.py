# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""TCP stream reassembly for UHFReader18 response frames."""

from __future__ import annotations

from dataclasses import dataclass, field

from .builder import build_heartbeat
from .constants import HEARTBEAT_LENGTH, HEARTBEAT_MARKER, MIN_FRAME_LENGTH, FrameError
from .frame import Frame, Heartbeat, validate_frame


@dataclass
class ParseResult:
    frames: list[Frame] = field(default_factory=lambda: [])
    heartbeats: list[Heartbeat] = field(default_factory=lambda: [])
    errors: list[str] = field(default_factory=lambda: [])


class StreamBuffer:
    """Accumulate arbitrary TCP chunks and extract complete messages."""

    def __init__(self, *, allowed_readers: set[int] | None = None) -> None:
        self._buffer = bytearray()
        self._allowed_readers = allowed_readers

    @property
    def pending_bytes(self) -> int:
        return len(self._buffer)

    def feed(self, data: bytes) -> ParseResult:
        self._buffer.extend(data)
        result = ParseResult()

        while self._buffer:
            # 0x56 is also a legal response length. Only exact marker is heartbeat.
            # ponytail: partial 0x56 waits for six bytes; timeout remains caller policy.
            if self._buffer[0] == HEARTBEAT_MARKER:
                if len(self._buffer) < HEARTBEAT_LENGTH:
                    break
                if bytes(self._buffer[:HEARTBEAT_LENGTH]) == build_heartbeat():
                    result.heartbeats.append(
                        Heartbeat(bytes(self._buffer[:HEARTBEAT_LENGTH]))
                    )
                    del self._buffer[:HEARTBEAT_LENGTH]
                    continue

            length = self._buffer[0]
            if length < MIN_FRAME_LENGTH:
                result.errors.append(
                    f"Invalid length byte: 0x{length:02X} (too small, discarding byte)"
                )
                del self._buffer[0]
                continue

            total = length + 1
            if len(self._buffer) < total:
                break
            raw = bytes(self._buffer[:total])
            del self._buffer[:total]
            try:
                frame = validate_frame(raw)
            except FrameError as exc:
                result.errors.append(str(exc))
                continue
            if (
                self._allowed_readers is not None
                and frame.reader_address not in self._allowed_readers
            ):
                allowed = ", ".join(
                    f"0x{reader:02X}" for reader in sorted(self._allowed_readers)
                )
                result.errors.append(
                    f"Unknown reader address: 0x{frame.reader_address:02X} "
                    f"(allowed: {allowed})"
                )
                continue
            result.frames.append(frame)

        return result

    def reset(self) -> None:
        self._buffer.clear()

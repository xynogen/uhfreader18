# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Synchronous UHFReader18 command client."""

from __future__ import annotations

import socket
from collections import deque
from dataclasses import dataclass

from .builder import build_command_frame
from .constants import Command, Status
from .frame import Frame, validate_frame
from .stream import StreamBuffer


@dataclass(frozen=True)
class RfidResponse:
    length: int
    address: int
    command: int
    status: int
    data: bytes
    crc: int

    @classmethod
    def from_frame(cls, frame: Frame) -> RfidResponse:
        return cls(
            frame.length,
            frame.reader_address,
            frame.command,
            frame.status,
            frame.data,
            frame.checksum,
        )

    @property
    def ok(self) -> bool:
        return self.status == Status.SUCCESS

    @property
    def status_text(self) -> str:
        try:
            return Status(self.status).name.replace("_", " ").title()
        except ValueError:
            return f"Unknown (0x{self.status:02X})"

    def to_bytes(self) -> bytes:
        return Frame(
            self.length,
            self.address,
            self.command,
            self.status,
            self.data,
            self.crc,
        ).to_bytes()


@dataclass(frozen=True)
class ReaderInfo:
    address: int
    version: str
    reader_type: int
    protocol_type: int
    max_freq: int
    min_freq: int
    power: int
    scan_time: int


def parse_response(raw: bytes) -> RfidResponse:
    """Parse one complete command response."""
    return RfidResponse.from_frame(validate_frame(raw))


class RfidClient:
    """One-command-at-a-time TCP client for a UHFReader18 reader."""

    def __init__(self, ip: str, port: int, timeout: float = 3.0) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._stream = StreamBuffer()
        self._responses: deque[Frame] = deque()

    def connect(self) -> None:
        if self._socket is not None:
            return
        self._socket = socket.create_connection((self.ip, self.port), self.timeout)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._stream.reset()
        self._responses.clear()

    def __enter__(self) -> RfidClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        self.close()

    def _send_command(
        self, address: int, command: int, data: bytes = b""
    ) -> RfidResponse:
        if self._socket is None:
            raise ConnectionError("Not connected; call connect() first")
        self._socket.sendall(build_command_frame(address, command, data))

        # ponytail: hardware supports one command at a time; no request IDs needed.
        while not self._responses:
            chunk = self._socket.recv(4096)
            if not chunk:
                raise ConnectionError("No response from reader")
            parsed = self._stream.feed(chunk)
            if parsed.errors:
                raise ConnectionError(f"Invalid reader response: {parsed.errors[0]}")
            if parsed.heartbeats:
                raise ConnectionError("Unexpected heartbeat while waiting for response")
            self._responses.extend(parsed.frames)

        frame = self._responses.popleft()
        if frame.command != command and not (
            frame.command == 0 and frame.status == Status.ILLEGAL_COMMAND_OR_CRC_ERROR
        ):
            raise ConnectionError(
                f"Unexpected response command 0x{frame.command:02X}; "
                f"expected 0x{command:02X}"
            )
        return RfidResponse.from_frame(frame)

    def get_reader_info(self, adr: int = 0) -> ReaderInfo:
        response = self._send_command(adr, Command.GET_READER_INFO)
        if not response.ok:
            raise RuntimeError(f"Get reader info failed: {response.status_text}")
        data = response.data
        if len(data) < 7:
            raise ValueError(f"Unexpected info response length: {len(data)} bytes")
        return ReaderInfo(
            response.address,
            f"{data[0]}.{data[1]}",
            data[2],
            data[3],
            data[4],
            data[5],
            data[6],
            data[7] if len(data) > 7 else 0,
        )

    def discover_address(self) -> tuple[ReaderInfo, int]:
        try:
            info = self.get_reader_info(0xFF)
        except (TimeoutError, ConnectionError) as exc:
            raise ConnectionError(
                "Reader did not respond to broadcast; check power and serial wiring"
            ) from exc
        return info, info.address

    def set_address(self, current_adr: int, new_adr: int) -> RfidResponse:
        if not 0 <= new_adr <= 0xFE:
            raise ValueError(f"Address must be 0x00-0xFE, got 0x{new_adr:02X}")
        response = self._send_command(
            current_adr, Command.SET_ADDRESS, bytes([new_adr])
        )
        if not response.ok:
            raise RuntimeError(f"Set address failed: {response.status_text}")
        return response

    def set_power(self, adr: int, power: int) -> RfidResponse:
        if not 0 <= power <= 30:
            raise ValueError(f"Power must be 0-30, got {power}")
        response = self._send_command(adr, Command.SET_POWER, bytes([power]))
        if not response.ok:
            raise RuntimeError(f"Set power failed: {response.status_text}")
        return response

    def set_scan_time(self, adr: int, scan_time: int) -> RfidResponse:
        if not 0 <= scan_time <= 255:
            raise ValueError(f"Scan time must be 0-255, got {scan_time}")
        response = self._send_command(adr, Command.SET_SCAN_TIME, bytes([scan_time]))
        if not response.ok:
            raise RuntimeError(f"Set scan time failed: {response.status_text}")
        return response

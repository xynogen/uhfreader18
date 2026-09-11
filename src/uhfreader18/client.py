# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Synchronous UHFReader18 command client."""

from __future__ import annotations

import socket
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TypeVar

from .builder import build_command_frame
from .constants import (
    Command,
    FreqBand,
    MemInven,
    ModeState,
    Protocol,
    ReaderBaudRate,
    ReaderType,
    Status,
    WiegandFormat,
    WorkMode,
)
from .frame import RfidResponse, validate_frame
from .stream import StreamBuffer


@dataclass(frozen=True)
class ReaderInfo:
    """Decoded Get Reader Info (0x21). Built via :meth:`from_bytes`.

    ``reader_model`` / ``band`` are ``None`` when the firmware reports a code
    this library does not know; the raw byte is kept in ``raw`` for debugging.
    """

    address: int
    version: str
    reader_model: ReaderType | None
    protocols: Protocol
    band: FreqBand | None
    max_index: int
    min_index: int
    power: int
    scan_time: int
    raw: bytes = field(repr=False, compare=False)

    @classmethod
    def from_bytes(cls, address: int, data: bytes) -> ReaderInfo:
        if len(data) < 7:
            raise ValueError(f"Unexpected info response length: {len(data)} bytes")
        band, max_index, min_index = FreqBand.unpack(data[4], data[5])
        return cls(
            address=address,
            version=f"{data[0]}.{data[1]}",
            reader_model=_enum_or_none(ReaderType, data[2]),
            protocols=Protocol(data[3] & 0b11),
            band=band,
            max_index=max_index,
            min_index=min_index,
            power=data[6],
            scan_time=data[7] if len(data) > 7 else 0,
            raw=data,
        )


@dataclass(frozen=True)
class WorkModeInfo:
    """Decoded Get WorkMode (0x36). Built via :meth:`from_bytes`.

    Field names and types mirror :meth:`RfidClient.set_work_mode` and
    :meth:`RfidClient.set_wiegand` so a value read back can be passed
    straight into the setter.
    """

    wiegand_format: WiegandFormat
    wg_data_interval: int
    wg_pulse_width: int
    wg_pulse_interval: int
    work_mode: WorkMode
    state: ModeState
    mem_inven: MemInven | None
    first_adr: int
    word_num: int
    tag_time: int
    eas_accuracy: int
    syris_offset: int
    raw: bytes = field(repr=False, compare=False)

    @classmethod
    def from_bytes(cls, data: bytes) -> WorkModeInfo:
        if len(data) < 12:
            raise ValueError(f"Unexpected work-mode response length: {len(data)} bytes")
        return cls(
            wiegand_format=WiegandFormat(data[0] & 0b11),
            wg_data_interval=data[1],
            wg_pulse_width=data[2],
            wg_pulse_interval=data[3],
            work_mode=WorkMode(data[4] & 0b11),
            state=ModeState(data[5] & 0b1_1111),
            mem_inven=_enum_or_none(MemInven, data[6]),
            first_adr=data[7],
            word_num=data[8],
            tag_time=data[9],
            eas_accuracy=data[10],
            syris_offset=data[11],
            raw=data,
        )


def parse_response(raw: bytes) -> RfidResponse:
    """Parse one complete command response."""
    return validate_frame(raw)


# ── input validation (the boundary between business code and the wire) ──

_E = TypeVar("_E", bound=IntEnum)


def _enum_or_none(kind: type[_E], code: int) -> _E | None:
    """Lenient decode for values *received*: unknown firmware code -> None."""
    try:
        return kind(code)
    except ValueError:
        return None


def _require(value: object, kind: type, name: str) -> None:
    """Strict check for values *sent*: reject a bare int where an enum is due.

    Annotations are not enforced at runtime; an untyped caller could pass ``6``
    for a ``ReaderBaudRate`` and it would serialize fine. Fail loudly instead.
    """
    if not isinstance(value, kind):
        raise TypeError(f"{name} must be {kind.__name__}, got {value!r}")


def _require_range(value: object, lo: int, hi: int, name: str) -> None:
    """Strict check for numeric values *sent*: must be a real int in range.

    ``bool`` is excluded on purpose: ``set_power(adr, True)`` is a bug, not 1.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {value!r}")
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be {lo}-{hi}, got {value}")


def _require_address(adr: int) -> None:
    """0x00-0xFE addresses a reader; 0xFF is the broadcast address."""
    _require_range(adr, 0x00, 0xFF, "adr")


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
        self._responses: deque[RfidResponse] = deque()

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
        self, address: int, command: Command, data: bytes = b""
    ) -> RfidResponse:
        if self._socket is None:
            raise ConnectionError("Not connected; call connect() first")
        # Last gate before the wire: every public method validates its own
        # parameters, but the frame itself is checked here regardless.
        _require_address(address)
        _require(command, Command, "command")
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
        return frame

    def _run(
        self, adr: int, command: Command, data: bytes = b"", *, action: str
    ) -> RfidResponse:
        """Send a command and raise ``RuntimeError`` unless the reader reports OK."""
        response = self._send_command(adr, command, data)
        if not response.ok:
            raise RuntimeError(f"{action} failed: {response.status_text}")
        return response

    def get_reader_info(self, adr: int = 0) -> ReaderInfo:
        response = self._run(adr, Command.GET_READER_INFO, action="Get reader info")
        return ReaderInfo.from_bytes(response.reader_address, response.data)

    def discover_address(self) -> tuple[ReaderInfo, int]:
        try:
            info = self.get_reader_info(0xFF)
        except (TimeoutError, ConnectionError) as exc:
            raise ConnectionError(
                "Reader did not respond to broadcast; check power and serial wiring"
            ) from exc
        return info, info.address

    def set_address(self, current_adr: int, new_adr: int) -> RfidResponse:
        """Change reader address (0x24). 0xFF is reserved for broadcast."""
        _require_range(new_adr, 0x00, 0xFE, "new_adr")
        return self._run(
            current_adr, Command.SET_ADDRESS, bytes([new_adr]), action="Set address"
        )

    def set_power(self, adr: int, power: int) -> RfidResponse:
        """Set RF output power (0x2F), 0-30 dBm."""
        _require_range(power, 0, 30, "power")
        return self._run(adr, Command.SET_POWER, bytes([power]), action="Set power")

    def set_scan_time(self, adr: int, scan_time: int) -> RfidResponse:
        """Set inventory scan time (0x25), 3-255 x 100 ms (manual 8.4.4)."""
        _require_range(scan_time, 3, 255, "scan_time")
        return self._run(
            adr, Command.SET_SCAN_TIME, bytes([scan_time]), action="Set scan time"
        )

    def set_region(
        self, adr: int, band: FreqBand, max_index: int, min_index: int
    ) -> RfidResponse:
        """Set frequency band (0x22): *band* plus the max/min channel index.
        The valid index range depends on the band (``band.max_index``); see
        manual 8.4.2 for the frequency formula."""
        _require(band, FreqBand, "band")
        _require_range(max_index, 0, band.max_index, "max_index")
        _require_range(min_index, 0, band.max_index, "min_index")
        if min_index > max_index:
            raise ValueError(f"min_index {min_index} exceeds max_index {max_index}")
        return self._run(
            adr,
            Command.SET_REGION,
            band.pack(max_index, min_index),
            action="Set region",
        )

    def set_baud_rate(self, adr: int, baud: ReaderBaudRate) -> RfidResponse:
        """Set serial baud rate (0x28). Nonvolatile; the response arrives at
        the OLD rate, the next command must use the new one."""
        _require(baud, ReaderBaudRate, "baud")
        return self._run(
            adr, Command.SET_BAUD_RATE, bytes([baud]), action="Set baud rate"
        )

    def acousto_optic_control(
        self, adr: int, active_t: int, silent_t: int, times: int
    ) -> RfidResponse:
        """LED/buzzer control (0x33). active_t/silent_t in units of 50ms,
        times = repeat count. All 0-255."""
        _require_range(active_t, 0, 0xFF, "active_t")
        _require_range(silent_t, 0, 0xFF, "silent_t")
        _require_range(times, 0, 0xFF, "times")
        return self._run(
            adr,
            Command.ACOUSTO_OPTIC_CONTROL,
            bytes([active_t, silent_t, times]),
            action="Acousto-optic control",
        )

    def set_wiegand(
        self,
        adr: int,
        wg_format: WiegandFormat,
        data_interval: int,
        pulse_width: int,
        pulse_interval: int,
    ) -> RfidResponse:
        """Configure Wiegand output (0x34), manual 8.4.8.
        data_interval 0-255 x10ms, pulse_width 1-255 x10us,
        pulse_interval 1-255 x100us."""
        _require(wg_format, WiegandFormat, "wg_format")
        _require_range(data_interval, 0, 0xFF, "data_interval")
        _require_range(pulse_width, 1, 0xFF, "pulse_width")
        _require_range(pulse_interval, 1, 0xFF, "pulse_interval")
        return self._run(
            adr,
            Command.SET_WIEGAND,
            bytes([wg_format, data_interval, pulse_width, pulse_interval]),
            action="Set Wiegand",
        )

    def set_work_mode(
        self,
        adr: int,
        work_mode: WorkMode,
        state: ModeState,
        mem_inven: MemInven,
        first_adr: int,
        word_num: int,
        tag_time: int,
    ) -> RfidResponse:
        """Set work mode (0x35), manual 8.4.9. Nonvolatile. WARNING:
        Scan/Trigger mode makes the reader respond only to reader-defined
        commands and auto-push tags. word_num 1-32 (1-4 in Syris485 mode),
        first_adr 0-255, tag_time 0-255 x1s."""
        _require(work_mode, WorkMode, "work_mode")
        _require(state, ModeState, "state")
        _require(mem_inven, MemInven, "mem_inven")
        _require_range(first_adr, 0, 0xFF, "first_adr")
        word_max = 4 if ModeState.SYRIS_485 in state else 32
        _require_range(word_num, 1, word_max, "word_num")
        _require_range(tag_time, 0, 0xFF, "tag_time")
        params = bytes([work_mode, state, mem_inven, first_adr, word_num, tag_time])
        return self._run(adr, Command.SET_WORK_MODE, params, action="Set work mode")

    def get_work_mode(self, adr: int = 0) -> WorkModeInfo:
        """Read Wiegand + work-mode parameters (0x36)."""
        response = self._run(adr, Command.GET_WORK_MODE, action="Get work mode")
        return WorkModeInfo.from_bytes(response.data)

    def set_eas_accuracy(self, adr: int, accuracy: int) -> RfidResponse:
        """Set EAS alarm accuracy (0x37), range 0-8, default 8."""
        _require_range(accuracy, 0, 8, "accuracy")
        return self._run(
            adr, Command.SET_EAS_ACCURACY, bytes([accuracy]), action="Set EAS accuracy"
        )

    def set_syris_response_offset(self, adr: int, offset_ms: int) -> RfidResponse:
        """Set Syris485 response offset (0x38), (0-100) x1ms, default 0."""
        _require_range(offset_ms, 0, 100, "offset_ms")
        return self._run(
            adr,
            Command.SYRIS_RESPONSE_OFFSET,
            bytes([offset_ms]),
            action="Set Syris offset",
        )

    def set_trigger_offset(self, adr: int, trigger_s: int) -> RfidResponse:
        """Set trigger offset (0x3B), (0-254) x1s; 255 queries current value.
        Firmware V2.36+ only."""
        _require_range(trigger_s, 0, 0xFF, "trigger_s")
        return self._run(
            adr, Command.TRIGGER_OFFSET, bytes([trigger_s]), action="Set trigger offset"
        )

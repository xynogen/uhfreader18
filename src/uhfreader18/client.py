# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Synchronous UHFReader18 command client."""

from __future__ import annotations

import socket
from collections import deque
from dataclasses import dataclass

from .builder import build_command_frame
from .constants import (
    Command,
    FreqBand,
    MemInven,
    ModeState,
    Protocol,
    ReaderType,
    Status,
    WiegandFormat,
    WorkMode,
)
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

    @property
    def reader_model(self) -> ReaderType | None:
        """Decoded reader model, or None if the type byte is unknown."""
        try:
            return ReaderType(self.reader_type)
        except ValueError:
            return None

    @property
    def protocols(self) -> Protocol:
        """Supported air-interface protocols decoded from the protocol byte."""
        return Protocol(self.protocol_type & 0b11)

    @property
    def max_band(self) -> FreqBand:
        """Frequency band of the maximum frequency (bit7-6)."""
        return FreqBand(self.max_freq >> 6)

    @property
    def min_band(self) -> FreqBand:
        """Frequency band of the minimum frequency (bit7-6)."""
        return FreqBand(self.min_freq >> 6)

    @property
    def max_freq_index(self) -> int:
        """Frequency channel index of the maximum frequency (bit5-0)."""
        return self.max_freq & 0b111111

    @property
    def min_freq_index(self) -> int:
        """Frequency channel index of the minimum frequency (bit5-0)."""
        return self.min_freq & 0b111111


@dataclass(frozen=True)
class WorkModeInfo:
    """Decoded response of Get WorkMode (0x36): Wiegand + work-mode params."""

    wg_mode: int
    wg_data_interval: int
    wg_pulse_width: int
    wg_pulse_interval: int
    read_mode: int
    mode_state: int
    mem_inven: int
    first_adr: int
    word_num: int
    tag_time: int
    eas_accuracy: int
    syris_offset: int

    @property
    def work_mode(self) -> WorkMode:
        """Reader work mode decoded from read_mode bit1-0."""
        return WorkMode(self.read_mode & 0b11)

    @property
    def wiegand_format(self) -> WiegandFormat:
        """Wiegand format flags decoded from wg_mode."""
        return WiegandFormat(self.wg_mode & 0b11)

    @property
    def state_flags(self) -> ModeState:
        """Work-mode state flags decoded from mode_state."""
        return ModeState(self.mode_state & 0b1_1111)

    @property
    def mem_target(self) -> MemInven | None:
        """Memory/inventory target from mem_inven, or None if out of range."""
        try:
            return MemInven(self.mem_inven)
        except ValueError:
            return None


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

    def set_region(self, adr: int, max_fre: int, min_fre: int) -> RfidResponse:
        """Set frequency band (0x22). max_fre/min_fre pack band in bit7-6 and
        the frequency index in bit5-0; see manual 8.4.2. Raw bytes, 0-255."""
        for name, val in (("max_fre", max_fre), ("min_fre", min_fre)):
            if not 0 <= val <= 0xFF:
                raise ValueError(f"{name} must be 0-255, got {val}")
        response = self._send_command(
            adr, Command.SET_REGION, bytes([max_fre, min_fre])
        )
        if not response.ok:
            raise RuntimeError(f"Set region failed: {response.status_text}")
        return response

    def set_baud_rate(self, adr: int, baud_code: int) -> RfidResponse:
        """Set serial baud rate (0x28). Codes: 0=9600 1=19200 2=38400
        5=57600 6=115200. Nonvolatile; response uses the OLD rate, the next
        command must use the new rate."""
        if baud_code not in (0, 1, 2, 5, 6):
            raise ValueError(f"baud_code must be one of 0,1,2,5,6, got {baud_code}")
        response = self._send_command(adr, Command.SET_BAUD_RATE, bytes([baud_code]))
        if not response.ok:
            raise RuntimeError(f"Set baud rate failed: {response.status_text}")
        return response

    def acousto_optic_control(
        self, adr: int, active_t: int, silent_t: int, times: int
    ) -> RfidResponse:
        """LED/buzzer control (0x33). active_t/silent_t in units of 50ms,
        times = repeat count. All 0-255."""
        for name, val in (
            ("active_t", active_t),
            ("silent_t", silent_t),
            ("times", times),
        ):
            if not 0 <= val <= 0xFF:
                raise ValueError(f"{name} must be 0-255, got {val}")
        response = self._send_command(
            adr, Command.ACOUSTO_OPTIC_CONTROL, bytes([active_t, silent_t, times])
        )
        if not response.ok:
            raise RuntimeError(f"Acousto-optic control failed: {response.status_text}")
        return response

    def set_wiegand(
        self,
        adr: int,
        wg_mode: int,
        data_interval: int,
        pulse_width: int,
        pulse_interval: int,
    ) -> RfidResponse:
        """Configure Wiegand output (0x34). See manual 8.4.8 for bit meanings.
        data_interval x10ms, pulse_width x10us, pulse_interval x100us."""
        for name, val in (
            ("wg_mode", wg_mode),
            ("data_interval", data_interval),
            ("pulse_width", pulse_width),
            ("pulse_interval", pulse_interval),
        ):
            if not 0 <= val <= 0xFF:
                raise ValueError(f"{name} must be 0-255, got {val}")
        response = self._send_command(
            adr,
            Command.SET_WIEGAND,
            bytes([wg_mode, data_interval, pulse_width, pulse_interval]),
        )
        if not response.ok:
            raise RuntimeError(f"Set Wiegand failed: {response.status_text}")
        return response

    def set_work_mode(
        self,
        adr: int,
        read_mode: int,
        mode_state: int,
        mem_inven: int,
        first_adr: int,
        word_num: int,
        tag_time: int,
    ) -> RfidResponse:
        """Set work mode (0x35). read_mode bit1-0: 0=Answer 1=Scan
        2=Trigger(Low) 3=Trigger(High). Nonvolatile. WARNING: Scan/Trigger
        mode makes the reader respond only to reader-defined commands and
        auto-push tags; see manual 8.4.9."""
        params = (read_mode, mode_state, mem_inven, first_adr, word_num, tag_time)
        for name, val in zip(
            (
                "read_mode",
                "mode_state",
                "mem_inven",
                "first_adr",
                "word_num",
                "tag_time",
            ),
            params,
            strict=True,
        ):
            if not 0 <= val <= 0xFF:
                raise ValueError(f"{name} must be 0-255, got {val}")
        response = self._send_command(adr, Command.SET_WORK_MODE, bytes(params))
        if not response.ok:
            raise RuntimeError(f"Set work mode failed: {response.status_text}")
        return response

    def get_work_mode(self, adr: int = 0) -> WorkModeInfo:
        """Read Wiegand + work-mode parameters (0x36)."""
        response = self._send_command(adr, Command.GET_WORK_MODE)
        if not response.ok:
            raise RuntimeError(f"Get work mode failed: {response.status_text}")
        d = response.data
        if len(d) < 12:
            raise ValueError(f"Unexpected work-mode response length: {len(d)} bytes")
        return WorkModeInfo(*d[:12])

    def set_eas_accuracy(self, adr: int, accuracy: int) -> RfidResponse:
        """Set EAS alarm accuracy (0x37), range 0-8, default 8."""
        if not 0 <= accuracy <= 8:
            raise ValueError(f"accuracy must be 0-8, got {accuracy}")
        response = self._send_command(adr, Command.SET_EAS_ACCURACY, bytes([accuracy]))
        if not response.ok:
            raise RuntimeError(f"Set EAS accuracy failed: {response.status_text}")
        return response

    def set_syris_response_offset(self, adr: int, offset_ms: int) -> RfidResponse:
        """Set Syris485 response offset (0x38), (0-100) x1ms, default 0."""
        if not 0 <= offset_ms <= 100:
            raise ValueError(f"offset_ms must be 0-100, got {offset_ms}")
        response = self._send_command(
            adr, Command.SYRIS_RESPONSE_OFFSET, bytes([offset_ms])
        )
        if not response.ok:
            raise RuntimeError(f"Set Syris offset failed: {response.status_text}")
        return response

    def set_trigger_offset(self, adr: int, trigger_s: int) -> RfidResponse:
        """Set trigger offset (0x3B), (0-254) x1s; 255 queries current value.
        Firmware V2.36+ only."""
        if not 0 <= trigger_s <= 255:
            raise ValueError(f"trigger_s must be 0-255, got {trigger_s}")
        response = self._send_command(adr, Command.TRIGGER_OFFSET, bytes([trigger_s]))
        if not response.ok:
            raise RuntimeError(f"Set trigger offset failed: {response.status_text}")
        return response

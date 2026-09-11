"""Protocol constants and enums for the UHFReader18 UHF RFID reader.

Reference: UHFReader18 User's Manual V2.0
"""

from __future__ import annotations

import enum

# Frame markers
HEARTBEAT_MARKER = 0x56
HEARTBEAT_LENGTH = 6

# Minimum remaining bytes: address + command + status + two-byte checksum.
MIN_FRAME_LENGTH = 5

# CRC-16 parameters (from docs C example)
CRC_PRESET = 0xFFFF
CRC_POLYNOMIAL = 0x8408


class Command(enum.IntEnum):
    """Command bytes (Cmd field in command data block).

    EPC C1G2 (ISO 18000-6C) commands: 0x01-0x10
    18000-6B commands: 0x50-0x55
    Reader-defined commands: 0x21-0x3F
    """

    # Scan/Trigger mode output (observed from HW-VX module)
    TAG_REPORT = 0xEE  # not in standard docs, observed in captured frames

    # EPC C1G2 (ISO 18000-6C)
    INVENTORY = 0x01
    READ_DATA = 0x02
    WRITE_DATA = 0x03
    WRITE_EPC = 0x04
    KILL_TAG = 0x05
    LOCK = 0x06
    BLOCK_ERASE = 0x07
    READ_PROTECT = 0x08
    READ_PROTECT_WITHOUT_EPC = 0x09
    RESET_READ_PROTECT = 0x0A
    CHECK_READ_PROTECT = 0x0B
    EAS_ALARM = 0x0C
    CHECK_EAS_ALARM = 0x0D
    BLOCK_LOCK = 0x0E
    INVENTORY_SINGLE = 0x0F
    BLOCK_WRITE = 0x10

    # 18000-6B
    INVENTORY_SIGNAL_6B = 0x50
    INVENTORY_MULTIPLE_6B = 0x51
    READ_DATA_6B = 0x52
    WRITE_DATA_6B = 0x53
    CHECK_LOCK_6B = 0x54
    LOCK_6B = 0x55

    # Reader-defined
    GET_READER_INFO = 0x21
    SET_REGION = 0x22
    SET_ADDRESS = 0x24
    SET_SCAN_TIME = 0x25
    SET_BAUD_RATE = 0x28
    SET_POWER = 0x2F
    ACOUSTO_OPTIC_CONTROL = 0x33
    SET_WIEGAND = 0x34
    SET_WORK_MODE = 0x35
    GET_WORK_MODE = 0x36
    SET_EAS_ACCURACY = 0x37
    SYRIS_RESPONSE_OFFSET = 0x38
    TRIGGER_OFFSET = 0x3B


class Status(enum.IntEnum):
    """Response status bytes (Status field in response data block)."""

    SUCCESS = 0x00
    INVENTORY_DONE_PARTIAL = 0x01  # got some tags before scan time finished
    INVENTORY_TIMEOUT = 0x02  # scan time overflow, partial results
    INVENTORY_MORE_DATA = 0x03  # too many tags, sent in multiple messages
    READER_MODULE_FULL = 0x04  # tag storage capacity exceeded
    ACCESS_PASSWORD_ERROR = 0x05  # wrong password
    KILL_TAG_ERROR = 0x09
    KILL_PASSWORD_ZERO = 0x0A
    TAG_NOT_SUPPORT_COMMAND = 0x0B
    ACCESS_PASSWORD_CANT_BE_ZERO = 0x0C
    TAG_ALREADY_PROTECTED = 0x0D
    TAG_NOT_PROTECTED = 0x0E
    WRITE_FAIL_LOCKED_BYTES_6B = 0x10
    LOCK_FAIL_6B = 0x11
    ALREADY_LOCKED_6B = 0x12
    SAVE_FAIL = 0x13
    CANNOT_ADJUST_POWER = 0x14
    INVENTORY_DONE_PARTIAL_6B = 0x15
    INVENTORY_TIMEOUT_6B = 0x16
    INVENTORY_MORE_DATA_6B = 0x17
    READER_MODULE_FULL_6B = 0x18
    NOT_SUPPORT_OR_ACCESS_PWD = 0x19
    COMMAND_EXECUTE_ERROR = 0xF9
    POOR_COMMUNICATION = 0xFA
    NO_TAG = 0xFB
    TAG_RETURN_ERROR_CODE = 0xFC
    COMMAND_LENGTH_WRONG = 0xFD
    ILLEGAL_COMMAND_OR_CRC_ERROR = 0xFE
    PARAMETER_ERROR = 0xFF


class MemBank(enum.IntEnum):
    """Tag memory bank selection."""

    PASSWORD = 0x00  # Reserved (kill + access passwords)
    EPC = 0x01
    TID = 0x02
    USER = 0x03


class ReaderType(enum.IntEnum):
    """Reader model, from the reader-type byte in Get Reader Info (0x21)."""

    UHFREADER18 = 0x09

    # Py3.11+ makes IntEnum str() return the number; keep the name for readability.
    __str__ = enum.Enum.__str__


class Protocol(enum.IntFlag):
    """Air-interface protocol support (protocol byte, bitfield).

    bit0 = ISO 18000-6B, bit1 = ISO 18000-6C (EPC C1 Gen2).
    """

    ISO18000_6B = 0b01
    ISO18000_6C = 0b10

    __str__ = enum.Enum.__str__


class FreqBand(enum.IntEnum):
    """Frequency band (manual 8.4.2).

    On the wire the band is a 4-bit value split across two bytes: bit3-2 live
    in MaxFre bit7-6, bit1-0 in MinFre bit7-6. Use :meth:`pack` /
    :meth:`unpack`; never assemble those bytes by hand.
    """

    USER = 0b00
    CHINESE_2 = 0b01
    US = 0b10
    KOREAN = 0b11

    @property
    def max_index(self) -> int:
        """Highest valid channel index N for this band (manual 8.4.2)."""
        return _BAND_MAX_INDEX[self]

    def frequency_mhz(self, index: int) -> float:
        """Centre frequency of channel *index* in MHz."""
        if not 0 <= index <= self.max_index:
            raise ValueError(f"{self.name} index must be 0-{self.max_index}")
        base, step = _BAND_FORMULA[self]
        return round(base + index * step, 3)

    def pack(self, max_index: int, min_index: int) -> bytes:
        """Encode (MaxFre, MinFre) bytes for Set Region / Get Reader Info."""
        hi, lo = self >> 2, self & 0b11
        return bytes([hi << 6 | max_index, lo << 6 | min_index])

    @classmethod
    def unpack(cls, max_fre: int, min_fre: int) -> tuple[FreqBand | None, int, int]:
        """Decode (band, max_index, min_index); band is None for RFU codes."""
        code = (max_fre >> 6) << 2 | (min_fre >> 6)
        try:
            band = cls(code)
        except ValueError:
            band = None
        return band, max_fre & 0b111111, min_fre & 0b111111

    __str__ = enum.Enum.__str__


_BAND_MAX_INDEX = {
    FreqBand.USER: 62,
    FreqBand.CHINESE_2: 19,
    FreqBand.US: 49,
    FreqBand.KOREAN: 31,
}
# (base MHz, step MHz): Fs = base + N * step
_BAND_FORMULA = {
    FreqBand.USER: (902.6, 0.4),
    FreqBand.CHINESE_2: (920.125, 0.25),
    FreqBand.US: (902.75, 0.5),
    FreqBand.KOREAN: (917.1, 0.2),
}


class WorkMode(enum.IntEnum):
    """Reader work mode, from read_mode bit1-0 (Get WorkMode 0x36).

    In Answer mode the reader replies to commands; Scan/Trigger modes push
    tags autonomously and stop responding to normal commands.
    """

    ANSWER = 0b00
    SCAN = 0b01
    TRIGGER_LOW = 0b10
    TRIGGER_HIGH = 0b11

    __str__ = enum.Enum.__str__


class WiegandFormat(enum.IntFlag):
    """Wiegand output config, from wg_mode (Set/Get Wiegand).

    bit0 = 1 -> 34-bit format (else 26-bit); bit1 = 1 -> low-bit first
    (else high-bit first). Default 0 = 26-bit, high-bit first.
    """

    FORMAT_34BIT = 0b01
    LOW_BIT_FIRST = 0b10

    __str__ = enum.Enum.__str__


class ModeState(enum.IntFlag):
    """Work-mode state flags, from mode_state (Get WorkMode 0x36).

    Each bit toggles one behaviour; an unset bit means the opposite default.
    """

    PROTOCOL_6B = 0b0_0001  # bit0: set = 18000-6B, unset = 18000-6C
    RS_OUTPUT = 0b0_0010  # bit1: set = RS232/RS485, unset = Wiegand
    BEEP_OFF = 0b0_0100  # bit2: set = beep off, unset = beep on
    BYTE_ADDRESS = 0b0_1000  # bit3: set = byte address, unset = word address
    SYRIS_485 = 0b1_0000  # bit4: set = Syris 485 (only when RS_OUTPUT set)

    __str__ = enum.Enum.__str__


class ReaderBaudRate(enum.IntEnum):
    """Serial baud rate of the reader (Set Baud Rate 0x28).

    Codes 3 and 4 are unassigned by the firmware. Distinct from
    ``hwvx.BaudRate``, which configures the TCP/IP module's own UART.
    """

    BAUD_9600 = 0
    BAUD_19200 = 1
    BAUD_38400 = 2
    BAUD_57600 = 5
    BAUD_115200 = 6

    @property
    def bps(self) -> int:
        """The baud rate as bits per second."""
        return _READER_BPS[self]

    __str__ = enum.Enum.__str__


_READER_BPS = {
    ReaderBaudRate.BAUD_9600: 9600,
    ReaderBaudRate.BAUD_19200: 19200,
    ReaderBaudRate.BAUD_38400: 38400,
    ReaderBaudRate.BAUD_57600: 57600,
    ReaderBaudRate.BAUD_115200: 115200,
}


class MemInven(enum.IntEnum):
    """Memory/inventory target for scan/trigger mode, from mem_inven (0x36).

    Valid only when the reader supports 18000-6C.
    """

    PASSWORD = 0x00
    EPC = 0x01
    TID = 0x02
    USER = 0x03
    INVENTORY_MULTIPLE = 0x04
    INVENTORY_SINGLE = 0x05
    EAS_ALARM = 0x06

    __str__ = enum.Enum.__str__


class FrameError(Exception):
    """Raised when a frame fails validation."""

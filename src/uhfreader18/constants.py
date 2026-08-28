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


class FrameError(Exception):
    """Raised when a frame fails validation."""

# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""HW-VX IP module constants and setting enums (UDP config protocol).

These describe the HW-VX6330K / HW-VX6346KL TCP/IP module that bridges the
reader's serial port onto the network, not the RFID air interface.
Values come from the C# Demo v2.11 (Networking.cs + Form1.cs).
"""

from __future__ import annotations

import enum

UDP_PORT: int = 65535
RECV_TIMEOUT: float = 1.0  # seconds
RECV_BUFFER: int = 1024

# Setting codes used by Get (G{code}) / Set (S{code}{value}) commands.
SETTINGS: dict[str, str] = {
    # Network settings
    "ON": "Username",
    "DN": "Device Name",
    "FE": "MAC Address",
    "IP": "IP Address",
    "PN": "Port Number",
    "TP": "Protocol",  # 0=UDP, 1=TCP
    "RM": "Work Mode",  # 0=Server, 1=Client
    "DI": "Remote IP",
    "DP": "Remote Port",
    "GI": "Gateway IP",
    "NM": "Subnet Mask",
    "DH": "DHCP",  # 0=Disabled, 1=Enabled
    # Serial settings
    "BR": "Baud Rate",  # 0=1200 … 7=115200
    "PR": "Parity",  # 0=None … 4=Space
    "BB": "Data Bits",  # 0=7bits, 1=8bits
    "DT": "DTR Mode",  # 0=Disabled, 1=Enabled
    "FC": "RTS",  # 0=Disabled, 1=Enabled
    # Advanced settings
    "CM": "Connection Mode",  # 0=Immediately, 1=Connect-with-data
    "CT": "Connection Timeout",
    "RC": "Reconnect",
    "ML": "Max Length",
    "MD": "Max Delay",
}


class NetProtocol(enum.IntEnum):
    """Transport protocol of the network module (setting code TP)."""

    UDP = 0
    TCP = 1

    __str__ = enum.Enum.__str__


class NetWorkMode(enum.IntEnum):
    """Network module role (setting code RM)."""

    SERVER = 0
    CLIENT = 1

    __str__ = enum.Enum.__str__


class BaudRate(enum.IntEnum):
    """Serial baud rate of the module (setting code BR)."""

    BAUD_1200 = 0
    BAUD_2400 = 1
    BAUD_4800 = 2
    BAUD_9600 = 3
    BAUD_19200 = 4
    BAUD_38400 = 5
    BAUD_57600 = 6
    BAUD_115200 = 7

    @property
    def bps(self) -> int:
        """The baud rate as bits per second."""
        return int(self.name.removeprefix("BAUD_"))

    __str__ = enum.Enum.__str__


class Parity(enum.IntEnum):
    """Serial parity of the module (setting code PR)."""

    NONE = 0
    EVEN = 1
    ODD = 2
    MARK = 3
    SPACE = 4

    __str__ = enum.Enum.__str__


class DataBits(enum.IntEnum):
    """Serial data bits of the module (setting code BB)."""

    SEVEN = 0
    EIGHT = 1

    @property
    def count(self) -> int:
        """Number of data bits."""
        return 7 if self is DataBits.SEVEN else 8

    __str__ = enum.Enum.__str__


class Toggle(enum.IntEnum):
    """Generic disabled/enabled flag (DHCP, DTR, RTS, connection mode)."""

    DISABLED = 0
    ENABLED = 1

    __str__ = enum.Enum.__str__

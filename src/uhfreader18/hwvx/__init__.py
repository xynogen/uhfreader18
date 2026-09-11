# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""HW-VX IP module protocol (UDP config for the reader's network bridge).

This sub-package speaks the HW-VX6330K / HW-VX6346KL setting protocol over
UDP, separate from the RFID air-interface protocol in the top-level package.
"""

from .config import DeviceConfig, SearchResult
from .constants import (
    RECV_BUFFER,
    RECV_TIMEOUT,
    SETTINGS,
    UDP_PORT,
    BaudRate,
    DataBits,
    NetProtocol,
    NetWorkMode,
    Parity,
    Toggle,
)
from .device import HwVxDevice
from .transport import HwVxNetworking

__all__ = [
    "RECV_BUFFER",
    "RECV_TIMEOUT",
    "SETTINGS",
    "UDP_PORT",
    "BaudRate",
    "DataBits",
    "DeviceConfig",
    "HwVxDevice",
    "HwVxNetworking",
    "NetProtocol",
    "NetWorkMode",
    "Parity",
    "SearchResult",
    "Toggle",
]

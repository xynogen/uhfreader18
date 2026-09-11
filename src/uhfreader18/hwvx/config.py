# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Data models for HW-VX search results and device configuration."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, fields

from .constants import BaudRate, DataBits, NetProtocol, NetWorkMode, Parity, Toggle

_PROTOCOL_VALUES = {p.value for p in NetProtocol}
_WORK_MODE_VALUES = {m.value for m in NetWorkMode}
_BAUD_VALUES = {b.value for b in BaudRate}
_PARITY_VALUES = {p.value for p in Parity}
_DATA_BITS_VALUES = {d.value for d in DataBits}
_TOGGLE_VALUES = {t.value for t in Toggle}


@dataclass
class SearchResult:
    """A single device discovered during a broadcast search."""

    mac_address: str = ""
    port_number: str = ""
    ip_address: str = ""
    username: str = ""
    device_name: str = ""


@dataclass
class DeviceConfig:
    """All settings that can be read / written via the UDP protocol."""

    # Network
    username: str = ""
    device_name: str = ""
    mac_address: str = ""
    ip_address: str = ""
    port_number: str = ""
    protocol: str = ""  # NetProtocol value
    work_mode: str = ""  # NetWorkMode value
    remote_ip: str = ""
    remote_port: str = ""
    gateway_ip: str = ""
    subnet_mask: str = ""
    dhcp: str = ""

    # Serial
    baud_rate: str = ""  # BaudRate value
    parity: str = ""  # Parity value
    data_bits: str = ""  # DataBits value
    dtr_mode: str = ""  # Toggle value
    rts: str = ""  # Toggle value

    # Advanced
    connection_mode: str = ""
    connection_timeout: str = ""
    reconnect: str = ""
    max_length: str = ""
    max_delay: str = ""

    def validate(self) -> None:
        """Check every settable field before it is sent on the wire.

        Raises ``ValueError`` listing all problems. Called by
        ``HwVxDevice.save_config`` so a bad config never reaches a device
        that would apply it and reboot.
        """
        errors: list[str] = []

        def check_ip(name: str, value: str) -> None:
            try:
                ipaddress.IPv4Address(value)
            except (ipaddress.AddressValueError, ValueError):
                errors.append(f"{name}: {value!r} is not a valid IPv4 address")

        def as_int(value: str) -> int | None:
            # isdigit() accepts unicode digits like '²' that int() rejects,
            # so parse defensively rather than trusting isdigit() alone.
            try:
                return int(value)
            except ValueError:
                return None

        def check_port(name: str, value: str) -> None:
            n = as_int(value)
            if n is None or not (1 <= n <= 65535):
                errors.append(f"{name}: {value!r} must be 1-65535")

        def check_option(name: str, value: str, valid: set[int]) -> None:
            n = as_int(value)
            if n is None or n not in valid:
                errors.append(f"{name}: {value!r} not in {sorted(valid)}")

        def check_uint(name: str, value: str) -> None:
            n = as_int(value)
            if n is None or n < 0:
                errors.append(f"{name}: {value!r} must be a non-negative integer")

        # `|` is the protocol delimiter and would corrupt the packet framing;
        # non-ASCII cannot be encoded by the transport.
        for f in fields(self):
            v = getattr(self, f.name)
            if "|" in v:
                errors.append(f"{f.name}: {v!r} must not contain '|'")
            if not v.isascii():
                errors.append(f"{f.name}: {v!r} must be ASCII")

        check_ip("ip_address", self.ip_address)
        check_ip("subnet_mask", self.subnet_mask)
        check_ip("gateway_ip", self.gateway_ip)
        check_ip("remote_ip", self.remote_ip)
        check_port("port_number", self.port_number)
        check_port("remote_port", self.remote_port)
        check_option("protocol", self.protocol, _PROTOCOL_VALUES)
        check_option("work_mode", self.work_mode, _WORK_MODE_VALUES)
        check_option("dhcp", self.dhcp, _TOGGLE_VALUES)
        check_option("baud_rate", self.baud_rate, _BAUD_VALUES)
        check_option("parity", self.parity, _PARITY_VALUES)
        check_option("data_bits", self.data_bits, _DATA_BITS_VALUES)
        check_option("dtr_mode", self.dtr_mode, _TOGGLE_VALUES)
        check_option("rts", self.rts, _TOGGLE_VALUES)
        check_option("connection_mode", self.connection_mode, _TOGGLE_VALUES)
        check_uint("connection_timeout", self.connection_timeout)
        check_uint("reconnect", self.reconnect)
        check_uint("max_length", self.max_length)
        check_uint("max_delay", self.max_delay)

        if errors:
            raise ValueError("Invalid configuration:\n  " + "\n  ".join(errors))

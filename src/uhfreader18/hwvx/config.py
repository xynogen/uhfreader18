# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Data models for HW-VX search results and device configuration.

``DeviceConfig`` holds *typed* values (``IPv4Address``, ``int``, enums). The
UDP protocol only carries ASCII strings, so conversion happens exactly once in
each direction: :meth:`DeviceConfig.from_wire` when reading the device and
:meth:`DeviceConfig.to_wire` when writing it. Nothing else in the package
touches raw setting strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import IntEnum
from ipaddress import IPv4Address
from typing import Any, get_type_hints

from .constants import BaudRate, DataBits, NetProtocol, NetWorkMode, Parity, Toggle

_PORT_MAX = 65535


@dataclass
class SearchResult:
    """A single device discovered during a broadcast search."""

    mac_address: str = ""
    port_number: int = 0
    ip_address: IPv4Address | None = None
    username: str = ""
    device_name: str = ""


@dataclass
class DeviceConfig:
    """All settings that can be read / written via the UDP protocol."""

    # Network
    username: str = ""
    device_name: str = ""
    mac_address: str = ""
    ip_address: IPv4Address = field(default_factory=lambda: IPv4Address("0.0.0.0"))
    port_number: int = 0
    protocol: NetProtocol = NetProtocol.TCP
    work_mode: NetWorkMode = NetWorkMode.SERVER
    remote_ip: IPv4Address = field(default_factory=lambda: IPv4Address("0.0.0.0"))
    remote_port: int = 0
    gateway_ip: IPv4Address = field(default_factory=lambda: IPv4Address("0.0.0.0"))
    subnet_mask: IPv4Address = field(
        default_factory=lambda: IPv4Address("255.255.255.0")
    )
    dhcp: Toggle = Toggle.DISABLED

    # Serial
    baud_rate: BaudRate = BaudRate.BAUD_9600
    parity: Parity = Parity.NONE
    data_bits: DataBits = DataBits.EIGHT
    dtr_mode: Toggle = Toggle.DISABLED
    rts: Toggle = Toggle.DISABLED

    # Advanced
    connection_mode: Toggle = Toggle.DISABLED
    connection_timeout: int = 0
    reconnect: int = 0
    max_length: int = 0
    max_delay: int = 0

    # ── wire boundary ────────────────────────────────────────────────

    @classmethod
    def from_wire(cls, raw: dict[str, str]) -> DeviceConfig:
        """Build a typed config from ``{field_name: wire_string}``.

        Raises ``ValueError`` naming every field the device returned in a
        form this model cannot represent, so a firmware quirk is reported
        rather than silently becoming a default.
        """
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        errors: list[str] = []
        for f in fields(cls):
            if f.name not in raw:
                continue
            try:
                kwargs[f.name] = _parse(hints[f.name], raw[f.name])
            except ValueError as exc:
                errors.append(f"{f.name}: {raw[f.name]!r} ({exc})")
        if errors:
            detail = "\n  ".join(errors)
            raise ValueError(f"Device returned unparseable settings:\n  {detail}")
        return cls(**kwargs)

    def to_wire(self) -> dict[str, str]:
        """Serialize to ``{field_name: wire_string}`` after :meth:`validate`."""
        self.validate()
        return {f.name: _dump(getattr(self, f.name)) for f in fields(self)}

    # ── validation ───────────────────────────────────────────────────

    def validate(self) -> None:
        """Check every field before it is sent on the wire.

        Types already carry most of the guarantees (an ``IPv4Address`` is
        always a valid address, an enum is always a legal option). What is
        left is range checks and the two framing rules for free-text fields.
        Raises ``ValueError`` listing all problems.
        """
        errors: list[str] = []
        hints = get_type_hints(type(self))

        for f in fields(self):
            v = getattr(self, f.name)
            expected = hints[f.name]
            if not isinstance(v, expected):
                # Python does not enforce annotations; a caller can still
                # assign a raw str. Fail loud instead of corrupting the wire.
                errors.append(f"{f.name}: {v!r} must be {expected.__name__}")
                continue
            if isinstance(v, str):
                # `|` is the protocol delimiter; non-ASCII cannot be encoded.
                if "|" in v:
                    errors.append(f"{f.name}: {v!r} must not contain '|'")
                if not v.isascii():
                    errors.append(f"{f.name}: {v!r} must be ASCII")

        for name in ("port_number", "remote_port"):
            port = getattr(self, name)
            if isinstance(port, int) and not 1 <= port <= _PORT_MAX:
                errors.append(f"{name}: {port} must be 1-{_PORT_MAX}")
        for name in ("connection_timeout", "reconnect", "max_length", "max_delay"):
            n = getattr(self, name)
            if isinstance(n, int) and n < 0:
                errors.append(f"{name}: {n} must be a non-negative integer")

        if errors:
            raise ValueError("Invalid configuration:\n  " + "\n  ".join(errors))


# ── string <-> type helpers (the only place wire strings are interpreted) ──


def _parse(kind: Any, text: str) -> Any:
    """Parse one wire string into *kind* (``str``, ``int``, ``IPv4Address``, enum).

    Deliberately lets ``ValueError`` propagate: :meth:`DeviceConfig.from_wire`
    catches it per field so the caller sees every bad setting at once.
    """
    if kind is str:
        return text
    if kind is IPv4Address:
        return IPv4Address(text)  # raises ValueError on bad input
    if kind is int:
        return _parse_int(text)
    # DeviceConfig only has str / int / IPv4Address / IntEnum fields.
    return _parse_enum(kind, text)


def _parse_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError("not an integer") from None


def _parse_enum(kind: type[IntEnum], text: str) -> IntEnum:
    number = _parse_int(text)
    try:
        return kind(number)
    except ValueError:
        members = sorted(int(m) for m in kind)
        raise ValueError(f"not in {members}") from None


def _dump(value: Any) -> str:
    """Serialize one typed value to its wire string."""
    if isinstance(value, IntEnum):
        return str(value.value)  # NOT str(enum): that gives the member name
    return str(value)  # str, int, IPv4Address all stringify correctly

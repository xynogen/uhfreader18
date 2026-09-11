# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""
High-level device operations.

Mirrors the C# ``Form1.cs`` button-click flows: search → select → login,
then get / set configuration.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from ipaddress import IPv4Address
from types import TracebackType

from .config import DeviceConfig, SearchResult
from .constants import Toggle
from .transport import HwVxNetworking

# One row per setting: (field, setting code, GET check, SET check).
# GET order matches C# configButton_Click; SET order matches its save flow.
_SETTINGS: tuple[tuple[str, str, str, str], ...] = (
    ("username", "ON", "01", "12"),
    ("device_name", "DN", "02", "13"),
    ("mac_address", "FE", "03", ""),  # read-only
    ("ip_address", "IP", "04", "25"),
    ("port_number", "PN", "05", "15"),
    ("protocol", "TP", "06", "14"),
    ("work_mode", "RM", "07", "16"),
    ("connection_mode", "CM", "08", "1D"),
    ("connection_timeout", "CT", "09", "1E"),
    ("rts", "FC", "0A", "17"),
    ("dtr_mode", "DT", "0B", "18"),
    ("baud_rate", "BR", "0C", "19"),
    ("parity", "PR", "0D", "1A"),
    ("data_bits", "BB", "0E", "1B"),
    ("reconnect", "RC", "0F", "1C"),
    ("max_length", "ML", "10", "1F"),
    ("max_delay", "MD", "11", "20"),
    ("remote_ip", "DI", "12", "21"),
    ("remote_port", "DP", "13", "22"),
    ("gateway_ip", "GI", "14", "23"),
    ("subnet_mask", "NM", "15", "24"),
    ("dhcp", "DH", "16", ""),  # set via set_dhcp(), not the config pass
)

# The device applies SET commands in this exact order (C# save flow); IP last
# so the unicast channel stays valid until the final command.
_SET_ORDER = (
    "username",
    "device_name",
    "protocol",
    "port_number",
    "work_mode",
    "rts",
    "dtr_mode",
    "baud_rate",
    "parity",
    "data_bits",
    "reconnect",
    "connection_mode",
    "connection_timeout",
    "max_length",
    "max_delay",
    "remote_ip",
    "remote_port",
    "gateway_ip",
    "subnet_mask",
    "ip_address",
)
_BY_FIELD = {row[0]: row for row in _SETTINGS}
_LAN_BROADCAST = IPv4Address("255.255.255.255")


class HwVxDevice:
    """
    High-level operations for a specific HW-VX reader.

    Parameters
    ----------
    ip_address : IPv4Address
        The current IP address of the target device.
    """

    def __init__(
        self,
        ip_address: IPv4Address,
        *,
        mac_address: str = "",
        broadcast: bool = False,
        broadcast_ip: IPv4Address = _LAN_BROADCAST,
    ) -> None:
        self.ip = ip_address
        self.broadcast = broadcast
        self.broadcast_ip = broadcast_ip
        self.net = HwVxNetworking(str(broadcast_ip if broadcast else ip_address))
        self.mac = mac_address

    # ── connection ───────────────────────────────────────────────────

    def connect(self) -> SearchResult:
        """Search, select (``W{mac}``), and login (``L``) to a reader."""
        if self.mac:
            # ponytail: caller supplies MAC from a prior scan; no revalidation.
            r = SearchResult(mac_address=self.mac, ip_address=self.ip)
        else:
            results = self.net.search()
            if not results:
                raise ConnectionError(f"No reader found at {self.ip}")
            r = results[0]
            self.mac = r.mac_address
        self.net.request(f"W{self.mac}", retries=3)
        self.net.request("L", retries=3)
        return r

    # ── read configuration ───────────────────────────────────────────

    def get_config(self) -> DeviceConfig:
        """Read all settings from the device (C# ``configButton_Click``).

        Raises ``ValueError`` if the device returns a setting this model
        cannot represent (unknown enum value, malformed IP, ...).
        """
        raw = {
            name: self.net.request_single(f"G{code}", check)
            for name, code, check, _ in _SETTINGS
        }
        return DeviceConfig.from_wire(raw)

    # ── write configuration ──────────────────────────────────────────

    def save_config(self, cfg: DeviceConfig) -> None:
        """
        Write all settings and reboot.

        Sends commands via unicast first, then retries via broadcast
        with ``W{mac}`` in case the IP changed mid-save.

        Raises
        ------
        ValueError
            If *cfg* fails validation; nothing is sent in that case.
        """
        wire = cfg.to_wire()  # validates; nothing is sent if it raises
        delay = 0.01  # 10 ms between commands, matching C#

        self._send_config_pass(self.net.send, wire, delay)

        if self.broadcast:
            return

        # Broadcast fallback
        with HwVxNetworking(str(self.broadcast_ip)) as broadcast:
            broadcast.send(f"W{self.mac}")
            time.sleep(0.1)
            self._send_config_pass(broadcast.send, wire, delay)

    @staticmethod
    def _send_config_pass(
        send: Callable[[str], None],
        wire: dict[str, str],
        delay: float,
    ) -> None:
        """Emit login, the full set-command sequence, then reboot via *send*."""
        send("L")
        time.sleep(0.05)

        for name in _SET_ORDER:
            _, code, _, check = _BY_FIELD[name]
            send(f"S{code}{wire[name]}|{check}")
            time.sleep(delay)

        send("E")
        time.sleep(0.5)

    # ── quick operations ─────────────────────────────────────────────

    def change_network(
        self, new_ip: IPv4Address, subnet_mask: IPv4Address, gateway_ip: IPv4Address
    ) -> None:
        """Change IP, subnet mask, and gateway, then reboot.

        Taking ``IPv4Address`` (not ``str``) means an invalid address cannot
        reach this method: the constructor already rejected it.
        """
        s = self.net.send

        # Unicast
        s("X")
        time.sleep(0.1)
        s("L")
        time.sleep(0.05)
        self.net.receive()  # drain reply
        s(f"SGI{gateway_ip}|23")
        time.sleep(0.1)
        s(f"SNM{subnet_mask}|24")
        time.sleep(0.1)
        s(f"SIP{new_ip}|25")
        time.sleep(0.1)
        self.net.receive()
        s("E")
        time.sleep(0.2)

        if self.broadcast:
            return

        # Broadcast fallback
        with HwVxNetworking(str(self.broadcast_ip)) as broadcast:
            broadcast.send(f"W{self.mac}")
            time.sleep(0.1)
            broadcast.send("L")
            time.sleep(0.05)
            broadcast.send(f"SGI{gateway_ip}|23")
            time.sleep(0.1)
            broadcast.send(f"SNM{subnet_mask}|24")
            time.sleep(0.1)
            broadcast.send(f"SIP{new_ip}|25")
            time.sleep(0.1)
            broadcast.receive()
            broadcast.send("E")

    def set_dhcp(self, enabled: bool) -> None:
        """Enable / disable DHCP and reboot."""
        val = Toggle.ENABLED if enabled else Toggle.DISABLED
        self.net.send("L")
        time.sleep(0.05)
        self.net.send(f"SDH{val.value}|28")
        time.sleep(0.1)
        self.net.send("E")

    def reboot(self) -> None:
        """Send a reboot command."""
        self.net.send("E")

    # ── lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying transport."""
        self.net.close()

    def __enter__(self) -> HwVxDevice:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

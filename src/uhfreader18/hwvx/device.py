# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""
High-level device operations.

Mirrors the C# ``Form1.cs`` button-click flows: search → select → login,
then get / set configuration.
"""

from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable
from types import TracebackType

from .config import DeviceConfig, SearchResult
from .transport import HwVxNetworking


class HwVxDevice:
    """
    High-level operations for a specific HW-VX reader.

    Parameters
    ----------
    ip_address : str
        The current IP address of the target device.
    """

    def __init__(
        self,
        ip_address: str,
        *,
        mac_address: str = "",
        broadcast: bool = False,
        broadcast_ip: str = "255.255.255.255",
    ) -> None:
        self.ip = ip_address
        self.broadcast = broadcast
        self.broadcast_ip = broadcast_ip
        self.net = HwVxNetworking(broadcast_ip if broadcast else ip_address)
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
        """Read all settings from the device (C# ``configButton_Click``)."""
        cfg = DeviceConfig()
        r = self.net.request_single
        cfg.username = r("GON", "01")
        cfg.device_name = r("GDN", "02")
        cfg.mac_address = r("GFE", "03")
        cfg.ip_address = r("GIP", "04")
        cfg.port_number = r("GPN", "05")
        cfg.protocol = r("GTP", "06")
        cfg.work_mode = r("GRM", "07")
        cfg.connection_mode = r("GCM", "08")
        cfg.connection_timeout = r("GCT", "09")
        cfg.rts = r("GFC", "0A")
        cfg.dtr_mode = r("GDT", "0B")
        cfg.baud_rate = r("GBR", "0C")
        cfg.parity = r("GPR", "0D")
        cfg.data_bits = r("GBB", "0E")
        cfg.reconnect = r("GRC", "0F")
        cfg.max_length = r("GML", "10")
        cfg.max_delay = r("GMD", "11")
        cfg.remote_ip = r("GDI", "12")
        cfg.remote_port = r("GDP", "13")
        cfg.gateway_ip = r("GGI", "14")
        cfg.subnet_mask = r("GNM", "15")
        cfg.dhcp = r("GDH", "16")
        return cfg

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
        cfg.validate()  # reject bad config before it reaches the device
        delay = 0.01  # 10 ms between commands, matching C#

        self._send_config_pass(self.net.send, cfg, delay, login=True)

        if self.broadcast:
            return

        # Broadcast fallback
        with HwVxNetworking(self.broadcast_ip) as broadcast:
            broadcast.send(f"W{self.mac}")
            time.sleep(0.1)
            self._send_config_pass(broadcast.send, cfg, delay, login=True)

    @staticmethod
    def _send_config_pass(
        send: Callable[[str], None],
        cfg: DeviceConfig,
        delay: float,
        *,
        login: bool = True,
    ) -> None:
        """Emit the full set-command sequence through *send*."""
        if login:
            send("L")
            time.sleep(0.05)

        commands = [
            f"SON{cfg.username}|12",
            f"SDN{cfg.device_name}|13",
            f"STP{cfg.protocol}|14",
            f"SPN{cfg.port_number}|15",
            f"SRM{cfg.work_mode}|16",
            f"SFC{cfg.rts}|17",
            f"SDT{cfg.dtr_mode}|18",
            f"SBR{cfg.baud_rate}|19",
            f"SPR{cfg.parity}|1A",
            f"SBB{cfg.data_bits}|1B",
            f"SRC{cfg.reconnect}|1C",
            f"SCM{cfg.connection_mode}|1D",
            f"SCT{cfg.connection_timeout}|1E",
            f"SML{cfg.max_length}|1F",
            f"SMD{cfg.max_delay}|20",
            f"SDI{cfg.remote_ip}|21",
            f"SDP{cfg.remote_port}|22",
            f"SGI{cfg.gateway_ip}|23",
            f"SNM{cfg.subnet_mask}|24",
            f"SIP{cfg.ip_address}|25",
        ]
        for cmd in commands:
            send(cmd)
            time.sleep(delay)

        send("E")
        time.sleep(0.5)

    # ── quick operations ─────────────────────────────────────────────

    def change_network(self, new_ip: str, subnet_mask: str, gateway_ip: str) -> None:
        """Change IP, subnet mask, and gateway, then reboot."""
        for name, value in (
            ("new_ip", new_ip),
            ("subnet_mask", subnet_mask),
            ("gateway_ip", gateway_ip),
        ):
            try:
                ipaddress.IPv4Address(value)
            except (ipaddress.AddressValueError, ValueError):
                raise ValueError(
                    f"{name}: {value!r} is not a valid IPv4 address"
                ) from None
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
        with HwVxNetworking(self.broadcast_ip) as broadcast:
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
        val = "1" if enabled else "0"
        self.net.send("L")
        time.sleep(0.05)
        self.net.send(f"SDH{val}|28")
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

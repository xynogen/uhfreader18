# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Low-level UDP transport for the HW-VX IP module protocol."""

from __future__ import annotations

import socket

from .config import SearchResult
from .constants import RECV_BUFFER, RECV_TIMEOUT, UDP_PORT


class HwVxNetworking:
    """UDP communication with HW-VX6330K / HW-VX6346KL TCP/IP modules.

    Parameters
    ----------
    ip_address : str
        Destination IP. Use ``"255.255.255.255"`` for broadcast.
    """

    def __init__(self, ip_address: str = "255.255.255.255") -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(RECV_TIMEOUT)
        self.target: tuple[str, int] = (ip_address, UDP_PORT)

    # ── low-level ────────────────────────────────────────────────────

    def send(self, command: str) -> None:
        """Send a raw ASCII command packet."""
        self.sock.sendto(command.encode("ascii"), self.target)

    def receive(self) -> str:
        """Block until a packet arrives or timeout. Returns ``""`` on timeout."""
        try:
            data, _addr = self.sock.recvfrom(RECV_BUFFER)
            return data.decode("ascii")
        except TimeoutError:
            return ""

    # ── request helpers ──────────────────────────────────────────────

    def request(self, command: str, retries: int = 5) -> str:
        """Send *command* and wait for an ``A``-prefixed reply.

        Returns the reply body (``A`` prefix stripped).

        Raises
        ------
        TimeoutError
            If no valid reply is received after *retries* attempts.
        """
        for _ in range(retries):
            self.send(command)
            reply = self.receive()
            if reply and reply[0] == "A":
                return reply[1:]
        raise TimeoutError(f"No response for command: {command}")

    def request_single(self, command: str, check: str) -> str:
        """Send ``command|check`` and expect ``A{value}|{check}`` back.

        Returns just the *value* portion. Matches the C# ``requestSingle``
        helper.

        Raises
        ------
        ValueError
            If the reply does not contain the expected check token.
        """
        reply = self.request(f"{command}|{check}")
        parts = reply.split("|")
        if len(parts) == 2 and parts[1] == check:
            return parts[0]
        raise ValueError(f"Unexpected reply for {command}: {reply}")

    # ── discovery ────────────────────────────────────────────────────

    def search(self) -> list[SearchResult]:
        """Broadcast an echo (``X``) and collect all device responses."""
        self.send("X")
        return self._collect_search_results()

    def search_targets(self, ip_addresses: list[str]) -> list[SearchResult]:
        """Send ``X`` to each target, then collect replies on the same socket."""
        for ip_address in ip_addresses:
            self.sock.sendto(b"X", (ip_address, UDP_PORT))
        return self._collect_search_results()

    def _collect_search_results(self) -> list[SearchResult]:
        """Collect search replies until the shared receive timeout expires."""
        results: list[SearchResult] = []
        for _ in range(255):
            try:
                data, addr = self.sock.recvfrom(RECV_BUFFER)
            except TimeoutError:
                break
            reply = data.decode("ascii")
            if not reply or reply[0] != "A":
                break
            result = SearchResult()
            parts = reply[1:].split("/")
            if len(parts) >= 2:
                result.mac_address = parts[0]
                result.port_number = parts[1]
            result.ip_address = addr[0]
            if len(parts) > 5:
                result.username = parts[4]
                result.device_name = parts[5]
            results.append(result)
        return results

    # ── lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying socket."""
        self.sock.close()

    def __enter__(self) -> HwVxNetworking:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

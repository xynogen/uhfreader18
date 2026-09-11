"""Tests for uhfreader18.hwvx.transport — all socket I/O is mocked."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, call, patch

import pytest

from uhfreader18.hwvx.transport import HwVxNetworking


@pytest.fixture()
def mock_socket() -> MagicMock:
    """Return a pre-configured mock socket."""
    sock = MagicMock(spec=socket.socket)
    return sock


@pytest.fixture()
def networking(mock_socket: MagicMock) -> HwVxNetworking:
    """HwVxNetworking with its socket replaced by the mock."""
    with patch("uhfreader18.hwvx.transport.socket.socket", return_value=mock_socket):
        net = HwVxNetworking("192.168.1.100")
    return net


class TestSend:
    def test_sends_ascii_encoded_command(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        networking.send("GON|1")
        mock_socket.sendto.assert_called_once_with(b"GON|1", ("192.168.1.100", 65535))


class TestReceive:
    def test_returns_decoded_string(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.return_value = (b"Aadmin|1", ("192.168.1.100", 65535))
        assert networking.receive() == "Aadmin|1"

    def test_returns_empty_on_timeout(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = socket.timeout
        assert networking.receive() == ""


class TestRequest:
    def test_strips_a_prefix(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.return_value = (b"Aadmin|1", ("192.168.1.100", 65535))
        result = networking.request("GON|1")
        assert result == "admin|1"

    def test_retries_on_timeout(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = [
            socket.timeout,
            socket.timeout,
            (b"Avalue|2", ("192.168.1.100", 65535)),
        ]
        result = networking.request("GDN|2", retries=3)
        assert result == "value|2"
        assert mock_socket.sendto.call_count == 3

    def test_raises_timeout_after_exhausting_retries(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = socket.timeout
        with pytest.raises(TimeoutError, match="No response"):
            networking.request("GON|1", retries=2)

    def test_ignores_non_a_replies(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = [
            (b"Xbogus", ("192.168.1.100", 65535)),
            (b"Agood|1", ("192.168.1.100", 65535)),
        ]
        result = networking.request("GON|1", retries=2)
        assert result == "good|1"


class TestRequestSingle:
    def test_returns_value_portion(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.return_value = (b"Aadmin|1", ("192.168.1.100", 65535))
        result = networking.request_single("GON", "1")
        assert result == "admin"

    def test_raises_on_bad_check_token(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.return_value = (b"Aadmin|99", ("192.168.1.100", 65535))
        with pytest.raises(ValueError, match="Unexpected reply"):
            networking.request_single("GON", "1")


class TestSearch:
    def test_collects_results(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = [
            (b"AAA:BB:CC:DD:EE:FF/4196/x/y/admin/MyDevice", ("192.168.1.100", 65535)),
            socket.timeout,  # end of responses
        ]
        results = networking.search()
        assert len(results) == 1
        r = results[0]
        assert r.mac_address == "AA:BB:CC:DD:EE:FF"
        assert r.port_number == "4196"
        assert r.ip_address == "192.168.1.100"
        assert r.username == "admin"
        assert r.device_name == "MyDevice"

    def test_search_targets_sends_echo_to_each_ip(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = socket.timeout

        assert networking.search_targets(["10.10.23.1", "10.10.23.2"]) == []
        assert mock_socket.sendto.call_args_list == [
            call(b"X", ("10.10.23.1", 65535)),
            call(b"X", ("10.10.23.2", 65535)),
        ]

    def test_empty_when_no_replies(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = socket.timeout
        assert networking.search() == []

    def test_stops_on_non_a_reply(
        self, networking: HwVxNetworking, mock_socket: MagicMock
    ) -> None:
        mock_socket.recvfrom.side_effect = [
            (b"AAA:BB/4196", ("192.168.1.100", 65535)),
            (b"Xbad", ("192.168.1.101", 65535)),
        ]
        results = networking.search()
        assert len(results) == 1


class TestContextManager:
    def test_closes_socket(self, mock_socket: MagicMock) -> None:
        with (
            patch("uhfreader18.hwvx.transport.socket.socket", return_value=mock_socket),
            HwVxNetworking("1.2.3.4") as _net,
        ):
            pass
        mock_socket.close.assert_called_once()

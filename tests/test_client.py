# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

import socket
from collections.abc import Callable

import pytest

from uhfreader18 import (
    Command,
    ReaderInfo,
    RfidClient,
    Status,
    build_heartbeat,
    build_response_frame,
)

INFO_DATA = bytes([2, 36, 9, 3, 32, 0, 30, 10])


class FakeSocket:
    def __init__(self, chunks: list[bytes | BaseException]) -> None:
        self.chunks = chunks
        self.sent: list[bytes] = []
        self.closed = False

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, _size: int) -> bytes:
        chunk = self.chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        self.close()


def patch_connection(
    monkeypatch: pytest.MonkeyPatch, sock: FakeSocket
) -> Callable[..., FakeSocket]:
    def create_connection(*_args: object, **_kwargs: object) -> FakeSocket:
        return sock

    monkeypatch.setattr(socket, "create_connection", create_connection)
    return create_connection


def info_response(address: int = 0) -> bytes:
    return build_response_frame(
        address, Command.GET_READER_INFO, Status.SUCCESS, INFO_DATA
    )


def test_get_reader_info_reassembles_fragmented_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = info_response()
    sock = FakeSocket([response[:3], response[3:8], response[8:]])
    patch_connection(monkeypatch, sock)

    with RfidClient("192.0.2.1", 2077) as client:
        info = client.get_reader_info()

    assert info == ReaderInfo(0, "2.36", 9, 3, 32, 0, 30, 10)
    assert sock.sent[0][1:3] == bytes([0, Command.GET_READER_INFO])
    assert sock.closed


def test_discover_address_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([info_response(7)])
    patch_connection(monkeypatch, sock)

    with RfidClient("192.0.2.1", 2077) as client:
        info, address = client.discover_address()

    assert info.address == address == 7
    assert sock.sent[0][1] == 0xFF


def test_set_address(monkeypatch: pytest.MonkeyPatch) -> None:
    response = build_response_frame(7, Command.SET_ADDRESS, Status.SUCCESS)
    sock = FakeSocket([response])
    patch_connection(monkeypatch, sock)

    with RfidClient("192.0.2.1", 2077) as client:
        result = client.set_address(7, 8)

    assert result.ok
    assert sock.sent[0][1:4] == bytes([7, Command.SET_ADDRESS, 8])


def test_set_address_rejects_broadcast_value() -> None:
    with pytest.raises(ValueError, match="0x00-0xFE"):
        RfidClient("192.0.2.1", 2077).set_address(0, 0xFF)


@pytest.mark.parametrize("power", [-1, 31])
def test_set_power_range(power: int) -> None:
    with pytest.raises(ValueError, match="0-30"):
        RfidClient("192.0.2.1", 2077).set_power(0, power)


@pytest.mark.parametrize("scan_time", [-1, 256])
def test_set_scan_time_range(scan_time: int) -> None:
    with pytest.raises(ValueError, match="0-255"):
        RfidClient("192.0.2.1", 2077).set_scan_time(0, scan_time)


def test_not_connected() -> None:
    with pytest.raises(ConnectionError, match="connect"):
        RfidClient("192.0.2.1", 2077).get_reader_info()


def test_eof_before_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([b""])
    patch_connection(monkeypatch, sock)

    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ConnectionError, match="No response"),
    ):
        client.get_reader_info()


def test_broadcast_timeout_has_connection_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sock = FakeSocket([TimeoutError()])
    patch_connection(monkeypatch, sock)

    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ConnectionError, match="broadcast"),
    ):
        client.discover_address()


def test_rejects_heartbeat_while_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([build_heartbeat()])
    patch_connection(monkeypatch, sock)

    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ConnectionError, match="heartbeat"),
    ):
        client.get_reader_info()


def test_rejects_mismatched_command(monkeypatch: pytest.MonkeyPatch) -> None:
    response = build_response_frame(0, Command.SET_POWER, Status.SUCCESS)
    sock = FakeSocket([response])
    patch_connection(monkeypatch, sock)

    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ConnectionError, match="Unexpected response command"),
    ):
        client.get_reader_info()

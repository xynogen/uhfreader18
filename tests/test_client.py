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
    WorkModeInfo,
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


def _ok(command: int, data: bytes = b"") -> bytes:
    return build_response_frame(0, command, Status.SUCCESS, data)


def test_set_region_sends_two_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_REGION)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_region(0, 0x20, 0x00).ok
    assert sock.sent[0][2:5] == bytes([Command.SET_REGION, 0x20, 0x00])


@pytest.mark.parametrize("code", [3, 4, 7, -1])
def test_set_baud_rate_rejects_bad_code(code: int) -> None:
    with pytest.raises(ValueError, match="0,1,2,5,6"):
        RfidClient("192.0.2.1", 2077).set_baud_rate(0, code)


def test_set_baud_rate_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_BAUD_RATE)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_baud_rate(0, 6).ok
    assert sock.sent[0][2:4] == bytes([Command.SET_BAUD_RATE, 6])


def test_acousto_optic_sends_three_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.ACOUSTO_OPTIC_CONTROL)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.acousto_optic_control(0, 2, 3, 5).ok
    assert sock.sent[0][2:6] == bytes([Command.ACOUSTO_OPTIC_CONTROL, 2, 3, 5])


def test_set_wiegand_sends_four_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_WIEGAND)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_wiegand(0, 1, 30, 10, 15).ok
    assert sock.sent[0][2:7] == bytes([Command.SET_WIEGAND, 1, 30, 10, 15])


def test_set_work_mode_sends_six_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_WORK_MODE)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_work_mode(0, 0, 2, 1, 0, 4, 0).ok
    assert sock.sent[0][2:9] == bytes([Command.SET_WORK_MODE, 0, 2, 1, 0, 4, 0])


def test_get_work_mode_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = bytes([1, 30, 10, 15, 0, 2, 1, 0, 4, 0, 8, 5])
    sock = FakeSocket([_ok(Command.GET_WORK_MODE, payload)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        wm = client.get_work_mode()
    assert wm == WorkModeInfo(1, 30, 10, 15, 0, 2, 1, 0, 4, 0, 8, 5)


@pytest.mark.parametrize("acc", [-1, 9])
def test_set_eas_accuracy_range(acc: int) -> None:
    with pytest.raises(ValueError, match="0-8"):
        RfidClient("192.0.2.1", 2077).set_eas_accuracy(0, acc)


@pytest.mark.parametrize("off", [-1, 101])
def test_set_syris_offset_range(off: int) -> None:
    with pytest.raises(ValueError, match="0-100"):
        RfidClient("192.0.2.1", 2077).set_syris_response_offset(0, off)


def test_set_trigger_offset_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.TRIGGER_OFFSET)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_trigger_offset(0, 10).ok
    assert sock.sent[0][2:4] == bytes([Command.TRIGGER_OFFSET, 10])


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

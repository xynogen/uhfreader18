# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

import socket
from collections.abc import Callable

import pytest

from uhfreader18 import (
    Command,
    FreqBand,
    MemInven,
    ModeState,
    Protocol,
    ReaderInfo,
    ReaderType,
    RfidClient,
    Status,
    WiegandFormat,
    WorkMode,
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


# Error branch: reader returns non-SUCCESS status -> RuntimeError, one per setter.
_SETTER_CALLS: list[tuple[int, Callable[[RfidClient], object]]] = [
    (Command.SET_ADDRESS, lambda c: c.set_address(0, 1)),
    (Command.SET_POWER, lambda c: c.set_power(0, 10)),
    (Command.SET_SCAN_TIME, lambda c: c.set_scan_time(0, 10)),
    (Command.SET_REGION, lambda c: c.set_region(0, 0x20, 0)),
    (Command.SET_BAUD_RATE, lambda c: c.set_baud_rate(0, 6)),
    (Command.ACOUSTO_OPTIC_CONTROL, lambda c: c.acousto_optic_control(0, 1, 1, 1)),
    (Command.SET_WIEGAND, lambda c: c.set_wiegand(0, 1, 30, 10, 15)),
    (Command.SET_WORK_MODE, lambda c: c.set_work_mode(0, 0, 2, 1, 0, 4, 0)),
    (Command.GET_WORK_MODE, lambda c: c.get_work_mode()),
    (Command.SET_EAS_ACCURACY, lambda c: c.set_eas_accuracy(0, 8)),
    (Command.SYRIS_RESPONSE_OFFSET, lambda c: c.set_syris_response_offset(0, 10)),
    (Command.TRIGGER_OFFSET, lambda c: c.set_trigger_offset(0, 10)),
    (Command.GET_READER_INFO, lambda c: c.get_reader_info()),
]


@pytest.mark.parametrize("command, call", _SETTER_CALLS)
def test_setter_raises_on_failure_status(
    monkeypatch: pytest.MonkeyPatch,
    command: int,
    call: Callable[[RfidClient], object],
) -> None:
    fail = build_response_frame(0, command, Status.PARAMETER_ERROR)
    sock = FakeSocket([fail])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client, pytest.raises(RuntimeError):
        call(client)


def test_set_power_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_POWER)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_power(0, 30).ok
    assert sock.sent[0][2:4] == bytes([Command.SET_POWER, 30])


def test_set_scan_time_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_SCAN_TIME)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_scan_time(0, 100).ok
    assert sock.sent[0][2:4] == bytes([Command.SET_SCAN_TIME, 100])


# Out-of-range rejection for the multi-byte wrappers (byte-range guards).
_RANGE_REJECTS: list[Callable[[RfidClient], object]] = [
    lambda c: c.set_region(0, 256, 0),
    lambda c: c.acousto_optic_control(0, 256, 0, 0),
    lambda c: c.set_wiegand(0, 256, 0, 0, 0),
    lambda c: c.set_work_mode(0, 256, 0, 0, 0, 0, 0),
    lambda c: c.set_trigger_offset(0, 256),
]


@pytest.mark.parametrize("call", _RANGE_REJECTS)
def test_multibyte_wrappers_reject_out_of_range(
    call: Callable[[RfidClient], object],
) -> None:
    with pytest.raises(ValueError):
        call(RfidClient("192.0.2.1", 2077))


def test_get_work_mode_short_response(monkeypatch: pytest.MonkeyPatch) -> None:
    short = build_response_frame(0, Command.GET_WORK_MODE, Status.SUCCESS, bytes(5))
    sock = FakeSocket([short])
    patch_connection(monkeypatch, sock)
    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ValueError, match="work-mode response length"),
    ):
        client.get_work_mode()


def test_get_reader_info_short_response(monkeypatch: pytest.MonkeyPatch) -> None:
    short = build_response_frame(0, Command.GET_READER_INFO, Status.SUCCESS, bytes(3))
    sock = FakeSocket([short])
    patch_connection(monkeypatch, sock)
    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ValueError, match="info response length"),
    ):
        client.get_reader_info()


@pytest.mark.parametrize("port", [0, 65536])
def test_init_rejects_bad_port(port: int) -> None:
    with pytest.raises(ValueError, match="port must be"):
        RfidClient("192.0.2.1", port)


def test_init_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        RfidClient("192.0.2.1", 2077, timeout=0)


def test_status_text_unknown_code() -> None:
    from uhfreader18 import RfidResponse

    resp = RfidResponse(5, 0, Command.SET_POWER, 0x77, b"", 0)
    assert "Unknown" in resp.status_text
    assert "0x77" in resp.status_text


def test_stream_error_while_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    # A frame with a bad CRC triggers a parse error mid-wait.
    good = _ok(Command.GET_READER_INFO, INFO_DATA)
    corrupt = good[:-1] + bytes([good[-1] ^ 0xFF])
    sock = FakeSocket([corrupt])
    patch_connection(monkeypatch, sock)
    with (
        RfidClient("192.0.2.1", 2077) as client,
        pytest.raises(ConnectionError),
    ):
        client.get_reader_info()


def test_set_eas_accuracy_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SET_EAS_ACCURACY)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_eas_accuracy(0, 8).ok
    assert sock.sent[0][2:4] == bytes([Command.SET_EAS_ACCURACY, 8])


def test_set_syris_offset_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([_ok(Command.SYRIS_RESPONSE_OFFSET)])
    patch_connection(monkeypatch, sock)
    with RfidClient("192.0.2.1", 2077) as client:
        assert client.set_syris_response_offset(0, 50).ok
    assert sock.sent[0][2:4] == bytes([Command.SYRIS_RESPONSE_OFFSET, 50])


def test_connect_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([info_response()])
    patch_connection(monkeypatch, sock)
    client = RfidClient("192.0.2.1", 2077)
    client.connect()
    client.connect()  # second call returns early, no new socket
    client.close()


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


class TestReaderInfoDecoding:
    def test_reader_model_known(self) -> None:
        info = ReaderInfo(0, "2.36", 0x09, 0x03, 0x20, 0x00, 30, 10)
        assert info.reader_model is ReaderType.UHFREADER18

    def test_reader_model_unknown_is_none(self) -> None:
        info = ReaderInfo(0, "2.36", 0xAB, 0x03, 0x20, 0x00, 30, 10)
        assert info.reader_model is None

    def test_protocols_both(self) -> None:
        info = ReaderInfo(0, "2.36", 0x09, 0x03, 0x20, 0x00, 30, 10)
        assert info.protocols is Protocol.ISO18000_6B | Protocol.ISO18000_6C
        assert Protocol.ISO18000_6C in info.protocols

    def test_protocols_6c_only(self) -> None:
        info = ReaderInfo(0, "2.36", 0x09, 0x02, 0x20, 0x00, 30, 10)
        assert info.protocols is Protocol.ISO18000_6C
        assert Protocol.ISO18000_6B not in info.protocols

    def test_freq_band_and_index(self) -> None:
        # max_freq 0x82 = band bit7-6 = 0b10 (US), index bit5-0 = 2
        info = ReaderInfo(0, "2.36", 0x09, 0x03, 0x82, 0x40, 30, 10)
        assert info.max_band is FreqBand.US
        assert info.max_freq_index == 2
        assert info.min_band is FreqBand.CHINESE_2
        assert info.min_freq_index == 0


class TestWorkModeDecoding:
    def _wm(
        self,
        *,
        read_mode: int = 0,
        wg_mode: int = 0,
        mode_state: int = 0,
        mem_inven: int = 0,
    ) -> WorkModeInfo:
        return WorkModeInfo(
            wg_mode, 0, 0, 0, read_mode, mode_state, mem_inven, 0, 0, 0, 0, 0
        )

    def test_work_mode(self) -> None:
        assert self._wm(read_mode=0).work_mode is WorkMode.ANSWER
        assert self._wm(read_mode=1).work_mode is WorkMode.SCAN
        assert self._wm(read_mode=0b11).work_mode is WorkMode.TRIGGER_HIGH

    def test_wiegand_format(self) -> None:
        assert self._wm(wg_mode=0).wiegand_format == WiegandFormat(0)
        wf = self._wm(wg_mode=0b11).wiegand_format
        assert WiegandFormat.FORMAT_34BIT in wf
        assert WiegandFormat.LOW_BIT_FIRST in wf

    def test_state_flags(self) -> None:
        sf = self._wm(mode_state=0b1_0110).state_flags
        assert ModeState.RS_OUTPUT in sf
        assert ModeState.BEEP_OFF in sf
        assert ModeState.SYRIS_485 in sf
        assert ModeState.PROTOCOL_6B not in sf

    def test_mem_target(self) -> None:
        assert self._wm(mem_inven=0x01).mem_target is MemInven.EPC
        assert self._wm(mem_inven=0x06).mem_target is MemInven.EAS_ALARM
        assert self._wm(mem_inven=0x09).mem_target is None

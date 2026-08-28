# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

import pytest

from uhfreader18 import (
    Command,
    FrameError,
    Status,
    StreamBuffer,
    build_command_frame,
    build_heartbeat,
    build_response_frame,
    crc16,
    parse_response,
    validate_frame,
)

CAPTURED_FRAME = bytes.fromhex("1100ee002000708c2b380b2d00000000e056")
HEARTBEAT = bytes.fromhex("560000000000")


def test_captured_frame() -> None:
    frame = validate_frame(CAPTURED_FRAME)
    assert frame.reader_address == 0
    assert frame.command == Command.TAG_REPORT
    assert frame.data == bytes.fromhex("2000708c2b380b2d00000000")
    assert frame.tag == "2000708C2B380B2D"
    assert frame.to_bytes() == CAPTURED_FRAME


def test_command_frame_uses_little_endian_crc() -> None:
    raw = build_command_frame(0, Command.GET_READER_INFO)
    assert raw[:3] == bytes([4, 0, 0x21])
    assert int.from_bytes(raw[-2:], "little") == crc16(raw[:-2])


def test_response_round_trip() -> None:
    raw = build_response_frame(7, Command.SET_POWER, Status.SUCCESS, b"\x1e")
    response = parse_response(raw)
    assert response.ok
    assert response.address == 7
    assert response.command == Command.SET_POWER
    assert response.data == b"\x1e"
    assert response.to_bytes() == raw


@pytest.mark.parametrize("address", [-1, 256])
def test_command_rejects_invalid_address(address: int) -> None:
    with pytest.raises(ValueError, match="address"):
        build_command_frame(address, Command.GET_READER_INFO)


def test_response_rejects_bad_crc() -> None:
    raw = bytearray(build_response_frame(0, Command.GET_READER_INFO, Status.SUCCESS))
    raw[-1] ^= 0xFF
    with pytest.raises(FrameError, match="CRC mismatch"):
        validate_frame(bytes(raw))


def test_stream_reassembles_frames_and_heartbeat() -> None:
    first = build_response_frame(1, Command.TAG_REPORT, Status.SUCCESS, b"first")
    second = build_response_frame(2, Command.TAG_REPORT, Status.SUCCESS, b"second")
    stream = StreamBuffer()

    assert stream.feed(first[:3]).frames == []
    result = stream.feed(first[3:] + HEARTBEAT + second)

    assert [frame.data for frame in result.frames] == [b"first", b"second"]
    assert [heartbeat.raw for heartbeat in result.heartbeats] == [HEARTBEAT]
    assert result.errors == []
    assert stream.pending_bytes == 0


def test_length_0x56_response_is_not_mistaken_for_heartbeat() -> None:
    raw = build_response_frame(0, Command.TAG_REPORT, Status.SUCCESS, bytes(range(81)))
    assert raw[0] == 0x56

    result = StreamBuffer().feed(raw)

    assert result.errors == []
    assert result.heartbeats == []
    assert result.frames[0].data == bytes(range(81))


def test_stream_reader_allowlist() -> None:
    raw = build_response_frame(2, Command.TAG_REPORT, Status.SUCCESS, b"tag")
    result = StreamBuffer(allowed_readers={1}).feed(raw)
    assert result.frames == []
    assert "Unknown reader address" in result.errors[0]


def test_heartbeat_builder() -> None:
    assert build_heartbeat() == HEARTBEAT

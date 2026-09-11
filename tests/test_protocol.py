# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

import pytest

from uhfreader18 import (
    Command,
    FrameError,
    Heartbeat,
    Status,
    StreamBuffer,
    build_command_frame,
    build_heartbeat,
    build_response_frame,
    compute_checksum,
    crc16,
    hex_readable,
    is_heartbeat,
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


def test_is_heartbeat() -> None:
    assert is_heartbeat(HEARTBEAT)
    assert not is_heartbeat(b"\x56\x00")
    assert not is_heartbeat(b"\x56\x01\x00\x00\x00\x00")


def test_partial_heartbeat_waits_for_more_bytes() -> None:
    stream = StreamBuffer()
    result = stream.feed(b"\x56\x00")
    assert stream.pending_bytes == 2
    assert result.frames == []
    assert result.heartbeats == []


def test_frame_unknown_names_and_hex_readable() -> None:
    raw = build_response_frame(0, 0x99, 0x88, b"\x01")
    frame = validate_frame(raw)
    assert frame.command_name == "UNKNOWN(0x99)"
    assert frame.status_name == "UNKNOWN(0x88)"
    assert frame.hex_readable() == raw.hex(" ").upper()

    heartbeat = Heartbeat(HEARTBEAT)
    assert heartbeat.hex_readable() == HEARTBEAT.hex(" ").upper()


@pytest.mark.parametrize(
    ("bad_frame", "match"),
    [
        (b"", "Empty frame"),
        (b"\x03\x00\x00\x00", "Length too small"),
        (b"\x0a\x00\x00\x00\x00", "Length mismatch"),
    ],
)
def test_validate_frame_invalid_lengths(bad_frame: bytes, match: str) -> None:
    with pytest.raises(FrameError, match=match):
        validate_frame(bad_frame)


def test_build_command_frame_oversize_data() -> None:
    with pytest.raises(ValueError, match="data cannot exceed 251 bytes"):
        build_command_frame(0, Command.GET_READER_INFO, b"\x00" * 252)


def test_build_response_frame_oversize_data() -> None:
    with pytest.raises(ValueError, match="data cannot exceed 250 bytes"):
        build_response_frame(0, Command.GET_READER_INFO, Status.SUCCESS, b"\x00" * 251)


def test_build_response_frame_invalid_fields() -> None:
    with pytest.raises(ValueError, match="reader_address"):
        build_response_frame(256, Command.GET_READER_INFO, Status.SUCCESS)
    with pytest.raises(ValueError, match="command"):
        build_response_frame(0, 256, Status.SUCCESS)
    with pytest.raises(ValueError, match="status"):
        build_response_frame(0, Command.GET_READER_INFO, 256)


def test_compute_checksum() -> None:
    raw = build_command_frame(0, Command.GET_READER_INFO)
    checksum = compute_checksum(raw)
    expected = int.from_bytes(crc16(raw[:-2]).to_bytes(2, "little"), "big")
    assert checksum == expected


def test_hex_readable_utility() -> None:
    assert hex_readable(0xAB) == "AB"
    assert hex_readable(b"\x01\x02\x03", separator="-") == "01-02-03"

# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from uhfreader18 import Command, Status, build_heartbeat, build_response_frame
from uhfreader18.server import (
    build_parser,
    handle_client,
    main,
    start_server,
)


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 2077
    assert args.allowed_readers is None
    assert args.fields == "tag,reader"
    assert not args.debug


def test_parser_allowed_readers() -> None:
    args = build_parser().parse_args(["--allowed-readers", "00, 0A, FF"])
    assert args.allowed_readers == {0x00, 0x0A, 0xFF}


@pytest.mark.parametrize("invalid_val", ["not_hex", "100", "-1"])
def test_parser_rejects_invalid_allowed_readers(invalid_val: str) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--allowed-readers", invalid_val])


@pytest.mark.parametrize("port", ["0", "65536"])
def test_main_rejects_invalid_port(port: str) -> None:
    with pytest.raises(SystemExit):
        main(["--port", port])


def test_main_rejects_unknown_fields() -> None:
    with pytest.raises(SystemExit):
        main(["--fields", "tag,unknown_field"])


def test_main_launches_server() -> None:
    with (
        patch("uhfreader18.server.start_server") as mock_start,
        patch("logging.basicConfig") as mock_logging,
    ):
        main(["--host", "127.0.0.1", "--port", "3000", "--debug"])
        mock_logging.assert_called_once_with(
            level=logging.DEBUG,
            stream=sys.stderr,
            format="%(levelname)s %(message)s",
        )
        mock_start.assert_called_once_with(
            "127.0.0.1",
            3000,
            allowed_readers=None,
            fields=("tag", "reader"),
        )


class FakeSocket:
    def __init__(self, chunks: list[bytes | BaseException]) -> None:
        self.chunks = chunks
        self.closed = False

    def recv(self, _size: int) -> bytes:
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk

    def close(self) -> None:
        self.closed = True


def test_handle_client_processes_frames_and_heartbeats(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tag_frame = build_response_frame(1, Command.TAG_REPORT, Status.SUCCESS, b"tag1")
    heartbeat = build_heartbeat()
    sock = FakeSocket([tag_frame + heartbeat, b""])

    with caplog.at_level(logging.DEBUG):
        handle_client(
            sock,  # pyright: ignore[reportArgumentType]
            ("127.0.0.1", 12345),
            fields=("tag", "reader", "cmd", "status", "peer"),
        )

    assert sock.closed
    assert "tag=74616731 | reader=0x01 | cmd=TAG_REPORT | status=SUCCESS" in caplog.text
    assert "Heartbeat from 127.0.0.1:12345: 56 00 00 00 00 00" in caplog.text


def test_handle_client_logs_errors_and_unconsumed_buffer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Send bad length byte (0x01 < 5) and partial unconsumed frame (0x10)
    sock = FakeSocket([b"\x01\x10", b""])

    with caplog.at_level(logging.WARNING):
        handle_client(
            sock,  # pyright: ignore[reportArgumentType]
            ("127.0.0.1", 12345),
        )

    assert sock.closed
    assert "Frame error from 127.0.0.1:12345: Invalid length byte" in caplog.text
    assert "Connection closed with 1 bytes still buffered" in caplog.text


def test_handle_client_handles_connection_reset(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sock = FakeSocket([ConnectionResetError("Connection reset")])

    with caplog.at_level(logging.WARNING):
        handle_client(
            sock,  # pyright: ignore[reportArgumentType]
            ("127.0.0.1", 12345),
        )

    assert sock.closed
    assert "Connection reset by 127.0.0.1:12345" in caplog.text


def test_start_server_shuts_down_on_keyboard_interrupt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_socket_instance = MagicMock()
    mock_client = MagicMock()
    mock_socket_instance.accept.side_effect = [
        (mock_client, ("127.0.0.1", 12345)),
        KeyboardInterrupt,
    ]

    with (
        patch("socket.socket", return_value=mock_socket_instance),
        patch("threading.Thread") as mock_thread,
        caplog.at_level(logging.INFO),
    ):
        mock_socket_instance.__enter__.return_value = mock_socket_instance
        start_server("127.0.0.1", 2077)
        mock_thread.assert_called_once()

    assert "Shutting down server" in caplog.text

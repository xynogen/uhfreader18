# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""Command-line TCP receiver for autonomous UHFReader18 reports."""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading

from .stream import StreamBuffer

logger = logging.getLogger(__name__)
AVAILABLE_FIELDS = ("tag", "reader", "cmd", "status", "peer")


def _reader_address(value: str) -> int:
    try:
        address = int(value, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid hex address: {value}") from exc
    if not 0 <= address <= 0xFF:
        raise argparse.ArgumentTypeError("reader address must be between 00 and FF")
    return address


def handle_client(
    client_socket: socket.socket,
    peer: tuple[str, int],
    *,
    allowed_readers: set[int] | None = None,
    fields: tuple[str, ...] = ("tag", "reader"),
) -> None:
    """Receive and log validated messages from one reader connection."""
    stream = StreamBuffer(allowed_readers=allowed_readers)
    logger.info("Connection from %s:%d", *peer)
    try:
        while data := client_socket.recv(4096):
            result = stream.feed(data)
            for frame in result.frames:
                values = {
                    "tag": frame.tag,
                    "reader": f"0x{frame.reader_address:02X}",
                    "cmd": frame.command_name,
                    "status": frame.status_name,
                    "peer": f"{peer[0]}:{peer[1]}",
                }
                logger.info(" | ".join(f"{key}={values[key]}" for key in fields))
            for heartbeat in result.heartbeats:
                logger.debug(
                    "Heartbeat from %s:%d: %s", *peer, heartbeat.hex_readable()
                )
            for error in result.errors:
                logger.warning("Frame error from %s:%d: %s", *peer, error)
    except ConnectionResetError:
        logger.warning("Connection reset by %s:%d", *peer)
    finally:
        if stream.pending_bytes:
            logger.warning(
                "Connection closed with %d bytes still buffered", stream.pending_bytes
            )
        client_socket.close()
        logger.info("Connection closed for %s:%d", *peer)


def start_server(
    host: str,
    port: int,
    *,
    allowed_readers: set[int] | None = None,
    fields: tuple[str, ...] = ("tag", "reader"),
) -> None:
    """Serve reader connections until interrupted."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(5)
        logger.info("Server listening on %s:%d", host, port)
        try:
            while True:
                client_socket, peer = server_socket.accept()
                threading.Thread(
                    target=handle_client,
                    args=(client_socket, peer),
                    kwargs={"allowed_readers": allowed_readers, "fields": fields},
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            logger.info("Shutting down server")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uhfreader18-server",
        description="Receive autonomous UHFReader18 tag reports over TCP",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=2077)
    parser.add_argument(
        "--allowed-readers",
        type=lambda value: {_reader_address(item.strip()) for item in value.split(",")},
        default=None,
        metavar="HEX,...",
    )
    parser.add_argument("--fields", default="tag,reader")
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    fields = tuple(field.strip() for field in args.fields.split(",") if field.strip())
    unknown = set(fields).difference(AVAILABLE_FIELDS)
    if unknown:
        parser.error(f"unknown fields: {', '.join(sorted(unknown))}")
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(message)s",
    )
    start_server(
        args.host,
        args.port,
        allowed_readers=args.allowed_readers,
        fields=fields,
    )


if __name__ == "__main__":  # pragma: no cover
    main()

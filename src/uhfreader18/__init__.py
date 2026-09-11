# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
"""UHFReader18 command, response, and push-stream protocol library."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("uhfreader18")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.3.0"

from .builder import (
    build_command_frame,
    build_heartbeat,
    build_response_frame,
    build_tag_frame,
    is_heartbeat,
)
from .checksum import compute_checksum, crc16
from .client import (
    ReaderInfo,
    RfidClient,
    RfidResponse,
    WorkModeInfo,
    parse_response,
)
from .constants import (
    Command,
    FrameError,
    FreqBand,
    MemBank,
    Protocol,
    ReaderType,
    Status,
)
from .frame import Frame, Heartbeat, validate_frame
from .stream import ParseResult, StreamBuffer
from .utils import hex_readable

__all__ = [
    "Command",
    "Frame",
    "FrameError",
    "FreqBand",
    "Heartbeat",
    "MemBank",
    "ParseResult",
    "Protocol",
    "ReaderInfo",
    "ReaderType",
    "RfidClient",
    "RfidResponse",
    "Status",
    "StreamBuffer",
    "WorkModeInfo",
    "__version__",
    "build_command_frame",
    "build_heartbeat",
    "build_response_frame",
    "build_tag_frame",
    "compute_checksum",
    "crc16",
    "hex_readable",
    "is_heartbeat",
    "parse_response",
    "validate_frame",
]

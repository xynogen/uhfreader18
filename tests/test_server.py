# pyright: reportMissingImports=false
# ponytail: parent workspace misses nested src layout; package Pyright stays strict.
from __future__ import annotations

from uhfreader18.server import build_parser


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 2077
    assert args.allowed_readers is None
    assert args.fields == "tag,reader"

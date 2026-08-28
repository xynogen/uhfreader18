from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_distribution_metadata() -> None:
    config = (ROOT / "pyproject.toml").read_text()
    for expected in (
        'name = "uhfreader18"',
        'version = "0.1.0"',
        'requires-python = ">=3.10"',
        "dependencies = []",
        'uhfreader18-server = "uhfreader18.server:main"',
    ):
        assert expected in config
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "src/uhfreader18/py.typed").is_file()

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from packaging.version import Version

ROOT = Path(__file__).parents[1]
PYPI_JSON = "https://pypi.org/pypi/uhfreader18/json"


def _local_version() -> str:
    config = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version = "([^"]+)"', config, re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    return match.group(1)


def test_distribution_metadata() -> None:
    config = (ROOT / "pyproject.toml").read_text()
    for expected in (
        'name = "uhfreader18"',
        'requires-python = ">=3.10"',
        "dependencies = []",
        'uhfreader18-server = "uhfreader18.server:main"',
    ):
        assert expected in config
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "src/uhfreader18/py.typed").is_file()


def test_package_version_matches_local() -> None:
    import uhfreader18

    assert uhfreader18.__version__ == _local_version()


def test_version_not_behind_published() -> None:
    """Local version must never be behind the published PyPI version.

    Equal is fine (just released, or between releases); only a local version
    *behind* PyPI is a regression. The "is this exact version already
    published" release gate lives in the publish workflow, not here, so this
    stays green on main after a release.

    Skips when PyPI is unreachable (offline dev) or the package is unpublished.
    """
    try:
        with urllib.request.urlopen(PYPI_JSON, timeout=5) as resp:
            published = json.load(resp)["info"]["version"]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # pragma: no cover
        pytest.skip(f"PyPI unreachable: {exc}")

    assert Version(_local_version()) >= Version(published), (
        f"local version {_local_version()} is behind published {published}"
    )

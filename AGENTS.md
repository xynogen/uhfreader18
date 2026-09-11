# AGENTS.md

Dependency-free Python library for the UHFReader18 reader stack. Two unrelated
protocols share nothing but the hardware:

- `uhfreader18` (top level) — RFID air-interface, command/response + autonomous
  tag push over TCP/RS232/RS485. Spec: `docs/uhfreader18/`.
- `uhfreader18.hwvx` — HW-VX IP-module config over UDP broadcast. Spec:
  `docs/hwvx_module/HWVX.md`, ported from the C# Demo v2.11.

The two protocols use unrelated numbering (baud index `0` = 9600 on the reader,
1200 on the HW-VX module). Never mix their constants.

## Golden rule: the wire is the spec

This is a protocol library. Byte-for-byte output must match the docs / C#
reference. Before changing anything that touches the wire:

1. Read the relevant section of `docs/` first — it is the source of truth.
2. Capture the current wire bytes, lock them in a characterization test, THEN
   refactor. See `test_*_wire_sequence_is_exact` in `tests/test_hwvx_device.py`
   for the pattern. Refactoring without that test is a defect.
3. Expected values in tests come from an independent oracle (published CRC check
   value, a byte literal from the manual, a capture) — never recomputed with the
   function under test. See `test_crc16_matches_published_check_value`.

## Commands (mise)

```
mise run install    # sync .venv (uv pip install -e '.[dev]')
mise run check      # FULL gate: lint + typecheck + test — run before commit
mise run test unit  # pytest (verbose)
mise run typecheck  # pyright --strict — THE authoritative type gate
mise run lint fix   # ruff --fix
mise run format fix # ruff format + lint --fix
```

`mise run typecheck` (pyright with the venv + `pyproject.toml` config) is the
only type gate that counts. A standalone pyright run without the venv reports
spurious "pytest unknown" errors in `tests/` — ignore those; trust `mise run
typecheck`.

## Conventions

- Python 3.10+, `from __future__ import annotations` in every module.
- pyright **strict**, ruff (line 88, `E F W I UP B SIM RUF`). Keep both green.
- Fully typed. `py.typed` ships. Every public function has param + return types.
- Enums carry `__str__ = enum.Enum.__str__` — py3.11+ `IntEnum.__str__` returns
  the number, this restores the name. Don't remove it.
- Input validation lives at the wire boundary (`_require*` in `client.py`,
  `DeviceConfig.validate` in hwvx). Never simplify these away.
- `ponytail:` comments mark deliberate simplifications with a named ceiling —
  respect them, don't silently "fix".

## Release (CI/CD, do not publish locally)

Trusted publishing via OIDC. Push a tag `vX.Y.Z` → `.github/workflows/publish.yml`
runs CI → build → PyPI. No twine, no tokens locally.

- Bump `version` in `pyproject.toml` AND the fallback in
  `src/uhfreader18/__init__.py` (both must match; a test enforces it).
- We are 0.x: breaking change → minor, else patch. Removing/renaming an exported
  symbol IS breaking.
- Update `CHANGELOG.md` in the same commit.
- Tag/publish is irreversible — a PyPI version can never be re-used. Confirm before
  pushing a tag.

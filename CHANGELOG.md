# Changelog

## 0.2.1

- Expose `__version__` on top-level `uhfreader18` package.
- Consolidate Pyright configuration into `pyproject.toml`.
- Expand test coverage for CLI parser, client handler, frame helpers, and checksum.
- Update GitHub Actions workflow action dependencies.

## 0.2.0

- Add reader-config wrappers on `RfidClient`, covering every reader-defined
  command (0x22-0x3B): `set_region`, `set_baud_rate`, `acousto_optic_control`,
  `set_wiegand`, `set_work_mode`, `get_work_mode`, `set_eas_accuracy`,
  `set_syris_response_offset`, `set_trigger_offset`.
- Add `WorkModeInfo` dataclass for the Get WorkMode (0x36) response.
- Cover `RfidClient` to 100% (error-status, range, and defensive branches).
- Adopt mise for tooling and CI (`mise.toml`, `jdx/mise-action`).

  Tag operations (0x01-0x10 EPC C1G2, 0x50-0x55 18000-6B) remain out of scope;
  this release wraps reader configuration only.

## 0.1.0

- Add UHFReader18 command and response frame codecs.
- Add synchronous `RfidClient` reader operations.
- Add CRC-validated TCP stream reassembly.
- Add autonomous tag-report and heartbeat parsing.
- Add `uhfreader18-server` receive CLI.

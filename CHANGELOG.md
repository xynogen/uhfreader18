# Changelog

## 0.5.0

**Breaking:** strongly-typed models with input validation everywhere.

### Reader (`RfidClient`)

- **Enum parameters replace magic bytes**: `set_baud_rate(baud: ReaderBaudRate)`,
  `set_region(band: FreqBand, max_index, min_index)`,
  `set_wiegand(wg_format: WiegandFormat, ...)`,
  `set_work_mode(work_mode: WorkMode, state: ModeState, mem_inven: MemInven, ...)`.
  A bare `int` where an enum is expected raises `TypeError` at runtime.
- New `ReaderBaudRate` enum (`BAUD_9600=0 … BAUD_115200=6`, `.bps`).
- `FreqBand` gains `.max_index`, `.frequency_mhz(n)`, `.pack()` / `.unpack()`.
  `set_region` packs the band into bit7-6 itself and validates the index
  against the band's actual channel count.
- `ReaderInfo` / `WorkModeInfo` are now decoded at construction
  (`from_bytes()`); fields are typed (`ReaderType | None`, `Protocol`,
  `FreqBand | None`, `WorkMode`, `ModeState`, `MemInven | None`, …).
  Unknown firmware codes → `None`, not an exception (Postel's law).
  Old int properties (`.max_band`, `.state_flags`, `.mem_target`, etc.) removed;
  use the typed fields directly. `raw` byte payload kept for debugging.
- **Input validation at every boundary**: `_require_range` rejects `bool`,
  `float`, `str` where `int` is expected. `scan_time` enforced 3–255 (manual
  8.4.4). `pulse_width` / `pulse_interval` enforced ≥ 1. `word_num` range
  depends on `ModeState.SYRIS_485` (1–32 normal, 1–4 Syris). `adr` validated
  0–255 in `_send_command`.

### HW-VX module (`uhfreader18.hwvx`)

- `DeviceConfig` fields hold real types: `IPv4Address` for addresses, `int` for
  ports and counters, and the module enums (`NetProtocol`, `NetWorkMode`,
  `BaudRate`, `Parity`, `DataBits`, `Toggle`) for every option. Assign the
  enum member directly; `"7"`-style strings are rejected by `validate()`.
- `SearchResult.ip_address` is `IPv4Address | None`; `port_number` is `int`.
- `HwVxDevice(ip_address: IPv4Address, ...)` and
  `change_network(new_ip, subnet_mask, gateway_ip)` take `IPv4Address`.
- Add `DeviceConfig.from_wire()` / `to_wire()`: the only two places protocol
  strings are interpreted. `get_config()` raises `ValueError` naming every
  field the firmware returned in a form the model cannot represent.
- Fix: assigning an `IntEnum` to a config field previously serialized its
  *name* (`SBRBaudRate.BAUD_115200`) instead of its value (`SBR7`).

## 0.4.0

- Add `WorkMode`, `WiegandFormat` (bitfield), `ModeState` (bitfield), and
  `MemInven` enums.
- Decode `WorkModeInfo` bytes via properties: `work_mode`, `wiegand_format`,
  `state_flags`, `mem_target`.
- Add `uhfreader18.hwvx` sub-package for the HW-VX IP module (UDP config
  protocol): `HwVxDevice`, `HwVxNetworking`, `DeviceConfig`, `SearchResult`,
  `SETTINGS`, `UDP_PORT`, and the `NetProtocol`, `NetWorkMode`, `BaudRate`
  (`.bps`), `Parity`, `DataBits` (`.count`), `Toggle` enums.
- Enum `str()` now returns the member name instead of the numeric value
  (restores pre-Python-3.11 behaviour) for all enums.
- Split `docs/` per protocol: `docs/uhfreader18/` (RFID air-interface) and
  `docs/hwvx_module/` (HW-VX UDP config).
- Rewrite README as a full reference: two-protocol overview, method tables, and
  a complete API listing for both packages.

## 0.3.0

- Add `ReaderType`, `Protocol` (bitfield), and `FreqBand` enums.
- Decode reader-info bytes via `ReaderInfo` properties: `reader_model`,
  `protocols`, `max_band`/`min_band`, `max_freq_index`/`min_freq_index`.

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

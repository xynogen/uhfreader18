# Changelog

## Unreleased

- Add reader-config wrappers on `RfidClient`: `set_region`, `set_baud_rate`,
  `acousto_optic_control`, `set_wiegand`, `set_work_mode`, `get_work_mode`,
  `set_eas_accuracy`, `set_syris_response_offset`, `set_trigger_offset`.
- Add `WorkModeInfo` dataclass for the Get WorkMode (0x36) response.

## 0.1.0

- Add UHFReader18 command and response frame codecs.
- Add synchronous `RfidClient` reader operations.
- Add CRC-validated TCP stream reassembly.
- Add autonomous tag-report and heartbeat parsing.
- Add `uhfreader18-server` receive CLI.

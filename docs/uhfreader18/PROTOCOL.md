# RFID Reader — TCP Push Protocol (Port 2077)

The reader initiates a TCP connection to the host on port **2077** and pushes tag reports autonomously. The host only sends TCP ACKs — no commands are issued over this channel.

See [`DOCUMENTATION.md`](DOCUMENTATION.md) for the full command/response protocol (RS232/RS485).

## Tag Report Frame (18 bytes)

| Offset | Field | Value |
|--------|-------|-------|
| 0 | Len | `0x11` — 17 remaining bytes |
| 1 | Adr | Reader address (default `0x00`) |
| 2 | reCmd | `0xEE` — tag report |
| 3 | Status | `0x00` — success |
| 4–15 | EPC | 8-byte EPC + 4 zero padding |
| 16 | CRC-16 LSB | CRC low byte |
| 17 | CRC-16 MSB | CRC high byte |

## CRC-16 Verification

CRC-16/CCITT reflected, computed over bytes 0–15 (Len through EPC). Stored little-endian.

```
PRESET_VALUE = 0xFFFF
POLYNOMIAL   = 0x8408
```

A frame is valid when CRC computed over all 18 bytes yields `0x0000`.

## Heartbeat

`56 00 00 00 00 00`, six bytes, sent every ~30 seconds. `0x56` is also a
legal length byte (86), so only the exact six-byte sequence is a heartbeat.

## Capture

[`captures/read_stream.pcapng`](captures/read_stream.pcapng): one tag
(EPC `708C2B380B2D`) pushed twice from an HW-VX6330K, host passive.

```
11 00 EE 00 20 00 70 8C 2B 38 0B 2D 00 00 00 00 E0 56
│  │  │  │  │     └─ EPC: 708C2B380B2D ──────┘  └─ CRC (LE)
│  │  │  │  └─ flags/antenna
│  │  │  └─ status: OK
│  │  └─ command: 0xEE (tag report)
│  └─ reader address: 0x00
└─ length: 17 remaining bytes
```

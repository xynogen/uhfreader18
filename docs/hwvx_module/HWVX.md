# HW-VX IP Module — UDP Configuration Protocol

The HW-VX6330K / HW-VX6346KL is the TCP/IP bridge module that fronts the
reader. It is configured over **UDP port 65535** with an ASCII setting
protocol, separate from the reader's RFID air-interface
([`../uhfreader18/DOCUMENTATION.md`](../uhfreader18/DOCUMENTATION.md), [`../uhfreader18/PROTOCOL.md`](../uhfreader18/PROTOCOL.md)).

> The two protocols use unrelated numbering. Example: baud-rate index `0`
> means 9600 on the reader (`0x28`) but 1200 on the HW-VX module (`BR`).

Everything here lives in the `uhfreader18.hwvx` sub-package.

## Protocol Overview

Commands are ASCII strings; every reply is prefixed with `A`.

```
Client                          Module
  │──── X (broadcast) ───────────>│  Search / echo
  │<─── A{mac}/{port}/… ──────────│  Reply
  │──── W{mac} ──────────────────>│  Select
  │<─── A… ───────────────────────│
  │──── L ───────────────────────>│  Login
  │<─── A… ───────────────────────│
  │──── G{code}|{seq} ───────────>│  Get setting
  │<─── A{value}|{seq} ───────────│
  │──── S{code}{value}|{seq} ────>│  Set setting
  │<─── A… ───────────────────────│
  │──── E ───────────────────────>│  Reboot
```

The `|{seq}` suffix is a sequence token used to match a reply to its
request (`request_single`).

## Quick Start

```python
from uhfreader18.hwvx import HwVxDevice, HwVxNetworking

# Discover every module on the LAN.
with HwVxNetworking() as net:
    for r in net.search():
        print(r.ip_address, r.mac_address, r.device_name)

# Read and change a device's configuration.
with HwVxDevice("192.168.1.100") as dev:
    dev.connect()
    cfg = dev.get_config()
    cfg.remote_ip = "192.168.1.50"
    cfg.work_mode = "1"          # NetWorkMode.CLIENT
    dev.save_config(cfg)         # writes all settings, then reboots
```

## `HwVxNetworking`

Low-level UDP transport. Context-manager capable.

```python
HwVxNetworking(ip_address: str = "255.255.255.255")
```

| Method | Description |
|---|---|
| `send(command)` | Send a raw ASCII command packet. |
| `receive() -> str` | Block until a packet arrives or timeout; `""` on timeout. |
| `request(command, retries=5) -> str` | Send and wait for an `A`-reply; returns the body with `A` stripped. Raises `TimeoutError`. |
| `request_single(command, check) -> str` | Send `command\|check`, expect `A{value}\|{check}`; returns *value*. Raises `ValueError` on mismatch. `check` is a zero-padded 2-digit uppercase hex token. |
| `search() -> list[SearchResult]` | Broadcast `X` and collect all module replies. |
| `search_targets(ip_addresses) -> list[SearchResult]` | Unicast the echo to each address; used for CIDR sweeps when broadcast can't reach the module. |
| `close()` | Close the socket. |

## `HwVxDevice`

High-level flows built on `HwVxNetworking`. Context-manager capable.

```python
HwVxDevice(
    ip_address: str,
    *,
    mac_address: str = "",
    broadcast: bool = False,
    broadcast_ip: str = "255.255.255.255",
)
```

Passing a known `mac_address` skips re-discovery. `broadcast=True` sends via
the broadcast address (useful when the module IP is about to change).

| Method | Description |
|---|---|
| `connect() -> SearchResult` | Search, select (`W{mac}`), and login (`L`). Raises `ConnectionError` if no module answers. |
| `get_config() -> DeviceConfig` | Read all settings (one `G{code}` per field). |
| `save_config(cfg)` | Write every setting, then reboot. Retries via broadcast if the IP changes mid-save. |
| `change_network(new_ip, subnet_mask, gateway_ip)` | Change IP/mask/gateway and reboot. |
| `set_dhcp(enabled)` | Enable or disable DHCP and reboot. |
| `reboot()` | Send the reboot command (`E`). |
| `close()` | Close the underlying transport. |

## Data Models

### `SearchResult`

```python
@dataclass
class SearchResult:
    mac_address: str = ""
    port_number: str = ""
    ip_address: str = ""
    username: str = ""
    device_name: str = ""
```

### `DeviceConfig`

All 22 read/writeable settings, each stored as a string. Numeric fields hold
an enum value as a string (e.g. `protocol="1"` → `NetProtocol.TCP`); use the
enums below to interpret or build them. `DeviceConfig.validate()` returns a
list of human-readable errors (empty when valid).

| Group | Fields |
|---|---|
| Network | `username`, `device_name`, `mac_address`, `ip_address`, `port_number`, `protocol`, `work_mode`, `remote_ip`, `remote_port`, `gateway_ip`, `subnet_mask`, `dhcp` |
| Serial | `baud_rate`, `parity`, `data_bits`, `dtr_mode`, `rts` |
| Advanced | `connection_mode`, `connection_timeout`, `reconnect`, `max_length`, `max_delay` |

## Enums

`str()` on any member returns its name; `int()` / `.value` returns the wire
value used in `DeviceConfig`.

| Enum | Members | Notes |
|---|---|---|
| `NetProtocol` | `UDP=0`, `TCP=1` | |
| `NetWorkMode` | `SERVER=0`, `CLIENT=1` | |
| `BaudRate` | `0`–`7` | `.bps` → 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 |
| `Parity` | `NONE=0`, `EVEN=1`, `ODD=2`, `MARK=3`, `SPACE=4` | |
| `DataBits` | `SEVEN=0`, `EIGHT=1` | `.count` → 7, 8 |
| `Toggle` | `DISABLED=0`, `ENABLED=1` | DHCP, DTR, RTS |

## Setting Codes (`SETTINGS`)

Two-letter codes used in `G{code}` / `S{code}{value}` commands.

| Group | Codes |
|---|---|
| Network | `ON` username, `DN` device name, `FE` MAC, `IP` address, `PN` port, `TP` protocol, `RM` work mode, `DI` remote IP, `DP` remote port, `GI` gateway, `NM` subnet mask, `DH` DHCP |
| Serial | `BR` baud rate, `PR` parity, `BB` data bits, `DT` DTR, `FC` RTS |
| Advanced | `CM` connection mode, `CT` connection timeout, `RC` reconnect, `ML` max length, `MD` max delay |

Also exported: `UDP_PORT` (65535), `RECV_TIMEOUT` (1.0 s), `RECV_BUFFER`
(1024 bytes).

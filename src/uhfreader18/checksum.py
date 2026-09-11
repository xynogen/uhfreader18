"""UHFReader18 CRC-16/CCITT-reflected checksum."""

from __future__ import annotations

from .constants import CRC_POLYNOMIAL, CRC_PRESET


def crc16(data: bytes) -> int:
    """Return raw CRC-16 for payload bytes, stored little-endian on wire."""
    crc = CRC_PRESET
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ CRC_POLYNOMIAL if crc & 1 else crc >> 1
    return crc & 0xFFFF

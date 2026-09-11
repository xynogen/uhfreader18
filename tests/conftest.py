"""Shared fixtures for the test suite."""

from __future__ import annotations

from ipaddress import IPv4Address

import pytest

from uhfreader18.hwvx import (
    BaudRate,
    DataBits,
    DeviceConfig,
    NetProtocol,
    NetWorkMode,
    Parity,
    SearchResult,
    Toggle,
)


@pytest.fixture()
def sample_search_result() -> SearchResult:
    """A typical search result from a reader."""
    return SearchResult(
        mac_address="AA:BB:CC:DD:EE:FF",
        port_number=4196,
        ip_address=IPv4Address("192.168.1.100"),
        username="admin",
        device_name="HW-VX6330K",
    )


@pytest.fixture()
def sample_config() -> DeviceConfig:
    """A fully-populated, valid device configuration."""
    return DeviceConfig(
        username="admin",
        device_name="HW-VX6330K",
        mac_address="AA:BB:CC:DD:EE:FF",
        ip_address=IPv4Address("192.168.1.100"),
        port_number=4196,
        protocol=NetProtocol.UDP,
        work_mode=NetWorkMode.SERVER,
        remote_ip=IPv4Address("192.168.1.1"),
        remote_port=5000,
        gateway_ip=IPv4Address("192.168.1.1"),
        subnet_mask=IPv4Address("255.255.255.0"),
        dhcp=Toggle.DISABLED,
        baud_rate=BaudRate.BAUD_9600,
        parity=Parity.NONE,
        data_bits=DataBits.EIGHT,
        dtr_mode=Toggle.DISABLED,
        rts=Toggle.DISABLED,
        connection_mode=Toggle.DISABLED,
        connection_timeout=0,
        reconnect=0,
        max_length=1024,
        max_delay=0,
    )


@pytest.fixture()
def sample_wire() -> dict[str, str]:
    """The same configuration as ``sample_config``, as the device sends it."""
    return {
        "username": "admin",
        "device_name": "HW-VX6330K",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "ip_address": "192.168.1.100",
        "port_number": "4196",
        "protocol": "0",
        "work_mode": "0",
        "remote_ip": "192.168.1.1",
        "remote_port": "5000",
        "gateway_ip": "192.168.1.1",
        "subnet_mask": "255.255.255.0",
        "dhcp": "0",
        "baud_rate": "3",
        "parity": "0",
        "data_bits": "1",
        "dtr_mode": "0",
        "rts": "0",
        "connection_mode": "0",
        "connection_timeout": "0",
        "reconnect": "0",
        "max_length": "1024",
        "max_delay": "0",
    }

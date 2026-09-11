"""Shared fixtures for the test suite."""

from __future__ import annotations

import pytest

from uhfreader18.hwvx import DeviceConfig, SearchResult


@pytest.fixture()
def sample_search_result() -> SearchResult:
    """A typical search result from a reader."""
    return SearchResult(
        mac_address="AA:BB:CC:DD:EE:FF",
        port_number="4196",
        ip_address="192.168.1.100",
        username="admin",
        device_name="HW-VX6330K",
    )


@pytest.fixture()
def sample_config() -> DeviceConfig:
    """A fully-populated device configuration."""
    return DeviceConfig(
        username="admin",
        device_name="HW-VX6330K",
        mac_address="AA:BB:CC:DD:EE:FF",
        ip_address="192.168.1.100",
        port_number="4196",
        protocol="0",
        work_mode="0",
        remote_ip="192.168.1.1",
        remote_port="5000",
        gateway_ip="192.168.1.1",
        subnet_mask="255.255.255.0",
        dhcp="0",
        baud_rate="3",
        parity="0",
        data_bits="1",
        dtr_mode="0",
        rts="0",
        connection_mode="0",
        connection_timeout="0",
        reconnect="0",
        max_length="1024",
        max_delay="0",
    )

"""Tests for uhfreader18.hwvx data models and the wire boundary."""

from dataclasses import fields, replace
from ipaddress import IPv4Address
from typing import Any

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


class TestSearchResult:
    def test_defaults(self) -> None:
        r = SearchResult()
        assert r.mac_address == ""
        assert r.port_number == 0
        assert r.ip_address is None
        assert r.username == ""
        assert r.device_name == ""

    def test_construction(self, sample_search_result: SearchResult) -> None:
        assert sample_search_result.ip_address == IPv4Address("192.168.1.100")
        assert sample_search_result.port_number == 4196
        assert sample_search_result.mac_address == "AA:BB:CC:DD:EE:FF"

    def test_equality(self) -> None:
        ip = IPv4Address("1.2.3.4")
        assert SearchResult(mac_address="AA", ip_address=ip) == SearchResult(
            mac_address="AA", ip_address=ip
        )
        assert SearchResult(mac_address="AA") != SearchResult(mac_address="BB")


class TestDeviceConfig:
    def test_defaults_are_typed(self) -> None:
        cfg = DeviceConfig()
        assert cfg.ip_address == IPv4Address("0.0.0.0")
        assert cfg.subnet_mask == IPv4Address("255.255.255.0")
        assert cfg.port_number == 0
        assert cfg.protocol is NetProtocol.TCP
        assert cfg.work_mode is NetWorkMode.SERVER
        assert cfg.baud_rate is BaudRate.BAUD_9600
        assert cfg.parity is Parity.NONE
        assert cfg.data_bits is DataBits.EIGHT
        assert cfg.dhcp is Toggle.DISABLED

    def test_field_count(self) -> None:
        """Ensure we haven't accidentally lost fields during refactoring."""
        assert len(fields(DeviceConfig())) == 22

    def test_construction(self, sample_config: DeviceConfig) -> None:
        assert sample_config.ip_address == IPv4Address("192.168.1.100")
        assert sample_config.baud_rate is BaudRate.BAUD_9600
        assert sample_config.subnet_mask == IPv4Address("255.255.255.0")


class TestWireBoundary:
    """from_wire / to_wire are the only places strings are interpreted."""

    def test_from_wire_builds_typed_config(
        self, sample_wire: dict[str, str], sample_config: DeviceConfig
    ) -> None:
        assert DeviceConfig.from_wire(sample_wire) == sample_config

    def test_to_wire_round_trips(
        self, sample_wire: dict[str, str], sample_config: DeviceConfig
    ) -> None:
        assert sample_config.to_wire() == sample_wire

    def test_to_wire_uses_enum_value_not_name(self) -> None:
        cfg = DeviceConfig(port_number=1, remote_port=1, baud_rate=BaudRate.BAUD_115200)
        wire = cfg.to_wire()
        assert wire["baud_rate"] == "7"  # NOT "BaudRate.BAUD_115200"
        assert wire["ip_address"] == "0.0.0.0"

    def test_from_wire_ignores_unknown_keys(self, sample_wire: dict[str, str]) -> None:
        sample_wire["not_a_field"] = "x"
        DeviceConfig.from_wire(sample_wire)  # must not raise

    def test_from_wire_missing_keys_use_defaults(self) -> None:
        cfg = DeviceConfig.from_wire({"username": "u"})
        assert cfg.username == "u"
        assert cfg.baud_rate is BaudRate.BAUD_9600

    @pytest.mark.parametrize(
        ("field", "bad", "needle"),
        [
            ("ip_address", "999.1.1.1", "ip_address"),
            ("subnet_mask", "not-an-ip", "subnet_mask"),
            ("gateway_ip", "1.2.3", "gateway_ip"),
            ("remote_ip", "", "remote_ip"),
            ("port_number", "abc", "not an integer"),
            ("protocol", "2", "not in \\[0, 1\\]"),
            ("work_mode", "5", "not in"),
            ("dhcp", "9", "not in"),
            ("baud_rate", "8", "not in"),
            ("parity", "5", "not in"),
            ("data_bits", "2", "not in"),
            ("dtr_mode", "3", "not in"),
            ("rts", "3", "not in"),
            ("connection_mode", "3", "not in"),
            ("reconnect", "x", "not an integer"),
            ("max_length", "1.5", "not an integer"),
            # unicode digit: isdigit() True, int() fails
            ("max_delay", "²", "not an integer"),
        ],
    )
    def test_from_wire_rejects_bad_device_values(
        self, sample_wire: dict[str, str], field: str, bad: str, needle: str
    ) -> None:
        sample_wire[field] = bad
        with pytest.raises(ValueError, match=needle):
            DeviceConfig.from_wire(sample_wire)

    def test_from_wire_reports_all_errors_at_once(
        self, sample_wire: dict[str, str]
    ) -> None:
        sample_wire.update(ip_address="bad", port_number="x", baud_rate="9")
        with pytest.raises(ValueError) as exc:
            DeviceConfig.from_wire(sample_wire)
        msg = str(exc.value)
        assert "ip_address" in msg
        assert "port_number" in msg
        assert "baud_rate" in msg


class TestDeviceConfigValidate:
    """validate() is the pre-send trust boundary for typed values."""

    def test_valid_config_passes(self, sample_config: DeviceConfig) -> None:
        sample_config.validate()  # must not raise

    @pytest.mark.parametrize(
        ("field", "bad", "needle"),
        [
            ("port_number", 0, "1-65535"),
            ("port_number", 70000, "1-65535"),
            ("remote_port", 0, "1-65535"),
            ("connection_timeout", -1, "non-negative"),
            ("reconnect", -5, "non-negative"),
        ],
    )
    def test_out_of_range_rejected(
        self, sample_config: DeviceConfig, field: str, bad: int, needle: str
    ) -> None:
        cfg = replace(sample_config, **{field: bad})
        with pytest.raises(ValueError, match=needle):
            cfg.validate()

    @pytest.mark.parametrize(
        ("field", "bad", "expected"),
        [
            ("ip_address", "192.168.1.1", "IPv4Address"),  # str, not IPv4Address
            ("baud_rate", "7", "BaudRate"),  # str, not enum
            ("baud_rate", 7, "BaudRate"),  # bare int, not enum
            ("port_number", "4196", "int"),
            ("dhcp", True, "Toggle"),  # bool is not a Toggle
        ],
    )
    def test_wrong_type_rejected_instead_of_corrupting_wire(
        self, sample_config: DeviceConfig, field: str, bad: Any, expected: str
    ) -> None:
        """Annotations are not enforced at runtime; validate() must be."""
        cfg = replace(sample_config, **{field: bad})
        with pytest.raises(ValueError, match=f"{field}: .* must be {expected}"):
            cfg.validate()

    def test_pipe_rejected(self, sample_config: DeviceConfig) -> None:
        cfg = replace(sample_config, username="a|b")
        with pytest.raises(ValueError, match="must not contain"):
            cfg.validate()

    def test_non_ascii_rejected(self, sample_config: DeviceConfig) -> None:
        cfg = replace(sample_config, device_name="café")
        with pytest.raises(ValueError, match="must be ASCII"):
            cfg.validate()

    def test_reports_all_errors_at_once(self, sample_config: DeviceConfig) -> None:
        cfg = replace(sample_config, username="a|b", port_number=0, baud_rate="9")
        with pytest.raises(ValueError) as exc:
            cfg.validate()
        msg = str(exc.value)
        assert "username" in msg
        assert "port_number" in msg
        assert "baud_rate" in msg


class TestNetworkModuleEnums:
    def test_baud_bps(self) -> None:
        assert BaudRate.BAUD_115200.bps == 115200
        assert BaudRate(3).bps == 9600

    def test_data_bits_count(self) -> None:
        assert DataBits.SEVEN.count == 7
        assert DataBits.EIGHT.count == 8

    def test_str_returns_name(self) -> None:
        assert str(NetProtocol.TCP) == "NetProtocol.TCP"
        assert str(NetWorkMode.CLIENT) == "NetWorkMode.CLIENT"
        assert str(Parity.EVEN) == "Parity.EVEN"

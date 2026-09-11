"""Tests for uhfreader18.hwvx."""

from dataclasses import fields, replace

import pytest

from uhfreader18.hwvx import DeviceConfig, SearchResult


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_defaults(self) -> None:
        r = SearchResult()
        assert r.mac_address == ""
        assert r.port_number == ""
        assert r.ip_address == ""
        assert r.username == ""
        assert r.device_name == ""

    def test_construction(self, sample_search_result: SearchResult) -> None:
        assert sample_search_result.ip_address == "192.168.1.100"
        assert sample_search_result.mac_address == "AA:BB:CC:DD:EE:FF"

    def test_equality(self) -> None:
        a = SearchResult(mac_address="AA", ip_address="1.2.3.4")
        b = SearchResult(mac_address="AA", ip_address="1.2.3.4")
        assert a == b

    def test_inequality(self) -> None:
        a = SearchResult(mac_address="AA")
        b = SearchResult(mac_address="BB")
        assert a != b


class TestDeviceConfig:
    """Tests for the DeviceConfig dataclass."""

    def test_defaults_all_empty_strings(self) -> None:
        cfg = DeviceConfig()
        for f in fields(cfg):
            assert getattr(cfg, f.name) == "", f"Field {f.name} should default to ''"

    def test_field_count(self) -> None:
        """Ensure we haven't accidentally lost fields during refactoring."""
        assert len(fields(DeviceConfig())) == 22

    def test_construction(self, sample_config: DeviceConfig) -> None:
        assert sample_config.ip_address == "192.168.1.100"
        assert sample_config.baud_rate == "3"
        assert sample_config.subnet_mask == "255.255.255.0"


class TestDeviceConfigValidate:
    """Tests for DeviceConfig.validate() — the pre-send trust boundary."""

    def test_valid_config_passes(self, sample_config: DeviceConfig) -> None:
        sample_config.validate()  # must not raise

    @pytest.mark.parametrize(
        ("field", "bad", "needle"),
        [
            ("ip_address", "999.1.1.1", "valid IPv4"),
            ("subnet_mask", "not-an-ip", "valid IPv4"),
            ("gateway_ip", "1.2.3", "valid IPv4"),
            ("remote_ip", "", "valid IPv4"),
            ("port_number", "0", "1-65535"),
            ("port_number", "70000", "1-65535"),
            ("remote_port", "abc", "1-65535"),
            ("protocol", "2", "not in"),
            ("work_mode", "5", "not in"),
            ("dhcp", "9", "not in"),
            ("baud_rate", "8", "not in"),
            ("parity", "5", "not in"),
            ("data_bits", "2", "not in"),
            ("dtr_mode", "3", "not in"),
            ("rts", "3", "not in"),
            ("connection_mode", "3", "not in"),
            ("connection_timeout", "-1", "non-negative"),
            ("reconnect", "x", "non-negative"),
            ("max_length", "1.5", "non-negative"),
            (
                "max_delay",
                "²",
                "non-negative",
            ),  # unicode digit: isdigit() True, int() fails
        ],
    )
    def test_bad_field_rejected(
        self, sample_config: DeviceConfig, field: str, bad: str, needle: str
    ) -> None:
        cfg = replace(sample_config, **{field: bad})
        with pytest.raises(ValueError, match=needle):
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
        cfg = replace(sample_config, ip_address="bad", port_number="0", baud_rate="9")
        with pytest.raises(ValueError) as exc:
            cfg.validate()
        msg = str(exc.value)
        assert "ip_address" in msg
        assert "port_number" in msg
        assert "baud_rate" in msg


class TestNetworkModuleEnums:
    def test_baud_bps(self) -> None:
        from uhfreader18.hwvx import BaudRate

        assert BaudRate.BAUD_115200.bps == 115200
        assert BaudRate(3).bps == 9600

    def test_data_bits_count(self) -> None:
        from uhfreader18.hwvx import DataBits

        assert DataBits.SEVEN.count == 7
        assert DataBits.EIGHT.count == 8

    def test_str_returns_name(self) -> None:
        from uhfreader18.hwvx import NetProtocol, NetWorkMode, Parity

        assert str(NetProtocol.TCP) == "NetProtocol.TCP"
        assert str(NetWorkMode.CLIENT) == "NetWorkMode.CLIENT"
        assert str(Parity.EVEN) == "Parity.EVEN"

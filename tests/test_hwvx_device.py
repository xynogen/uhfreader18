"""Tests for uhfreader18.hwvx.device — transport layer is mocked."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import IPv4Address
from unittest.mock import MagicMock, call, patch

import pytest

from uhfreader18.hwvx import BaudRate, DeviceConfig, SearchResult
from uhfreader18.hwvx.device import HwVxDevice

DEVICE_IP = IPv4Address("192.168.1.100")
NEW_IP = IPv4Address("10.0.0.50")
NEW_MASK = IPv4Address("255.255.0.0")
NEW_GW = IPv4Address("10.0.0.1")


@pytest.fixture()
def mock_transport() -> MagicMock:
    """A fully mocked HwVxNetworking instance."""
    transport = MagicMock()
    transport.search.return_value = [
        SearchResult(
            mac_address="AA:BB:CC:DD:EE:FF",
            port_number=4196,
            ip_address=DEVICE_IP,
        )
    ]
    transport.request.return_value = "OK"
    return transport


@pytest.fixture()
def device(mock_transport: MagicMock) -> HwVxDevice:
    """HwVxDevice with mocked transport."""
    with patch("uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport):
        dev = HwVxDevice(DEVICE_IP)
    return dev


class TestConnect:
    def test_directed_broadcast_uses_requested_target(
        self, mock_transport: MagicMock
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            HwVxDevice(
                DEVICE_IP,
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
                broadcast_ip=IPv4Address("10.10.0.255"),
            )

        networking.assert_called_once_with("10.10.0.255")

    def test_broadcast_with_known_mac_skips_second_scan(
        self, mock_transport: MagicMock
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            dev = HwVxDevice(
                DEVICE_IP,
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )

        result = dev.connect()

        networking.assert_called_once_with("255.255.255.255")
        mock_transport.search.assert_not_called()
        mock_transport.request.assert_any_call("WAA:BB:CC:DD:EE:FF", retries=3)
        assert result.ip_address == DEVICE_IP

    def test_sets_mac_from_search(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        result = device.connect()
        assert device.mac == "AA:BB:CC:DD:EE:FF"
        assert result.ip_address == DEVICE_IP

    def test_sends_select_and_login(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        device.connect()
        mock_transport.request.assert_any_call("WAA:BB:CC:DD:EE:FF", retries=3)
        mock_transport.request.assert_any_call("L", retries=3)

    def test_raises_on_no_readers(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        mock_transport.search.return_value = []
        with pytest.raises(ConnectionError, match="No reader found"):
            device.connect()


# GET check token -> wire value, as the device would answer.
_DEVICE_ANSWERS = {
    "01": "admin",
    "02": "MyDevice",
    "03": "AA:BB",
    "04": "192.168.1.100",
    "05": "4196",
    "06": "0",
    "07": "0",
    "08": "0",
    "09": "60",
    "0A": "0",
    "0B": "0",
    "0C": "3",
    "0D": "0",
    "0E": "1",
    "0F": "0",
    "10": "1024",
    "11": "0",
    "12": "192.168.1.1",
    "13": "5000",
    "14": "192.168.1.1",
    "15": "255.255.255.0",
    "16": "0",
}


def _answer_from(table: dict[str, str]) -> Callable[[str, str], str]:
    """Build a ``request_single`` side effect that answers by check token."""

    def answer(_cmd: str, check: str) -> str:
        return table[check]

    return answer


class TestGetConfig:
    def test_reads_all_settings_as_typed_values(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        mock_transport.request_single.side_effect = _answer_from(_DEVICE_ANSWERS)

        device.connect()
        cfg = device.get_config()

        assert cfg.username == "admin"
        assert cfg.device_name == "MyDevice"
        assert cfg.ip_address == DEVICE_IP
        assert cfg.baud_rate is BaudRate.BAUD_9600
        assert cfg.subnet_mask == IPv4Address("255.255.255.0")
        assert cfg.connection_timeout == 60
        assert mock_transport.request_single.call_count == 22

    def test_sends_get_command_with_matching_check(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        mock_transport.request_single.side_effect = _answer_from(_DEVICE_ANSWERS)
        device.connect()
        device.get_config()
        mock_transport.request_single.assert_any_call("GBR", "0C")
        mock_transport.request_single.assert_any_call("GIP", "04")

    def test_surfaces_unparseable_device_value(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        answers = {**_DEVICE_ANSWERS, "0C": "9"}  # baud index 9 does not exist
        mock_transport.request_single.side_effect = _answer_from(answers)
        device.connect()
        with pytest.raises(ValueError, match="baud_rate: '9'"):
            device.get_config()


class TestSaveConfig:
    def test_broadcast_mode_does_not_repeat_config_pass(
        self, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            dev = HwVxDevice(
                DEVICE_IP,
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )
            dev.save_config(sample_config)

        networking.assert_called_once_with("255.255.255.255")
        assert mock_transport.send.call_count == 22  # L + 20 settings + E

    def test_serializes_enum_values_not_names(
        self, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        sample_config.baud_rate = BaudRate.BAUD_115200
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ):
            dev = HwVxDevice(DEVICE_IP, mac_address="AA", broadcast=True)
            dev.save_config(sample_config)

        cmds = [c[0][0] for c in mock_transport.send.call_args_list]
        assert "SBR7|19" in cmds
        assert "SIP192.168.1.100|25" in cmds
        assert not any("BaudRate." in c for c in cmds)

    def test_ip_is_last_setting_written(
        self, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        """IP must change last or the unicast channel dies mid-save."""
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ):
            HwVxDevice(DEVICE_IP, mac_address="AA", broadcast=True).save_config(
                sample_config
            )
        cmds = [c[0][0] for c in mock_transport.send.call_args_list]
        settings = [c for c in cmds if c.startswith("S")]
        assert settings[-1].startswith("SIP")

    def test_invalid_config_sends_nothing(
        self, device: HwVxDevice, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        sample_config.port_number = 0
        with pytest.raises(ValueError):
            device.save_config(sample_config)
        mock_transport.send.assert_not_called()

    def test_sends_login_and_reboot(
        self, device: HwVxDevice, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        device.mac = "AA:BB:CC:DD:EE:FF"

        with patch("uhfreader18.hwvx.device.HwVxNetworking") as mock_net:
            broadcast_mock = MagicMock()
            mock_net.return_value = broadcast_mock
            broadcast_mock.__enter__ = MagicMock(return_value=broadcast_mock)
            broadcast_mock.__exit__ = MagicMock(return_value=False)

            device.save_config(sample_config)

        # Unicast pass should start with login
        send_calls = [c for c in mock_transport.send.call_args_list]
        assert send_calls[0] == call("L")
        # Last unicast call should be reboot
        unicast_commands = [c[0][0] for c in send_calls]
        assert "E" in unicast_commands


class TestChangeNetwork:
    def _run(
        self,
        device: HwVxDevice,
        mock_transport: MagicMock,
    ) -> tuple[list[str], MagicMock]:
        """Call change_network and return (unicast_cmds, broadcast_mock)."""
        device.mac = "AA:BB:CC:DD:EE:FF"
        mock_transport.receive.return_value = ""

        broadcast_mock = MagicMock()
        broadcast_mock.__enter__ = MagicMock(return_value=broadcast_mock)
        broadcast_mock.__exit__ = MagicMock(return_value=False)
        broadcast_mock.receive.return_value = ""

        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=broadcast_mock
        ):
            device.change_network(NEW_IP, NEW_MASK, NEW_GW)

        unicast_cmds = [c[0][0] for c in mock_transport.send.call_args_list]
        return unicast_cmds, broadcast_mock

    def test_broadcast_mode_does_not_run_fallback_pass(
        self, mock_transport: MagicMock
    ) -> None:
        mock_transport.receive.return_value = ""
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            dev = HwVxDevice(
                DEVICE_IP,
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )
            dev.change_network(NEW_IP, NEW_MASK, NEW_GW)

        networking.assert_called_once_with("255.255.255.255")
        assert mock_transport.send.call_count == 6

    def test_bad_ip_cannot_be_constructed(self) -> None:
        """Taking IPv4Address means invalid input never reaches the device."""
        with pytest.raises(ValueError):
            IPv4Address("999.1.1.1")

    def test_sends_ip_command(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        cmds, _ = self._run(device, mock_transport)
        assert "SIP10.0.0.50|25" in cmds

    def test_sends_subnet_mask_command(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        cmds, _ = self._run(device, mock_transport)
        assert "SNM255.255.0.0|24" in cmds

    def test_sends_gateway_command(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        cmds, _ = self._run(device, mock_transport)
        assert "SGI10.0.0.1|23" in cmds

    def test_sends_reboot(self, device: HwVxDevice, mock_transport: MagicMock) -> None:
        cmds, _ = self._run(device, mock_transport)
        assert "E" in cmds

    def test_gateway_sent_before_ip(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        """Order must be: SGI → SNM → SIP so IP change happens last."""
        cmds, _ = self._run(device, mock_transport)
        gw_idx = cmds.index("SGI10.0.0.1|23")
        nm_idx = cmds.index("SNM255.255.0.0|24")
        ip_idx = cmds.index("SIP10.0.0.50|25")
        assert gw_idx < nm_idx < ip_idx

    def test_broadcast_fallback_sends_all_three(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        _, bcast = self._run(device, mock_transport)
        bcast_cmds = [c[0][0] for c in bcast.send.call_args_list]
        assert "SGI10.0.0.1|23" in bcast_cmds
        assert "SNM255.255.0.0|24" in bcast_cmds
        assert "SIP10.0.0.50|25" in bcast_cmds


class TestSetDhcp:
    def test_enable_dhcp(self, device: HwVxDevice, mock_transport: MagicMock) -> None:
        device.set_dhcp(True)
        cmds = [c[0][0] for c in mock_transport.send.call_args_list]
        assert "SDH1|28" in cmds
        assert "E" in cmds

    def test_disable_dhcp(self, device: HwVxDevice, mock_transport: MagicMock) -> None:
        device.set_dhcp(False)
        cmds = [c[0][0] for c in mock_transport.send.call_args_list]
        assert "SDH0|28" in cmds


class TestReboot:
    def test_sends_reboot(self, device: HwVxDevice, mock_transport: MagicMock) -> None:
        device.reboot()
        mock_transport.send.assert_called_once_with("E")


class TestContextManager:
    def test_closes_transport(self, mock_transport: MagicMock) -> None:
        with (
            patch(
                "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
            ),
            HwVxDevice(IPv4Address("1.2.3.4")) as _dev,
        ):
            pass
        mock_transport.close.assert_called_once()

"""Tests for uhfreader18.hwvx.device — transport layer is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from uhfreader18.hwvx import DeviceConfig, SearchResult
from uhfreader18.hwvx.device import HwVxDevice


@pytest.fixture()
def mock_transport() -> MagicMock:
    """A fully mocked HwVxNetworking instance."""
    transport = MagicMock()
    transport.search.return_value = [
        SearchResult(
            mac_address="AA:BB:CC:DD:EE:FF",
            port_number="4196",
            ip_address="192.168.1.100",
        )
    ]
    transport.request.return_value = "OK"
    return transport


@pytest.fixture()
def device(mock_transport: MagicMock) -> HwVxDevice:
    """HwVxDevice with mocked transport."""
    with patch("uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport):
        dev = HwVxDevice("192.168.1.100")
    return dev


class TestConnect:
    def test_directed_broadcast_uses_requested_target(
        self, mock_transport: MagicMock
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            HwVxDevice(
                "192.168.1.100",
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
                broadcast_ip="10.10.0.255",
            )

        networking.assert_called_once_with("10.10.0.255")

    def test_broadcast_with_known_mac_skips_second_scan(
        self, mock_transport: MagicMock
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            dev = HwVxDevice(
                "192.168.1.100",
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )

        result = dev.connect()

        networking.assert_called_once_with("255.255.255.255")
        mock_transport.search.assert_not_called()
        mock_transport.request.assert_any_call("WAA:BB:CC:DD:EE:FF", retries=3)
        assert result.ip_address == "192.168.1.100"

    def test_sets_mac_from_search(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        result = device.connect()
        assert device.mac == "AA:BB:CC:DD:EE:FF"
        assert result.ip_address == "192.168.1.100"

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


class TestGetConfig:
    def test_reads_all_settings(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        # Map each check token to a value
        values = {
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

        def fake_request_single(cmd: str, check: str) -> str:
            return values[check]

        mock_transport.request_single.side_effect = fake_request_single

        device.connect()
        cfg = device.get_config()

        assert cfg.username == "admin"
        assert cfg.device_name == "MyDevice"
        assert cfg.ip_address == "192.168.1.100"
        assert cfg.baud_rate == "3"
        assert cfg.subnet_mask == "255.255.255.0"
        assert cfg.dhcp == "0"
        assert mock_transport.request_single.call_count == 22


class TestSaveConfig:
    def test_broadcast_mode_does_not_repeat_config_pass(
        self, mock_transport: MagicMock, sample_config: DeviceConfig
    ) -> None:
        with patch(
            "uhfreader18.hwvx.device.HwVxNetworking", return_value=mock_transport
        ) as networking:
            dev = HwVxDevice(
                "192.168.1.100",
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )
            dev.save_config(sample_config)

        networking.assert_called_once_with("255.255.255.255")
        assert mock_transport.send.call_count == 22

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
        new_ip: str = "10.0.0.50",
        mask: str = "255.255.0.0",
        gw: str = "10.0.0.1",
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
            device.change_network(new_ip, mask, gw)

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
                "192.168.1.100",
                mac_address="AA:BB:CC:DD:EE:FF",
                broadcast=True,
            )
            dev.change_network("10.0.0.50", "255.255.0.0", "10.0.0.1")

        networking.assert_called_once_with("255.255.255.255")
        assert mock_transport.send.call_count == 6

    def test_rejects_bad_ip_before_send(
        self, device: HwVxDevice, mock_transport: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="valid IPv4"):
            device.change_network("999.1.1.1", "255.255.0.0", "10.0.0.1")
        mock_transport.send.assert_not_called()

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
            HwVxDevice("1.2.3.4") as _dev,
        ):
            pass
        mock_transport.close.assert_called_once()

import subprocess
import unittest

from multitool.net import network_info


class NetTests(unittest.TestCase):
    def test_ipv4_network_details(self) -> None:
        self.assertEqual(
            network_info("192.0.2.0/29"),
            {
                "network": "192.0.2.0/29",
                "broadcast": "192.0.2.7",
                "netmask": "255.255.255.248",
                "first_host": "192.0.2.1",
                "last_host": "192.0.2.6",
                "host_count": 6,
            },
        )

    def test_ipv4_small_network_host_boundaries(self) -> None:
        self.assertEqual(
            network_info("198.51.100.10/31"),
            {
                "network": "198.51.100.10/31",
                "broadcast": "198.51.100.11",
                "netmask": "255.255.255.254",
                "first_host": "198.51.100.10",
                "last_host": "198.51.100.11",
                "host_count": 2,
            },
        )
        self.assertEqual(network_info("198.51.100.10/32")["host_count"], 1)

    def test_ipv6_network_details(self) -> None:
        self.assertEqual(
            network_info("2001:db8::/126"),
            {
                "network": "2001:db8::/126",
                "broadcast": "2001:db8::3",
                "netmask": "ffff:ffff:ffff:ffff:ffff:ffff:ffff:fffc",
                "first_host": "2001:db8::1",
                "last_host": "2001:db8::3",
                "host_count": 3,
            },
        )

    def test_ipv6_point_to_point_host_boundaries(self) -> None:
        self.assertEqual(
            network_info("2001:db8::/127"),
            {
                "network": "2001:db8::/127",
                "broadcast": "2001:db8::1",
                "netmask": "ffff:ffff:ffff:ffff:ffff:ffff:ffff:fffe",
                "first_host": "2001:db8::",
                "last_host": "2001:db8::1",
                "host_count": 2,
            },
        )

    def test_cli_prints_network_details(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "net", "10.0.0.0/30"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "network: 10.0.0.0/30\n"
            "broadcast: 10.0.0.3\n"
            "netmask: 255.255.255.252\n"
            "first_host: 10.0.0.1\n"
            "last_host: 10.0.0.2\n"
            "host_count: 2\n",
        )

    def test_cli_rejects_invalid_cidr(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "net", "not-a-cidr"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)

    def test_cli_rejects_ipv4_host_bits(self) -> None:
        result = subprocess.run(
            ["uv", "run", "mt", "net", "192.0.2.5/24"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

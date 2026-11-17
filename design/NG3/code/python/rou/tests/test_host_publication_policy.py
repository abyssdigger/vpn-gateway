from __future__ import annotations

from ipaddress import IPv4Address
import unittest

from rou.host_publication_policy import (
    HostPublicationMappingIntent,
    HostPublicationProjectionError,
    HostPublicationSelectorKind,
    build_host_publication_desired,
)
from rou.local_publication_policy import PublicationProtocol


def intent(
    *,
    kind=HostPublicationSelectorKind.ANY,
    value=None,
    port=443,
    target=8443,
    device="vpn",
):
    return HostPublicationMappingIntent(
        device_id=device,
        protocol=PublicationProtocol.TCP,
        selector_kind=kind,
        selector_value=value,
        host_port=port,
        internal_address=IPv4Address("192.0.2.2"),
        internal_port=target,
    )


class HostPublicationPolicyTests(unittest.TestCase):
    def test_identical_physical_contribution_deduplicates_across_devices(self):
        desired = build_host_publication_desired(
            (intent(device="a"), intent(device="b"))
        )
        self.assertEqual(len(desired.rules), 1)

    def test_any_overlap_with_different_target_is_rejected(self):
        with self.assertRaisesRegex(
            HostPublicationProjectionError, "ambiguous host publication"
        ):
            build_host_publication_desired(
                (
                    intent(target=8443),
                    intent(
                        kind=HostPublicationSelectorKind.IPV4,
                        value=IPv4Address("198.51.100.10"),
                        target=9443,
                    ),
                )
            )

    def test_interface_and_ipv4_overlap_is_rejected_without_precedence(self):
        with self.assertRaises(HostPublicationProjectionError):
            build_host_publication_desired(
                (
                    intent(
                        kind=HostPublicationSelectorKind.INTERFACE,
                        value="eth0",
                        target=8443,
                    ),
                    intent(
                        kind=HostPublicationSelectorKind.IPV4,
                        value=IPv4Address("198.51.100.10"),
                        target=9443,
                    ),
                )
            )

    def test_distinct_interfaces_may_reuse_port_for_distinct_targets(self):
        desired = build_host_publication_desired(
            (
                intent(
                    kind=HostPublicationSelectorKind.INTERFACE,
                    value="eth0",
                    target=8443,
                ),
                intent(
                    kind=HostPublicationSelectorKind.INTERFACE,
                    value="eth1",
                    target=9443,
                ),
            )
        )
        self.assertEqual(len(desired.rules), 2)

    def test_distinct_ipv4_selectors_may_reuse_port_for_distinct_targets(self):
        desired = build_host_publication_desired(
            (
                intent(
                    kind=HostPublicationSelectorKind.IPV4,
                    value=IPv4Address("198.51.100.10"),
                    target=8443,
                ),
                intent(
                    kind=HostPublicationSelectorKind.IPV4,
                    value=IPv4Address("198.51.100.11"),
                    target=9443,
                ),
            )
        )
        self.assertEqual(len(desired.rules), 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from rou.managed_l3_boundary import (
    ManagedL3BoundaryBackend,
    ManagedL3BoundaryCapabilities,
    ManagedL3BoundarySelectionError,
    select_managed_l3_boundary_backend,
)


class ManagedL3BoundarySelectionTests(unittest.TestCase):
    def test_release1_default_prefers_routed_veth_when_both_are_available(self):
        self.assertIs(
            select_managed_l3_boundary_backend(
                ManagedL3BoundaryCapabilities(
                    routed_veth_proxy_arp=True,
                    netkit_l3=True,
                )
            ),
            ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP,
        )

    def test_netkit_is_compatible_fallback_when_veth_backend_is_unavailable(self):
        self.assertIs(
            select_managed_l3_boundary_backend(
                ManagedL3BoundaryCapabilities(
                    routed_veth_proxy_arp=False,
                    netkit_l3=True,
                )
            ),
            ManagedL3BoundaryBackend.NETKIT_L3,
        )

    def test_lower_override_can_select_netkit_without_changing_product_intent(self):
        self.assertIs(
            select_managed_l3_boundary_backend(
                ManagedL3BoundaryCapabilities(
                    routed_veth_proxy_arp=True,
                    netkit_l3=True,
                ),
                override=ManagedL3BoundaryBackend.NETKIT_L3,
            ),
            ManagedL3BoundaryBackend.NETKIT_L3,
        )

    def test_unavailable_override_fails_closed(self):
        with self.assertRaises(ManagedL3BoundarySelectionError):
            select_managed_l3_boundary_backend(
                ManagedL3BoundaryCapabilities(
                    routed_veth_proxy_arp=True,
                    netkit_l3=False,
                ),
                override=ManagedL3BoundaryBackend.NETKIT_L3,
            )

    def test_no_backend_fails_closed(self):
        with self.assertRaises(ManagedL3BoundarySelectionError):
            select_managed_l3_boundary_backend(
                ManagedL3BoundaryCapabilities(
                    routed_veth_proxy_arp=False,
                    netkit_l3=False,
                )
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from rou.host_publication_adapter import HostPublicationAdapter
from rou.host_publication_policy import HostPublicationDesiredState
from rou.linux_host_publication import LinuxHostPublicationBackend


class HostPublicationAdapterTests(unittest.TestCase):
    def adapter(self):
        backend = LinuxHostPublicationBackend(Mock())
        return HostPublicationAdapter(backend), backend

    def test_observe_delegates_to_lower_backend(self):
        adapter, backend = self.adapter()
        expected = object()
        with patch.object(
            LinuxHostPublicationBackend,
            "observe",
            return_value=expected,
        ) as observe:
            self.assertIs(adapter.observe(), expected)
        observe.assert_called_once_with()

    def test_apply_delegates_exact_desired_state_to_verified_convergence(self):
        adapter, backend = self.adapter()
        desired = HostPublicationDesiredState(())
        expected = object()

        with patch(
            "rou.host_publication_adapter.converge_host_publication_once",
            return_value=expected,
        ) as converge:
            self.assertIs(adapter.apply(desired), expected)

        converge.assert_called_once_with(backend, desired)

    def test_cleanup_converges_empty_owned_scope(self):
        adapter, backend = self.adapter()
        expected = object()

        with patch(
            "rou.host_publication_adapter.converge_host_publication_once",
            return_value=expected,
        ) as converge:
            self.assertIs(adapter.cleanup(), expected)

        backend_arg, desired = converge.call_args.args
        self.assertIs(backend_arg, backend)
        self.assertEqual(desired, HostPublicationDesiredState(()))

    def test_apply_rejects_non_desired_input(self):
        adapter, _ = self.adapter()
        with self.assertRaisesRegex(ValueError, "HostPublicationDesiredState"):
            adapter.apply(object())


if __name__ == "__main__":
    unittest.main()

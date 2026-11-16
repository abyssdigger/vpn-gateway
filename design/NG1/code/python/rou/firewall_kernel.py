from __future__ import annotations

from dataclasses import dataclass

from .command_backend import NamespaceBackend
from .firewall_state import FirewallDesiredState, normalize_iptables_save


@dataclass(frozen=True)
class FirewallVerification:
    ok: bool
    actual: str
    expected: str


def apply_filter_state(
    desired: FirewallDesiredState,
    backend: NamespaceBackend,
) -> None:
    """Atomically replace the ROU-owned IPv4 filter table through iptables-restore."""

    backend.run(
        ("iptables-legacy-restore",),
        input_text=desired.restore_text,
    )


def observe_filter_state(backend: NamespaceBackend) -> str:
    """Return canonical current ROU-owned IPv4 filter table."""

    result = backend.run(
        ("iptables-legacy-save", "-c", "-t", "filter")
    )
    return normalize_iptables_save(result.stdout)


def verify_filter_state(
    desired: FirewallDesiredState,
    backend: NamespaceBackend,
) -> FirewallVerification:
    actual = observe_filter_state(backend)
    return FirewallVerification(
        ok=actual == desired.canonical_save,
        actual=actual,
        expected=desired.canonical_save,
    )

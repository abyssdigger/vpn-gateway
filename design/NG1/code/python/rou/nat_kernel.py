from __future__ import annotations

from dataclasses import dataclass

from .command_backend import NamespaceBackend
from .firewall_state import normalize_iptables_save
from .nat_state import NatDesiredState


@dataclass(frozen=True)
class NatVerification:
    ok: bool
    actual: str
    expected: str


def apply_nat_state(
    desired: NatDesiredState,
    backend: NamespaceBackend,
) -> None:
    backend.run(
        ("iptables-legacy-restore",),
        input_text=desired.restore_text,
    )


def observe_nat_state(backend: NamespaceBackend) -> str:
    result = backend.run(
        ("iptables-legacy-save", "-c", "-t", "nat")
    )
    return normalize_iptables_save(result.stdout)


def verify_nat_state(
    desired: NatDesiredState,
    backend: NamespaceBackend,
) -> NatVerification:
    actual = observe_nat_state(backend)
    return NatVerification(
        ok=actual == desired.canonical_save,
        actual=actual,
        expected=desired.canonical_save,
    )

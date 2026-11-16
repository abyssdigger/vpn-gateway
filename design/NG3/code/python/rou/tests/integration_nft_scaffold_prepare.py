from __future__ import annotations

import os
import subprocess

from rou.forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import (
    LinuxNftScaffoldBackend,
    SubprocessNftRunner,
)
from rou.nft_payload_scaffold import (
    PAYLOAD_POSTROUTING_CHAIN,
    compare_payload_nft_scaffold,
)
from rou.nft_scaffold_executor import (
    PayloadNftScaffoldPrepareStatus,
    prepare_payload_nft_scaffold_once,
)


def run(*argv, input_text=None):
    subprocess.run(
        argv,
        input=input_text,
        check=True,
        text=True,
        capture_output=True,
    )


def main():
    ns = f"vpng-ng3-nft-prepare-{os.getpid()}"
    runner = SubprocessNftRunner()

    try:
        run("ip", "netns", "add", ns)
        gate = LinuxForwardingGateBackend(runner, ns)
        nft = LinuxNftScaffoldBackend(runner, ns)

        enabled = converge_forwarding_gate_once(
            gate,
            ForwardingGateState.ENABLED,
        )
        assert enabled.confirmed, enabled

        created = prepare_payload_nft_scaffold_once(gate, nft)
        assert created.status is PayloadNftScaffoldPrepareStatus.SUCCESS, created
        assert created.confirmed
        assert gate.observe_forwarding_gate() is ForwardingGateState.DISABLED

        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "chain", "ip", "vpn_gate",
            PAYLOAD_POSTROUTING_CHAIN,
        )
        repaired = prepare_payload_nft_scaffold_once(gate, nft)
        assert repaired.confirmed, repaired
        assert repaired.mutation_attempted

        # Add an unclassified rule, then remove one invariant chain. The
        # scaffold-only executor must refuse to repair through unknown state.
        run(
            "ip", "netns", "exec", ns,
            "nft", "add", "rule", "ip", "vpn_gate",
            "payload_forward", "counter",
        )
        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "chain", "ip", "vpn_gate",
            PAYLOAD_POSTROUTING_CHAIN,
        )

        refused = prepare_payload_nft_scaffold_once(gate, nft)
        assert refused.status is PayloadNftScaffoldPrepareStatus.CONFLICT, refused
        assert not refused.mutation_attempted
        current = compare_payload_nft_scaffold(nft.observe_nft_namespace())
        assert [spec.name for spec in current.missing_chains] == [
            PAYLOAD_POSTROUTING_CHAIN
        ]
        assert current.unclassified_objects

        print("NG3 payload nft scaffold prepare Linux integration: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import subprocess

from rou.forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.linux_forwarding_gate import LinuxForwardingGateBackend


def run(*argv):
    subprocess.run(argv, check=True, text=True, capture_output=True)


def main():
    ns = f"vpng-ng3-gate-{os.getpid()}"
    runner = SubprocessCommandRunner()

    try:
        run("ip", "netns", "add", ns)
        backend = LinuxForwardingGateBackend(
            runner=runner,
            namespace=ns,
        )

        enabled = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.ENABLED,
        )
        assert enabled.confirmed, enabled
        assert backend.observe_forwarding_gate() is ForwardingGateState.ENABLED

        disabled = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        assert disabled.confirmed, disabled
        assert backend.observe_forwarding_gate() is ForwardingGateState.DISABLED

        noop = converge_forwarding_gate_once(
            backend,
            ForwardingGateState.DISABLED,
        )
        assert noop.confirmed, noop
        assert not noop.mutation_attempted

        print("NG3 forwarding-gate Linux integration: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import subprocess

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.nft_namespace_inventory import LinuxNftNamespaceBackend
from rou.nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_POSTROUTING_CHAIN,
    compare_payload_nft_scaffold,
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
    ns = f"vpng-ng3-nft-scaffold-{os.getpid()}"
    runner = SubprocessCommandRunner()

    try:
        run("ip", "netns", "add", ns)
        backend = LinuxNftNamespaceBackend(
            runner=runner,
            namespace=ns,
        )

        run(
            "ip", "netns", "exec", ns, "nft", "-f", "-",
            input_text=(
                'table ip vpn_gate {\n'
                '  comment "vpn-gate:ng3:owner-v1"\n'
                '  chain payload_forward {\n'
                '    type filter hook forward priority 0; policy drop;\n'
                '    comment "vpn-gate:ng3:payload-forward-v1"\n'
                '  }\n'
                '  chain payload_postrouting {\n'
                '    type nat hook postrouting priority 100; policy accept;\n'
                '    comment "vpn-gate:ng3:payload-postrouting-v1"\n'
                '  }\n'
                '}\n'
            ),
        )

        observed = backend.observe_nft_namespace()
        exact = compare_payload_nft_scaffold(observed)
        assert exact.scaffold_confirmed, exact
        assert exact.full_policy_classified, exact

        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "chain", "ip", "vpn_gate",
            PAYLOAD_POSTROUTING_CHAIN,
        )
        missing = compare_payload_nft_scaffold(
            backend.observe_nft_namespace()
        )
        assert not missing.scaffold_confirmed, missing
        assert [item.name for item in missing.missing_chains] == [
            PAYLOAD_POSTROUTING_CHAIN
        ]

        print("NG3 payload nft scaffold comparison Linux integration: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    main()

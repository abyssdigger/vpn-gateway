from __future__ import annotations

import os
import subprocess

from rou.iproute_priority_backend import SubprocessCommandRunner
from rou.nft_namespace_inventory import (
    LinuxNftNamespaceBackend,
    NftNamespaceStatus,
)


OWNER_COMMENT = "vpn-gate:ng3:owner-v1"


def run(*argv, input_text=None):
    subprocess.run(
        argv,
        input=input_text,
        check=True,
        text=True,
        capture_output=True,
    )


def main():
    ns = f"vpng-ng3-nft-owner-{os.getpid()}"
    runner = SubprocessCommandRunner()

    try:
        run("ip", "netns", "add", ns)
        backend = LinuxNftNamespaceBackend(
            runner=runner,
            namespace=ns,
        )

        absent = backend.observe_nft_namespace()
        assert absent.status is NftNamespaceStatus.ABSENT

        run(
            "ip", "netns", "exec", ns, "nft", "-f", "-",
            input_text=(
                "table ip vpn_gate {\n"
                f'  comment "{OWNER_COMMENT}"\n'
                "  chain scratch { }\n"
                "}\n"
            ),
        )
        owned = backend.observe_nft_namespace()
        assert owned.status is NftNamespaceStatus.OWNED, owned
        assert owned.marker_confirmed
        assert len(owned.objects) == 1
        assert owned.objects[0].kind == "chain"

        run(
            "ip", "netns", "exec", ns,
            "nft", "delete", "table", "ip", "vpn_gate",
        )
        run(
            "ip", "netns", "exec", ns,
            "nft", "add", "table", "ip", "vpn_gate",
        )
        conflict = backend.observe_nft_namespace()
        assert conflict.status is NftNamespaceStatus.CONFLICT, conflict
        assert not conflict.marker_confirmed

        print("NG3 nft namespace inventory Linux integration: PASS")
    finally:
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    main()

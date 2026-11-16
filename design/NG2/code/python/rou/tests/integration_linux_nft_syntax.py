from __future__ import annotations

import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.interface_identity import InterfaceIdentity
from rou.linux_nft import compile_nft_filter_desired
from rou.network_rules import (
    IcmpType,
    NetworkEndpoint,
    NetworkRulesSpec,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)
from rou.network_rules_composition import (
    OwnedNetworkRules,
    OwnerToken,
    compose_network_rules,
)


def main() -> int:
    local = NetworkEndpoint.local_network()
    path = NetworkEndpoint.interface_path(
        InterfaceIdentity("vpns00", 4242)
    )

    exact = TrafficPredicate.match(
        TrafficSelector(
            protocol=TrafficProtocol.ICMP,
            icmp_types=(IcmpType.ECHO_REQUEST,),
        )
    )
    not_echo = TrafficPredicate.negate(
        TrafficPredicate.match(
            TrafficSelector(
                protocol=TrafficProtocol.ICMP,
                icmp_types=(
                    IcmpType.ECHO_REPLY,
                    IcmpType.ECHO_REQUEST,
                ),
            )
        )
    )

    rules = NetworkRulesSpec(
        traffic_allows=(
            TrafficAllowSpec(local, path, exact),
            TrafficAllowSpec(path, local, not_echo),
        )
    )
    desired = compile_nft_filter_desired(
        compose_network_rules(
            (OwnedNetworkRules(OwnerToken(1), rules),)
        ),
        local_interface="host0",
    )

    completed = subprocess.run(
        ("nft", "-c", "-f", "-"),
        input=desired.definition,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "kernel nft parser rejected production ICMP selector output:\n"
            + completed.stdout
            + completed.stderr
            + "\nDEFINITION:\n"
            + desired.definition
        )

    print("NG2_LINUX_NFT_ICMP_SELECTOR_SYNTAX=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

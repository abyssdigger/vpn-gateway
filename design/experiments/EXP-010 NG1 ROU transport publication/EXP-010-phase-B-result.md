# EXP-010 Phase B — live network-namespace result

**Status:** PASS  
**Experiment:** EXP-010 — NG1 ROU transport publication relay  
**Phase:** B — ROU network namespace  
**Run:** live Debian client host, user-reported result

Observed result:

    EXP-010 NG1 ROU transport publication namespace relay
    H1 published socket -> relay -> netns listener: PASS
    H2 netns listener -> dependent host-visible payload: PASS
    H3 netns listener -> relay -> original client response: PASS

    OVERALL=PASS

Interpretation:

- the host-side published UDP socket received the client datagram;
- the relay forwarded the datagram across the veth boundary into the private network namespace;
- the listener inside the namespace observed the exact input;
- the listener generated a second datagram whose payload depended on the received input;
- that dependent datagram traversed back to a host-visible sink and was observed;
- the listener reply returned through the relay to the original client.

This validates the generic NG1 transport-publication topology independently of WireGuard/OpenConnect.

EXP-010 therefore establishes that a ROU-owned host-side TCP/UDP publication layer can bridge transport traffic to a stable listener inside the private ROU namespace without requiring the VPN transport itself to own the host-facing port.

The next experiment may replace the dummy internal listener with a real VPN endpoint while preserving the same publication boundary.

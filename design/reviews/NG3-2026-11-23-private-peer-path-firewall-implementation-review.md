# NG3 2026-11-23 — private-peer path firewall implementation review

**Scope:** implementation of the accepted narrow `via peer <IPv4>` Device-firewall
path selector through code head `77fd3ef76c6383697cd8c93b0f1df8708427c185`.

**Governing design:** `NG3-2026-11-23-private-peer-path-firewall-design-review.md`.

## Verdict

**PASS — IMPLEMENTATION SATISFIES THE ACCEPTED PRIVATE-PEER PER-PATH SCOPE.**

No unresolved finding remains in this review unit.

## Evidence

GitHub Actions run `45075280405` on code head
`77fd3ef76c6383697cd8c93b0f1df8708427c185` confirmed the material acceptance paths:

- `unit` — PASS;
- `linux-endpoint-provenance` — PASS, including both EXP-039 and the new
  `Private-peer VPNPathAdapter integration` step;
- `linux-alpha-smoke` — PASS.

The focused Linux integration creates a real TUN, assigns
`local 10.239.0.1/32 peer 10.239.0.2/32`, moves it into a disposable namespace and verifies
that the production `LinuxVpnPathAdapter` returns the exact current
`InterfaceIdentity -> private peer` association.

## Findings and dispositions

### F1 — grammar and semantic intent are narrow and typed

**Decision:** accepted.  
**Resolution:** fixed.

`release1_config.py` accepts optional `via peer <IPv4>` only as part of a Device firewall
rule and normalizes it to `FirewallRuleConfig.private_peer_ipv4`.
`DeviceFirewallRuleIntent` carries the typed `IPv4Address | None` fact.

Malformed `via`, missing peer address, IPv6 input and duplicate `via` clauses are covered
by permanent unit tests.

### F2 — ordinary configurations do not acquire a new observation dependency

**Decision:** accepted.  
**Resolution:** fixed.

`AlphaPreparedPolicy.requires_private_peer_observation` is derived from accepted active
Device rules. Controller startup and periodic reconcile request address/private-peer
observation only when at least one active rule contains `via peer`.

Without such a rule, `LinuxVpnPathAdapter` performs the pre-existing one-shot
`ip -j link show` observation only.

### F3 — private peer is correlated to exact current interface generation

**Decision:** accepted.  
**Resolution:** fixed.

When demanded, `LinuxVpnPathAdapter` obtains:

```text
fresh link snapshot
fresh full address snapshot
```

and requires the exact `(ifname, ifindex)` identity sets to agree. Address rows expose a
single IPv4 point-to-point remote value from the observed `peer` / iproute2 `address`
field. Multiple distinct peer candidates, missing generations, new generations appearing
between snapshots, parse errors or lower command failures are observation failures rather
than guessed absence.

The live TUN integration proves the selected parser/command shape on Linux.

### F4 — Device ownership precedes peer selection

**Decision:** accepted.  
**Resolution:** fixed.

The existing binding projection still decides which current endpoints belong to each Device.
The peer map is consumed only later while compiling Device firewall policy for those current
routes. An arbitrary unrelated host/namespace interface with the same peer cannot create a
Device path.

No VPN-specific session Manager, transport daemon inspection or global peer registry was
introduced.

### F5 — ordered firewall semantics are preserved per current path

**Decision:** accepted.  
**Resolution:** fixed.

For each current exact path:

- unqualified rules retain their declared order;
- a `via peer` rule is retained only when the verified private peer equals its operand;
- a rule scoped to another peer is skipped;
- the remaining rules preserve relative order;
- an explicit Device firewall still receives terminal no-match DROP even when every explicit
  rule was skipped for that path.

A requested peer matching more than one current path of the same Device is rejected as
ambiguous. A peer-scoped Device with missing current peer observation is rejected rather than
compiled as if the restriction were absent.

### F6 — runtime wiring initially exposed a fail-open observation-error path

**Decision:** accepted.  
**Resolution:** fixed.

Review found that periodic alpha reconciliation previously returned `FAILED` immediately
when fresh path observation / desired rebuild failed. That was already questionable for the
general current-path model and became materially unsafe once a private-peer rule could depend
on fresh association: stale allowing policy could otherwise remain active after the evidence
needed to select the restricted path became unknown.

The runtime now attempts verified `ForwardingGate=DISABLED` containment before returning the
desired-rebuild failure. A permanent unit test injects path-observation failure and verifies
that fail-closed containment is invoked and reported.

Startup already used the corresponding containment path and required no semantic change.

### F7 — historical evidence was reused rather than reimplemented as transport-specific machinery

**Decision:** accepted.  
**Resolution:** fixed.

The implementation relies on the recovered evidence chain:

- EXP-004.3 — dynamic ocserv interface family;
- EXP-009 — simultaneous OpenConnect P2P interfaces and the historical
  `PeerBinding(peer, name, ifindex)` association;
- EXP-039 — generic inner P2P peer visibility and separation from external userspace
  transport endpoint provenance.

`design/NG3/experiment-evidence-transition.md` now records the previously missing
interpretation that removal of `PeerBinding` from the later route model was a routing
simplification, not a disproof of the private-peer association.

## Traceability / simplification conclusion

The accepted component allocation remains sufficient:

```text
A.002 ConfigurationAdapter
    -> normalized optional private peer
A.005 PayloadPolicyCalculator
    -> rule/path applicability semantics
C.004 VPNPathAdapter
    -> demand-scoped fresh private-peer observation
C.001 NetworkPolicyAdapter
    -> exact current-path firewall lowering
C.003 NetworkPolicyEnforcer
    -> existing structural convergence / fail-closed barrier
```

No new Engine, Manager, durable path identity, VPN technology adapter or persistent mapping is
required.

## Closure recommendation

The implementation/review evidence is sufficient to close:

- `VPNG-U001-R1.R4.R2.R1`;
- `VPNG-U001-R1.R4.R2.R1.R1`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U001-R4.R4.R6.R2.R5`.

Their narrow-scope constraints remain `closed` as written.

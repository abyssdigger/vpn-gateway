# NG3 CD checkpoint — endpoint provenance, ordered Device firewall and gateway NAT

**Cycle branch:** `ng3-design-cycle-20261116-endpoint-provenance-35m`  
**CYCLE_START_COMMIT:** `72b6215057bbc385980fd10010eece3311f6faa6`  
**T0:** `2026-11-16T15:29:24Z`  
**CYCLE_INTERVAL:** 35 minutes  
**Deadline:** `2026-11-16T16:04:24Z`

## Completed review units

### 1. Transport endpoint provenance — closed, Release-1 implementation postponed

Added and closed:

- `VPNG-U001-R1.R3.R5`;
- `VPNG-U001-R1.R3.R5.C1`;
- `VPNG-U001-R1.R3.R5.C1.R1`.

Accepted semantics:

- transport endpoint/peer provenance is optional current-path provenance, not stable
  `LogicalPathId`;
- provenance is scoped to the exact current concrete binding;
- generic interface name/slot/inner peer must not be used as transport-peer inference;
- absence of provenance does not make the path unusable for functions that do not need it;
- provenance-dependent conveniences must diagnose/refuse rather than guess;
- named-endpoint configuration syntax is postponed.

EXP-039 privileged Linux evidence passed in Actions run `43897774703`.
A real point-to-point TUN exposed its inner peer but generic `ip -j -d link` /
`ip -j addr` state stayed unchanged when the userspace transport socket peer changed from
`198.51.100.39` to `203.0.113.39`.

Conclusion:

```text
generic point-to-point TUN discovery
    !=
transport endpoint provenance
```

Integration-specific provenance is required.

### 2. Ordered Device firewall — closed semantics, lower physical completion gated

Refined `VPNG-U001-R1.R2.R4.R6.R2` and added/closed R1-R5 descendants plus
endpoint-scoped first-release constraint.

Accepted semantics:

- ordered first-match Device firewall;
- `IN|OUT` relative to Device/path, both physically FORWARD;
- `ALLOW|DENY|REJECT`;
- optional protocol/source-port/destination-port/source-CIDR/destination-CIDR/comment;
- literal payload L3/L4 fields at the managed forwarding point;
- user order is preserved exactly;
- omitted Device firewall means permissive Device layer;
- explicit policy no-match means DROP;
- Device ALLOW cannot widen Profile permission;
- endpoint-scoped filtering is future capability gated by confirmed endpoint provenance;
- runtime ifname is not a durable user endpoint selector.

Architecture composition:

```text
ordered Device chain
    DENY   -> drop
    REJECT -> reject
    ALLOW  -> return to Profile hard gate

Profile hard gate
    permitted -> accept
    otherwise -> payload_forward policy drop
```

The current EXP-035..038 / `PayloadForwardRuleSpec` contract remains valid only as the
positive Profile NEW/RETURN sub-contract. Full Device jump/ordered-chain owner observation,
desired state and physical mutation remain separate evidence/implementation work.

### 3. Managed stack DROP/DROP/DROP — closed semantics, physical INPUT/OUTPUT evidence gated

Added and closed:

- `VPNG-U004-R4.R6.R1.R5`;
- `VPNG-U004-R4.R6.R1.R5.R1`.

Managed-domain defaults are:

```text
INPUT   DROP
FORWARD DROP
OUTPUT  DROP
```

User Device firewall owns payload FORWARD semantics only. VPN-GATE owns explicit local
control/probe/publication/integration exceptions.

Existing EXP-032 proves the FORWARD/postrouting scaffold only. Exact INPUT/OUTPUT owner
shapes and exceptions require a later bounded lower unit.

### 4. Ordinary-side Profile gateway NAT — closed semantics, Linux association mechanism gated

Added and closed:

- `VPNG-U001-R1.R2.R4.R4.R4`;
- `VPNG-U001-R1.R2.R4.R4.R4.R1`;
- `VPNG-U001-R1.R2.R4.R4.R4.C1`;
- `VPNG-U004-R4.R6.R1.R6`;
- `VPNG-U004-R4.R6.R1.R6.R1`.

The two NAT purposes are separate:

```text
ordinary -> managed firewall -> Device/path MASQUERADE -> VPN

VPN -> managed firewall -> host boundary
    -> optional Profile ordinary-side gateway MASQUERADE
    -> ordinary LAN
```

Gateway NAT is for host-forwarded traffic where ordinary downstream hosts lack return routes
to remote VPN prefixes. Traffic terminating on the VPN-GATE host does not require this NAT.

Per-Profile gateway NAT may not reclassify solely from remote source CIDR after the common
boundary because inbound Profile selection is path-relative. Architecture therefore requires
a verified lower `BoundaryProfileAssociation` carrying the already-selected Profile to the
host-boundary `ProfileGatewayNatOwner(profile_id)`.

The exact Linux carrier (mark/conntrack metadata/distinct boundary resource/etc.) is not
selected. It requires an experiment with overlapping remote prefixes on distinct ingress
paths, downstream forwarding, host-local traffic and unrelated-host negative controls.

### 5. Requirements model — unreachable causal links

Added the new non-hierarchical association:

```text
[unreachable because of <R/C-ID>, <R/C-ID>, ...]
```

It records a minimal sufficient set of accepted normative causes whose conjunction makes one
Requirement impossible to satisfy.

It is explicitly distinct from:

- `[decomp: ...]` — insufficient semantics for further decomposition;
- `[rejected_closure]` — one architecture candidate failed;
- a normal Constraint — product is narrowed but still satisfiable.

An active unreachable link blocks `pending_closure`, `closed` and implementation and
requires human requirement resolution. It is removed from the current tree only after the
normative conflict is actually resolved; Git/review history retains the former conflict.

No current NG3 product Requirement has an active unreachable link.

## Configuration-format postponements retained

No compact external syntax was invented for:

- ordered Device firewall rules;
- named VPN endpoints / endpoint selectors;
- Profile ordinary-side gateway NAT;
- existing publication details still under the configuration-format boundary.

`design/NG3/config-model.md` now distinguishes accepted ordered-firewall semantics from
historical `traffic_envelope` prototype spelling.

## Final requirement/architecture audit

Mechanical result on the cycle branch:

```text
Requirement/Constraint nodes: 144
closed:                     144
pending_closure:              0
rejected_closure:             0
unlabeled:                    0
closed without architecture:  0
decomp -> pending:             0
active unreachable links:     0
```

Therefore the current requirement tree is **all closed/postponed**: accepted product
semantics are architecturally closed, while deliberately deferred implementation/configuration
details are represented as explicit constraints/evidence gates rather than hidden open
requirement semantics.

## Evidence

GitHub Actions run `43897774703` on the EXP-039/workflow commit completed successfully.
All 10 jobs passed, including the new privileged `linux-endpoint-provenance` job and the
existing Linux route, forwarding barrier, nft scaffold, NAT and payload-forward jobs.

Later cycle commits are requirement/architecture/review/config-model documentation only.

## Remaining non-semantic implementation/evidence gates

The following do not reopen the product requirement tree:

- per-integration endpoint-provenance implementation/evidence;
- final external config grammar for Device firewall, named endpoints, gateway NAT and
  publication where still deferred;
- exact supported protocol/port validation combinations;
- exact nft REJECT realization;
- complete ordered Device-firewall lower owner/observer/desired/mutation model;
- managed INPUT/OUTPUT owner shapes and local system exceptions;
- ordinary-side Profile gateway NAT boundary-association Linux evidence;
- full structural Executor composition;
- existing target-platform/future-release evidence backlog, including EXP-014 for Release 2
  multi-path inbound/bidirectional.

## Final verdict

**PASS — cycle complete.**

No accepted defect remains in the completed requirement/architecture units. Current NG3
requirements are all closed/postponed with explicit future/evidence gates.

# Response to external NG1 Draft 5 review

Status: **accepted with refinements; implementation correction required**

This response evaluates every finding against the current Draft 5 codebase rather than the
older Draft 4 state read by the reviewer.

## 1. Return steering for INBOUND/BIDIRECTIONAL — ACCEPT

The bug is real. OUTBOUND return traffic needs no architecture-mandated conntrack mark, but
a remote-initiated flow can return through another lower-metric Device/interface.

### Production rule

- OUTBOUND: no interface-capacity restriction.
- INBOUND/BIDIRECTIONAL: accepted only when
  `capacity(Profile) == 1`, where capacity is the sum of interface_quota for enabled,
  active Devices referenced by the Profile.
- The rule is validated before kernel mutation and remains a valid production restriction,
  not merely a temporary test limitation.
- Multi-interface remote-initiated flows remain a future extension.

### Future extension

A dedicated experiment will validate connmark restoration before routing, fwmark RPDB
return tables, rp_filter interaction, mark retirement and blackhole behavior after ingress
interface disappearance. No speculative flow-pinning implementation is added before that
evidence.

## 2. ESTABLISHED,RELATED interface scoping — ACCEPT / CODE ALREADY CORRECT

The current implementation already emits state ACCEPT only for each currently bound
interface I:

```text
-i I     -o host0 ESTABLISHED,RELATED -> ACCEPT
-i host0 -o I     ESTABLISHED,RELATED -> ACCEPT
```

There is no state ACCEPT for over-quota/unbound interfaces or Device-to-Device pairs.
Architecture and tests will be updated to make this normative.

Residual cross-bound-interface tuple matching remains relevant only to remote-initiated
flows and is one reason capacity>1 is disallowed until flow pinning is proven.

## 3. INPUT policy and remote host-side trust boundary — ACCEPT WITH CURRENT DRAFT 5 ENVELOPE

The reviewer correctly identified an INPUT trust-boundary gap.

ROU-owned filter policy becomes:

- INPUT default DROP;
- loopback ACCEPT;
- ESTABLISHED,RELATED ACCEPT for ROU-local traffic;
- host0 -> configured internal publication endpoints ACCEPT;
- no Device-interface INPUT admission, including publication/listener endpoints.

Device->ROU-local DROP is defense-in-depth and does not block the relay: the host-side
publication worker reaches the internal listener through host0.

Draft 5 already has a traffic-envelope grammar, so INBOUND/BIDIRECTIONAL do not need to be
reserved entirely. Instead they require both:

1. capacity(Profile) == 1;
2. every enabled active Device referenced by that Profile has a traffic_envelope with
   default = "drop".

This makes the host-side trust boundary administrator-explicit. The envelope can then
enumerate the host destinations/protocols/ports remotely initiated traffic may reach.

## 4. Shadow fallback and protective barrier — ACCEPT / INVARIANT 62 REPLACED

Persistent shadow fallback is retained.

Its mechanism is implemented now by design. Its trigger, a normalized transition to
UNAVAILABLE, is consciously deferred to future DeviceManager work. Until then bound
interfaces ordinarily remain UNKNOWN and therefore keep normal routes. This is deliberate,
not an unfinished routing model.

The global barrier is narrowed:

- ordinary binding appearance/disappearance: incremental reprojection, no global barrier;
- availability changes: incremental reprojection, no global barrier;
- structural or unknown owned-state drift: global fail-closed barrier;
- crash recovery / unverified state: global fail-closed barrier;
- policy transitions that cannot be proven additive/safe: global fail-closed barrier.

Member disappearance may remove the kernel multipath route as EXP-013 proved. During its
rebuild the terminal blackhole and surviving normal routes preserve fail-closed behavior;
global forwarding shutdown is therefore unnecessary.

A future Profile-local barrier may be useful but is not required for the first production
implementation.

## 5. rou up ordering — ACCEPT

Normative lifecycle is corrected to match the implementation:

1. create namespace/veth;
2. establish fail-closed sysctl/filter prerequisites;
3. verify bootstrap;
4. start runtime/publication supervision;
5. reconcile complete desired state;
6. fresh verify;
7. open forwarding.

Publication sockets must never create an unprotected forwarding window.

## 6. NAT — ALREADY RESOLVED IN DRAFT 5

Enabled Devices already require explicit `nat = "none" | "masquerade"`.
Production MASQUERADE is Device-scoped, bound-interface-scoped and remote-prefix-scoped.
No implicit NAT default remains.

## 7. MTU/MSS — ACCEPT / EXPERIMENT REQUIRED

No TCPMSS behavior will be guessed.

A dedicated production experiment will validate real TCP over OpenConnect/WireGuard,
effective MTU, PMTUD, DF behavior and SYN/SYN-ACK MSS. Until that evidence exists,
automatic MSS clamping remains a documented gate rather than an inferred default.

## 8. ECMP hash policy — ACCEPT

`net.ipv4.fib_multipath_hash_policy` becomes an observed/owned namespace prerequisite.
The production value will be fixed after target-kernel verification; parser/planner support
must not depend on the host default.

## 9. OUTPUT policy — ACCEPTED ADDITION

ROU-owned OUTPUT becomes default DROP.

First production policy:

- loopback ACCEPT;
- ESTABLISHED,RELATED ACCEPT;
- NEW/ESTABLISHED/RELATED to host0 ACCEPT as the sole local underlay egress;
- no local OUTPUT through Device interfaces.

This deliberately leaves underlay destination unrestricted in schema v1. Later
DeviceManager transport configuration may narrow NEW host0 traffic to explicit transport
endpoints without changing routing semantics.

## 10. Documentation/conventions — ACCEPT

NG1 becomes the current normative architecture. RC2/RC3 are archived baselines.
NG1 English-language architecture documents remain allowed; a translation pass is not a
current priority.

## Implementation/testing consequences

Rootless coverage will include:

- remote-initiated capacity validation;
- restrictive-envelope requirement;
- bound-only state pairs;
- no Device-to-Device state ACCEPT;
- same-name/new-ifindex rule regeneration;
- INPUT default DROP plus publication admission;
- OUTPUT default DROP plus host0-only local egress;
- transition classification: normal binding lifecycle incremental, structural drift
  barrier-required.

Two future experiment gates are recorded:

- flow pinning for capacity>1 remote-initiated Profiles;
- MTU/MSS production behavior.

The implementation cycle then resumes under the established function-by-function external
review process.

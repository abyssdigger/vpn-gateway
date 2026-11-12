# Response to external NG1 network review — 2026-11-12

Architecture baseline: NG1 Draft 5.

This response evaluates the external findings against the current Draft 5 and current
production Python implementation. Several review findings were originally phrased against
an earlier architecture state; where Draft 5 has already resolved the issue, the response
records that fact rather than reintroducing obsolete restrictions.

## 1. Remote-initiated return steering

**Accepted.**

The review correctly identifies that destination-based Profile dispatch alone is
insufficient for a remote-initiated flow when more than one egress interface can carry the
Profile. The host reply can otherwise leave through a lower-metric interface different
from the one that admitted the request.

Production schema version 1 therefore keeps a deliberately simple, fully supportable
contract:

- OUTBOUND has no capacity restriction from this issue.
- INBOUND and BIDIRECTIONAL require active interface capacity exactly 1.
- Capacity is the sum of interface quotas of enabled Devices in the Profile's device_order.
- Disabled Device references do not count.
- Any configuration transition that would make remote-initiated capacity greater than 1 is
  rejected before kernel mutation.

This is not merely a temporary development workaround. It is an acceptable production
constraint in its own right.

A future relaxation to capacity > 1 is possible, but only through proven flow pinning.
EXP-014 is prepared for connmark/fwmark return steering, retired-mark fail-close,
rp_filter interaction, same-name/new-ifindex handling and conntrack cleanup. No code may
silently relax the capacity-one rule before that experiment passes and architecture is
updated.

## 2. Host-side trust boundary for INBOUND/BIDIRECTIONAL

**Accepted with refinement for current Draft 5.**

The original review suggested rejecting INBOUND/BIDIRECTIONAL until Device envelope syntax
exists. Draft 5 now has a real traffic_envelope grammar and materializer, so total parser
rejection is no longer necessary.

Instead, every active Device referenced by an INBOUND/BIDIRECTIONAL Profile must have a
traffic_envelope with terminal default=drop.

The two requirements solve different problems:

- capacity==1 makes return routing correct without marks;
- restrictive Device envelope requires the administrator to state the host-side reach that
  remote-initiated traffic is actually allowed to have.

The Profile itself continues to define the remote source prefix, not the host-side
destination policy.

This is the explicit production offer for remote initiation: the system does not merely
promise a return path; it requires an explicit restrictive boundary for what that path may
reach.

## 3. ESTABLISHED,RELATED interface scoping

**Accepted; current implementation already follows the safe model.**

State-based FORWARD ACCEPT exists only for each currently bound concrete interface I in:

    host0 -> I
    I -> host0

No Device-to-Device state ACCEPT exists. Over-quota, unbound and mere selector-matching
interfaces receive no such rule.

This is now normative architecture, not merely an implementation choice.

Residual tuple matching across two different bound interfaces is acknowledged. For
schema-v1 remote-initiated Profiles it is excluded by capacity==1. General multi-interface
closure belongs to the EXP-014 flow-pinning extension.

## 4. ROU-local INPUT policy

**Accepted.**

ROU owns INPUT as default DROP.

Schema version 1 admits only:

- loopback;
- appropriate ESTABLISHED,RELATED traffic for local connections;
- NEW from host0 only to configured internal publication endpoints.

Device interfaces have no implicit access to ROU-local listeners, including transport
listeners. This is defense-in-depth and does not break publication: the host-side relay
reaches the internal listener through host0.

The current generated firewall implements this model.

## 5. ROU-local OUTPUT policy

**Accepted as an additional hardening decision.**

ROU owns OUTPUT as default DROP.

Schema version 1 admits:

- loopback;
- ESTABLISHED,RELATED local traffic;
- locally initiated traffic whose egress is host0.

No locally generated traffic is implicitly admitted through Device interfaces.

The first production version intentionally does not yet constrain NEW host0 egress by
specific VPN transport destination/protocol because DeviceManager transport configuration
does not yet exist. Future DeviceManager work may narrow this from "NEW via host0" to
explicit transport endpoints without changing the routing model.

## 6. Shadow fallback and UNAVAILABLE trigger

**Shadow fallback retained; trigger intentionally deferred.**

The review is correct that current normal operation never produces UNAVAILABLE from a real
detector. That is deliberate.

The project chooses to implement the fallback mechanism now because:

- EXP-013 already proves its kernel model;
- route projection and verification are implemented and tested;
- retaining it avoids a later routing-model rewrite when availability detection arrives.

What is consciously deferred is the **trigger**: raw Device-specific evidence that
classifies a bound interface as positively UNAVAILABLE. That work belongs to future
DeviceManager/Device-specific availability design.

UNKNOWN and AVAILABLE continue to use normal routes. No production availability detector
may make the ECMP fallback operationally effective until the relevant prerequisite evidence
is complete.

## 7. Protective barrier scope

**Accepted; previous broad invariant is replaced.**

Ordinary binding appearance/disappearance and normalized availability transition do not
by themselves require global ip_forward=0.

The important safety condition is that Profile-local terminal blackhole remains
continuously installed and the observed state is provably one of the previous/new verified
binding generations.

Therefore:

- ordinary verified binding lifecycle -> incremental repair;
- structural/unknown drift -> global protective barrier.

Structural/unknown includes unexpected owned RPDB state, foreign/unrepresentable routes,
unexplained firewall/NAT drift, infrastructure loss, unverified crash recovery and policy
changes whose safe incremental transition cannot be proven.

The persistent shadow fallback remains part of the model.

One backend-specific exception is documented: with interface-name-only iptables matching,
same-name/new-ifindex replacement is not safely distinguishable from the retired generation
during transition and therefore remains structural. The generation-aware nftables backend
is being developed to remove that backend limitation.

## 8. Lifecycle ordering

**Accepted; current implementation already follows the corrected order.**

Fail-closed namespace/bootstrap state is established and verified before the supervised
runtime/publication relay is started. Publications are not used as a pre-barrier bootstrap
step.

Architecture lifecycle text is aligned to that implementation.

## 9. NAT

**Finding valid historically; resolved by Draft 5.**

Enabled Device NAT is explicit:

    nat = "none"
    nat = "masquerade"

There is no inferred production default.

MASQUERADE is Device-scoped and emitted only for currently bound interfaces and remote
prefixes of enabled Profiles referencing the Device.

No additional architecture change is required from this review item.

## 10. MTU/MSS

**Accepted as a production-readiness evidence gate.**

No MSS clamp is introduced by assumption.

EXP-015 is prepared for the real OpenConnect/WireGuard payload topology and will determine
from evidence whether production needs:

- no clamp;
- clamp-to-PMTU;
- or an explicitly justified fixed/Device-specific MSS.

Control-plane implementation may continue; final real-TCP production signoff is gated by
EXP-015.

## 11. ECMP hash policy

**Accepted.**

net.ipv4.fib_multipath_hash_policy is now an observed/owned namespace prerequisite rather
than an inherited implicit default.

A concrete production value is intentionally not guessed. EXP-016 is prepared to determine
accepted values and flow-hash behavior on the target Debian 13 kernel.

Because the production UNAVAILABLE trigger is deliberately deferred, EXP-016 gates the
future activation of ECMP fallback through real availability classification, not ordinary
UNKNOWN-tier routing.

## 12. Language/project conventions

**Accepted and already corrected.**

PROJECT-CONVENTIONS now identifies:

- RC2/RC3 as archived baselines;
- NG1 as current normative architecture;
- English as permitted for the existing NG1 architecture/design/review baseline;
- Russian as preferred for project discussion and operational notes.

No translation pass is required before implementation continues.

## 13. Required tests

Accepted test obligations:

- INBOUND/BIDIRECTIONAL capacity > 1 rejected before mutation;
- capacity 1 with restrictive envelope accepted;
- remote-initiated Profile without default-drop envelope rejected;
- ESTABLISHED/RELATED exists only for bound I<->host0 pairs;
- over-quota interface gets no route/state/local admission;
- no Device<->Device state ACCEPT;
- INPUT host0 publication endpoint accepted; arbitrary host0 local port and all Device-local
  INPUT remain dropped;
- normal verified binding disappearance classified incremental;
- foreign/unknown owned state classified structural/barrier-required;
- same-name/new-ifindex behavior tested explicitly for the selected firewall backend.

## Verdict

The review is accepted as a material semantic correction.

The corrected Draft 5 production contract is:

1. remote-initiated capacity-one + mandatory restrictive envelope;
2. bound-interface-scoped state acceptance;
3. INPUT/FORWARD/OUTPUT default DROP with explicit narrow admissions;
4. persistent shadow fallback retained while its real UNAVAILABLE trigger is consciously
   deferred to future DeviceManager work;
5. incremental ordinary binding lifecycle with global barrier reserved for
   structural/unknown drift;
6. MTU/MSS and future multi-interface return pinning remain explicit prepared experiments,
   not guessed implementation;
7. ECMP hash policy is owned/observed and its eventual concrete value is experiment-gated.

Implementation is reviewed and corrected against this contract before the normal
function-by-function production development cycle resumes.

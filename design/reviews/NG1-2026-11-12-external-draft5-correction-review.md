# External review — NG1 Draft 5 pre-correction

The following review was supplied verbatim by the external reviewer and is archived as
input to the Draft 5 correction cycle.

## Serious findings

1. Return routing for inbound/bidirectional Profiles with multiple interfaces is not
pinned to the ingress tunnel. Destination dispatch may return through another Device.
Suggested first-slice fix: capacity(Profile)=1; later connmark/fwmark flow pinning under a
dedicated kernel experiment.

2. ESTABLISHED,RELATED acceptance must be interface-scoped to each currently bound
interface and host0 in both directions. No state ACCEPT should exist for unbound,
over-quota or Device-to-Device pairs.

3. ROU INPUT policy is underspecified. It should default DROP and admit only loopback,
local ESTABLISHED/RELATED and host0 to configured publication endpoints. Device interfaces
must have no implicit ROU-local INPUT access. Remote-initiated host reach also needs an
explicit trust boundary.

4. Persistent shadow fallback plus global barrier is over-scoped. Ordinary binding
appearance/disappearance and availability changes do not require a global ip_forward=0
barrier when normal survivor routes and terminal blackhole preserve fail-closed behavior.
Structural/unknown drift still requires a protective barrier.

## Smaller findings

- rou up ordering should establish fail-closed state before publication traffic can relay.
- NAT policy must be explicit.
- MTU/MSS behavior needs a real-TCP production experiment.
- net.ipv4.fib_multipath_hash_policy must be owned/verified.
- PROJECT-CONVENTIONS must be aligned with NG1 being the current normative architecture.

## Suggested first-production constraints

- OUTBOUND remains unrestricted by interface capacity.
- INBOUND/BIDIRECTIONAL may be admitted only when capacity(Profile)=1 until proven
  connmark/fwmark flow pinning exists.
- State ACCEPT must be generated only for bound-interface <-> host0 pairs.
- INPUT default DROP with only narrow local/publication admissions.
- Future multi-interface inbound return steering must be gated by a dedicated experiment.

## Suggested tests

- inbound capacity 2 rejected; capacity 1 accepted once policy prerequisites hold;
- over-quota interface creates no state ACCEPT, routes or INPUT admission;
- same-name/new-ifindex binding does not inherit state rules;
- no Device-to-Device ESTABLISHED pair;
- INPUT from Device to ROU-local is dropped; host0 to publication endpoint is accepted;
- normal member disappearance is incremental/no-global-barrier;
- structural drift requires barrier.

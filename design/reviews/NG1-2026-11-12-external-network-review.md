# External review — NG1 Draft 5 follow-up

Source: external reviewer ("зануда"), archived from project discussion on 2026-11-12.

## Serious findings

### 1. Return path for inbound/bidirectional with multiple interfaces

§5.4 says marks are not needed because the host reply to an inbound flow enters on host0
and is dispatched to the Profile table. But that table selects by metric, not by the
interface on which the request was admitted. With multiple bound interfaces, a request
arriving via wg-backup can receive its reply via preferred oc-main. At best the flow
breaks; at worst the reply crosses into another trust domain.

For outbound, no marks are needed. For inbound/bidirectional, either use connmark/fwmark
return steering (gated by a dedicated experiment) or constrain the first production
implementation to Profiles whose active interface capacity is exactly one.

Suggested first-slice constraint:

    capacity(Profile) = sum(Device.interface_quota)
        over active Devices in device_order

Inbound/bidirectional with capacity > 1 is a configuration error before mutation.
Disabled Device references do not count. A later flow-pinning extension can remove this
constraint, but must be experimentally proven.

### 2. ESTABLISHED,RELATED must be interface-scoped

State acceptance must be generated only for currently bound interface pairs:

    -i I     -o host0   ESTABLISHED,RELATED -> ACCEPT
    -i host0 -o I       ESTABLISHED,RELATED -> ACCEPT

No state-based ACCEPT exists for Device-to-Device transit, over-quota/unbound interfaces,
or selector matches alone. A residual case remains when a tuple admitted through bound
interface A arrives through another bound B; closing that requires flow pinning.

### 3. INPUT policy and inbound host-side trust boundary

ROU-owned INPUT should default DROP and accept only loopback, appropriate
ESTABLISHED/RELATED local traffic, and host0->configured internal publication endpoints.
Traffic arriving from any Device interface toward ROU-local addresses should be dropped.

For inbound/bidirectional, Profile source-prefix matching alone does not constrain host-side
destinations. The remote side can otherwise reach any host address reachable via host0 that
BOU/host policy does not block.

The original review proposed rejecting inbound/bidirectional until Device envelope syntax
exists. In the current project state, the envelope syntax now exists, so this needs to be
adapted rather than copied literally.

## Simplification / barrier finding

### 4. Persistent shadow fallback does not require global barrier on ordinary binding changes

Without an availability detector, all bound paths remain UNKNOWN and UNAVAILABLE is not
triggered. The persistent shadow fallback is therefore implemented ahead of its trigger.

EXP-013 showed that disappearance of one member can delete the whole multipath route, but
normal survivor routes remain and terminal blackhole remains. Rebuilding the fallback
from fresh survivors does not create a fail-open window.

Therefore ordinary binding appearance/disappearance and availability transitions do not
require a global ip_forward=0 barrier. Global barrier should be reserved for structural or
unknown drift where safe incremental transition cannot be proven.

The review suggested optionally deferring shadow fallback until availability detection
exists. Secondary analysis preferred retaining it because the projection and EXP-013
evidence already exist and DeviceManager can later add the trigger without changing the
routing model.

## Smaller findings

- rou up ordering should establish fail-closed state before publications can relay.
- NAT policy must be explicit rather than inferred.
- MTU/MSS behavior needs explicit production treatment and a live TCP experiment.
- net.ipv4.fib_multipath_hash_policy should be observed/owned in the namespace.
- PROJECT-CONVENTIONS still names RC3 as current and conflicts with NG1 document language.

## Suggested tests

1. inbound capacity 2 -> configuration error before mutation; capacity 1 -> accepted when
   the value is otherwise supported.
2. over-quota interface creates no ESTABLISHED pairs, routes or INPUT admission.
3. bound interface pair rules disappear with the binding; same-name/new-ifindex is fresh.
4. no Device-interface to Device-interface state ACCEPT pair.
5. INPUT: Device-interface -> ROU-local drops; host0 -> configured publication endpoint
   accepts; host0 -> unrelated local port drops.
6. structural drift requires barrier; normal member disappearance does not.

## Future flow-pinning experiment

For capacity > 1, verify on the target kernel:

- connmark set on admitted remote-initiated flow;
- connmark restore in mangle PREROUTING before route lookup;
- fwmark RPDB selection into per-interface return table;
- rp_filter interaction;
- disappearance of a marked interface resolves to explicit blackhole rather than falling
  through to destination dispatch;
- conntrack handling when an interface generation is retired.

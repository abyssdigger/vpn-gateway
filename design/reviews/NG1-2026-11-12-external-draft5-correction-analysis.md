# Independent analysis of external NG1 review

This analysis was supplied by the second reviewer and is archived as input to the same
correction cycle.

## Verdict

The external reviewer is correct on the substantive findings.

### Return steering

OUTBOUND requires no conntrack mark. Remote-initiated flows do: with several bound egress
interfaces, a host reply is destination-dispatched to the Profile table and can leave by a
different tunnel. Capacity 1 is a correct production restriction until a connmark/fwmark
extension is experimentally proven.

### ESTABLISHED scoping

The architecture wording was ambiguous even though the implementation already generated
bound-interface <-> host0 state pairs. The architecture must make that behavior normative.

### INPUT and host-side trust boundary

ROU-local INPUT was underspecified. Default DROP is required. Remote-initiated Profile
traffic constrains the remote source prefix but not host-side destination, therefore an
administrative restrictive envelope is required if INBOUND/BIDIRECTIONAL is admitted.

### Barrier

Invariant 62 is not merely broad: with persistent shadow fallback and terminal blackhole,
ordinary binding and availability lifecycle transitions do not require a global barrier.
Global barrier belongs to structural/unknown drift. Retaining the shadow fallback is
preferred because it keeps future availability detection additive.

### Smaller findings

rou-up ordering, MTU/MSS, fib_multipath_hash_policy and PROJECT-CONVENTIONS findings are
valid. The NAT finding is already resolved by Draft 5 explicit Device NAT.

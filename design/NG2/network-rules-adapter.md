# VPN-GATE NG2 — NetworkRulesAdapter lower-domain design

**Статус:** active NG2 implementation design  
**Дата:** 2026-11-14  
**Область:** concrete lower domain behind `NetworkRulesAdapter`

## 1. Boundary

Public caller contract remains:

```text
apply(owner, spec: NetworkRulesSpec) -> ActionResult
renewState(owner) -> ActionResult
getLastState(owner) -> NetworkRulesState
cleanup(owner) -> ActionResult
```

`owner` is opaque caller-instance identity. `NetworkRulesSpec` remains independent from
owner/scope usage.

The lower domain owns:

- owner lifetime and physical composition;
- technical Linux allocation;
- route/RPDB/nft/sysctl materialization;
- safe transition ordering;
- fresh observation and semantic reconstruction;
- per-owner `NetworkRulesState`.

## 2. Internal owner identity

The Adapter assigns a monotonically increasing internal `owner_token` to each live caller
instance.

Properties:

- same Python object identity -> same token for its registered lifetime;
- equal-but-distinct objects -> different tokens;
- token has no payload/probe/domain meaning;
- Adapter keeps a strong reference while the owner is registered;
- cleanup releases the owner and its token registration;
- tokens are not reused during one Adapter instance lifetime.

The token exists only below the public Adapter boundary.

## 3. Owner-scoped logical identity

Routing-domain names are caller-local.

Physical/internal identity is therefore:

```text
(owner_token, logical_domain_name)
```

Two callers may both use `"default"` or `"corp"` without collision.

No owner name, type name or semantic caller label is used for technical identity.

## 4. Composition

The Adapter maintains one current desired `NetworkRulesSpec` per registered owner and
composes all live owners for the common physical backend.

Composition rules:

- routing domains remain owner-scoped;
- dispatch rules are considered in one common dispatch space;
- exact duplicate dispatch selectors owned by different owners are ambiguous and rejected;
- different destination prefix lengths remain deterministic through longest-prefix
  ordering;
- allow-only filtering intents from owners compose positively; one owner cannot delete
  another owner's permission by omission;
- flow-initiation allows follow the same positive composition rule;
- source-NAT intents remain owner-scoped during compilation so observation/cleanup can
  preserve provenance;
- no inter-owner priority is invented.

A backend may deduplicate physically equivalent rules, but such optimization must not
destroy the ability to reconstruct each owner's semantic state or to cleanup one owner
without changing another owner's effective state.


## 5. Committed owner generation vs owner lifetime

Owner identity registration and committed desired generation are separate.

A first apply(owner, candidate) may register the caller identity/token before the operation
succeeds, because the caller must still be able to use getLastState(owner) and
cleanup(owner).

However:

- candidate rules are staged;
- committed owner rules change only after verified physical SUCCESS;
- technical routing allocation changes only after the same verified SUCCESS;
- failed replacement leaves the previous committed rules generation intact;
- failed first apply leaves a registered owner with no committed rules;
- failed shared mutation makes current state of all registered owners UNKNOWN until fresh
  observation proves otherwise.

If the requested owner's current interface projection is incomplete, that candidate is
rejected before it becomes physical desired state. The Adapter instead structurally
reconciles the fail-closed projection of the **last committed** owner composition and
returns FAILURE for the candidate. Thus a failed request cannot leave the backend derived
from an uncommitted semantic generation.

This is the Adapter transaction boundary.

## 6. Concrete interface generation projection

Multiple owners may refer to the same concrete interface generation.

A same-name/new-ifindex replacement creates an unavoidable sequential-update window where
owner A already requests the fresh generation while owner B still requests the stale one.

The lower domain must not deadlock waiting for both callers to change atomically.

Before physical compilation the Adapter therefore takes a fresh stable interface inventory
and projects every owner's rules fail-closed:

- absent routing path is removed from ordered_paths;
- routing domain, destinations and terminal disposition remain;
- traffic allow with an absent interface endpoint is removed;
- flow-initiation allow with an absent interface endpoint is removed;
- source-NAT rule with an absent interface endpoint is removed;
- dispatch from LOCAL_NETWORK remains, so the domain terminal route continues to fail-close
  the destination.

This projection does not rewrite an owner's desired intent. It is the observed realisable
subset for the current Linux generation.

apply(owner, spec) may return SUCCESS only when the requested owner's projected rules equal
the requested spec. Other owners may simultaneously be freshly observed as KNOWN divergent
subsets until their own normal RequestEvents update them.

This permits ordinary sequential multi-owner generation updates without cross-owner policy
mutation.

## 7. Namespace prerequisites

The first production backend is deliberately IPv4-only. Before any structural generation
may reopen IPv4 forwarding, the Adapter/Driver lower domain must materialize and freshly
verify these namespace prerequisites:

- `net.ipv4.conf.all.rp_filter=0`;
- `net.ipv4.conf.default.rp_filter=0`;
- `net.ipv4.conf.<local/path>.rp_filter=0` for the local interface and every concrete
  interface generation referenced by the composed rules;
- `net.ipv6.conf.all.forwarding=0`;
- `net.ipv6.conf.default.forwarding=0`;
- `net.ipv6.conf.default.disable_ipv6=1`;
- `net.ipv6.conf.<local/path>.disable_ipv6=1` for the same concrete interfaces.

Global/default values protect the namespace and future interfaces; per-interface values
cover interfaces that already existed before the current structural transaction.

Per-interface sysctl access uses slash-form paths so an interface name containing a dot is
not misparsed as sysctl hierarchy.

These are technical Linux prerequisites, not `NetworkRulesSpec` semantics. They remain
below the Adapter boundary.

Drift in any required value makes exact verification fail. Structural repair applies the
prerequisites only after `ip_forward=0` and verifies them before forwarding can reopen.

## 8. Routing compilation

Each owner-scoped logical routing domain receives a Linux table ID.

Allocation properties:

- existing live (owner_token, domain_name) keeps its table ID;
- reserved Linux tables are never allocated;
- a table removed from the candidate generation remains reserved until verified commit of
  that removal;
- only after verified commit may the ID be reused;
- route protocol 202 marks owned unicast routes;
- route protocol 201 marks owned terminal routes and provides restart ownership evidence;
- ordered paths receive technical metrics 10, 20, 30, ...;
- every normal path metric is strictly below terminal metric 65536;
- every domain receives terminal blackhole default metric 65536.

Global RPDB dispatch follows composed longest-prefix ordering.

For every non-empty owner set the routing backend additionally installs a final host-ingress
unreachable rule after all owned dispatch rules. This terminal rule prevents fall-through
to the namespace main table even if filtering is later damaged. Full cleanup removes it.

The first backend supports dispatch only from semantic LOCAL_NETWORK. Unsupported
interface-origin dispatch is rejected explicitly.

## 9. Filtering and NAT compilation

### 9.1. Filtering

Filtering is materialized into one owned IPv4 nft table with default-drop forwarding.

Dynamic path identity is compiled using numeric iif/oif ifindex, while the stable local
infrastructure endpoint uses iifname/oifname.

Owner provenance is retained in compiler-owned rule comments.

Established/related byte permission is the positive union of owner traffic_allows.

NEW flow permission is not calculated by globally intersecting unions. It is the OR over
owners of traffic_allow_of_owner AND flow_initiation_allow_of_same_owner, so two owners
cannot accidentally synthesize a permission that neither requested.

Semantic TrafficPredicate is compiled below the Adapter boundary into nft expressions;
payload envelope concepts never reach this layer.

### 9.2. Source NAT

Current source NAT support is LOCAL_NETWORK to concrete INTERFACE with target
EGRESS_ADDRESS, materialized as narrow masquerade rules with owner/generation markers.

The local ingress interface is included in the rule so locally generated namespace traffic
does not accidentally enter payload NAT policy.

## 10. Exact observation and verification

### 10.1. Routing

Verification checks:

- fresh interface inventory;
- exact (ifname, ifindex) generation for every desired path;
- exact routes in all owned/transition tables;
- no unexpected route in those tables;
- owned protocol 201/202 routes do not exist outside tracked tables;
- exact RPDB state in the owned priority window;
- terminal host-ingress rule;
- requested net.ipv4.ip_forward state.

Foreign untagged routes outside the owned tables remain outside this Adapter's domain.

### 10.2. nft

EXP-017 showed that nft may render a live numeric interface reference back as an interface
name.

Verification therefore requires both complete canonical table policy and the exact
compiler-owned rule-marker multiset carrying owner and numeric generation data.

A marker match alone is insufficient; canonical policy match alone is also insufficient.

## 10. Structural Driver

The first Driver deliberately implements only one safe structural path:

    1. protectively close IPv4 and IPv6 forwarding
    2. materialize required namespace prerequisites (rp_filter / IPv6 disablement)
    3. fresh observation
    4. remove owned RPDB rules
    5. flush tracked + restart-discovered owned routing tables
    6. install desired routes
    7. install dispatch rules
    8. install terminal host-ingress guard
    9. replace NAT table
    10. replace filter table last
    11. fresh exact verification, including namespace prerequisites, while forwarding
        remains closed
    12. enable IPv4 forwarding only if desired policy requires it
    13. fresh exact final verification

Any failure after mutation begins performs a best-effort protective dual-stack forwarding
close and returns FAILURE.

There is no speculative rollback to a guessed prior state. Recovery is driven by the next
fresh observation/reconcile.

Incremental optimization is intentionally deferred until this exact structural path is
stable.

## 11. Public Linux NetworkRulesAdapter

The current executable Adapter:

- stages owner replacement/removal;
- observes stable interface generations;
- builds the fail-closed realisable owner projection;
- composes owner-scoped semantic rules;
- allocates and compiles concrete Linux desired state;
- invokes the structural Driver;
- commits owner generation and routing allocation only on verified SUCCESS;
- publishes per-owner last state as the freshly verified projected semantic rules;
- keeps getLastState() I/O-free;
- makes unknown-owner cleanup idempotent.

A failed physical mutation marks all registered owner states UNKNOWN because the backend is
shared.

## 12. Evidence gates

Current automated gates include:

- Python unit suite for owner composition, allocation, compiler, verifier and Adapter
  semantics;
- disposable Linux namespace structural integration covering apply/exact renew, terminal
  RPDB guard, same-name/new-ifindex drift, sequential multi-owner generation transition,
  route-drift repair behind the forwarding barrier, per-owner cleanup and final cleanup;
- disposable Linux payload dataplane integration for stateful flow-direction semantics.

Existing EXP-012 and EXP-017 remain supporting architecture evidence; the NG2 live gates
exercise the new compiler and Driver directly.

## 13. Local-process semantic extension

The semantic NetworkRules contract also admits `LOCAL_PROCESS` endpoints for future
AvailabilityProbeManager ownership.

A local-process dispatch is intentionally stricter than host-ingress dispatch and requires:

- destination;
- explicit protocol;
- concrete bound output interface.

This preserves the isolated probe-plane property established by EXP-022/023.

The first Linux backend does **not** materialize this endpoint yet. It rejects
`LOCAL_PROCESS` dispatch explicitly until EXP-024 is confirmed on the Debian 13 target
and routing/nft observation are extended as one physical-policy unit.

The intended lower-domain mapping uses process identity only at local OUTPUT, carries the
admitted flow identity through conntrack state and matches the reverse INPUT flow by that
technical state. Numeric uid/conntrack mark do not belong to the semantic spec.

## 14. Deferred work

Not part of the current structural baseline:

- incremental transition optimizer;
- richer interface-origin dispatch;
- persistent allocation across daemon restart;
- broader predicate-implication analysis above the backend;
- non-Linux backend implementation.

These require separate review units rather than expanding the first safe Driver implicitly.

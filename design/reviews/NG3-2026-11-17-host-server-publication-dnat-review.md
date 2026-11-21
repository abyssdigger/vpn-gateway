# NG3 host server-publication lower-mechanism review — 2026-11-17

## Review unit

Review the EXP-052 result before runtime implementation of canonical
`publish_vpn_server`.

Primary trace:

- `VPNG0001-R1.R2.R4.R6.R3`;
- `VPNG0001-R1.R2`;
- `VPNG0004-R4.R6.R1.R1`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0007-R7.R1`, `R7.R3`, `R7.R5`, `R7.R7`.

## Requirement gate

No new product semantics are required for this unit.

The user-facing grammar, selector semantics and positional port-bundle mapping are already
closed. The implementation obligation is to realize those accepted facts without widening
host/network ownership.

## Constraint gate

The current first-release integration boundary does not grant this unit ownership of
arbitrary host forwarding, host firewall or routing state.

EXP-052 is therefore usable only as a lower realization under an already suitable external
host-forwarding environment. Absence of that prerequisite is an observable unready/error
condition, not permission to set a host-global sysctl.

This is not an `unreal` requirement: historical relay evidence provides an alternate
mechanism if a future deployment cannot satisfy the forwarding prerequisite.

## Component-model review

No new Manager/Agent is justified.

The accepted upper owner remains Device transport publication. The existing
`NetworkPolicyAdapter` boundary may expose a separate host-boundary publication realization
sub-contract, analogous in ownership shape (but not semantics) to the already designed
host-boundary gateway-NAT sub-contract:

```text
observe HostPublicationOwner
apply desired host publication mapping + verify
cleanup owned host publication mapping + verify absence
```

The Linux nft implementation is lower Driver/Executor machinery behind that Adapter. The
managed-domain local admission remains in the existing managed structural policy machinery.

## Finding F1 — host publication must never become a generic port-forwarder

Accepted.

For interface-selected and selector-less entries, the lower rule must prove that the original
destination is local to the host before DNAT. EXP-052 proves `fib daddr type local` for this
purpose.

An exact IPv4 selector additionally matches the configured local IPv4 address.

No rule may match arbitrary transit solely because protocol/port/interface happen to match.

## Finding F2 — normalized mapping must be the only source of DNAT targets

Accepted.

Lower code does not parse configuration strings. It consumes normalized publication records
and expands the already accepted ordered host/internal bundles positionally:

```text
(host_port[0], internal_port[0])
(host_port[1], internal_port[1])
...
```

The target address is the current exact managed-domain local publication address used by the
corresponding EXP-046/047 local-admission intent.

## Finding F3 — ambiguous external keys are a lower-policy conflict

Accepted.

Two normalized publication contributions that would claim the same effective external
protocol/selector/host-port but require different internal targets cannot be materialized by
rule ordering. The desired-state projection must reject the ambiguity rather than making
declaration or Device iteration order semantic.

Identical physical contributions may be set-deduplicated.

This follows the existing unambiguous-configuration/safety requirements and does not add a
new user precedence rule.

## Finding F4 — host and managed halves need separate exact postconditions

Accepted.

A publication is runtime-ready only when both are confirmed:

1. host-boundary external mapping;
2. managed-domain local INPUT/OUTPUT admission.

The host mapping is not folded into `table ip vpn_gate`, and managed publication rules are
not moved to the ordinary host namespace.

For additions, host-side exposure is the final positive edge: managed local admission should
be converged before a missing host mapping is added. For removal/replacement, stale owned
host mappings are removed before obsolete managed local admission is relaxed. Fresh
observation remains authoritative after each lower operation.

## Finding F5 — forwarding prerequisite remains external in this unit

Accepted with explicit visibility.

The DNAT path requires host forwarding. This unit does not mutate host-global
`net.ipv4.ip_forward`, does not reinterpret the managed `ForwardingGate`, and does not
claim that a successful DNAT write alone makes publication ready.

The alpha/beta reference runtime may diagnose the prerequisite as unavailable. If product
ownership of host forwarding is later desired, that is a separate requirement/architecture
review because it can affect unrelated host traffic.

## Implementation gate

PASS.

The next implementation unit may add:

- pure normalized host-publication desired projection;
- strict owned host nft observation/comparison;
- bounded Linux host-publication convergence;
- runtime composition with existing managed local-publication desired state;
- unit + privileged integration evidence.

It must not add:

- a universal host firewall Manager;
- a userspace transport relay merely because legacy generations had one;
- implicit host-global sysctl ownership;
- declaration-order conflict resolution;
- new user-facing publication grammar.

## Accumulated link inventory

- decomp: no new decomp links in this unit; existing accepted decomp links unchanged.
- unreal: none active.
- broken: none active.
- closure_rejected: none.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R1` -> `VPNG9001-R1.R1.R1`

The original IDs in the historical body are intentionally preserved.

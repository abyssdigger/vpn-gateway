# NG3 WireGuard peer-probe reuse boundary — 2026-11-25

## Question

Can D.002 `WireGuardPeerManager` directly reuse the existing production availability probe
runtime/policy stack for per-peer technical probes, or would that silently change the identity
model selected for same-interface WireGuard peers?

## Relevant selected architecture

D.002 keeps all peers behind one managed `wg0` inside one logical path. A peer is explicitly
not a `LogicalPathId`. Its permanent `probe_target /32` is technical evidence used only for
peer selection. D.002 owns selection and peer-realization generation; D.003 owns exact
full-state `AllowedIPs` convergence.

## Current implementation inventory

The current production availability machinery is reusable only in narrower layers than its
names suggest:

- `ProbePolicyOwner` is structurally `(profile_id, LogicalPathId)`;
- probe layout/projection sorts and allocates directly by `owner.profile_id` and
  `owner.path_id`;
- `AvailabilityProbeRuntime` maps current intents to path routes through
  `owner.path_id`;
- `ProbeExecutionPrecondition` is keyed by that same owner type;
- `LinuxIcmpProbeDriver.check()` accepts `ProbeObservationContext`, which embeds
  `AvailabilityProbeIntent` and therefore the A.007 owner model;
- the genuinely reusable lower pieces are the bounded subprocess runner, timeout policy,
  ICMP command/result classification mechanics, and C.001 routing/nft machinery underneath
  the A.007-specific desired projection.

## Finding

Direct reuse of the complete availability stack would require inventing a synthetic Profile and
`LogicalPathId` per WireGuard peer. That would violate D.002 decision 1, leak peer identity
into the path model, and make A.007 status/availability semantics accidentally own technical
peer selection.

Duplicating the ping implementation inside D.002 would avoid that identity violation but would
create a second physical probe Driver with the same namespace/UID/timeout/result-classification
mechanics.

Neither is acceptable.

## Selected implementation boundary

The production implementation should proceed in three lower-to-upper increments:

1. **D.003 exact owner-state Enforcer.** Implement fresh observation and full desired
   `AllowedIPs` convergence independently of selection policy. This is already supported by
   EV-00050 and does not require a peer-probe semantic owner.
2. **C.008/C.001 reusable physical peer-probe seam.** Extract a protocol-neutral ICMP physical
   execution context from the A.007-specific `ProbeObservationContext`, while keeping A.007
   wrappers/API behavior unchanged. Add a separate D.002 peer-probe owner identity for
   owner-scoped route/local-admission preconditions; do not widen `ProbePolicyOwner` by
   pretending peers are paths.
3. **D.002 Manager.** Own current ordered peer set, current base/interface generations,
   per-peer bounded technical evidence, selected owner, peer-realization generation and
   problem state; call D.003 only with complete desired owner state.

A.007 Profile availability remains downstream. When D.002 publishes a new confirmed
peer-realization generation, old Profile availability evidence for the unchanged
`LogicalPathId` must be invalidated rather than reused.

## Selection semantics retained

No new preference policy is introduced. With no confirmed owner, choose the first configured
peer with fresh positive technical evidence. Keep a current owner while it remains positively
confirmed. On confirmed current-owner failure, choose the most preferred peer with fresh
positive evidence. Recovery of a more preferred non-owner alone does not force failback.

## Consequence for the next implementation unit

The shortest production path is D.003 first, then the narrow C.008/C.001 reuse seam, then
D.002. Implementing a D.002 mock-only manager before those lower contracts would prove only
selection arithmetic and would leave the difficult ownership/observation boundary unresolved.

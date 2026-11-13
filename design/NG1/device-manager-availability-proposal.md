# NG1 Profile-binding availability/control — design reset

Status: **SEMANTIC MODEL AGREED; PROBE-PLANE MECHANISM PENDING EXP-022**

> The filename is retained for link stability. Availability is no longer modeled as a
> DeviceManager-owned global interface state.

## 1. Core abstraction

Availability answers one question:

    is concrete interface A available in Profile B right now?

The runtime key is conceptually:

    (Profile, concrete bound interface)

and the control result is:

    ON | OFF

`ON` means that binding may participate in that Profile's payload materialization.
`OFF` means it may not.

Availability is therefore Profile-local. The same `vpns0` may be ON in `profile1` and OFF
in `profile2` at the same time.

## 2. Ownership boundary

DeviceEngine owns Device discovery, binding, quota and publication. It reports which
concrete interfaces are bound to each Device and does not own Profile availability.

An external Profile-binding control layer combines:

- administrator intent from configuration;
- current Device bindings;
- current condition results;

and produces ON/OFF for each relevant `(Profile, binding)` pair.

TrafficEngine consumes the pair result, not the detector mechanics or reason strings.

## 3. Conditions

Availability is not synonymous with ping. It is the conjunction of the conditions selected
for a pair by configuration and runtime policy.

Possible conditions include:

- interface exists and is administratively usable;
- endpoint A is reachable through this concrete interface;
- no manual administrative inhibit is active;
- current time is inside an allowed schedule;
- future Profile/interface-specific predicates.

An ICMP echo check is merely the first active condition with useful experimental evidence.

When no additional control is configured, ordinary baseline interface usability is enough
for ON. When additional conditions are configured, a fresh pair starts OFF and becomes ON
only after all required conditions are positively satisfied.

## 4. State lifetime

ON/OFF is **never persisted**.

Availability describes now. After restart every condition is evaluated again from current
evidence. Retrospective availability history belongs in journald/logs, including transition
reason and relevant condition diagnostics.

Device binding history and deterministic metric history remain separate existing concerns.

## 5. Metrics and payload state

Metric allocation depends on configuration plus Device bindings, not ON/OFF.

For example:

    vpns0 -> metric 1
    vpns1 -> metric 2

remains the metric projection while `(profile1, vpns0)` is OFF. Returning that pair to ON
restores its Profile-specific materialization at metric 1; no availability-specific metric
slot is created or retained.

There is no `UNAVAILABLE_METRIC` and no shadow payload fallback. If all pairs usable by a
Profile are OFF, the Profile's terminal blackhole is the routing result.

## 6. Complete TrafficEngine effect

OFF is broader than deleting one route. A future implementation must suppress every
Profile-specific payload permission associated with that pair consistently, including:

- its normal Profile route;
- generated Profile direction policy for that concrete binding;
- Profile-derived NAT contribution where applicable.

Device-scoped state such as the binding itself and the Device traffic envelope remains
separate. This is why ON/OFF must not be implemented as an availability field inside
`BoundInterface`.

## 7. Probe/control plane

A condition that is responsible for turning a pair back ON must continue operating while
the payload pair is OFF. Therefore active probes require routing and firewall state
isolated from Profile payload tables.

Desired shape, subject to EXP-022:

- dedicated probe identity/UID;
- socket bound to the concrete interface;
- RPDB selection restricted by probe identity, target, protocol and bound output device;
- dedicated probe routing table;
- fail-closed terminal action in that table;
- separate narrow nft admission for probe request/reply;
- no probe route in a Profile payload table.

## 8. Evidence already established

EXP-019 (WireGuard) and EXP-020 (OpenConnect) prove that process/interface presence can
survive while the payload path is unusable, and that an active path probe can distinguish
loss/recovery without ending the binding lifetime.

EXP-021 proves on the target Debian 13 system that:

- ICMP ping sockets work with empty capability sets and `NoNewPrivs=1` when a narrow
  namespace-local `ping_group_range` admits the probe gid;
- nft admission can be restricted to concrete ifindex, exact target and echo request/reply;
- an interface-bound ping does not silently follow an alternate ordinary route;
- same-name/new-ifindex does not inherit stale numeric nft admission;
- exact numeric ifindex reuse is possible and stale numeric nft admission matches the new
  interface if the same ifindex is deliberately reused.

The last result means `(ifname,ifindex)` is useful during continuously observed lifetime
but cannot prove continuity across a missed lifecycle/restart. This is another reason
current availability/control state is never restored from durable storage.

EXP-013 and EXP-016 remain valid evidence about Linux ECMP/fallback behavior, but their old
persistent-shadow production use is superseded by the present model.

## 9. Current implementation gap

The production core has been returned to the deterministic baseline: Device bindings,
stable metric projection, normal routes and terminal blackholes. Old global
`UNKNOWN/AVAILABLE/UNAVAILABLE`, `UNAVAILABLE_METRIC` and shadow fallback code have been
removed.

The current `EnvironmentInterface` model still records identity only, not administrative
`UP` state. That is intentional for now: Device binding must not be redefined as Profile
availability. The future Profile-binding control layer will need current link usability
evidence without changing DeviceEngine ownership.

## 10. Next gate — EXP-022

Before choosing the production condition scheduler or configuration grammar, prove that an
active probe can live in an isolated control plane while the corresponding Profile payload
path is absent.

EXP-022 must establish at least:

1. combined RPDB selectors can steer only the intended locally generated bound probe into
   a dedicated table;
2. ordinary payload and unrelated local traffic cannot consume the probe table;
3. the probe remains functional with no Profile payload route for that interface;
4. alternate paths cannot turn the probe into a false positive;
5. interface deletion/recreation and ifindex reuse have understood fail-closed semantics;
6. narrow nft probe admission remains sufficient.

## 11. Decisions deliberately left open

After EXP-022, human review still needs to choose:

- the exact router-config grammar and schema-version transition;
- condition composition grammar beyond the initial all-required/AND model;
- ICMP timing, timeout and failure/recovery hysteresis;
- APIs/grammar for future manual inhibits and schedules;
- the final runtime component name and ownership boundary for the control evaluator.

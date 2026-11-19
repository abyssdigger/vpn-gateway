# NG3 — Development declarations

These declarations record current engineering intent that is deliberately **not** promoted to
the normative requirement tree yet. They do not create product acceptance criteria,
architecture closure gates or implementation obligations by themselves. The project may
revisit and, where justified by working-code evidence and product need, convert them into
formal Requirements/Constraints later.

## Resource efficiency and weak-device suitability

VPN-GATE should remain practically suitable not only for powerful hosts but also for
resource-constrained gateways and weak devices.

Where several designs provide the required observable behavior, prefer the simpler design
with lower steady-state CPU, memory, allocation and state-tracking cost. In particular,
per-flow/conntrack-like state, large lifecycle tables, background bookkeeping and other
resource-expensive machinery should not be introduced merely for theoretical completeness
when bounded Profile/path-level state provides the needed behavior.

This declaration is supporting engineering guidance only. It is intentionally not a current
Requirement or Constraint; quantitative limits and acceptance thresholds are deferred until
working implementation evidence provides a useful basis for them.


## Runtime transparency / config-shaped current-state snapshot

Preliminary user expectation: VPN-GATE should provide a way to render a current-state snapshot
in a representation deliberately close to the human-facing configuration model, so an
administrator can understand what the gate is actually using without reconstructing that
state from Linux routes, nftables rules, metrics or logs.

The snapshot is expected to be organized primarily by the same stable user-facing entities:

```text
Device
    -> currently observed runtime facts/bindings relevant to that Device

Profile
    -> currently used concrete interfaces/paths in effective route-preference order
    -> availability annotation for each such path/interface
```

For Devices, the presentation should expose the runtime parameters/facts the product currently
observes and uses when resolving the configured Device, while preserving the distinction
between configured expectations and observed current state.

For Profiles, the presentation should make the effective path order visible rather than merely
echoing configured `device_order`: the user should be able to see which concrete interfaces
or logical paths currently participate, in the order in which routing would actually prefer
them, together with their current availability state.

The output should remain conceptually close enough to the configuration language that a user
can compare intended configuration with effective runtime state directly. Internal Linux
implementation identifiers may be included when diagnostically useful, but must not become
the primary organizing model.

This is intentionally only a preliminary user expectation in the current cycle. It is **not**
yet a normative Requirement/Constraint, does not reopen the currently closed requirement
tree, and does not yet define a command/API, serialization format, exact field set, freshness
or atomicity guarantee, persistence behavior, or compatibility contract. Those semantics
require separate requirement discussion before implementation.

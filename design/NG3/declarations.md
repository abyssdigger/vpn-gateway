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

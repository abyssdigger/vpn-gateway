# Production implementation review 12 — long-running reconcile loop

Role: external expert review focused on daemon containment, retry/liveness behavior,
event-vs-snapshot semantics, durable state use and Rust migration.

## Scope

Reviewed `runtime.py`, runtime-loop tests, PlannerEngine and runtime state store contract.

## Findings

### F1 — wakeup-source failure could exit without containment

The first loop version only closed forwarding on normal termination. A failing event
source could raise outside Planner and leave the last verified forwarding state enabled
while the control daemon had stopped.

Severity: high, containment.

Recommendation: wrap the entire long-lived loop in `try/finally` and best-effort close
IPv4 forwarding on every exit, while allowing the original exception to propagate.

Disposition: fixed. A regression test verifies watcher failure propagation plus final
forwarding close.

### F2 — persistent interface churn could busy-spin retry

`PlannerRetryRequired` correctly avoids waiting for another external event, but an
unstable environment could produce unbounded immediate retries.

Severity: low/medium, liveness/resource use.

Recommendation: use the configured retry delay for failed/churned Planner passes while
retaining event-independent immediate scheduling. Successful
`needs_immediate_reconcile` promotion passes should remain delay-free.

Disposition: fixed.

### F3 — mechanical finally edit briefly suppressed exceptions

During implementation, a mechanical edit placed a return inside `finally`, which would
have hidden wakeup exceptions. This was caught by source inspection before test/merge and
corrected. Final code has a containment-only finally and returns after it.

Severity: implementation-process defect, resolved before baseline.

## Whole-scope review

- startup closes forwarding before loading runtime state;
- corrupt/insecure runtime state aborts startup fail-closed;
- first reconcile is immediate;
- events are wakeups only; their payload is never used for decisions;
- periodic audit guarantees drift detection even if an event is lost;
- metric-release follow-up pass runs without waiting for an event;
- failed Planner passes remain fail-closed and retry;
- every loop exit closes forwarding.

## Rust-alignment review

The event source and stop predicate are trait-shaped. The loop owns explicit counters and
has no hidden async state. It can later map to a synchronous Rust loop or tokio task while
preserving the same Planner contract.

## Verdict

Approved after F1/F2 corrections. No remaining recommendation in runtime-loop scope.

# Production implementation review 19 — instance runtime composition

Role: external expert review focused on crash recovery, service composition, single-instance
ownership, error propagation and Rust migration.

## Scope

Reviewed `runtime_app.py`, runtime-app tests and the composition of instance verification,
publication supervision, RTNETLINK wakeups, Planner loop and durable state.

## Findings

### F1 — restart after SIGKILL could be permanently blocked by stale open forwarding

The initial composition verified the instance before explicitly closing forwarding. If the
previous process died via SIGKILL/power interruption while ip_forward=1, the new runtime
would reject the instance rather than contain and recover it.

Severity: high, crash recovery.

Recommendation: after loading the known instance config, best-effort set namespace
ip_forward=0 before structural/prerequisite verification.

Disposition: fixed.

### F2 — publication teardown failure could mask the primary runtime exception

A bare finally calling supervisor.close() could replace the original Planner/event failure
with a secondary teardown error.

Severity: medium, diagnostics/control flow.

Recommendation: preserve and re-raise the primary exception; log secondary teardown
failure. On normal completion, publication teardown failure may remain fatal.

Disposition: fixed.

## Whole-scope review

- runtime never creates/adopts namespace infrastructure;
- instance is verified after fail-close containment;
- single-instance lock is acquired from a protected runtime directory;
- router and instance config are loaded before services start;
- publication endpoints are derived from typed config plus explicit instance addresses;
- publication supervisor health feeds runtime containment;
- RTNETLINK source remains wakeup-only;
- ConfigNatProvider is the production NAT implementation;
- state path comes from instance config.

## Rust-alignment review

Composition is explicit dependency wiring. RuntimeLock, supervisor, watcher and Planner are
separate ownership objects and can map directly to Rust RAII guards.

## Verdict

Approved after F1/F2 corrections. No remaining recommendation in runtime-composition scope.

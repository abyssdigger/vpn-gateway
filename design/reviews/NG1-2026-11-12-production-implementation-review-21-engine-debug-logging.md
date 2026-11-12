# Production implementation review 21 — Engine DEBUG decision trail

Role: external expert review focused on operational observability, secret safety and
Python-to-Rust tracing compatibility.

## Scope

Reviewed DEBUG logging added to DeviceEngine, TrafficEngine and PlannerEngine plus its
tests and Draft 5 §16 requirements.

## Finding

### F1 — Planner start log initially executed before configuration validation

The first logging implementation evaluated `config.active_device_names` before entering
the Planner try/validation boundary. A malformed programmatic ActiveConfig containing an
unknown Device reference could therefore raise from diagnostic code before Planner
best-effort containment.

Severity: medium; diagnostic code must never alter safety semantics.

Disposition: fixed. Configuration is validated first, then the start record is emitted
inside the fail-closed Planner exception boundary.

## Whole-scope assessment

DeviceEngine now exposes:

- ordered observed (ifname,ifindex) identities;
- previous expectation count and active Device IDs;
- selector/quota candidate projection;
- final bound/over-quota identities and normalized availability.

TrafficEngine exposes:

- bound and committed-history counts;
- enabled Profile IDs;
- per-range member/reservation state;
- final stable metric assignments and waiting-for-slot identities.

PlannerEngine exposes:

- validated Profile/Device scope and committed-state sizes;
- fresh observed interface/routing summary;
- desired projection counts;
- steady-open / verified-closed-reopen / incremental-lifecycle / structural-barrier
  decision path;
- transition-classifier reasons;
- mutation-plan command counts;
- verification failure reasons;
- durable commit outcome and follow-up-reconcile requirement.

No credential-bearing Device configuration, passwords, keys, publication packet contents,
raw TOML or generic full argv are logged.

The stable subject prefixes are suitable for direct migration to structured Rust
`tracing` events without changing the control-plane model.

## Verdict

Approved after F1 correction. No remaining recommendation in Engine DEBUG logging scope.

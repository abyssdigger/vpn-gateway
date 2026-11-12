# Production implementation review 04 — routing/RPDB mutation planner

Role: external expert review focused on mutation safety, Linux command semantics, drift
repair and future Rust command-backend design.

## Scope

Reviewed `kernel_mutation.py`, its tests, v0 proven apply sequence and Draft 4 barrier
requirements.

## Command-semantics verification

- direct and multipath route command shape reuses the EXP-013/v0 proven iproute2 forms;
- RPDB terminal rule uses documented `type unreachable` with `iif host0`;
- explicit rule priorities remain before the conventional main rule.

## Findings

No corrective finding remains.

## Safety observations

- the first command always closes `net.ipv4.ip_forward`;
- the plan never contains a command that reopens forwarding;
- all current custom RPDB rules in priorities 1..32765 are removed, which is valid because
  the ROU network namespace owns that policy domain;
- desired Profile tables are full-rebuild objects, so observed tables are flushed before
  reinstall;
- stale historical ROU tables are discovered by ROU route protocol tags and flushed;
- a ROU-tagged route in a reserved table is treated as structural error rather than
  risking a flush of local/main/default;
- any race/failure after barrier-close leaves forwarding disabled.

## Rust-alignment review

Commands are immutable argv vectors, never shell strings. Planning is pure and execution
is intentionally separate. This maps naturally to a Rust enum/Vec<OsString> mutation plan
and avoids quoting/injection concerns.

## Verdict

Approved. No recommendation remains in this scope.

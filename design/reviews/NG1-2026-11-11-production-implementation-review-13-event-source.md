# Production implementation review 13 — RTNETLINK wakeup source

Role: external expert review focused on iproute2 process behavior, event-loop robustness,
lost-event tolerance and Rust migration.

## Scope

Reviewed `event_source.py`, its tests, current ip-monitor documentation and the runtime
rule that events are wakeups only.

## External behavior verification

Current iproute2 documentation confirms that `ip monitor` accepts an OBJECT-LIST
including `link`, `address`, `route` and `rule`, opens RTNETLINK and reports state
changes continuously. The implementation monitors exactly those objects. Sysctl and
iptables drift remain covered by the runtime periodic audit rather than falsely assumed to
be RTNETLINK events.

## Findings

### F1 — separate unread stderr pipe could theoretically block watcher

The first implementation created a dedicated stderr pipe but did not consume it while the
monitor was alive. A sufficiently chatty warning/error stream could fill that pipe and
stall the event source.

Severity: low/medium, long-running process robustness.

Recommendation: use one nonblocking merged stdout/stderr pipe. If bytes are read after the
child has exited, treat them as exit diagnostics rather than an ordinary wakeup.

Disposition: fixed.

## Whole-scope review

- monitor payload is opaque and never becomes policy input;
- raw nonblocking FD avoids TextIOWrapper buffering traps;
- timeout is distinct from event;
- monitor process death is surfaced as EventSourceError;
- burst output is safely collapsed into wakeup semantics;
- close terminates and reaps the child;
- runtime periodic audit covers lost RTNETLINK events and non-netlink drift.

## Rust-alignment review

The source is a small Wait trait implementation with explicit lifecycle and opaque event
bytes. A Rust implementation can replace the iproute2 subprocess with a netlink socket
without changing RuntimeLoop or Planner interfaces.

## Verdict

Approved after F1 correction. No remaining recommendation in this scope.

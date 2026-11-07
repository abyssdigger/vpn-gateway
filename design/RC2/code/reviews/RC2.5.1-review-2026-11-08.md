# Independent Technical Review — RC2.5.1 / RC2.4.1

**Date:** 2026-11-08  
**Implementation:** RC2.5.1  
**Architecture:** RC2.4.1  
**Basis:** current daemon implementation, RC2.4.1 architecture, CHANGELOG, EXP-001..EXP-003, and the five test files present at review time.

This review is retained as an implementation-stage expert assessment. It is not normative architecture; accepted findings should be reflected separately in code, experiments, architecture, or CHANGELOG as appropriate.

## EXP-003 — what is confirmed and what is not

### Confirmed by the live result

- foreground startup, including config-independent startup cleanup, completed;
- `ip_forward=1` was enabled;
- owned `proto 201 metric 65536` blackhole for `10.0.0.0/8` was present;
- owned `proto 202 metric 10 onlink via 172.20.130.5 dev vpns0` route was present;
- `VPNG-OC-*` chains and prefix jumps were present;
- MASQUERADE through `vpns0` worked;
- a Windows LAN client traversed the complete path
  `<gateway-lan-ip> -> 172.20.130.5 -> <lan-router-ip> -> <protected-target-ip>`;
- the target remained reachable after installing the route through the gateway.

### Not confirmed by EXP-003

- graceful shutdown cleanup;
- crash / `kill -9` recovery;
- runtime drift repair;
- periodic reconciliation;
- Netlink self-healing.

Therefore the bootstrap happy path is validated, while fail-closed behavior in abnormal scenarios and cleanup-safety still require live validation.

---

## Q1 — bootstrap logic / fail-closed

No critical fail-closed violation was found. The `apply()` sequence follows the intended architecture:

1. initial route/interface snapshot;
2. `_build_plan` + `_validate_plan` before side effects;
3. `iptables-restore --noflush`;
4. `_check_fixed_firewall_nat` must return `SAFE`;
5. `_apply_plan`: BLACKHOLE first, then deletes, replaces, remaining adds;
6. `_verify_plan` against the same desired snapshot;
7. `_require_complete_profile_results`;
8. `_commit_owned`;
9. `set_ip_forward(True)` last.

This is consistent with invariants 12, 13, 93, 144, 145, and 169. Any failure before forwarding is enabled remains fail-closed: forwarding is still disabled, blackholes protect managed prefixes, and the next start begins with config-independent cleanup.

### 1.1 `_commit_owned` occurs before `set_ip_forward(True)`

Current ordering:

```python
self._commit_owned(...)
self.kernel.set_ip_forward(True)
if not self.kernel.get_ip_forward():
    raise KernelError(...)
```

This is functionally safe because a subsequent startup cleanup removes the partial state, but it weakens the semantic meaning of OWNED: state is committed before the whole apply operation has succeeded.

**Recommendation:** move `_commit_owned` after successful `set_ip_forward(True)` and confirmation.

### 1.2 `apply()` does not use read-before-write for `ip_forward`

Current bootstrap always writes `1`, while invariant 162 requires read-before-write. Startup cleanup currently guarantees `0`, so this is not a practical defect in the present lifecycle, but it becomes relevant if `apply()` is ever reused without cleanup.

**Recommendation:** align bootstrap with the read-before-write pattern already used by the runtime helper.

### 1.3 Route and interface inventory are two kernel reads

```python
initial_routes = self.kernel.list_routes()
interface_ipv4 = self.kernel.list_interface_ipv4()
```

These are independent calls, so kernel state may change between them. For bootstrap this is a small race, but invariant 93 describes one fresh snapshot.

**Recommendation:** consider a kernel snapshot abstraction returning both inventories together if strict snapshot semantics are required.

### 1.4 Metric collision with a foreign route is not rejected during validation

Validation compares exact `RouteSpec` values. A foreign route with the same destination/metric but different type or protocol may not be detected before `ip route add`, which can then fail with `EEXIST`.

This remains fail-hard rather than fail-open. It is an edge case, not a blocker for the current lab topology.

---

## Q2 — blackhole + unicast coexistence and materialization order

The coexistence model is sound:

- `proto 201 metric 65536 type blackhole` is the low-priority safety route;
- `proto 202 metric 10 type unicast via peer dev iface onlink` is the preferred forwarding route.

With the unicast route present, it wins route selection. If the unicast route disappears, the blackhole remains and protects the managed prefix.

The materialize -> verify -> enable-forwarding sequence is also correct.

### Readiness caveat

Architecture readiness is defined as interface exists + expected local address present, not by `operstate` or `LOWER_UP`. If an interface is administratively down but retains its address, `_profile_is_ready` may still report ready.

This is not necessarily a bug because the fixed FORWARD policy adds defense in depth, but the distinction should remain explicit.

### Foreign exact metric collision

A foreign unicast route with the same prefix and metric can cause a hard `ip route add` failure. If such initial state is realistic on deployment targets, validation should detect it and either reject it clearly or deliberately convert the operation to replace semantics.

---

## Q3 — fixed firewall/NAT ownership and cleanup semantics

Ownership is sound:

- daemon-owned chains are identified by the `VPNG-` prefix;
- built-in jumps are identified by jump targets into the `VPNG-` namespace;
- cleanup does not flush complete tables;
- foreign UFW/Docker/SSH rules are retained;
- comparison accepts foreign rules after the daemon-owned prefix;
- MASQUERADE is owned by `VPNG-<PROFILE>-NAT`.

Cleanup ordering also matches the architecture:

1. disable forwarding;
2. remove owned `proto 202` routes;
3. remove daemon firewall/NAT resources;
4. remove `proto 201 metric 65536` blackholes only after the prior cleanup succeeds;
5. verify absence of owned routes and firewall resources.

Cleanup is config-independent.

### 3.1 Unconditional write of `ip_forward=0`

Current cleanup writes `0` even when forwarding is already disabled. If the process can read procfs but cannot write it, cleanup may fail unnecessarily despite the desired value already being present.

**Recommendation:** read first and write only when forwarding is enabled, then confirm the result.

### 3.2 Empty firewall cleanup payload

If no `VPNG-*` resources exist, the cleanup payload is empty and `iptables_restore` is skipped. This is correct idempotent behavior.

### 3.3 Fresh verification catches races

The final no-VPNG verification uses a fresh `iptables-save`. If another actor inserts a `VPNG-*` jump between deletion and verification, cleanup fails rather than declaring success. This is correct fail-closed behavior.

---

## Q4 — required validation before runtime self-healing

### A. Required before the next stage

#### A1. Graceful shutdown from RUN

Send `SIGTERM` while the daemon is in RUN and verify:

- signal wakeup exits the blocking loop;
- cleanup completes;
- process exits successfully;
- `ip_forward=0`;
- no owned `proto 202` routes;
- no owned `proto 201 metric 65536` blackholes;
- no `VPNG-*` chains or jumps.

Then repeat cleanup against already-clean state to confirm idempotency.

#### A2. Cleanup failure path

Artificially break a cleanup boundary, for example the iptables inventory/restore path.

Expected behavior:

- cleanup fails with non-zero exit;
- `ip_forward=0`;
- blackholes are not removed if earlier cleanup stages failed;
- the failure is clearly logged.

#### A3. `kill -9` recovery

Test both:

- `kill -9` during RUN;
- `kill -9` during apply.

On the next startup, config-independent cleanup must remove orphaned/partial markers and a fresh apply must succeed.

#### A4. Idempotent up -> down -> up

- first startup produces state A;
- graceful shutdown leaves no daemon-owned state;
- second startup produces state B;
- A and B are equivalent apart from insignificant iptables counters/comments.

#### A5. SIGTERM between forwarding enable and READY

Exercise the startup shutdown checkpoint after apply but before `READY=1`.

Expected:

- cleanup runs;
- `READY=1` is not emitted;
- RUN is not entered;
- process exits cleanly;
- no daemon-owned state remains.

#### A6. Deployment / systemd behavior

Before enabling service watchdog behavior, verify the deployment contract live:

- `iptables-save` invocation without unsupported `-w`;
- `iptables-restore -w N --noflush` bounded wait;
- service stop/recovery semantics after abnormal process death;
- watchdog design.

Current `run()` blocks indefinitely in `select.select([reader], [], [])`. Therefore a future `WatchdogSec=` cannot be enabled until RUN periodically wakes and sends `WATCHDOG=1`.

### B. Useful corrections before runtime reconciliation

1. make cleanup `ip_forward` handling read-before-write;
2. move `_commit_owned` after confirmed forwarding enable;
3. make bootstrap forwarding enable read-before-write;
4. consider a combined kernel route/interface snapshot;
5. optionally detect foreign destination/metric collisions before route mutation.

### C. Optional cleanup

- `InterruptedError` handling in `run()` is probably unnecessary on modern Python due to PEP 475, but harmless as defensive code;
- replace parser-related `assert isinstance(...)` with explicit errors if optimized Python execution must preserve those checks;
- revisit `_routes_for_profile` overlap semantics if it later becomes more than a diagnostic helper.

---

## Summary

| Area | Assessment |
|---|---|
| Bootstrap / fail-closed | No critical violation found. Minor semantic/robustness improvements remain. |
| Blackhole + unicast | Correct for the tested model and live topology. |
| Firewall/NAT ownership | Correctly scoped to daemon namespace; no blind table flush. |
| Cleanup | Semantically correct; read-before-write for forwarding would improve robustness. |
| Next validation | Graceful shutdown, cleanup failure, kill -9 recovery, up/down/up idempotency, pre-READY signal handling, deployment/watchdog behavior. |

**Worst fail-closed risk found in RC2.5.1:** none.

The next milestone can remain narrowly scoped to graceful shutdown/cleanup validation. Runtime reconciliation and self-healing should remain deferred until the lifecycle and recovery cases above are proven live.

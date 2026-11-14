# NG2 — IPv4-only namespace prerequisites review

**Дата:** 2026-11-14  
**Тип:** autonomous cross-baseline safety review  
**Scope:** Linux namespace prerequisites and forwarding containment

## Trigger

При подготовке namespace lifecycle следующего runtime unit NG2 lower domain был сравнен с
закрытым NG1 production baseline.

NG1 явно materialize/verify'ил:

- reverse-path filtering prerequisites;
- IPv6 forwarding closure;
- IPv6 disablement for payload interfaces.

В текущем NG2 structural Linux Adapter эти требования отсутствовали: exact verification
покрывал routes/RPDB/nft/`ip_forward`, но не namespace sysctls.

Поскольку NG2 backend по-прежнему является IPv4-only и nft policy использует family
`ip`, это не редакторское расхождение, а safety/effective-service gap.

## Findings

### P1 — NG2 lost reverse-path filtering prerequisites from the proven baseline

**Severity:** correctness/service  
**Disposition:** fixed.

Strict/default `rp_filter` can invalidate asymmetric/multipath VPN traffic independently
of an otherwise correct route/nft generation.

NG2 desired physical state now includes:

- `net.ipv4.conf.all.rp_filter=0`;
- `net.ipv4.conf.default.rp_filter=0`;
- per-interface `rp_filter=0` for the local interface and every concrete referenced path.

Structural materialization applies these only after the forwarding barrier is closed.
Exact observation/renew verifies them and therefore detects drift.

### P2 — IPv4-only nft policy requires explicit IPv6 containment

**Severity:** safety  
**Disposition:** fixed.

An IPv4-only nft table cannot be treated as a complete forwarding policy while namespace
IPv6 forwarding may be enabled.

NG2 now requires:

- `net.ipv6.conf.all.forwarding=0`;
- `net.ipv6.conf.default.forwarding=0`;
- `net.ipv6.conf.default.disable_ipv6=1`;
- per-interface `disable_ipv6=1` for the local interface and referenced concrete paths.

Global/default forwarding closure protects the whole namespace. Per-interface disablement
also covers interfaces that existed before defaults were set.

These requirements remain Linux technical state below `NetworkRulesAdapter`; they are not
added to `NetworkRulesSpec`.

### P3 — bootstrap barrier originally closed only IPv4 forwarding

**Severity:** safety/startup  
**Disposition:** fixed during review.

Even after P2, waiting until the first owner apply to close IPv6 left a restart window in
which stale IPv6 forwarding could remain active.

`close_forwarding_verified()` now closes and freshly verifies:

- `net.ipv4.ip_forward=0`;
- `net.ipv6.conf.all.forwarding=0`;
- `net.ipv6.conf.default.forwarding=0`.

Ordinary policy opening remains IPv4-only. Failure containment also invokes the dual-stack
close.

Privileged restart integration deliberately starts with both IPv4 and IPv6 forwarding
enabled and proves they are closed before Adapter publication.

### P4 — dotted interface names make dotted sysctl lookup ambiguous

**Severity:** correctness  
**Disposition:** fixed before final evidence.

Per-interface sysctls use slash-form paths for both write and observation, for example:

```text
net/ipv4/conf/eth0.100/rp_filter
net/ipv6/conf/eth0.100/disable_ipv6
```

The normalized dotted spelling is retained only as a diagnostic key.

Unit coverage locks this behavior.

### P5 — prerequisite drift belongs to exact Adapter observation

**Severity:** boundary clarity  
**Disposition:** implemented.

Prerequisites are part of `LinuxNetworkDesired` / `LinuxNetworkObservation` and the
same exact verifier used by `renew_state()`.

A changed prerequisite therefore causes Adapter observation FAILURE/UNKNOWN just like route
or nft drift. Structural `apply()` repairs it behind the forwarding barrier.

Privileged integration injects `vpns00.rp_filter=1`, combines it with route/nft drift and
proves repair before forwarding reopens.

### P6 — intermediate unit CI failures were test-model drift, not production behavior

**Severity:** test maintenance  
**Disposition:** fixed.

After dual-stack protective close was introduced, the bootstrap fake still modeled only
IPv4 sysctl commands. Rootless unit CI failed while privileged Linux integration already
passed.

The fake was extended to model the complete protective contract. This is retained as
visible evidence rather than hidden by squashing history.

## Cross-baseline conclusion

This unit restores NG1-proven namespace safety prerequisites without restoring NG1
architecture above the Adapter boundary.

No NG1 DeviceBindingSnapshot, EnvironmentSnapshot, planner or namespace-prerequisite API is
reintroduced. NG2 owns the same technical facts in its concrete Linux desired/observation
model.

## Evidence

Expected final gate:

- rootless NG2 unit suite;
- privileged structural Linux integration;
- privileged live dataplane/NAT integration;
- NG1 Python regression.

Live integration additionally covers prerequisite mutation/observation against a disposable
kernel namespace.

## Final verdict

**PASS pending final green branch gate.**

No design issue remains open in this review unit. The PASS becomes unconditional once the
post-fix branch CI is green.

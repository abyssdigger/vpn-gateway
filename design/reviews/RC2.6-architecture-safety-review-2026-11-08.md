# Independent technical review — RC2.6 architecture safety/state machine

**Date:** 2026-11-08  
**Reviewed commit:** `00c1bcd52f167ab3f77934d84fcf62a66c6713fc`  
**Scope:** fail-closed semantics, binding transitions, firewall/NAT ordering, lifecycle states  
**Implementation reviewed only for compatibility context:** RC2.5.1

## Summary

RC2.6 corrects the two main architecture gaps exposed by EXP-004:

- complete daemon ownership of IPv4 FORWARD decisions;
- separation of configured interface selectors from concrete runtime interfaces.

The new model is materially safer and more honest about dynamic ocserv interface allocation.

One **high-severity ordering issue** remains in the architecture, plus several smaller
contracts that should be made explicit before implementation.

## S1 — HIGH: filter -> NAT repair is unsafe if forwarding cannot be disabled

RC2.6 correctly makes MASQUERADE binding-specific and states that binding-sensitive
FORWARD accepts also use the concrete interface.

It also retains the older policy:

```text
UNSAFE
-> best-effort ip_forward=0
-> repair filter
-> repair nat
```

and explicitly says failure to disable forwarding does not stop useful repair.

Those two decisions are no longer safely composable.

### Failure case

Assume a new binding is discovered and `set_ip_forward(False)` fails.

If repair applies the **full desired filter first**, the new exact profile FORWARD ACCEPT can
become active before the new exact MASQUERADE exists.

Normally the managed proto-202 route is restored only later, but a foreign exact or
more-specific route through the same new interface can already make packets egress.

Result: a packet that should be NATed can be accepted by daemon filter before desired NAT is
present.

The old static-NAT architecture did not have this ordering problem.

### Recommendation

Introduce an explicit fail-closed filter baseline for repair/binding transition.

Safe generic sequence when forwarding cannot be confirmed OFF:

```text
1. materialize + verify deny-only filter baseline
   - no binding-specific ACCEPT
   - protected destination rejects present
   - terminal FORWARD deny present
   - managed INPUT guards present

2. materialize + verify desired NAT

3. materialize + verify full desired filter including exact ACCEPT rules

4. reconcile routes

5. enable/confirm forwarding only after full verify
```

This sequence is also safe for binding removal: allows disappear before NAT is removed or
changed.

If forwarding is confirmed OFF, the implementation may use a simpler path, but one uniform
deny-first sequence may be easier to audit.

Do not merely swap the old order to NAT -> filter globally: when current filter is already
UNSAFE/open, repairing NAT first leaves unsafe forwarding policy active longer. A deny-first
filter baseline resolves both directions.

**Disposition recommended:** architecture change required before RC2.6 implementation.

---

## S2 — HIGH: interface inventory failure must be an isolation-class failure

In RC2.6 the expected firewall/NAT policy itself depends on the current immutable binding
snapshot.

Therefore failure to obtain/parse the interface snapshot is no longer equivalent to an
ordinary route-pass failure.

Without a trustworthy interface snapshot the daemon cannot know:

- which exact INPUT/FORWARD allows should exist;
- which exact MASQUERADE should exist;
- whether a family is absent, bound or ambiguous;
- whether a same-name interface was recreated with a new ifindex.

The current architecture does not state the failure class explicitly enough.

### Recommendation

If fresh interface inventory/resolution cannot be completed during RUN:

```text
best-effort ip_forward=0
state = ISOLATED
do not blind-repair binding-specific policy
retry on next reconciliation
```

This should be treated analogously to firewall safety `UNKNOWN`, not as ordinary
profile-route `DEGRADED` while forwarding may remain ON.

**Disposition recommended:** architecture clarification required.

---

## S3 — MEDIUM: the dynamic-name residual INPUT window is real and should be a named risk

RC2.6 correctly documents the kernel-event -> daemon-reaction window.

The most important case is not ordinary FORWARD traffic, which has blackhole + terminal
FORWARD deny protection, but local INPUT under same-name reuse:

```text
old vpns0 deleted
new vpns0 created quickly
old exact INPUT rules still exist until daemon processes event
```

iptables matches the name, not the historical ifindex. The new interface can therefore match
the old exact-name policy during the reaction window.

The architecture already accepts this bounded race on a dedicated trusted gateway, but it
should name the trust assumption explicitly:

- untrusted local processes/users must not have CAP_NET_ADMIN / ability to create netdevs;
- runtime interface creation is trusted VPN software + kernel;
- ifindex detects identity replacement for reconciliation, but cannot make existing iptables
  rules match historical ifindex.

This is not necessarily a blocker; it is a residual threat-model boundary.

**Disposition recommended:** document explicitly, no new mechanism required now.

---

## S4 — MEDIUM: a numeric-family selector reserves an operational interface namespace

A deny-only family guard may necessarily match a broader textual prefix than the numeric
selector itself, depending on the tested iptables syntax.

Even without overmatch, a foreign/unrelated interface whose name matches `^prefix[0-9]+$`
participates in selector cardinality and can make the profile ambiguous.

Therefore config such as:

```text
interface = "vpns%"
```

must be understood as reserving that runtime interface-name family for this managed profile
on the dedicated host.

Administrators should use a different prefix for another ocserv/WireGuard instance or any
unrelated netdev family.

**Disposition recommended:** add explicit namespace-reservation wording to §15/§4.

---

## S5 — LOW: ACTIVE does not imply VPN connectivity

RC2.6 intentionally treats ABSENT/not-ready as a successfully materialized fail-closed state,
not a profile FAIL.

Therefore the daemon can be:

```text
ACTIVE
policy SAFE
ip_forward=1
profile VPN interface absent
protected routes blackholed
```

This is internally consistent: ACTIVE means desired kernel policy is fully realized, not
“VPN tunnel is connected”.

Operational status should display binding/readiness separately so an administrator does not
misread ACTIVE as connectivity.

**Disposition recommended:** documentation/status clarification only.

---

## S6 — PASS: complete FORWARD ownership

The terminal `VPNG-FORWARD-DENY` design correctly fixes EXP-004.1 without mutating the
built-in FORWARD policy or deleting foreign rules.

The ordering is coherent:

```text
VPNG-INGRESS
VPNG-RESERVED
profile destination policy
VPNG-FORWARD-DENY
foreign rules
```

This is preferable to changing `-P FORWARD DROP` because cleanup can remove daemon policy
without needing to restore an unknown historical built-in policy.

---

## S7 — PASS: ambiguity model

The selector cardinality model is sound:

- 0 -> absent;
- 1 -> concrete binding;
- >1 -> ambiguous.

The rule “never choose the first/lowest/newest candidate” is important and correct.

Startup fatal vs runtime DEGRADED is also consistent with existing fail-hard startup
semantics.

---

## S8 — PASS: blackhole and selective cleanup

EXP-004 evidence supports retaining:

- `proto 201 metric 65536` blackhole;
- `proto 202` managed unicast;
- protocol-selective cleanup inventory;
- strict full route inventory for normal reconciliation.

No architecture change is recommended in this area.

## Overall verdict

**RC2.6 is directionally sound but not yet ready for implementation unchanged.**

Required before implementation:

1. fix cross-table repair ordering around binding-specific NAT/filter;
2. classify interface inventory failure as ISOLATED/UNKNOWN-like;
3. explicitly document selector family namespace reservation and trusted-host reaction-window
   assumption.

After those changes, the architecture is suitable for implementation-oriented review.

---

## Maintainer disposition

**ACCEPTED in architecture RC2.6.1.**

All substantive findings in this review were accepted for the architecture correction.
Implementation remains unchanged pending RC2.6.1 re-review and the target validation required
for deny-only selector-family iptables matching.

See `design/RC2/vpn-gateway-architecture-rc2.wip.md` and the RC2.6.1 changelog entry.

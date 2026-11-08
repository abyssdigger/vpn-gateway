# Independent re-review — RC2.6.1 architecture safety/state machine

**Date:** 2026-11-08  
**Reviewed commit:** `174f9a1dff396098a20d6882397aeffabf8261ae`  
**Scope:** previous RC2.6 safety findings, fail-closed transitions, cross-table ordering,
dynamic binding reaction window

## Previous findings disposition check

### RC2.6 S1 — filter before NAT with forwarding possibly ON

**RESOLVED.**

RC2.6.1 now requires:

```text
isolation filter
-> verify
-> desired NAT
-> verify
-> full desired filter
-> verify
-> routes
-> verify
-> forwarding
```

This remains mandatory even if `ip_forward=0` cannot be confirmed.

The previous leak window in which full FORWARD ACCEPT could precede MASQUERADE is closed.

### RC2.6 S2 — interface inventory failure classification

**RESOLVED.**

Interface read/parse/resolution failure is explicitly isolation-class:

- best-effort forwarding OFF;
- lifecycle ISOLATED;
- no binding-specific blind repair;
- config-only isolation filter may be used when firewall boundary is readable.

This is the correct classification now that expected full policy depends on runtime binding.

### RC2.6 S3 — same-name dynamic interface reaction window

**RESOLVED AS THREAT-MODEL BOUNDARY.**

RC2.6.1 explicitly states that:

- the event/reaction window is unavoidable in the multitasking OS model;
- untrusted local processes do not possess CAP_NET_ADMIN/netdev lifecycle control;
- ifindex detects replacement on reconciliation but cannot retroactively scope an existing
  iptables name match.

No additional kernel mechanism is required for the current dedicated trusted-host model.

### RC2.6 S4 — selector family namespace reservation

**RESOLVED.**

A numeric-family selector reserves its matching runtime ifname namespace. Unrelated matching
netdevs participate in cardinality and can deliberately produce AMBIGUOUS fail-closed state.

The architecture also correctly defers any broader reservation caused by actual iptables
prefix-match semantics until that CLI behavior is target-validated.

### RC2.6 S5 — ACTIVE vs connectivity

**RESOLVED.**

ACTIVE is now explicitly policy-state, not proof of VPN connectivity; status must expose
binding/readiness separately.

---

## New review findings

### S1.1 — MEDIUM: isolation-filter verification must never satisfy full policy SAFE

RC2.6.1 describes both:

- full `FirewallSafety = SAFE/UNSAFE/UNKNOWN`;
- a separately verified `desired_isolation_filter(config)`.

The sequencing text is safe, but the semantic boundary should be explicit enough that an
implementation cannot accidentally reuse a generic “SAFE” result from the isolation
baseline to satisfy the later forwarding gate.

Required distinction:

```text
isolation filter verified
    !=
full desired firewall/NAT SAFE
```

Only the latter may permit route restoration completion to lead to forwarding enable.

This can be an architecture sentence/invariant rather than a new public enum.

**Severity:** MEDIUM contract-clarity issue, not a demonstrated safety defect in the current
written sequence.

### S1.2 — LOW: isolation filter should explicitly remove stale daemon binding ACCEPTs

The intended meaning is apparent because the isolation filter “contains no binding-specific
ACCEPT”, but the repair contract should make the replacement semantics explicit:

when materialized, the isolation filter is the complete daemon-owned filter desired state for
that stage, not an additive set of deny rules layered on top of stale profile chains.

Otherwise an implementation could append terminal deny while stale earlier ACCEPT rules
remain reachable.

The existing one-policy-builder direction strongly suggests replacement, but a one-line
normative clarification would remove ambiguity.

**Severity:** LOW/MEDIUM implementation guardrail.

---

## Safety verdict

**RC2.6.1 resolves all substantive HIGH findings from the RC2.6 review.**

No new architectural blocker was found.

Before implementation, two small clarifications are recommended:

1. isolation-filter verification is not full-policy `SAFE`;
2. isolation materialization replaces/removes stale daemon binding-specific ACCEPT state,
   rather than merely appending deny rules.

After those clarifications, the safety model is suitable for implementation.

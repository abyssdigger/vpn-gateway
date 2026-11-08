# Independent vivisection — RC2.6.2 architecture safety/state machine

**Date:** 2026-11-08  
**Reviewed commit:** `b5a4a3de029709bf1ddd17c457f5910524565150`  
**Scope:** adversarial fail-closed analysis after final isolation-barrier clarification  
**Implementation baseline:** RC2.5.1, intentionally not treated as RC2.6.2-conformant

## Review method

The review walks failure paths rather than the happy path:

- `ip_forward=0` succeeds or fails;
- interface inventory succeeds or fails;
- firewall inventory is SAFE / UNSAFE / UNKNOWN;
- NAT materialization succeeds or fails;
- full-filter materialization succeeds or fails;
- route inventory/apply/verify succeeds or fails;
- binding changes, disappears, becomes ambiguous, or is recreated under the same name.

The target property is: no failure ordering may expose ordinary-network forwarding or a
binding-specific ACCEPT before required NAT/safety prerequisites.

## V1 — isolation barrier semantics

**PASS.**

RC2.6.2 closes both ambiguities left by the RC2.6.1 re-review.

The isolation filter is now explicitly the **complete daemon-owned filter desired state for
that stage**, not an additive patch. Therefore stale earlier binding-specific daemon ACCEPT
rules must be removed/canonicalized when the barrier is installed.

The architecture also explicitly distinguishes:

```text
isolation filter verified
!=
full desired firewall/NAT SAFE
```

No forwarding gate may consume the isolation-only result as if full policy were ready.

This is the required semantic separation.

## V2 — failure to disable ip_forward

**PASS.**

If `set_ip_forward(False)` fails, the daemon still executes:

```text
complete isolation filter
-> verify
-> desired NAT
-> verify
-> full filter
-> verify
-> routes
-> verify
```

At no point does a binding-specific FORWARD ACCEPT precede verified NAT.

If NAT fails, the verified isolation filter remains the active daemon policy.
If full filter fails atomically, the isolation filter remains.
If route reconciliation fails after full filter, the filter still requires the expected
concrete VPN egress and protected destinations cannot fall through ordinary default routing.

No default-route leak is found in this sequence.

## V3 — interface inventory failure

**PASS.**

Without trustworthy interface inventory the daemon:

- attempts forwarding OFF;
- enters ISOLATED;
- does not derive or blind-repair binding-specific allow/NAT state;
- may use only the config-derived isolation filter when firewall inspection is available.

This is correctly stronger than ordinary route DEGRADED behavior.

## V4 — full-filter-before-route-verify with forwarding possibly still ON

**PASS under the stated ownership model.**

After NAT verify, full filter may become active before route reconciliation completes even if
the daemon failed to force `ip_forward=0`.

This does not create an ordinary-network leak because profile ACCEPT requires the exact
resolved VPN egress. A missing/foreign route through another egress reaches the unconditional
protected-destination REJECT instead.

A foreign more-specific route through the same managed concrete VPN interface can pass.
This is consistent with the existing architecture, which deliberately does not classify
same-managed-egress overlap as ordinary-network leakage and does not automatically delete
more-specific overlaps.

No new contradiction is introduced by RC2.6.2.

## V5 — binding removal / ambiguity

**PASS.**

For ABSENT/not-ready/AMBIGUOUS desired policy:

- exact binding ACCEPT disappears;
- exact MASQUERADE disappears;
- proto-202 desired routes disappear;
- blackhole remains;
- protected-destination reject remains;
- global FORWARD deny remains;
- selector INPUT guard remains.

AMBIGUOUS is additionally profile FAIL/DEGRADED.

The transition is fail-closed even when global forwarding remains available for other
profiles after the isolation/reconciliation sequence completes.

## V6 — same-name replacement race

**ACCEPTED RESIDUAL RISK, not an architecture defect.**

Existing iptables `-i/-o name` matches cannot be tied to the historical ifindex.
A rapid delete/recreate under the same name can therefore use old exact-name rules until the
daemon observes the replacement.

RC2.6.2 documents this as an unavoidable bounded reaction window on a dedicated trusted
gateway where untrusted local actors do not control netdev lifecycle/CAP_NET_ADMIN.

The architecture is honest about the limitation and has a coherent threat boundary.

## V7 — bootstrap full filter before NAT

**PASS.**

Bootstrap still permits full filter before NAT, unlike runtime deny-first repair.

This is safe because startup is entered only after successful universal cleanup has
confirmed `ip_forward=0`. Any failure to obtain that state aborts startup before APPLY.

Therefore the runtime repair ordering does not need to be mechanically imposed on bootstrap.

## V8 — isolation/filter verification vocabulary

**PASS.**

RC2.6.2 does not require a public enum for the isolation-barrier result. It only requires
that this result cannot be mistaken for full-policy SAFE.

An implementation may model this as distinct methods/types or as orchestration-local state,
provided the forwarding gate can only consume the full NAT + full-filter verified result.

## V9 — cleanup and blackhole

**PASS, unchanged.**

The EXP-004 validated contracts remain intact:

- selective proto-201/202 cleanup;
- strict parsing inside reserved marker protocols;
- blackhole removed only after firewall/NAT cleanup;
- exact per-table iptables cleanup transaction.

## Safety verdict

**APPROVE RC2.6.2 for implementation.**

No unresolved HIGH/MEDIUM architecture safety defect was found.

The only material uncertainty intentionally left open is the exact target behavior and
canonicalization of the deny-only selector-family iptables interface-prefix match. That is
already listed as a required target experiment and does not justify guessing the CLI
contract in architecture or code.

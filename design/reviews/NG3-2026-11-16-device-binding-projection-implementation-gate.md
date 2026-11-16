# VPN-GATE NG3 — Device binding projection implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** pure stable-slot Device binding projection

## 1. Scope

Implement the pure projection that combines:

```text
active DeviceBindingIntent set
+
fresh ordered interface inventory
+
previous committed binding projection
```

into:

```text
stable logical-path slot bindings
+
bounded waiting-candidate state
+
next proposed projection
```

No Netlink listener, Manager, kernel mutation or Profile policy is part of this unit.

## 2. Requirements

Primary:

- `VPNG-R1.R3.R1`;
- `VPNG-R1.R3.R2`;
- `VPNG-R1.R3.R3`;
- `VPNG-R1.R3.R4`;
- `VPNG-R1.R3.R4.R1`;
- `VPNG-R1.R3.R4.R2`;
- `VPNG-R1.R3.R4.R3`;
- `VPNG-R1.R3.R4.R3.R1`;
- `VPNG-R1.R3.R4.R4`;
- `VPNG-R3.R1.R1`;
- `VPNG-R4.R1`;
- `VPNG-R7.R1.R1`.

All are currently architecture-closed.

## 3. Architecture boundary

The current architecture keeps the shared Device binding projection inside
`PayloadTrafficManager` because no independent asynchronous Device-binding responsibility is
justified.

This review unit therefore implements a pure helper/state projection used by that owner. It
does **not** create a Device Engine.

## 4. Current endpoint identity

Concrete current Linux endpoint identity:

```text
(ifname, ifindex)
```

Same-name/new-ifindex is a fresh endpoint instance.

Logical path identity remains independent:

```text
LogicalPathId =
    device_id
    + selector_index
    + stable slot_index
```

## 5. State required

For each active Device selector retain only bounded current state:

```text
selector definition/fingerprint
slot_bindings[quota] = InterfaceIdentity | empty
waiting_order[]      = unbound matching InterfaceIdentity
```

This is not event history.

Inactive Devices/selectors are absent from next state.

If the configured selector/quota at the same position changes, that selector lifecycle is
treated as new and old assignment state is not silently reused.

## 6. Projection rules

For one selector:

1. retain each previous bound endpoint that is still present and still matches **in the same
   stable slot**;
2. remove disappeared/non-matching bound endpoints from the proposed slots;
3. retain previous waiting candidates that are still present/matching, preserving committed
   order;
4. append newly observed matching candidates in fresh inventory order;
5. a slot that was already free in the **previous committed state** may be filled from waiting
   candidates, lowest slot index first;
6. a slot that becomes free because a bound endpoint disappears in the current projection is
   **not** reused in the same projection;
7. after that removal-only projection is verified/committed, the next reconciliation sees the
   slot as previously committed free and may promote the oldest waiting candidate;
8. no candidate may occupy more than one selector/slot;
9. remaining matching candidates stay observable as waiting/unbound.

This realizes the accepted rule:

> once a bound disappearance is verified/committed, a waiting candidate may occupy the freed
> slot on a later reconciliation.

## 7. Admission order

Initial/new candidates use fresh ordered inventory order.

Committed waiting order survives later snapshot reordering.

Lexical ifname sorting is not policy.

The upstream inventory boundary is responsible for any required same-event tie normalization;
the projector consumes an already ordered fresh inventory.

## 8. Observation validity

The pure input contract rejects impossible/ambiguous inventory such as duplicate concrete
identity, duplicate ifname with different ifindex, or duplicate ifindex with different
ifname.

If one observed endpoint matches more than one active selector, projection fails rather than
guessing ownership.

This is defensive validation of the binding contract, not a new selector precedence policy.

## 9. Simplification review

Not introduced:

- DeviceManager/DeviceEngine;
- Netlink event state;
- event replay/history;
- persistent database;
- Linux mutation;
- route metrics;
- Profile availability;
- retry loop;
- asynchronous queue.

Only stable slots and waiting order are retained because accepted survivor/promotion semantics
cannot be implemented without them.

## 10. Evidence plan

Rootless unit tests:

- initial snapshot fills slots in observation order;
- later snapshot reorder does not move survivors;
- waiting candidate remains unbound while quota full;
- disappeared bound endpoint leaves its slot empty in the first projection;
- after committing that removal projection, next reconcile promotes oldest waiting candidate
  into the exact freed slot;
- same-name/new-ifindex is a fresh candidate and cannot inherit the old binding in the same
  pass;
- newcomer cannot evict survivor;
- selector position and slot identity remain stable;
- selector/quota change resets only that selector lifecycle;
- inactive Device intent disappears from projection;
- invalid/ambiguous inventory fails closed.

## Verdict

**PASS — pure stable-slot binding projection may be implemented.**

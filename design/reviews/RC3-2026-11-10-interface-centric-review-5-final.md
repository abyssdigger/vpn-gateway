# RC3 — interface-centric architecture review 5 — final

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** independent cross-domain architecture auditor  
**Область:** Linux networking, firewall/NAT safety, config/domain semantics, daemon lifecycle  
**Вердикт:** **ACCEPT — NO FINDINGS**

## Проверенный baseline

Финальный RC3 после EXP-009 использует interface-centric model:

```text
selector
-> candidates
-> active concrete bindings (name + ifindex + expected local_address)
-> exact firewall/NAT resources
-> direct proto-202 routes
```

Transport peer association отсутствует из VPN-GATE route model.

Поддерживаемые selector forms:

```text
"vpn"                    exact
"vpn+"                   multiple prefix
["vpnA","vpnB","vpnC"]   ordered explicit exact list
```

Legacy `%`, configured `peers`, `PeerBinding` и normal selector ambiguity не входят
в normative domain model.

## Cross-domain checks

### Networking / routing

- daemon-owned UNICAST is direct `dev <exact-interface> proto 202`;
- `via=None`, `onlink=False`;
- exact metric = 10;
- prefix active order = case-sensitive bytewise ASCII current snapshot;
- explicit-list order = config slots, absent elements do not renumber later slots;
- prefix metric overflow is checked at runtime without wrap;
- interface disappearance/rematerialization semantics match EXP-009;
- route metric is not described as transport health detection.

**Result:** no findings.

### Selector / binding model

- exact candidate count is naturally 0..1;
- prefix/list multiplicity is normal;
- active binding requires expected `local_address`;
- candidate without local address stays guard-blocked;
- `name+ifindex` defines concrete identity;
- one normative active order feeds routes, filter, NAT and status.

**Result:** no findings.

### Firewall / NAT safety

- wildcard prefix appears only in deny guard;
- allowing resources use exact active names;
- active-binding transition uses protective barrier;
- candidate-only no-barrier rule is conditional on successful IPv6 prerequisite check;
- runtime IPv6 prerequisites are revalidated before allowing policy;
- blackhole and protected-destination REJECT remain independent fail-closed layers.

**Result:** no findings.

### Lifecycle / status

- verification success is distinct from functional ProfileResult;
- verified zero-path state is committed and gives ProfileResult FAIL;
- successful startup may enter RUN/DEGRADED for verified availability loss;
- actual apply/verification failure remains hard startup failure;
- ACTIVE requires SAFE policy, all profiles SUCCESS and ip_forward=1;
- observability failure remains ISOLATED.

**Result:** no findings.

### Configuration

- closed schema has no transport peer list;
- legacy `peers` is unknown key;
- legacy `%` is invalid selector;
- ordered explicit interface list has duplicate rejection and stable priority semantics;
- managed selector guard namespaces cannot overlap;
- `network` and `local_address` retain clear transport-agnostic roles.

**Result:** no findings.

## Structural audit

Confirmed:

- exactly 99 numbered invariants;
- invariant numbering is sequential 1..99;
- all explicit `§N` / `§N.M` references resolve;
- EXP-009 is COMPLETE — PASS in journal and result artifact;
- normative glossary contains no `prefix%`, `PeerBinding`, single-/multi-binding legacy terms;
- project normative prose follows the `е` convention;
- architecture and glossary agree on supported selector forms.

## Final conclusion

**ACCEPT — NO FINDINGS.**

The interface-centric RC3 documents can be used as the authoritative baseline for the
Python implementation update.

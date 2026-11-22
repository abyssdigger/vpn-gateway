# NG3 2026-11-23 — Device firewall path-selector implementation review

**Scope:** implementation of the accepted Device firewall rule-scope model:
Device-wide by omission, `via if <exact-ifname>`, or
`via peer <private-IPv4>`.

**Governing design:** `NG3-2026-11-23-device-firewall-path-selector-design-review.md`.

**Code head:** `7e7fa1e45a3e4c7eae881be54fb5034866182a99`.

## Verdict

**PASS — THE IMPLEMENTATION SATISFIES THE ACCEPTED THREE-SCOPE DEVICE FIREWALL MODEL.**

No unresolved finding remains in this review unit.

## Evidence

GitHub Actions run `45078333568` on code head
`7e7fa1e45a3e4c7eae881be54fb5034866182a99` completed **SUCCESS**.

Material acceptance jobs include:

- `unit` — PASS;
- `linux-payload-forward` — PASS;
- `linux-endpoint-provenance` — PASS;
- `linux-alpha-smoke` — PASS;
- all other jobs in the full NG3 Python workflow — PASS.

No new platform experiment was required for exact-if selection because it consumes the
already established current `InterfaceIdentity` / `PathBinding`. The existing
private-peer Linux integration and historical EXP-004.3/EXP-009/EXP-039 evidence remain the
applicable proof for `via peer`.

## Findings and dispositions

### F1 — external grammar implements one mutually exclusive optional path selector

**Decision:** accepted.  
**Resolution:** fixed.

`release1_config.py` accepts:

```text
no via
via if <exact-ifname>
via peer <IPv4>
```

The parser rejects duplicate/mixed `via`, missing operands, wildcard/non-exact interface
names, overlong Linux interface names, unsupported `via` modes and malformed peer IPv4.

`FirewallRuleConfig` carries either `path_ifname`, `private_peer_ipv4`, or neither.

### F2 — normalized rule intent preserves the same invariant

**Decision:** accepted.  
**Resolution:** fixed.

`DeviceFirewallRuleIntent` now has an optional exact `path_ifname` in addition to the
existing optional private-peer value. The two fields are explicitly mutually exclusive.

This is path applicability metadata; it does not become a payload packet predicate and does
not change action/protocol/source/destination semantics.

### F3 — exact-if selection is Device-scoped through current path realization

**Decision:** accepted.  
**Resolution:** fixed.

The Device firewall compiler evaluates `path_ifname` only while compiling an already
current `RoutePriorityPathRoute` owned by the Device. Therefore a same-named unrelated
interface cannot create policy applicability.

The selector compares the configured exact name against the current endpoint's ifname; lower
enforcement continues to use the existing exact current interface-generation realization.

### F4 — exact-if introduces no new observation dependency

**Decision:** accepted.  
**Resolution:** fixed.

`AlphaPreparedPolicy.requires_private_peer_observation` remains true only when at least one
active rule contains `via peer`.

A configuration using Device-wide and/or `via if` rules continues to use the ordinary
link-only VPN-path observation. Permanent alpha tests verify this explicitly.

### F5 — private-peer behavior remains unchanged and fail-closed

**Decision:** accepted.  
**Resolution:** fixed.

The existing peer-only machinery was not generalized into a VPN-specific identity framework.
Peer resolution remains demand-scoped, generation-correlated, and restricted to current
Device paths.

Missing required peer observation, observation failure and duplicate requested-peer
association remain errors rather than implicit proof that the restriction is absent.

### F6 — all three scopes coexist in one ordered Device policy

**Decision:** accepted.  
**Resolution:** fixed.

Permanent policy-compiler evidence uses one Device policy containing:

1. an unqualified Device-wide rule;
2. an exact-if rule for one current path;
3. a private-peer rule for another current path.

For each current path, inapplicable rules are skipped while applicable rules retain declared
relative order. The existing explicit-policy terminal no-match DROP remains present after
path projection.

This confirms the design did not accidentally create separate path firewalls or alter
first-terminal-verdict semantics.

### F7 — no new architectural owner or lower firewall mechanism was introduced

**Decision:** accepted.  
**Resolution:** fixed.

The final responsibility allocation remains:

```text
A.002 ConfigurationAdapter
    -> normalize optional rule-local selector

A.005 PayloadPolicyCalculator
    -> path-relative applicability semantics

C.004 VPNPathAdapter
    -> current exact binding
    -> additional private-peer observation only when peer selector is demanded

C.001 NetworkPolicyAdapter
    -> per-current-path ordered Device-rule projection and existing exact-path lowering

C.003 NetworkPolicyEnforcer
    -> unchanged convergence / verification / fail-closed containment
```

No Profile-local firewall, generic path registry, VPN technology Manager, new nft packet
selector or additional durable identity was added.

## Closure recommendation

The implementation, permanent tests and full workflow evidence are sufficient to close the
broadened current semantics of:

- `VPNG-U001-R1.R4.R2.R1`;
- `VPNG-U001-R1.R4.R2.R1.R1`;
- `VPNG-U001-R4.R4.R6.R2.R1`;
- `VPNG-U001-R4.R4.R6.R2.R5`.

Their current scope constraints remain `closed`.

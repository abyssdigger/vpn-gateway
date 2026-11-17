# VPN-GATE NG3 — complete direct-device pure payload pipeline review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-direct-device-bootstrap-35m`

## Scope

Review the end-to-end pure composition path for the currently accepted direct-device
integration shape, from structural configuration and current interface binding through the
complete payload lower desired state consumed by network-policy activation.

No new production wrapper is introduced by this unit.

## Verdict

**PASS.**

The existing pure contracts already compose without an additional abstraction:

```text
structural config
    -> current Device binding projection
    -> PayloadProfileRequest
    -> explicit direct-device RoutePriorityPathRoute realization
    -> NetworkPolicyLayout allocation
    -> explicit normalized Device NAT/firewall inputs
    -> complete PayloadNetworkPolicyDesiredState
```

The proof covers both current-path and zero-path states.

## Current-path proof

The existing outbound multi-path structural scenario now continues beyond Profile-forward
compilation.

For three current direct-device bindings:

- `realize_direct_device_path_routes(...)` produces exactly the current logical path set;
- `allocate_network_policy_layout(...)` allocates the Profile table/RPDB space;
- explicit normalized Device no-op semantics are supplied:
  - `DeviceNatPolicyIntent("oc", NatIntent.NONE)`;
  - `DeviceFirewallPolicyIntent("oc", rules=None)`;
- `build_payload_network_policy_desired_state(...)` produces:
  - one terminal guard plus three ordinary path routes;
  - one Profile RPDB dispatch rule;
  - six exact Profile NEW/RETURN rules;
  - no NAT rules;
  - no Device firewall child chains;
  - no publication-local rules.

This is the exact lower input shape expected by `activate_network_policy(...)`.

## Zero-path proof

The zero-binding Profile remains a semantic policy domain and now also reaches complete lower
desired assembly.

The direct-device realization is empty, but the complete desired state still contains:

- the Profile terminal blackhole guard;
- the Profile RPDB dispatch rule;
- no positive Profile-forward rules;
- no NAT rules;
- no Device firewall chains.

This preserves the accepted fail-closed zero-path behavior through the full pure pipeline.

## Finding F1 — no extra production Calculator is justified

Every transformation in the chain already has a distinct reviewed responsibility:

- config parser/normalizer;
- stable binding projection;
- Profile request assembly;
- direct-device integration realization;
- lower resource allocator;
- owner-specific desired-state compilers;
- complete payload desired-state assembly.

Adding another production wrapper merely to call these functions would not introduce a new
invariant or semantic responsibility.

**Disposition:** this unit is closed by cross-contract integration evidence only.

A later lifecycle/Manager boundary may orchestrate these existing functions when it has
actual runtime ownership, but it must not duplicate their semantics.

## Finding F2 — direct-device realization remains integration-specific

The proof does not turn direct-device routing into a generic inference rule.

`realize_direct_device_path_routes(...)` remains valid only for an integration/onboarding
contract that already guarantees protected destinations are directly reachable through the
bound endpoint without a Linux next-hop gateway/onlink requirement.

This integration proof therefore does not constrain future gateway/onlink-capable
integrations.

## Finding F3 — deferred external Device policy grammar is not reopened

The structural TOML parser still intentionally does not accept final NAT/firewall/publication
syntax.

The integration supplies normalized internal no-op Device policy intents directly. This
proves lower composition without inventing external configuration defaults or field names.

## Evidence

Workflow `43989220547`: **SUCCESS**

```text
Ran 493 tests
OK
```

The modified cross-contract test is
`design/NG3/code/python/rou/tests/test_pure_structural_pipeline.py`.

No new privileged evidence is required: no Linux representation or mutation mechanism is
introduced. Physical activation remains covered by the existing network-policy activation
and structural integration suites.

## Component-model review

No component is added.

The proof confirms that the current Calculator/Adapter contracts compose directly. This is
preferable to introducing a pass-through assembly class with no independent responsibility.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Conclusion

**PASS.**

The currently accepted direct-device path now has a complete pure semantic-to-lower desired
pipeline. The next implementation gap is physical managed-domain/bootstrap ownership, not
another desired-state Calculator.

# VPN-GATE NG3 — Structural configuration code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** first executable NG3 structural configuration slice

## Scope

Reviewed:

- `design/NG3/code/python/rou/domain.py`;
- `design/NG3/code/python/rou/config.py`;
- `design/NG3/code/python/rou/tests/test_config.py`;
- implementation gate:
  `design/reviews/NG3-2026-11-16-structural-config-implementation-gate.md`.

Compared against:

- current NG3 requirements;
- `design/NG3/config-model.md`;
- `design/NG3/architecture.md`;
- `design/NG3/transition-tips.md`;
- historical NG1 parser/tests only as evidence inventory.

## Evidence

Rootless command:

```sh
PYTHONPATH=design/NG3/code/python \
python3 -m unittest discover \
    -s design/NG3/code/python/rou/tests \
    -p 'test_*.py' -v
```

Equivalent working-copy execution after accepted fixes:

```text
19 tests
PASS
```

Python compilation check also passed.

## Finding 1 — partial normalized contracts reused full-contract names

**Severity:** material architecture-contract defect  
**Disposition:** accepted and fixed

Initial code named the bounded structural values:

```text
DeviceConfigIntent
ProfileConfigIntent
```

Those names are already used by current NG3 architecture for fuller normalized contracts
that include policy fields outside this implementation unit.

Keeping the names would make a partial value look like the architecture's complete contract
and would make later extension ambiguous.

Fix:

```text
DeviceStructuralIntent
ProfileStructuralIntent
```

`DeviceBindingIntent` remains unchanged because the implemented value matches the current
binding-intent contract.

No new component or requirement was introduced.

## Finding 2 — set-like Profile destinations retained authored ordering

**Severity:** semantic normalization defect  
**Disposition:** accepted and fixed

Requirement `VPNG-R1.R2.R5.R4` and the config model say destination list ordering has no
routing semantics.

The initial normalized tuple retained TOML list order. That allowed two semantically
equivalent configs to produce different normalized values.

Fix:

- validate strict IPv4 networks and duplicates first;
- canonicalize the normalized destination tuple by network address and prefix length;
- keep `device_order` and `expected_interfaces` authored order unchanged because their
  order is explicit policy.

Regression coverage verifies reversed destination input produces identical normalized
destination ordering.

## Finding 3 — regression matrix missed cross-Device capacity composition

**Severity:** test coverage defect  
**Disposition:** accepted and fixed

The first-release inbound/bidirectional constraint depends on the sum of selector quotas from
all **enabled referenced** Devices, not only one Device.

Added coverage verifies:

- two enabled referenced exact-selector Devices produce capacity 2 and are rejected;
- a referenced disabled Device contributes zero;
- active Device derivation matches the same semantics.

## Finding 4 — strict active-object field handling needed direct coverage

**Severity:** test coverage defect  
**Disposition:** accepted and fixed

The bounded parser intentionally rejects active fields outside the accepted structural slice
rather than guessing historical transport-policy grammar.

Added direct tests for unsupported active Device/Profile fields.

Disabled placeholders remain intentionally shallow: after validating mandatory boolean
`enabled = false`, inactive fields are not deeply interpreted by this slice.

## Requirement conformance

Verified:

- Device/Profile IDs use accepted grammar;
- `enabled` is mandatory and boolean;
- enabled Device requires non-empty ordered `expected_interfaces`;
- exact selector quota is 1;
- prefix selector requires explicit positive quota;
- intra-Device overlap is rejected;
- cross-Device overlap is rejected only among active Devices;
- unknown Device references are rejected;
- known disabled references are accepted;
- active Device set is demand-driven by enabled Profile references;
- enabled Profile requires direction/destinations/device_order;
- destination CIDRs are strict IPv4 and host bits are rejected;
- duplicate exact destination ownership is rejected;
- different-length overlap remains allowed;
- Release 1 inbound/bidirectional capacity >1 is rejected from configuration capacity;
- outbound multi-path remains accepted;
- no Linux runtime identity leaks into user config.

## Component-model review

The unit remains inside the existing Direct `ConfigurationAdapter` boundary.

The dataclasses/enums and parsing helpers are internal synchronous machinery, not additional
components.

No Manager, Agent, event queue, retry state, lifecycle owner, history or replay mechanism was
introduced.

## Scope-boundary review

Not implemented and not guessed:

- final NAT user spelling;
- traffic-envelope grammar;
- publication grammar;
- availability/timing grammar;
- runtime binding;
- kernel/network mutation.

This is consistent with `VPNG-R1.R2.R4.R6.C1`.

## Verdict

**PASS — STRUCTURAL CONFIGURATION IMPLEMENTATION UNIT ACCEPTED.**

No unresolved finding blocks the next independent review unit.

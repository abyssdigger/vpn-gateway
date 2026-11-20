# NG3 review — canonical Release-1 config grammar + target Rust runtime boundary

> **Current requirement mapping (2026-11-20):** the systemd-specific requirement subtree
> used by this historical review was later normalized without changing the accepted systemd
> architecture/evidence:
>
> - historical `VPNG0001-R1.R3.C1.C1` -> current `VPNG0001-R1.R3.C3`
>   (external VPN runtime lifecycle ownership/supervision constraint);
> - historical `VPNG0001-R1.R3.C1.C1.R1` -> current `VPNG0001-R1.R3.C3.R1`
>   (external lifecycle integration contract);
> - historical `VPNG0001-R1.R3.C1.C1.R2` -> current `VPNG0001-R1.R3.C1.R1.R2`
>   (policy-neutral administrator onboarding configuration);
> - historical `VPNG0001-R1.R3.C1.C1.R3` -> current `VPNG0001-R1.R2.R4.R6.R4`
>   (Device client-side VPN transport/control intent).
>
> The concrete systemd/`NetworkNamespacePath`/`BindsTo`/`After` mechanism remains selected
> architecture and evidence, not current generic requirement wording.

**Date:** 2026-11-17  
**Cycle:** `ng3-beta-cycle-20261117-config-grammar-35m`  
**Baseline:** main snapshot 72, `48587d41f8c7313081909a673ddcf2c7902e1ab8`  
**CI evidence:** NG3 Python run `44128242193`, source `4a8d2dfd30de5e2f11b2f17eb4bd052b04f2d099`, PASS

## Review-unit scope

This unit resolves two accepted decisions:

1. the ordinary Release-1 human-facing Device/Profile grammar that had previously been
   postponed; and
2. the target production implementation-language boundary requested for the privileged
   long-running runtime.

The second decision does **not** change the beta release gate: early alpha/beta releases may
continue to use the Python reference runtime under `VPNG0007-R7.R8.C1`.

## Requirement gate

### Canonical config

Revalidated affected closed requirements:

- `VPNG0001-R1.R2.R4.R4.R4` / `.R1` / `.C1` — Profile ordinary-side NAT remains a
  distinct capability and is encoded as direction `+snat`;
- `VPNG0001-R1.R2.R4.R6.R1` — Device ordinary->VPN NAT is explicit
  `use_outbound_nat = true|false`;
- `VPNG0001-R1.R2.R4.R6.R2.R1` — ordered one-line Device firewall grammar;
- `VPNG0001-R1.R2.R4.R6.R3` — Device server publication grammar;
- `VPNG0001-R1.R2.R4.R6.C1` — one canonical Release-1 grammar, legacy aliases rejected;
- `VPNG0001-R1.R3.C1.C1.R3` — Device-owned `allow_vpn_client`, no public
  top-level `integration.*`;
- `VPNG0003-R3.R6.R3.R1.C1.R1` — Profile `availability_check = "icmp[/IPv4]"`.

Human acceptance in this cycle resolves the previous configuration-format decision. The
remaining endpoint-scoped Device firewall grammar is still independently constrained by
`VPNG0001-R1.R2.R4.R6.R2.R5.C1`.

### Target Rust production runtime

New subtree:

- `VPNG0007-R7.R8`;
- `VPNG0007-R7.R8.C1`;
- `VPNG0007-R7.R8.R1`;
- `VPNG0007-R7.R8.R2`;
- `VPNG0007-R7.R8.R3`.

The initial R7.R8 Purpose was reviewed critically. Runtime fail-closed correctness belongs to
the existing R4 tree and is **not** claimed to follow automatically from choosing Rust.
R7.R8 instead refines the immediate R7 implementation-quality obligation: the final
privileged runtime is to be maintainable without relying on manual prevention of whole
classes of memory-management faults and with a predictable native runtime model.

The architecture closure is `architecture.md §13.1`:

- Rust is the target final production/stable runtime boundary, not a new component type;
- alpha/beta Python is explicitly allowed;
- experiments/tests/tooling/reference work may use other languages;
- production `unsafe`/memory-unsafe FFI is narrow, localized and justified;
- a Rust port preserves requirement/architecture behavior rather than becoming an excuse for
  semantic redesign.

This is sufficient architecture closure for the new R7.R8 subtree. No Rust implementation is
required in this review unit because C1 explicitly postpones that implementation gate until
the first release claiming the target production/stable boundary.

## Accepted external grammar

Canonical Device fields:

```toml
use_outbound_nat = true | false

allow_vpn_client = "tcp|udp[:local-port]>remote-IPv4:remote-port"
# or array

firewall = [
    "<in|out> <allow|deny|reject> [tcp|udp|icmp] [from CIDR[:port]] [to CIDR[:port]] [ # comment]",
]

publish_vpn_server = "tcp|udp[/host-IPv4|host-interface]:host-port[>internal-port]"
# or array
```

Canonical Profile additions:

```toml
direction = "outbound"
direction = "inbound"
direction = "inbound+snat"
direction = "bidirectional"
direction = "bidirectional+snat"

availability_check = "icmp"
availability_check = "icmp/<IPv4>"
```

Important distinctions remain explicit:

- `use_outbound_nat` = ordinary->VPN Device/path MASQUERADE;
- Profile `+snat` = VPN->ordinary Profile-scoped gateway source NAT;
- `allow_vpn_client` = local/system permission for the VPN implementation's own transport;
- `publish_vpn_server` = server-side transport publication;
- Device firewall = additional payload restriction only;
- availability = Profile/path criterion, not Device endpoint metadata.

Rejected aliases include historical `nat`, `traffic_envelope`, `publications`,
`interface_balancing` and top-level `[integration.*]`.

## Implementation review

Added `release1_config.py` as the canonical Direct ConfigurationAdapter. It parses TOML once,
normalizes `+snat` to base direction + ordinary-side NAT intent, preserves ordered firewall
rules and returns typed values for Device client transport/publication and Profile
availability.

The existing structural parser remains a lower bounded structural normalizer. Its internal
ability to coexist with old experiment-only transport parsing is not the public Release-1
contract; `parse_release1_config` is the canonical boundary and rejects the legacy top-level
integration object.

The executable alpha now consumes `parse_release1_config`:

- Device `use_outbound_nat` -> existing `DeviceNatPolicyIntent`;
- Device `firewall` -> existing ordered `DeviceFirewallPolicyIntent`;
- Device `allow_vpn_client` -> existing exact `IntegrationLocalTransportIntent`;
- canonical but not-yet-complete `+snat`, `availability_check` and
  `publish_vpn_server` -> fail-fast config rejection, never silent ignore.

This is preferable to keeping compatibility aliases or adding another generic config object.

> **Corrective note, later 2026-11-17 CD:** the statement below that firewall ranges were
> an accidental over-generalization was itself a review mistake. The owner clarified that the
> intended Release-1 grammar retains port ranges and additionally allows comma-separated exact
> ports/ranges as one compact port bundle. The corrective review
> `NG3-2026-11-17-port-bundle-correction-review.md` supersedes Finding 2 and the corresponding
> simplification bullet; the rest of this historical review remains valid.

## Findings discovered during review

### 1. Wrong NAT suffix corrected

An intermediate draft used `+masquerade` for Profile ordinary-side NAT. That would conflate
the direction/opposite-side function with Device outbound MASQUERADE. The accepted suffix is
`+snat`.

### 2. Firewall range over-generalization removed — **SUPERSEDED**

This finding was incorrect. It conflated “not re-discussed in that short grammar pass” with
“deliberately removed.” The later corrective CD restores the intended port-range capability
and extends it to compact ordered port bundles.

### 3. Canonical example initially violated selector ownership

The first full example used:

```text
device.oc-backup expected_interfaces = ["vpn*/2"]
device.oc-server expected_interfaces = ["vpns0"]
```

Those selectors overlap. Unit CI rejected the example through the already accepted active
selector-overlap invariant. The server example was corrected to a disjoint exact interface.
This is a real review finding, not a parser workaround.

### 4. Adapter error type leak corrected

The first parser implementation exposed lower `ConfigError` on structural validation rather
than the canonical `Release1ConfigError`. The adapter now translates lower validation
failures at its boundary.

## Evidence

NG3 Python run `44128242193` passed all jobs.

Rootless unit evidence:

```text
Ran 560 tests
OK
```

Installed systemd alpha regression with canonical config:

```text
EXP051_ALPHA_CONTROLLER_READY=PASS
EXP051_ZERO_PATH_TRANSPORT_ALLOW=PASS
EXP051_VPN_SYSTEMD_NAMESPACE=PASS
EXP051_FIRST_PAYLOAD=PASS
EXP051_FIRST_MANAGER_RECONCILE=PASS
EXP051_MANAGER_RECONCILE_COUNT=PASS:2
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The same run also passed EXP-049 and EXP-050 real OpenVPN/systemd applicability and lifecycle
evidence.

A dedicated rerun record is stored at
`design/experiments/EXP-051 NG3 first functioning alpha/EXP-051-result-20261117-canonical-config-pass.md`.

## Simplification review

Deliberately **not** introduced:

- backward-compatible parser aliases;
- a public Integration object separate from Device;
- a dedicated availability table when Release 1 has only one scalar criterion;
- user timing/hysteresis knobs;
- ~~firewall port ranges~~ — **superseded by the port-bundle corrective CD**;
- a generic firewall AST exposed to the user;
- a dual Python/Rust runtime abstraction;
- a plugin-language/FFI framework;
- an immediate Rust rewrite before beta evidence.

Each omitted mechanism either lacks a requirement or would increase complexity without
changing accepted Release-1 behavior.

## Requirement-state inventory before Rust closure

Mechanical count on the current tree before applying this review verdict:

- normative R/C nodes: **159**;
- closed: **154**;
- pending_closure: **5** — exactly R7.R8, R7.R8.C1, R7.R8.R1, R7.R8.R2, R7.R8.R3;
- rejected_closure: **0**;
- open: **0**;
- active `unreal`: **0**;
- active `broken`: **0**.

Accumulated resolved `decomp` annotations: **6 occurrences**, all with concrete deblockers:

1. `VPNG0005-R5 -> VPNG0005-R5.R6`;
2. `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` (recorded in two affected paths);
3. `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` (recorded in two affected paths);
4. `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

No pending decomp remains.

## Verdict

**ACCEPT.**

- Canonical Release-1 grammar is closed and may be implemented/used without the former
  grammar deferral.
- R7.R8 target-Rust architecture is sufficient; its five pending nodes may move to
  `[closed]`.
- Early Python alpha/beta remains explicitly allowed and therefore the Rust target creates no
  beta blocker.

## Remaining beta blockers after this unit

This cycle does **not** make the current alpha a real beta by itself. Remaining material
implementation/evidence units include at least:

1. real canonical `use_outbound_nat = true` end-to-end payload smoke, removing reliance on a
   remote return route for that scenario;
2. end-to-end availability observation/effective-order/failover runtime;
3. truthful operator status presentation;
4. completion or an explicit beta-scope decision for accepted-but-alpha-rejected
   `+snat` / server publication capabilities.

The Rust production rewrite is deliberately **not** on that beta list.

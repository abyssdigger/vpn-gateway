# Independent technical review after EXP-004

**Date:** 2026-11-08  
**Reviewed baseline:** architecture RC2.4.1, implementation RC2.5.1  
**Evidence:** committed EXP-004 laboratory record

## Scope

This review is deliberately performed after EXP-004 was committed, using the repository
record as the evidence base rather than relying on transient chat context.

The review asks:

- which EXP-004 findings invalidate or refine architecture contracts;
- which current implementation structures can remain;
- which changes are implementation-only;
- which changes require architecture revision before code work;
- what should be validated next.

No architecture or implementation change is made by this review document itself.

## Executive assessment

EXP-004 validates two important existing designs:

1. the `proto 201 metric 65536` blackhole guard remains an effective fail-closed route
   fallback when the VPN-dependent unicast route disappears;
2. the current per-table `iptables-restore --noflush` cleanup transaction form is viable on
   the tested Debian 13 / iptables-nft 1.8.11 backend.

However, EXP-004 also exposes two architecture-level gaps:

1. vpn-gatewayd owns global `net.ipv4.ip_forward` but RC2.4.1 does not currently make a
   terminal decision for all IPv4 FORWARD traffic;
2. a configured VPN interface cannot always be represented as one static exact Linux
   interface name. ocserv allocates runtime devices from a numeric family.

These findings require architecture revision before implementation work.

---

## R1 — Complete IPv4 FORWARD ownership

### Evidence

EXP-004.1 demonstrated real unmanaged traffic entering the gateway and traversing it because
all daemon-owned FORWARD chains returned and the built-in policy was ACCEPT.

### Assessment

This is an architecture-level policy defect.

The existing statement that vpn-gatewayd owns IPv4 forwarding and exclusively controls
`net.ipv4.ip_forward` implies responsibility for the complete transit decision while
forwarding is enabled.

It is not sufficient to own only traffic whose destination matches configured protected
routes or VPN transport networks.

### Recommendation

Do not change the host's built-in `FORWARD` policy.

Instead, keep the deterministic daemon-owned prefix and add a final daemon-owned terminal
FORWARD guard after all explicit daemon allows/rejects and before foreign rules.

Conceptually:

```text
FORWARD
  -> VPNG-INGRESS
  -> VPNG-RESERVED
  -> VPNG-<PROFILE>-FORWARD ...
  -> VPNG-FORWARD-DENY
  -> foreign rules...
```

The final daemon-owned chain must make a terminal decision for every packet that reaches it.

This preserves foreign rules physically and restores their relevance after daemon cleanup,
while making them unreachable for forwarded IPv4 traffic during daemon ownership.

---

## R2 — Interface selector and runtime concrete binding

### Evidence

EXP-004.3 established:

- sequential ocserv reconnects commonly reuse `vpns0`;
- if `vpns0` is occupied, ocserv can allocate `vpns1`;
- `device = vpns0` produces `vpns00`.

Therefore ocserv `device` is a basename/prefix, not a stable exact netdev name.

### Configuration recommendation

Keep one configuration key:

```toml
interface = "wg0"
interface = "vpns%"
```

The trailing `%` is a vpn-gatewayd sentinel, not a general glob or regex.

Semantics:

```text
wg0    -> exact runtime interface "wg0"
vpns%  -> concrete names matching ^vpns[0-9]+$
```

`%` is allowed only once and only as the final character.

### Critical internal-model requirement

The selector string must never be materialized into kernel resources.

`vpns%` exists only at the discovery/configuration boundary.

The daemon must resolve configuration selectors against the current interface inventory and
produce a concrete runtime binding such as `vpns0` or `vpns1`.

Only that concrete name may enter:

- `RouteSpec.interface`;
- iptables `-i` / `-o` rules;
- MASQUERADE egress matching;
- runtime profile diagnostics/ownership;
- Netlink-to-profile dispatch.

The correct model is therefore:

```text
configured interface selector
        |
        v
runtime discovery / resolution
        |
        v
exact concrete runtime interface
        |
        +--> routes
        +--> INPUT/FORWARD rules
        +--> NAT
```

### Cardinality

For a numeric-family selector:

- zero matches -> profile not ready / no concrete binding;
- exactly one match -> bind to that concrete interface;
- more than one match -> ambiguous and fail closed.

The daemon must never choose the first, lowest-numbered, newest or otherwise arbitrary
candidate.

### Configuration conflicts

Potential selector overlap inside the simultaneously managed set is a configuration error and
must prevent service startup.

Examples of conflicts:

```text
vpns%  + vpns0
vpns%  + vpns1%
```

The configuration must guarantee that one possible runtime interface cannot belong to two
managed profiles.

This conflict is semantic, not merely string equality.

---

## R3 — Consequence for fixed firewall/NAT

### Assessment

RC2.4.1 currently derives profile INPUT/FORWARD/NAT rules directly from
`profile.interface`, assuming it is a concrete immutable netdev name.

That model cannot remain unchanged for selector profiles.

This is deeper than permitting `%` in the config parser.

### Required architecture split

For exact-name profiles, existing static materialization remains naturally possible.

For selector profiles, interface-specific allow/NAT rules must follow the resolved concrete
runtime binding.

Therefore the architecture should distinguish:

1. **fixed structural safety policy**, independent of a current binding;
2. **runtime-bound interface policy**, materialized only for the one resolved concrete
   interface.

The runtime-bound portion includes at minimum:

- interface-specific INPUT rules;
- protected-route FORWARD ACCEPT rules requiring the concrete egress;
- MASQUERADE for the concrete managed egress;
- concrete route `dev` fields.

The selector itself must not be converted into an iptables wildcard for allow or NAT policy.

### Event gap

Moving binding-sensitive policy to interface discovery creates an unavoidable reaction window
between kernel interface appearance/disappearance and daemon reconciliation.

Architecture must explicitly design this gap fail-closed rather than pretending the old
fully-static policy still exists.

A deny-only prefix guard may be a viable mechanism because overmatching a deny is safer than
overmatching an allow, but the exact iptables interface-prefix contract should be validated
on the target backend before it becomes normative.

---

## R4 — Marker-selective cleanup route inventory

### Evidence

EXP-004.5 proved that:

```text
ip -j -N -4 route show table main proto 201
ip -j -N -4 route show table main proto 202
```

exclude unrelated foreign multipath state.

The selected protocol is omitted from each JSON result because it is already known from the
query.

### Recommendation

Keep the current strict full-table route inventory for normal reconciliation.

Add a cleanup-specific marker inventory path for `proto 201` and `proto 202`.

The cleanup parser may assign the protocol from query context.

This prevents unrelated unsupported multipath/nhid routes elsewhere in `main` from blocking
config-independent cleanup without weakening normal reconciliation.

---

## R5 — Runtime directory / lifetime lock

### Evidence

Standalone foreground startup after reboot failed because `/run/vpn-gateway` did not exist.

### Recommendation

Before opening the lifetime lock, safely ensure the runtime directory:

- parent `/run` is expected;
- final component is not followed as a symlink;
- existing object must be a directory;
- mode is private (`0700`);
- owner is the expected daemon service identity.

If absent and the process has sufficient permission, create it with `0700`.

Do not silently repair an existing wrong owner/mode with chmod/chown; treat that as a
security/configuration failure.

`RuntimeDirectory=vpn-gateway` remains the preferred systemd deployment mechanism and is
especially useful for a future non-root service identity.

A configurable alternative shared lock path is unnecessary until a real multi-instance
coordination use case exists.

---

## R6 — Existing designs to retain

### Blackhole

Retain:

```text
BLACKHOLE proto 201 metric 65536
preferred UNICAST proto 202 metric 10/20/... 
```

EXP-004.2 confirmed the intended FIB behavior: loss of the interface-dependent unicast route
does not fall through to the ordinary default route.

### iptables cleanup transaction

Retain the current per-table cleanup form:

```text
-D owned jumps
-F owned chains
-X owned chains
COMMIT
```

EXP-004.4 confirmed success with duplicate jumps and preservation of foreign state.

The synthetic undeleted-reference case also confirmed that a failing `CHAIN_DEL` leaves the
table unchanged on the tested backend.

### Exact-route authoritative reconciliation

No EXP-004 evidence invalidates the current exact-prefix authoritative routing model.

### OWNED commit ordering

Retain the prior maintainer decision:

```text
route verify
-> commit process-local OWNED
-> enable + confirm ip_forward
```

Moving process-local OWNED commit after forwarding would create a worse failure window.

---

## R7 — Existing implementation corrections still pending

The previous independent review accepted read-before-write for `ip_forward`.

That remains correct:

- cleanup should read before writing `0`;
- bootstrap should read before writing `1`;
- resulting state must still be confirmed.

This is independent of EXP-004 and should remain in the next implementation block.

The earlier foreign route metric-collision concern remains deferred to a dedicated experiment;
EXP-004 did not resolve it.

---

## R8 — Small architecture/code inconsistencies noticed during reread

These are not EXP-004 blockers but should be corrected when the architecture is revised.

1. §9.2 prose first describes the profile FORWARD order as
   `INVALID DROP -> ACCEPT -> REJECT`, but the later compact ordering block omits the
   INVALID step. The implementation contains the safer intended order.
2. The architecture says IPv4 address inventory considers only
   `addr_info[].family == "inet"`; the implementation currently also accepts a missing
   `family` field. The adapter should eventually match the stated strict contract unless a
   real iproute2 observation justifies the compatibility path.

---

## Recommended sequencing

1. Revise architecture before changing Python.
2. Make complete IPv4 FORWARD ownership normative.
3. Introduce interface-selector -> concrete-runtime-binding semantics and configuration
   overlap validation.
4. Redesign binding-sensitive firewall/NAT around concrete runtime names, with an explicit
   fail-closed answer for the interface event/reconciliation gap.
5. Add marker-selective cleanup inventory and secure runtime-directory creation/validation.
6. Retain blackhole and iptables cleanup transaction designs.
7. Validate any newly introduced external CLI contract on target Debian before encoding it.
8. Implement the revised architecture with focused unit tests.
9. Run the next live lifecycle/binding experiment only after the new safety model exists.
10. Implement full RUN-time Netlink/periodic reconciliation after lifecycle/binding behavior
    has been validated.

## Versioning recommendation

Do not treat the full post-EXP-004 change set as a cosmetic RC2.5.2 maintenance patch.

The accepted read-before-write correction alone would fit RC2.5.2, but complete FORWARD
ownership plus dynamic interface binding alter policy semantics.

The architecture should receive a substantive revision first; implementation versioning
should then reflect that revised contract.

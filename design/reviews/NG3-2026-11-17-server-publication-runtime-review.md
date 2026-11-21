# NG3 server-publication runtime final review — 2026-11-17

## Review unit

Close the Release-1 runtime materialization unit for canonical Device
`publish_vpn_server` on the Python reference alpha/beta runtime without widening product
semantics or ordinary-host ownership.

Cycle branch:

`ng3-beta-cycle-20261117-server-publication-35m`

Cycle start:

`c3d8fe3903037794a0e03dd7f7457c56401efb85`

Base clean main:

`b242fd9d74ba9a62b88f07225da6a61b62d7e4ab`

## Requirement trace

Primary implementation trace:

- `VPNG0001-R1.R2.R4.R6.R3` — Device-owned server publication and canonical
  `publish_vpn_server` grammar;
- `VPNG0001-R1.R2` — VPN-GATE materializes its required internal network actions;
- `VPNG0004-R4.R6.R1.R1` — mutable lower state must live in an explicit owned boundary;
- `VPNG0004-R4.R6.R1.R5.R1` — publication-specific managed INPUT/OUTPUT exceptions are
  VPN-GATE-owned without becoming arbitrary payload/host firewall ownership;
- `VPNG0006-R6.R4` — required/current/unknown state must not be conflated when it matters
  for user understanding or safety;
- `VPNG0007-R7.1/R7.3/R7.5/R7.7` — bounded implementation, authoritative observation,
  review/evidence and requirements-driven development.

No requirement text was changed in this cycle.

## Resulting component boundary

One normalized Device publication now produces two separately observed lower postconditions:

```text
publish_vpn_server
    |
    +--> managed-domain local publication admission
    |       table ip vpn_gate
    |       stack_input / stack_output
    |       EXP-046/047 owner
    |
    +--> ordinary-host publication mapping
            table ip vpn_gate_publication
            publication_prerouting
            EXP-052 owner
```

No new long-lived Manager/Agent was introduced. The existing network-policy/runtime owner
synchronously invokes the dedicated host-boundary Driver/Executor.

The ordinary-host owner is intentionally narrow:

- one reserved nft table;
- one NAT prerouting chain;
- exact owner comments;
- exact normalized publication rules;
- strict refusal to adopt or delete foreign objects inside the reserved table;
- no ownership of unrelated host firewall/routing/interface/address/sysctl state.

## Evidence

### EXP-052 — lower host publication

The initial packet experiment proved TCP/UDP DNAT and reverse conntrack translation, then
expert review identified that interface/port-only and selector-less/port-only matches could
capture unrelated transit.

The accepted lower rule therefore proves original destination locality before DNAT:

```text
fib daddr type local
```

Final reference-backend evidence runs the actual
`LinuxHostPublicationBackend + converge_host_publication_once` implementation.

Final evidence:

- GitHub Actions run `44168281782`;
- job `linux-host-publication-dnat` — PASS;
- same-port foreign transit — untouched;
- interface selector — exact;
- IPv4 selector — exact;
- omitted selector — local destination with no additional user-selected address/interface
  restriction;
- TCP and UDP reverse translation — PASS;
- original external client source visible at managed listener — PASS;
- unrelated host-local listener — untouched;
- strict owner observation — PASS;
- explicit empty-desired cleanup — PASS.

### EXP-051 extension — installed runtime

Installed Debian 13/systemd alpha evidence:

- GitHub Actions run `44167358884`;
- job `linux-alpha-smoke` / `134336862209` — PASS.

The installed controller proved:

- publication is materialized before a concrete VPN endpoint exists;
- host DNAT and managed local admission are both present before READY;
- external TCP actually traverses host publication into the managed listener;
- ordinary OpenVPN startup/payload/restart reconciliation remains green;
- controller stop removes the host publication owner before managed-domain teardown.

Observed markers include:

```text
EXP051_SERVER_PUBLICATION_E2E=PASS
EXP051_SERVER_PUBLICATION_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The later full run `44168281782` also passed after the final code hardening.

## Expert-review findings and dispositions

### F1 — initial rule shape could capture foreign transit

**Severity:** major if left unfixed.  
**Disposition:** fixed and evidenced.

Interface-selected and selector-less publication require `fib daddr type local`.
EXP-052 explicitly proves same-port foreign transit remains untouched.

### F2 — ordinary-host forwarding must not become implicit ownership

**Disposition:** fixed by boundary definition.

The DNAT path requires host IPv4 forwarding. The runtime freshly observes
`net.ipv4.ip_forward` but does not enable it.

A positive requested publication with forwarding disabled becomes `UNREADY`; cleanup of
owned publication remains possible even when forwarding is disabled.

Changing ownership of ordinary-host forwarding would require a separate requirement/design
decision.

### F3 — explicit selectors require authoritative host facts

**Disposition:** fixed.

Before positive mutation:

- an interface selector must name an existing UP host interface;
- an exact IPv4 selector must already be assigned locally;
- omitted selector introduces no additional user-selected interface/address prerequisite.

The runtime does not create/raise interfaces or assign host addresses.

### F4 — overlapping publication selectors cannot acquire declaration-order semantics

**Disposition:** fixed.

Potentially overlapping external selectors for the same protocol/host port that require
different internal targets are rejected as an ambiguous lower projection.

Identical physical contributions may be set-deduplicated.

### F5 — ambiguity validation originally happened too late in startup

**Severity:** major if left unfixed.  
**Disposition:** fixed in `3158530c25a8e8011a5de368f2f7a82c6dbbe4f4`.

The original runtime wiring could discover an overlap only after managed-domain activation.
That could let a pure configuration/projection failure escape the intended bounded startup
cleanup path.

`AlphaPreparedPolicy.from_text(...)` now validates the complete host-publication projection
before domain creation or lower mutation.

### F6 — lower ifname type was weaker than canonical parser

**Severity:** security hardening.  
**Disposition:** fixed in `4ba2db57587f2bd8797c70f75e46ee120aee0d8a`.

Because the lower Driver renders an nft transaction, the internal intent type now independently
requires the same safe ASCII Linux-ifname subset used by the canonical Adapter:

```text
[A-Za-z0-9_.-]+
<= 15 bytes
```

A unit regression rejects newline/script-metacharacter input.

### F7 — omitted selector must not invent an unstated public-only address set

**Disposition:** no code change; semantic cross-check passed.

The requirement says omitted selector publishes on permissible host addresses. The accepted
`config-model.md` further states that omission means there is **no additional user-selected
host address/interface restriction**.

Therefore the implementation may use host-local destination proof as the ownership guard. It
must not invent a hidden public-interface whitelist or silently exclude local addresses absent
a separate accepted product rule.

### F8 — foreign ordinary-host NAT/firewall can still externally interfere

**Disposition:** outside this owner's postcondition; no ownership expansion.

The host publication owner proves its own exact lower state and explicit prerequisites. It
does not parse, adopt, reorder or delete arbitrary foreign host NAT/firewall state.

Arbitrary external interference can make real-world reachability differ from the owned lower
postcondition. Treating all host networking as VPN-GATE-owned merely to eliminate that
possibility would violate the accepted ownership boundary.

A future promise to actively prove end-to-end public reachability or to arbitrate conflicting
foreign host NAT requires its own requirement/evidence unit.

### F9 — nft cleanup does not claim forced destruction of established sessions

**Disposition:** scope made explicit.

Removing the publication owner removes the classification path for new flows. Existing kernel
conntrack/session state may have its own lifetime.

No current accepted requirement demands forced termination of already-established published
transport sessions when publication is withdrawn. This cycle therefore does not invent
conntrack deletion semantics.

## Fail-closed / lifecycle review

Startup order:

```text
canonical config + publication projection validation
    ->
managed domain ensure
    ->
managed local publication admission / structural policy exact
    ->
host publication prerequisite observation
    ->
host owner convergence + fresh verification
    ->
READY
```

Stop order:

```text
STOPPING
    ->
host publication desired = empty + fresh absence verification
    ->
managed controller/domain teardown
    ->
successful stop
```

Periodic reconciliation confirms both managed and host halves. Host loss/prerequisite loss
does not remain silently EXACT; the reconcile result becomes failed/unready with a diagnostic.

The broader user-facing `RuntimeStatusAgent` remains a separate project unit. This cycle
does not falsely claim that systemd/log diagnostics are the final status API.

## Simplification review

Rejected as unnecessary:

- reusing the NG1 userspace relay merely because it existed historically;
- a generic ordinary-host firewall/NAT Manager;
- per-publication processes;
- persistent nft handle databases;
- declaration-order selector precedence;
- automatic host forwarding/interface/address mutation;
- a new user-facing selector grammar;
- conntrack/session killing not required by accepted semantics.

The current implementation uses one pure projection and one synchronous bounded host
Driver/Executor.

## Requirement-state inventory

### decomp

No new `decomp` links were created by this unit. The accumulated unique links are all
resolved because their decomposition targets are closed:

- `VPNG0005-R5 -> VPNG0005-R5.R6` — resolved;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` — resolved;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` — resolved;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2` — resolved.

Repeated occurrences of the same link in the requirements tree do not create additional
open decomposition state.

### unreal

None active.

### broken

None active.

### closure_rejected

None.

## Verdict

**PASS — logical review unit complete.**

Canonical Release-1 `publish_vpn_server` now has:

- normalized positional PortBundle mapping;
- managed local admission;
- separate strict host DNAT owner;
- authoritative prerequisite observation;
- bounded convergence and cleanup;
- installed end-to-end systemd evidence;
- explicit ownership and non-claims.

No human product decision remains for this unit.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`
- `VPNG0006-R6.R4` -> `VPNG9101-R2.R1.R4`

The original IDs in the historical body are intentionally preserved.

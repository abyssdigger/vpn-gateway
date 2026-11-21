# NG3 lower-boundary reuse / traceability CDC

**Status:** completed / reviewed  
**Date:** 2026-11-21  
**Cycle start:** 2026-11-21 23:39:50 +03  
**Interval:** 30 minutes  
**Branch:** `ng3-lower-boundary-reuse-trace-cd`  
**Base:** `9dbba5e88b5b32a8b1a9d5a238c405f83b91f777`  
**Main base:** snapshot 151, `2073808bc1ba61af9d79bdac1d97fccb9319fcf6`

## Scope

This CDC starts by testing whether the current Linux lower layer benefits from reusable
Driver/Reader/Executor boundaries under `design/component-model.md`. The result is then used
for the Backend/Driver terminology comb, followed by requirement-to-architecture trace
completion, stable evidence indexing and final review.

Relevant maintainability requirements include `VPNG0007-R7.R2`,
`VPNG0007-R7.R3.R5`, `VPNG0007-R7.R4` and `VPNG0007-R7.R6.R1`.

## Initial applicability assessment

The component model permits a separate Reader/Executor only when it creates practical
architectural value: reuse, independent replacement/testing, a clearer responsibility
boundary or simpler composition. A raw `run(argv)` helper remains below the component model.

### A. Reusable lower boundaries that are justified

| Candidate | Assessment | Decision |
| --- | --- | --- |
| `LinuxStructuralRoutingDriver` | Payload structural routing and probe routing genuinely share the same exact route rendering/mutation contract. Probe-specific RPDB rules remain outside it. | **Keep and reuse.** This is the useful model for lower reuse: identical technical semantics, not merely the same executable. |
| nft namespace owner/inventory observation | A standalone read-only contract already exists as `LinuxNftNamespaceBackend`; it is independently tested and used by executable evidence. It performs one observation and no composition. | **Classify as Reader**, not Backend. Keep the scope narrow: reserved NG3 nft namespace observation/normalization. |
| raw process/script runners | `NftScriptRunner`, `CommandRunner` and subprocess implementations are reused injection/transport primitives. | **Keep below Machinery-role classification.** Do not promote them to generic Executor components. |

### B. Generic reusable boundaries that are not justified now

| Candidate | Why not |
| --- | --- |
| universal `NftDriver` | Current nft owners have materially different ownership, observation and safety contracts. A generic nft command facade would become a CLI passthrough or force semantic owner knowledge into a supposedly generic Driver. |
| universal `IpRouteDriver` | Payload structural routing, probe RPDB, priority-only make-before-break, host helper routing and transition lifecycle do not share one exact mutation/observation contract. Shared route mutation already exists where semantics actually coincide. |
| generic `SysctlDriver` | Current sysctl uses are small and belong to different boundaries (Private forwarding gate, transition invariants, host prerequisite observation). Extraction would add indirection without a useful shared contract. |
| generic `RouteReader` / `RuleReader` | Authoritative observations differ by owner and often require link-generation bracketing, reserved-pool classification or desired-state context. Reusing only the JSON command would discard the correctness contract. |
| one Executor per nft/ip command | This would be micro-component decomposition. The operations are naturally methods of the corresponding Driver unless multiple callers need the exact same action contract. |

### C. Current `*Backend` classification comb

**Real Backend compositions — retain the term:**

- `LinuxStructuralPolicyBackend` — composes routing and composite-nft lower boundaries.
- `LinuxCompositeNftBackend` — composes several owner-specific nft lower boundaries plus
  combined observation.
- `LinuxProbeRoutingBackend` — composes the shared structural-routing Driver with
  probe-specific RPDB operations and owner-specific observation.
- `LinuxStackReturnAffinityBackend` — presents one lower API over two mechanisms:
  nft state and RPDB state. Convergence/postcondition remains outside in
  `stack_return_affinity_convergence.py`.

**Narrow mechanism boundaries — rename/classify as Driver:**

- `LinuxNftScaffoldBackend`;
- `LinuxDeviceFirewallBackend`;
- `LinuxPayloadNatBackend`;
- `LinuxLocalPublicationBackend`;
- `LinuxIntegrationLocalBackend`;
- `LinuxProbeLocalBackend`;
- `LinuxHostManagedRoutingBackend`;
- `IproutePriorityBackend`.

Already correctly named Drivers:

- `LinuxStructuralRoutingDriver`;
- `LinuxForwardingGateDriver`;
- `LinuxHostPublicationDriver`.

### D. Reader/Executor extraction decisions

1. **Extract/rename the existing nft namespace observation object as a Reader.**
   This is a real independently testable read contract and already exists as its own object.
2. **Do not split the narrow Drivers into separate Reader + Executor classes.**
   Their read/write methods share one mechanism boundary and no caller currently benefits
   from another object boundary.
3. **Do not introduce generic Executors around individual `nft`, `ip` or `sysctl`
   commands.** Existing raw runners are the correct injection boundary below the component
   model.
4. **Keep convergence outside Drivers/Backends.** If the comb finds a lower object choosing a
   broader desired-state plan or owning final postcondition, that is a separate Enforcer
   finding rather than a reason to invent a generic Executor.

## Expected implementation consequences

The terminology comb should be mostly mechanical renames plus protocol/call-site/test updates,
with no product semantic change. The only reusable-boundary change expected is the
`LinuxNftNamespaceReader` classification and reuse where the exact same observation contract
is needed.

No new universal lower framework is justified by the current code. Introducing one would
increase coupling and weaken owner-specific correctness checks, contrary to the purpose of
the component-model decomposition.

## CDC frontier after this assessment

1. apply the Backend/Driver/Reader comb to current production code and architecture;
2. run mechanical/unit/integration evidence;
3. complete the missing requirement -> structured architecture side of traceability without
   blind link insertion;
4. create the next stable evidence entry (`EV-00010`) for the accepted baseline;
5. expert-review the whole CDC, including this applicability assessment and any rejected
   reuse candidates;
6. snapshot only after a clean completed development block.


## Applied terminology comb

The assessment was applied to current production call sites without introducing a universal
Linux lower framework.

Current production role names now use:

- `LinuxNftNamespaceReader`;
- `LinuxNftScaffoldDriver`;
- `LinuxDeviceFirewallDriver`;
- `LinuxPayloadNatDriver`;
- `LinuxLocalPublicationDriver`;
- `LinuxIntegrationLocalDriver`;
- `LinuxProbeLocalDriver`;
- `IproutePriorityDriver` / `RoutePriorityDriver`;
- `LinuxHostManagedRoutingDriver`.

Existing broad `LinuxStructuralPolicyBackend`, `LinuxCompositeNftBackend`,
`LinuxProbeRoutingBackend` and `LinuxStackReturnAffinityBackend` remain Backends because
they are actual compositions.

Old class names remain only as explicit aliases in implementation modules so historical NG3
executable evidence can continue to import the terminology it was recorded with. Current
production call sites and package exports use the role-correct names.


## Requirement-side traceability closure

The previous code-side trace invariant covered every production Python unit, but a fresh
closed-requirement scan found 60 closed Requirement/Constraint IDs with no occurrence in the
structured architecture.

The fix does not blindly append those IDs to component specs. Structured architecture now
contains a closed-requirement coverage index grouping parent/root and cross-cutting
requirements by their real architecture owners. The previously flat-only production-runtime
language boundary was also migrated into the structured architecture.

The architecture traceability test now fails if any `closed` requirement has no explicit
structured-architecture entry. This completes the mechanical requirement -> architecture
entry-point invariant while preserving component-local `Implements / Constrained by`
mapping for requirements that genuinely belong to one component.


## Final evidence

Reviewed implementation baseline:

- `f2e045285510c8d202db95efef450811bfcdfa87`

GitHub Actions:

- workflow: `NG3 Python`
- run: `44949136760`
- result: **SUCCESS — 21/21 jobs**
- unit suite: **790 tests PASS**
- alpha smoke: PASS
- host publication / host managed routing: PASS
- OpenVPN/systemd applicability: PASS
- Debian-12 routed-veth portability: PASS

Mechanical trace checks on the reviewed tree:

- closed requirements: **144/144** have a structured-architecture entry point;
- production Python implementation units: **109/109** are represented by
  `design/NG3/implementation-traceability.md`.

## Expert review

### F1 — universal Linux mechanism Drivers would weaken, not improve, the architecture

**Disposition:** accepted assessment; no implementation required.

A universal `NftDriver`, `IpRouteDriver` or `SysctlDriver` would share executable syntax
while discarding owner-specific observation, ownership and safety contracts. Raw runners
remain below the component model; no generic framework was introduced.

### F2 — nft namespace observation is a useful standalone Reader only at its exact contract

**Disposition:** accepted; implemented.

`LinuxNftNamespaceReader` is independently testable and now reused by
`LinuxNftScaffoldDriver`. Composite nft observations retain their own link-generation
bracketing instead of being forced through a weaker Reader contract.

### F3 — narrow Backends were misnamed Drivers

**Disposition:** fixed.

Current production role names use Drivers for nft scaffold/owner mutation, priority-route
technical operations and host-managed routing. Structural-policy, composite-nft,
probe-routing and stack-return-affinity remain Backends because they are actual lower
compositions.

Historical class names remain explicit aliases only for executable-evidence compatibility.
Two historical module filenames still contain `backend`; filenames are not architecture
roles, and renaming them would require compatibility modules solely to preserve old evidence
imports. This cosmetic cleanup is therefore not required for the current block.

### F4 — priority Driver is not a hidden Enforcer

**Disposition:** accepted.

`IproutePriorityDriver` may implement one concrete semantic move using local
add/verify/delete technical safety. It does not choose the caller's desired assignment or
the sequence of convergence steps. `RoutePriorityEnforcer` still plans the broader
transition and performs final desired-state verification.

### F5 — host-managed routing Driver does not own host-routing policy

**Disposition:** accepted.

Its desired-aware observation is against an already lowered Linux contract and only exposes
technical missing/stale/conflict facts. The peaceful helper / outer convergence code retains
choice of desired contribution, mutation ordering, lifecycle scope and final success
semantics.

### F6 — requirement-side trace had a real completeness gap

**Disposition:** fixed and mechanically enforced.

The previous implementation manifest gave a strong code -> architecture path, but 60 closed
parent/root/cross-cutting requirements had no structured-architecture entry point. The new
coverage index maps them to real architecture owners instead of manufacturing component
ownership. CI now rejects any closed requirement absent from structured architecture.

### F7 — production-language architecture existed only in the flat document

**Disposition:** fixed.

The Rust production boundary, Python reference/tooling exception and safe-Rust/unsafe-FFI
rule are now present in structured architecture and trace the relevant closed requirements.

### F8 — historical compatibility surface remains explicit

**Disposition:** fixed during review.

The old `route_priority_executor` shim briefly lost its historical
`RoutePriorityBackend` export during the mechanical rename. The alias was restored while
current production remains on `RoutePriorityDriver`.

## Remaining non-blocking topics

1. The historical module filenames `iproute_priority_backend.py` and
   `linux_host_managed_routing_backend.py` may eventually be renamed if executable evidence
   no longer needs their import paths. No component/API semantics depend on this cleanup.
2. The closed-requirement coverage index is intentionally normative and human-readable. If it
   grows substantially, generation/checking may later move to a dedicated trace artifact,
   but the current explicit architecture entry points should remain reviewable.
3. `__init__.py` remains the previously declared packaging-only architecture debt in the
   implementation trace manifest; this CDC neither creates nor worsens that debt.

## Requirement-state inventory

No active `decomp`, `unreal`, `broken` or `rejected_closure` requirement state was
found in the current normative tree.

## Verdict

**PASS — DEVELOPMENT BLOCK COMPLETE.**

The reusable-boundary decision is now explicit and applied; current lower role names follow
the component model without introducing a generic Linux framework; closed requirements and
production implementation are both mechanically connected to structured architecture; the
full executable evidence matrix passes.

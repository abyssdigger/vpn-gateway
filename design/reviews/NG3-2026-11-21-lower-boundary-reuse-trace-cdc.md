# NG3 lower-boundary reuse / traceability CDC

**Status:** active CDC working document  
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

# VPN-GATE NG3 — Purpose/parent correction impact assessment

**Status:** non-normative research artifact  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`

## Главный вывод

Большинство обнаруженных дефектов — **traceability/ancestry defects, а не доказанные
behavior defects**.

Если project holder подтверждает существующую capability и мы только переносим requirement
под честный parent / меняем Basis/Purpose, текущая архитектура и Python code в большинстве
случаев могут остаться функционально неизменными. Большая работа будет в remap точных
requirement IDs по architecture, config-model, experiments и reviews.

Код нужно переделывать только там, где human decision изменит или удалит сам Statement.

## Impact matrix

| Scope | Если сохранить capability и исправить ancestry | Если capability отклонить/сузить |
| --- | --- | --- |
| `VPNG0001-R1.R2` Purpose wording | **Very low.** Только requirement text; architecture/code semantics не меняются. | n/a |
| duplicate `VPNG0001-R1.R2.R4.R4.R1` | **Low.** Удалить duplicate ID и remap config/architecture/review references на `VPNG0003` subtree. Code не меняется. | n/a: семантика уже существует в `VPNG0003`. |
| Profile `+snat` | **Medium docs / low code.** Reparent IDs in architecture/config/evidence; dataplane остается. | **High.** Затронуты `payload_nat_desired.py`, `payload_network_policy_desired.py`, `alpha_runtime.py`, stack-affinity composition, EXP-075/076 и tests. |
| Device outbound NAT | **Medium docs / low code.** | **Medium-high.** NAT normalization/projection/observation/mutation and composite nft evidence become removable/reworkable. |
| Device firewall | **High trace remap / low code.** Большой review/evidence surface, но behavior можно сохранить. | **High.** `device_policy.py`, `device_firewall_compiler.py`, `device_firewall_policy_compiler.py`, composite nft planner/mutation and integrations. |
| VPN-server publication | **Medium trace remap / low code.** | **High.** `host_publication_policy.py`, `linux_host_publication.py`, local publication owner, alpha composition and EXP-052/051 coverage. |
| client transport/control admission | **Medium trace remap / low code.** Вероятный reparent к onboarding не требует behavior change. | **High for supported in-stack VPN onboarding.** `local_integration_policy.py`, local integration nft owner, alpha/OpenVPN integration. |
| transport endpoint provenance | **Low-medium.** В основном architecture/evidence; current Release-1 core не зависит от provenance. | **Low current code impact.** Future endpoint-dependent features lose prerequisite. |
| peaceful helper | **Medium-high trace remap / low code if retained.** `config-model`, helper docs/EXP-077..080 and architecture IDs. | **High Release-1 behavior impact.** `release1_host_route_helper.py`, Linux host-routing backend, config/runtime/status/tests and host-integration expectations. |
| aggressive helper | **Medium docs.** Capability already postponed; reparenting mostly trace cleanup. | **Low current Release-1 code impact**, but detached prototype/evidence (`host_managed_routing.py`, `selected_host_boundary.py`, EXP-074) becomes removable archival evidence. |
| established-flow return affinity | **Medium-high trace remap / low code.** | **High safety/forwarding impact.** `stack_return_affinity.py`, `linux_stack_return_affinity.py`, convergence/activation/alpha integration and EXP-061/076. |
| user-selected availability criterion | **Medium-high trace remap / low code.** | **High config/behavior impact.** availability description/resolver, probe desired/runtime, alpha config/status and EXP-068-related path. |
| `VPNG0004-R4.R6` host isolation | **Very high docs trace, low code if only reparented.** Exact ID has broad architecture/review/evidence usage. | **Very high architecture/code impact** only if non-interference/isolation promise itself is rejected. |
| managed network domain requirement status | **High documentation, near-zero runtime if reclassified as architecture.** Keep selected architecture but stop pretending the mechanism is product semantics. | **Very high** if architecture itself must be replaced: `managed_network_domain.py`, controller lifecycle, path observation, nft/routing ownership and most privileged evidence. |
| literal default DROP requirement | **Medium docs / zero code** if rewritten to mechanism-neutral default-deny behavior while existing nft architecture remains selected. | **High safety code impact** if default-deny behavior itself is rejected; affects scaffold/local owners/composite nft/probe/publication integration. |
| administrative containment | **Low current code.** Pending architecture can be reparented without implementation change. | **Low current code**, future aggressive-helper composition changes. |
| reload | **Low current code.** Alpha implements no reload; mainly requirements/architecture/docs cleanup. | **Low.** Remove future obligation; start/stop/restart unchanged. |
| lifecycle applicability experiment child | **Docs/evidence only.** Reparent/remap EXP-050 trace. | **No production-code impact** unless evidence policy itself is relaxed. |

## Architecture-wide estimate

### If all disputed capabilities are retained

Expected effect:

1. **No dataplane redesign is implied by this audit.**
2. Architecture must remap exact requirement IDs and, for a few blocks, stop presenting a
   selected mechanism as requirement semantics.
3. The largest traceability churn is around:
   - managed-domain/isolation (`VPNG0004-R4.R6*`);
   - Device firewall/NAT/publication;
   - host-routing helpers;
   - availability criterion;
   - Profile SNAT/return affinity.
4. Historical reviews/experiment results must **not** be rewritten. Current registry/current
   architecture may record superseding ID mappings; historical documents retain original IDs
   with branch/time context.

Qualitative estimate: **high documentation churn, low functional-code churn**.

### If some disputed capabilities are rejected

Potential code impact ranges from low (reload, containment, endpoint provenance) to very high
(managed-domain architecture, Device firewall, Profile SNAT, return affinity, peaceful helper).

Therefore this audit does **not** recommend deleting implementation merely because ancestry is
currently wrong. First fix product provenance/placement; only then use the resulting
Requirement/Constraint decision to decide whether code is retained, re-traced or removed.

## Current code areas already materially coupled to disputed nodes

- Profile SNAT: `payload_nat_desired.py`, `payload_network_policy_desired.py`,
  `alpha_runtime.py`, stack return-affinity allocation.
- Device firewall: `device_policy.py`, `device_firewall_compiler.py`,
  `device_firewall_policy_compiler.py`, composite nft code.
- Publication: `host_publication_policy.py`, `linux_host_publication.py`,
  local publication owner and alpha runtime.
- VPN client transport admission: `local_integration_policy.py` and its Linux/local nft owner.
- Return affinity: `stack_return_affinity.py`, `linux_stack_return_affinity.py`,
  `stack_return_affinity_convergence.py`, activation/startup integration.
- Managed domain: `managed_network_domain.py`, controller startup/stop/restart,
  VPN-path observation and all managed-netns lower policy.
- Default-deny local/forwarding surface: `nft_payload_scaffold.py`,
  `composite_nft_policy.py`, probe/local integration/publication owners.
- Reload: no current Python `rou` implementation was found.

## Recommendation before any normative rewrite

Resolve the unresolved questions in semantic groups, not ID-by-ID:

1. **Which capabilities are real product promises?**
2. **Which are only configuration placement decisions?**
3. **Which are selected architecture mechanisms?**
4. Then rebuild ancestry and IDs.
5. Only after the new tree is accepted, remap current architecture/evidence.
6. Touch production/reference code only for Statements whose product semantics actually
   changed.

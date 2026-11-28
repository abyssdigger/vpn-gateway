# NG3 warm-presence evaluation implementation review

**Review type:** internal expert self-review of the implementation, not an independent external review.
**Evaluation branch:** `gpt6-eval-warm-paths-reserve-cdc-20261125`.
**Input product baseline:** `8021fc07f32d3f9e4945c1c1a1ce3408baeb2d70`.
**Process rules:** AGENTS.md and CONTINUOUS-DEVELOPMENT.md from
`main@c86b4ad0b84a228ac84c52a2b2749ac171f45326`.
**Reviewed code baseline:** `74bfb5e3a5116cc998c6aa4578728d2bdca8ffee`.
**Scope:** accepted R7.R3 and R7.R3.R1–R4; A.002, A.012, A.013, C.004,
D.001/D.003 composition and A.008 truthfulness. No change to product requirements,
frozen Release-1 grammar, remote availability semantics or external Device ownership.

## Review against the accepted contracts

| Contract | Review result and evidence |
|---|---|
| R7.R3.R1: normalized 0 / N / all, ordinary-only capacity | Current parser strips warm_paths before historical parser and validates capacity excluding reserve and disabled Devices. Direct grammar/negative tests and frozen deployment QA pass. |
| R7.R3.R2: observed ordinary paths, minimal baseline demand, no proactive identity rebalance, shared OR | Pure projection counts distinct logical paths, accounts for external capacity without actuation, retains present managed capacity before absent candidates, selects absent candidates in baseline order. Per-Profile roles and shared OR are tested, including a Device ordinary in one Profile and reserve in another. |
| R7.R3.R3: ordinary attempt, fresh deficit, reserve exception, recovery and dependency release | Bounded executor re-observes after each attempt, does not stop Devices during presence phases, and attempts alternatives before reserve. Reserve cannot reduce regular_deficit. Actual Linux failure/recovery and selective release acceptance pass; release is gated by confirmed dependent policy, D.003 and exact current binding generations. |
| R7.R3.R4: no traffic or availability demand input | A.013 receives only config and structural PathBindings. A.012 convergence is driven by that projection. Lower availability-cycle confirmation used for release is structural/priority convergence, not positive remote health. No payload, idle or first-packet trigger is consulted. |
| R7.R1/R7.R2: explicit opt-in and independently confirmed realization | Desired set validated against active explicitly managed Devices. D.001 confirms each generation; failed or different-generation endpoint is not treated as accepted managed capacity. External interfaces use the same observation/binding mechanism as before. |
| A.008 truthful observation | Configured warm policy, A.013 diagnostic projection from last confirmed normal binding, and A.012 last accepted desired/confirmed realization are separate. Unknown projection is null. Compact-text grammar is not expanded. |

## Findings and dispositions

1. **F1 — A.013 had no executable reverse trace; C.004 partial edge lacked materialization.**
   Baseline CI run 45638032333 failed exactly those two unit checks.  
   **Decision:** accepted. **Resolution:** fixed in 06a7c082: implement the Calculator,
   add the real trace and explain C.004 scope. No fake trace/placeholder was added.
2. **F2 — Old referenced-set A.012 demand and abort-on-first-global-problem would defeat
   reserve fallback and configured warm cardinality.**  
   **Decision:** accepted. **Resolution:** fixed in 167d3033 / b9473ce9. The caller supplies
   the calculated set; bounded per-Device attempts continue with fresh observations.
   A local D.001 problem degrades status without suppressing confirmed unrelated policy.
3. **F3 — D.001 base success and raw interface-name observation are not interchangeable.**
   A failed start with a same-name endpoint could otherwise count false managed capacity.  
   **Decision:** accepted. **Resolution:** fixed in 167d3033 / b9473ce9: exact confirmed
   endpoint identity, normal binding remains separately authoritative, failure test added.
4. **F4 — Releasing reserve after only the ordinary projection would be break-before-make;
   removing only route/probe policy also leaves a D.003 dynamic dependency.**  
   **Decision:** accepted. **Resolution:** fixed in b9473ce9 and verified in f9e2fdb0 /
   3d865b13. Confirm C.001 and D.002, then exact D.003 probe-only state, before authorizing
   D.001 stop. Negative D.003 test retains reserve; actual kernel AllowedIPs checked just
   before real stop. Reconcile again after the stop attempt.
5. **F5 — Comparing only the desired Device IDs misses a replacement of a concrete path
   generation between policy confirmation and release.**  
   **Decision:** accepted. **Resolution:** fixed in 04a31bdd, strengthened in 3d865b13.
   Release now requires fresh exact binding equality as well as unchanged desired set.
   The negative test keeps the same LogicalPathId/name, changes ifindex and checks no stop.
   This is a fresh-confirmation contract, not a claim of atomicity against out-of-band root.
6. **F6 — A pre-release presence count may be stale after our own successful D.001 stop.**  
   **Decision:** accepted. **Resolution:** fixed in 74bfb5e3. Refresh A.013 diagnostics from
   the last confirmed normal binding after release; actual post-release test confirms
   regular_present=1, regular_deficit=0, reserve_present=0. A.012 desired/confirmed
   realization remains its own source of truth.

The earlier unit failure was corrected without changing requirement status. Subsequent
intermediate runs were superseded by branch concurrency, not treated as full PASS.
The final code workflow completed successfully. No material unresolved finding remains
within the accepted current WireGuard presence scope. The isolated integration does not
prove payload delivery through a live remote reserve; its acceptance target is lifecycle,
structural binding and release ordering. Existing general payload and WireGuard integration
jobs remain green. No additional VPN technology or hot-reload contract is introduced.

## Evidence and verdict

- [Original baseline CI](https://github.com/abyssdigger/vpn-gateway/actions/runs/45638032333):
  922/924 unit tests passed, two traceability failures; other jobs passed.
- [Calculator/parser baseline](https://github.com/abyssdigger/vpn-gateway/actions/runs/45642712898):
  25/25 jobs PASS, 933/933 unit tests.
- [Reviewed final code baseline](https://github.com/abyssdigger/vpn-gateway/actions/runs/45645208959):
  25/25 jobs PASS, 940/940 unit tests; Linux managed runtime job 139314334848 includes
  RESERVE_AFTER_FAILED_ORDINARY, STALE_REPLACEMENT_BLOCKS_RELEASE,
  PEER_RELEASE_FAILURE_BLOCKS_STOP, DYNAMIC_PEER_DEPENDENCY_REMOVED_BEFORE_STOP,
  POST_RELEASE_DEMAND_STATUS and MAKE_BEFORE_BREAK PASS.
- [Lineage guard](https://github.com/abyssdigger/vpn-gateway/actions/runs/45645208720): PASS.
- Stable evidence address: EV-00300.

**Verdict:** accept implementation and evidence for this evaluation development block,
subject to trace/document validation on the subsequent documentation commit.
All eight R7 family nodes remain closed, decomposition complete; no new active decomp,
unreal, broken or rejected_closure in this family. Existing product semantics are unchanged.
No main publication or release approval is implied. CHANGELOG-NG3 remains unchanged:
the evaluation is not an adopted active-lineage milestone.

## Execution limitations

The executor used the GitHub connector and GitHub Actions because this chat's local
runtime could not resolve GitHub for a local clone; no local test PASS is claimed.
The first UTC cycle timestamp (15:10:37Z) was obtained after initial process/baseline
reading, not before it as the methodology requires. The conservative cycle budget was
measured from the user launch minute 15:09Z; this procedural defect does not alter
the reviewed source or evidence. The runtime publication ref initially returned the
previous SHA immediately after a successful update; independent read-only ref and branch
confirmation established the expected SHA before further mutation.

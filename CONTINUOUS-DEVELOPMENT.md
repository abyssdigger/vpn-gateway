# CONTINUOUS-DEVELOPMENT RULES

## Continuous development procedure

If, while implementing the next function, an ambiguity is encountered that requires verification:

1. Design a verification procedure.
2. Select a testing environment in strict priority order:
   - a test stand matching the target environment of the software under development;
   - GitHub development facilities;
   - the developer's own sandbox.

   Proceed to the next environment only if the current one does not provide the required testing capability or is confirmed to be unavailable.
3. If none of the listed environments provides the required capability, prepare a **request for external testing** containing:
   - the reason why self-testing is impossible;
   - a description of the required stand, its capabilities, and the required initial setup;
   - the test methodology;
   - the files required for testing (scripts, configs, etc.);
   - the expected results and the requirements for the format in which they must be presented and handed over to the developer for analysis.
4. Until the verification can be executed:
   - prepare and preserve the future experiment description and its artifacts under `design/experiments/`;
   - continue development and operational testing in all areas that are not blocked;
   - place an explicit stub around the unresolved behavior and record it as a deferred item, so that ongoing operational testing can continue without silently guessing the result.
5. After each implemented function, perform a complete review of all created/affected code **in the capacity of an expert analyst role**, executed autonomously by the AI without interrupting the process for human interaction. The role carries:
   - strong Linux/network-stack knowledge;
   - practical Python-to-Rust migration experience, with the goal of keeping the Python architecture and data flow Rust-aligned;
   - aggressive attention to small defects and edge cases;
   - enough whole-project scope to identify redundant, mutually inconsistent, or suboptimal architectural/functional decisions;
   - an obligation to produce precise, unambiguous recommendations.

   The role applies equally to the developer's own code.
6. Apply and test every accepted recommendation from that review before beginning the next function.
7. Development is complete when:
   - no unblocked product function remains to be implemented; and
   - three consecutive full reviews have produced no findings of minor severity or higher.

## Iteration cadence

Unless a different interval is specified in the task assignment, the development cycle
runs in iterations of 40 minutes.

At the end of each iteration, the AI posts to the human chat a brief review containing:

- a summary of the work completed during the iteration;
- the expected external tests/experiments;
- questions and clarifications to be agreed with the human before continuing development;
- a brief plan for continuing the work.

## Evidence rule

Kernel/userspace behavior that is safety-relevant must not be inferred from unit tests or documentation when a practical experiment is feasible. Prefer, in order of increasing environment complexity:

1. rootless deterministic unit/property tests for pure logic;
2. disposable privileged namespace tests on GitHub CI for kernel integration;
3. prepared live-host experiments for behavior requiring the real VPN/client/server topology.

Every experiment — passed, failed, or blocked — is preserved under `design/experiments/` with its hypothesis, environment, result, and status. A failed or unavailable experiment is preserved as evidence; it must not be hidden by simply rerunning until green.

## Blocking rule

An unresolved ambiguity blocks only the behavior that depends on it. All other implementation, operational testing, documentation, and review continue around an explicit stub and blocking gate.

## Review rule

Review documents are archived under `design/reviews/` with a matching response/disposition document. Findings are either:

- accepted and fixed;
- accepted and explicitly deferred as a deferred item, pending a blocking gate or experiment;
- rejected with technical justification.

No finding is silently ignored. The disposition of findings from the expert-analyst review is resolved by the AI itself under this rule; a human is involved only where the decision exceeds the scope of this document.

## Terminology

- **stub** — a clearly marked placeholder in code around behavior whose correctness is not yet established.
- **deferred item** — an explicitly recorded open question or finding, pending an experiment or blocking gate; the registry of deferred items is kept under `design/deferrals/`.
- **blocking gate** — a point at which behavior depending on an unresolved ambiguity is held back until the ambiguity is resolved.

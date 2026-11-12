# CONTINUOUS-DEVELOPMENT.md

## Continuous development procedure

If, while implementing the next function, an ambiguity is encountered that requires
verification:

1. Design a verification procedure.
2. Execute it in a sandbox or on GitHub when possible.
3. If it cannot be executed yet:
   - prepare and preserve the future experiment description and artifacts;
   - continue development and testing in all areas that are not blocked;
   - place an explicit stub/gate around the unresolved behavior so integrated testing can
     continue without silently guessing the result.
4. After each implemented function, perform a complete review of all created/affected code
   from the perspective of an external expert analyst with:
   - strong Linux/network-stack knowledge;
   - practical Python-to-Rust migration experience, with the goal of keeping Python
     architecture and data flow Rust-aligned;
   - aggressive attention to small defects and edge cases;
   - enough whole-project scope to identify redundant, mutually inconsistent, or
     suboptimal architectural/functional decisions;
   - an obligation to produce precise, unambiguous recommendations.
5. Apply and test every accepted recommendation from that review before beginning the next
   function.
6. Continue until:
   - no unblocked product function remains to be implemented; and
   - the external-expert review has no remaining recommendation for the implemented code.

## Evidence rule

Kernel/userspace behavior that is safety-relevant must not be inferred from unit tests or
documentation when a practical experiment is feasible. Prefer:

1. rootless deterministic unit/property tests for pure logic;
2. disposable privileged namespace tests on GitHub CI for kernel integration;
3. prepared live-host experiments for behavior requiring the real VPN/client/server
   topology.

A failed or unavailable experiment is preserved as evidence; it is not hidden by simply
rerunning until green.

## Blocking rule

An unresolved ambiguity blocks only the behavior that depends on it. Other implementation,
tests, documentation and review continue around an explicit gate.

## Review rule

Review documents are archived under `design/reviews/` with a matching response/disposition
document. Findings are either:

- accepted and fixed;
- accepted and explicitly deferred behind a gate/experiment;
- rejected with technical justification.

No finding is silently ignored.

## Backend direction

For NG1 production packet filtering, nftables is the target backend. Legacy
iptables-based materializers may remain as historical/regression evidence but must not
define new production semantics.

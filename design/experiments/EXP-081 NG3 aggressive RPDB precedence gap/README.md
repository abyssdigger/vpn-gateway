# EXP-081 — aggressive host-routing RPDB precedence gap

## Status

Research experiment for the re-entered `VPNG-U001-R5.R2` branch.

## Requirement traceability

- `VPNG-U001-R5.R2.R1` — authoritative managed-destination routing;
- `VPNG-U001-R5.R2.R2` — continuous observation/recovery;
- `VPNG-U001-R5.R2.R3` — fail-closed escalation when the guarantee cannot be restored.

## Question

Does the current EXP-074 / `NG3_HOST_MANAGED_ROUTING_LINUX_ALLOCATION` realization remain
authoritative when ordinary host policy contains a foreign RPDB rule with higher precedence
than the VPN-GATE dispatch rule?

The current accepted evidence proves that more-specific routes in host table `main` do not
override the managed table. It does not test a foreign policy rule that executes before the
VPN-GATE rule.

## Hypotheses

- **H1:** current aggressive desired state converges and is reported exact;
- **H2:** before foreign interference, route lookup for a managed destination selects the
  VPN-GATE boundary;
- **H3:** a foreign higher-precedence RPDB rule that looks up `main` can redirect the same
  managed destination away from VPN-GATE;
- **H4:** the current owner observation still reports its own state exact after that foreign
  rule is added, demonstrating that the current postcondition does not cover the full
  authoritative-routing promise.

## Interpretation

A PASS is a **negative architecture finding**, not product acceptance. It means EXP-074
remains valid evidence against competing `main` routes, but is insufficient to close the
broader requirement against competing ordinary host routing policy.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-081 NG3 aggressive RPDB precedence gap/exp081_aggressive_rpdb_precedence_gap.py"
```

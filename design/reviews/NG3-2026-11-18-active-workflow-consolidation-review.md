# NG3 2026-11-18 — active workflow consolidation review

## Verdict

**PASS for active-lineage workflow hygiene.**

## Finding

The active-lineage guard introduced with futuremain has always declared exactly two permitted
workflow files:

- `.github/workflows/actual-main-hygiene.yml`;
- `.github/workflows/ng3-python.yml`.

The active tree nevertheless still contained the older standalone
`.github/workflows/ng3-host-bootstrap.yml`. Consequently every normal branch push failed the
lineage guard even when the changed project content was otherwise clean.

## Coverage check before removal

The standalone host-bootstrap workflow covered:

- EXP-059 paired RPDB bootstrap;
- EXP-060 selected host-bootstrap backend.

The consolidated `ng3-python.yml` already contained a dedicated EXP-059 job and path trigger.
EXP-060 was the only evidence lane unique to the redundant workflow.

## Correction

The active workflow set is now reduced to the guard's intended pair.

Before removing the standalone workflow, `ng3-python.yml` gained:

- push and pull-request path triggers for
  `design/experiments/EXP-060 NG3 selected host bootstrap backend/**`;
- a dedicated `linux-selected-host-bootstrap-backend` job;
- Python 3.13 setup, compile check, Linux networking dependencies and the same EXP-060
  invocation/PYTHONPATH contract previously used by the standalone workflow.

EXP-059 remains in its existing dedicated consolidated job and is not duplicated.

## Verification

On branch head `5c572d3f8e2abe1e0bc9f3f4d8dc8a991d9e1a0a`:

- `Actual main lineage guard` run `44398497228`: **PASS**;
- the tracked workflow directory contains exactly
  `actual-main-hygiene.yml` and `ng3-python.yml`.

The consolidated NG3 workflow run `44398482888` confirms that:

- `unit`: **PASS**;
- the new EXP-060 job is discovered and executed.

EXP-060 itself still fails with the same pre-existing
`host bootstrap fresh postcondition does not match desired state` signature seen in the
historical standalone workflow run `44309370834`. The consolidation therefore neither
creates nor hides that evidence failure; it only moves the existing lane into the canonical
workflow.

The already-known EXP-057 and EXP-063 privileged failures also remain independent of this
workflow-hygiene change.

## Requirement-state inventory

This cleanup changes no product semantics and creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

The red EXP-060 evidence is pre-existing runtime/evidence work, not a new requirement-state
finding caused by this consolidation.

## Conclusion

The active lineage now satisfies its own workflow-set invariant without losing host-bootstrap
evidence coverage. EXP-060 remains visible in the canonical NG3 CI instead of surviving in a
third legacy workflow file.

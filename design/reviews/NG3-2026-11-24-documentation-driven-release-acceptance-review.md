# NG3 2026-11-24 — documentation-driven release acceptance review

**Scope:** refinement of the release methodology so published administrator/user documentation
must be proven operationally applicable before fulfillment review.

**Process owner:** `PROJECT-CONVENTIONS.md` §10.4  
**Reviewed head:** `6d73595095d487c77a2cdbb30d15807dc14e289a`

## Verdict

**PASS — the release methodology now distinguishes mechanism QA from proof that the published
administrator/user procedure is itself usable as the supported release path.**

## Findings and dispositions

### F1 — existing release QA could prove the same mechanisms without proving the documentation

**Decision:** accepted.  
**Resolution:** fixed.

The previous 0.1.0 QA installed the real release bundle and exercised real VPN integrations and
Protective mode. However, QA code could use project knowledge independently of the published
administrator procedure.

That is insufficient evidence that an administrator can actually deploy and operate the product
from the release documentation.

### F2 — documentation-driven acceptance must follow the published path without turning the document into a test script

**Decision:** accepted.  
**Resolution:** fixed.

The published document remains an administrator/user instruction, not a QA protocol.

QA derives a walkthrough from it and records for each covered section:

- documented administrator action;
- expected externally visible result;
- actual result;
- supported observation/diagnostic surface used to confirm the result.

Disposable peer/container/namespace setup may remain QA harness machinery when it merely creates
the external environment. Product-specific actions expected from an administrator may not be
silently replaced by undocumented QA-only knowledge.

### F3 — built-in diagnostics are part of applicability evidence

**Decision:** accepted.  
**Resolution:** fixed.

Where the documentation directs the administrator to VPN-GATE status/current-state diagnostics,
the walkthrough must use those diagnostics to confirm the visible result. Real payload is used in
addition when the documented property is dataplane behavior.

This proves both that the product behaves correctly and that the documented diagnostic route is
usable for operational confirmation.

### F4 — all release-supported documented integration paths must be traversed

**Decision:** accepted.  
**Resolution:** fixed.

For NG3 Release-1 the mandatory walkthrough includes:

- installation from the release bundle;
- release configuration;
- documented WireGuard integration;
- documented OpenConnect integration;
- documented L2TP integration;
- current-state/diagnostic verification for each integration;
- real payload for each integration;
- manual Protective-mode status/enter/status/leave/status;
- admin-visible confirmation of Protective-mode effect and release.

Lower-level unit/Linux integration evidence does not substitute for this walkthrough.

### F5 — negative/safety QA remains separate

**Decision:** accepted.

Fault injection, protective-gate deletion, failed leave, drift repair and other safety-negative
tests remain important release evidence but are additional to the successful documented
administrator path.

A release cannot claim documentation applicability merely because stronger internal fault tests
passed.

### F6 — documentation changes invalidate affected acceptance

**Decision:** accepted.  
**Resolution:** fixed.

Changes to release-published administrator/user documentation, installer, example configuration,
bundle contents or runtime behavior that can alter the documented operational path require the
affected documentation-driven walkthrough to be repeated.

## 0.1.0 consequence

The existing frozen-candidate fulfillment verdict is no longer sufficient as release-decision
evidence until 0.1.0 passes the newly required documentation-driven walkthrough.

The candidate is not declared defective by this process correction. The missing evidence is
whether the published procedure itself is proven operationally applicable end to end.

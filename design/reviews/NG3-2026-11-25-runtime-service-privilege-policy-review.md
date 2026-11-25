# NG3 runtime service privilege policy review — 2026-11-25

**Review unit:** release-runtime service account privilege minimization  
**Requirements:** `VPNG-M001-R5*`  
**Architecture:** cross-cutting runtime/deployment privilege boundary  
**Release scope:** `release/0.1.0/RELEASE-SCOPE.md`  
**Reviewed head:** `ebebc69b0e57f7f2d8ef0067bd3662b125e3cc77`

## Verdict

**PASS — runtime privilege minimization is now a maintenance/operational requirement with an explicit escalation hierarchy and a first-release-only omission.**

The requirement applies to the long-running service account, not to one-shot installation,
upgrade or administrative actions. It therefore does not prohibit normal administrator use of
`sudo` to install files, create units/namespaces or perform other bounded setup operations.

## Accepted hierarchy

The preferred runtime privilege order is:

```text
ordinary non-root/non-sudo service account
    -> restricted sudoer with finite explicit sudoers allowlist
    -> unrestricted sudoer
    -> direct root service
```

A broader tier is acceptable only when the applicable narrower tier is impossible or
materially impractical for required supported runtime behavior, and that escalation is
technically justified in reviewable architecture/deployment/release evidence.

## Findings and dispositions

### F1 — privilege policy must be scoped to runtime service execution

**Decision:** accepted.

`VPNG-M001-R5` explicitly applies to the long-running service runtime. One-shot
installation/upgrade/administrative operations are outside this privilege-minimization
hierarchy merely because they require elevated administrator access.

### F2 — restricted sudo must be preferred to generic sudo authority

**Decision:** accepted.

`VPNG-M001-R5.R1.R2` requires a finite explicit sudoers command/operation set whenever that
is practically sufficient. Merely choosing a non-root account while granting arbitrary sudo
does not satisfy the preferred restricted-sudo tier.

### F3 — privilege escalation requires explicit rationale

**Decision:** accepted.

`VPNG-M001-R5.R2` prevents root/unrestricted sudo from becoming implementation convenience:
each applicable narrower alternative that is not used needs explicit technical justification
sufficient for review of the chosen privilege boundary.

### F4 — non-root filesystem prerequisites must be administrator-visible

**Decision:** accepted.

When a supported runtime service uses a non-root account, `VPNG-M001-R5.R3` requires admin
documentation to identify the required files/directories and required access/ownership where
the installation procedure does not already make that access self-evident. This requirement
is part of the existing documentation-driven acceptance boundary.

### F5 — first release may omit the privilege-hardening implementation

**Decision:** accepted.

`VPNG-M001-R5.C1` makes this family non-mandatory for the first release only; it does not
become a standing exemption for later releases. The requirement text contains no
release-specific historical justification.

The approved 0.1.0 release scope explicitly exercises this allowed first-release omission, so
the newly introduced permanent requirement does not retroactively invalidate the already
prepared Release-1 candidate solely because its service privilege boundary has not been
reworked.

## Evidence

- Normative/architecture source: `0ec2b639d4de71644bc0ce020683ec92c3144b3b`.
- Release-scope alignment: `ebebc69b0e57f7f2d8ef0067bd3662b125e3cc77`.
- NG3 Python run `45570050367`, unit job `139054298419`: **PASS**.
- Actual-main lineage run `45570050385`: **PASS**.
- No runtime implementation or release bundle behavior was changed in this unit.

## Remaining implementation boundary

No Release-1 implementation work is required because `VPNG-M001-R5.C1` is exercised.
Before the first release scope that does not exercise this omission, the concrete service
unit/deployment model must receive architecture/evidence review for its chosen privilege tier,
including the exact restricted sudoers surface or root rationale where applicable and the
administrator-visible filesystem access contract for a non-root service account.

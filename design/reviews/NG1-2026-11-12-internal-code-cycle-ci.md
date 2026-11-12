# Internal review — code-cycle CI boundary

Date: 2026-11-12

Role: internal process/tooling review under `CONTINUOUS-DEVELOPMENT.md`.

## Scope

Reviewed whether the new GitHub-visible code-cycle workflow provides useful automatic
evidence without turning every micro-commit into an expensive privileged networking run.

## Finding F1 — code-cycle pushes had no automatic CI

Severity: medium process reliability.

The repository workflows originally listened only to main pushes and pull requests.
Code-cycle commits were externally visible on GitHub, but received no automatic test
feedback.

### Disposition

Accepted and fixed.

Both NG1 and RC3 rootless workflows now run on `code-cycle-*` pushes.

Observed on the current cycle branch:

- NG1 Python validation: SUCCESS;
- RC3 Python validation: SUCCESS.

## Finding F2 — privileged kernel integration must not run on every micro-commit

Severity: process efficiency.

The NG1 workflow combines fast rootless tests with a much heavier privileged job that
installs networking/VPN packages and runs the complete namespace/experiment suite.

Running that job for every small code-cycle commit would add cost/noise without adding
proportional evidence.

### Disposition

Resolved by workflow gating.

On code-cycle push:

- rootless NG1 job runs;
- kernel-integration job is SKIPPED.

On main push or pull request:

- privileged integration remains enabled.

The current code-cycle run confirms the expected skipped kernel job.

## Process documentation

`CONTINUOUS-DEVELOPMENT.md` now records the same distinction:

- every code-cycle push gets cheap rootless feedback;
- kernel-semantic review units and production acceptance require the privileged PR/main
  boundary;
- no PR is manufactured for each helper commit.

## Verdict

Approved. No remaining recommendation in this review unit.

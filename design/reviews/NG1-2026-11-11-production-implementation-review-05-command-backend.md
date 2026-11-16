# Production implementation review 05 — command backend and executor

Role: external expert review focused on process execution safety, observability, secret
handling, fail-closed mutation semantics and Rust migration shape.

## Scope

Reviewed `command_backend.py`, backend/executor tests and the previously approved
mutation-plan boundary.

## Findings

### F1 — generic command error text echoed full argv

The initial `CommandExecutionError` rendered the complete argv vector. That is harmless
for current route/sysctl commands but unsafe as a reusable production primitive because a
future caller might pass credentials or tokens in argv and the exception could be logged.

Severity: medium, security/maintenance.

Recommendation: retain argv structurally in `CommandResult` for controlled diagnostics,
but do not include the complete argv in the default exception string.

Disposition: fixed. The exception identifies only the executable and return code plus
stdout/stderr.

### F2 — exec/launch failures escaped the kernel apply error boundary

`subprocess.run()` may fail before a process exists (for example ENOENT). The first
executor version normalized non-zero exit status but not launch errors, so callers could
receive an unrelated `OSError` instead of the planner's apply-failure type.

Severity: medium, control-loop correctness.

Recommendation: normalize launch failures into a backend-specific exception and translate
both launch and exit-status failures to `KernelApplyError`.

Disposition: fixed with `BackendLaunchError` and regression coverage.

## Whole-scope review

- no shell invocation is used;
- namespace execution is an argv prefix, not string concatenation;
- execution order is preserved;
- execution stops at first failure;
- no rollback or forwarding reopen is attempted after partial apply;
- the pure plan and imperative executor remain separated.

## Rust-alignment review

`CommandBackend` is already trait-shaped. `CommandResult`, typed backend failures and
immutable argv tuples map cleanly to Rust process abstractions. Avoiding shell strings and
implicit exception classes reduces migration friction.

## Verdict

Approved after F1/F2 corrections. No remaining recommendation in this scope.

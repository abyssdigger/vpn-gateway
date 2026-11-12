# Production implementation review 11 — runtime state persistence

Role: external expert review focused on crash consistency, filesystem integrity, config
evolution and future Rust persistence.

## Scope

Reviewed `state_store.py`, state-store tests and Planner durable-commit requirements.

## Findings

### F1 — parent/file symlink handling was too permissive

The first hardening pass used `parent.stat()`, which follows a parent symlink, and
`Path.exists()`, which treats a dangling target symlink as absent. Runtime history
influences routing priorities and therefore must not silently traverse or ignore these
filesystem indirections.

Severity: medium, integrity.

Recommendation:

- use `lstat` on the parent and reject symlinked runtime directories;
- use `lexists` for the state path;
- reject symlinked/non-regular/wrong-owner/permissive existing state before read or replace.

Disposition: fixed with dedicated regression tests.

## Whole-scope review

- state format is versioned;
- corrupt/unknown-version state fails explicitly rather than becoming empty;
- writes are temp-file + fsync + atomic replace + directory fsync;
- file mode is 0600 and parent must be current-euid-owned/non-group-world-writable;
- candidate history and metrics are structurally revalidated against current ActiveConfig;
- policy-only changes retain compatible history;
- selector/layout changes discard only incompatible entries rather than all state;
- metric assignments outside the new layout are not trusted.

This is preferable to binding state validity to a hash of the whole TOML configuration:
irrelevant policy edits do not churn stable interface history.

## Rust-alignment review

The JSON schema is explicit, versioned and composed of primitive records. Validation is
separate from serialization and maps cleanly to serde plus typed validation in Rust.

## Verdict

Approved after F1 correction. No remaining recommendation in this scope.

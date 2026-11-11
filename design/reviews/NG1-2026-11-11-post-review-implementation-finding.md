# NG1 — post-review implementation finding: overlapping selector example

Date: **2026-11-11**

During the first rootless implementation test of the agreed configuration model, the
example:

```toml
expected_interfaces = [
    "vpns-main",
    "vpns*/3",
    "vpns-backup",
]
```

was correctly rejected by the selector-overlap validator.

This exposed a documentation-example defect, not an architecture defect: both exact names
begin with the `vpns` PREFIX selector and therefore violate the already normative rule
that ExpectedInterface selector namespaces are pairwise disjoint.

The examples in `rou-config.md` and the brainstorm brief were corrected to:

```toml
expected_interfaces = [
    "oc-main",
    "vpns*/3",
    "oc-backup",
]
```

No model semantics changed.

Implementation validation then passed all current rootless tests.

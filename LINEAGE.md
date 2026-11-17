# Repository lineage

This branch is the active VPN-GATE development line.

The repository was split on 2026-11-17 so the active `main` tree no longer carries
historical generation implementations and their CI.

Historical lines are preserved as branches:

| Branch | Preserved boundary |
| --- | --- |
| `legacy-main-rc` | RC2/RC3 line through the last pre-NG1 main commit |
| `legacy-main-ng1-2` | NG1/NG2 line through main snapshot 30/44, immediately before NG3 |
| `legacy-main-ng3` | former mixed `main` through NG3 snapshot 74 |

The active `main` contains only:

- current NG3 normative/design/runtime artifacts;
- shared generation-independent project models;
- NG3 experiments, reviews and deferrals;
- current project/process documents;
- current NG3 CI and the actual-main lineage guard.

Historical evidence may be cited by branch-qualified reference, for example:

```text
legacy-main-ng1-2:design/NG2/availability-routing-model.md
legacy-main-rc:design/RC3/architecture.md
```

Legacy files are not copied back into active `main` merely to make a historical relative
link resolve. If historical evidence becomes materially relevant to a new NG3 decision,
reference the preserved legacy branch/commit explicitly.

# NG2 cycle — payload/probing tail review

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-payload-probing-tail-review-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Base:** `e281330a424aaa830a01b5d432f2ab5ed6d00f40`

## Goal

Review payload-domain code and active architecture for leftovers from superseded designs
that made availability probing part of payload intent/runtime backbone.

No runtime assembly work starts until this review is complete.

Search targets:

- obsolete availability/probing fields in payload request/state contracts;
- stale calculators or intermediate projections;
- prefix/boundary state that belongs below payload semantics;
- probing-specific status semantics in payload state;
- duplicate ownership between PayloadTrafficManager and probe subsystem;
- dead hooks, methods, imports and tests left after the availability simplification;
- assumptions that probing is required rather than optional.

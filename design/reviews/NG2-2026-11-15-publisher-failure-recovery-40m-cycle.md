# NG2 cycle — publisher failure recovery

**Date:** 2026-11-15  
**Branch:** `code-cycle-20261115-publisher-failure-recovery-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**Base:** `9c3b9af38861804519a6313028a215e7f3fd49c4`

## First review unit

Recover the interrupted publisher-failure isolation work:

1. correct the single failing retry regression without weakening production guarantees;
2. rerun the complete automated gate;
3. review Agent publisher-failure isolation across tick, good-news fanout and diagnostics;
4. continue only with autonomous non-interactive review units if the recovered head is green.

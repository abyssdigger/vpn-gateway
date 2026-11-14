from __future__ import annotations

# Lower-domain identity for the dedicated availability-probe process.
#
# This is intentionally not part of NetworkRulesSpec. The semantic contract says only
# LOCAL_PROCESS; Linux chooses how to identify that process and how to carry admitted-flow
# identity into the reverse direction.
LOCAL_PROCESS_UID = 65534

# Conntrack mark used only inside the dedicated ROU namespace to carry a successfully
# admitted LOCAL_PROCESS OUTPUT flow into reverse INPUT matching.
LOCAL_PROCESS_CT_MARK = 0x24

"""Compatibility shim for the pre-Enforcer route-priority module name.

Current code imports :mod:`rou.route_priority_enforcer`. This module remains only so
older executable evidence or external test code can resolve the terminology transition
without changing behavior.
"""

from .route_priority_enforcer import (
    RoutePriorityBackend,
    RoutePriorityEnforcementResult,
    RoutePriorityEnforcementStatus,
    RoutePrioritySnapshot,
    converge_route_priority_once,
)

RoutePriorityExecutionResult = RoutePriorityEnforcementResult
RoutePriorityExecutionStatus = RoutePriorityEnforcementStatus

__all__ = [
    "RoutePriorityBackend",
    "RoutePriorityEnforcementResult",
    "RoutePriorityEnforcementStatus",
    "RoutePriorityExecutionResult",
    "RoutePriorityExecutionStatus",
    "RoutePrioritySnapshot",
    "converge_route_priority_once",
]

from __future__ import annotations

class GatewayError(Exception):
    """Base class for expected daemon/domain errors."""


class ConfigError(GatewayError):
    """Runtime configuration cannot be projected safely."""


class InstanceLockError(GatewayError):
    """Lifetime lock could not be acquired safely."""


class CleanupError(GatewayError):
    """Marker-based cleanup could not be completed and verified."""


class PlanValidationError(GatewayError):
    """A route plan violates architecture invariants."""


class ReconciliationError(GatewayError):
    """A reconciliation pass violated its completion/result contract."""


class FirewallInspectionError(GatewayError):
    """Expected firewall snapshot parse/normalization/comparison failure."""


class KernelError(GatewayError):

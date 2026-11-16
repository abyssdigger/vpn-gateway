"""VPN-GATE NG3 Python reference slice."""

from .availability_priority import (
    AvailabilityPriorityError,
    calculate_effective_path_order,
)
from .availability_confirmation import (
    AvailabilityConfirmationState,
    AvailabilityOutcome,
    apply_availability_evidence,
)
from .binding import (
    BindingProjectionError,
    DeviceBindingProjection,
    DeviceBindingState,
    LogicalPathId,
    PathBinding,
    SelectorBindingState,
    WaitingCandidate,
    project_device_bindings,
)
from .config import ConfigError, parse_structural_config
from .domain import (
    DeviceBindingIntent,
    DeviceStructuralIntent,
    Direction,
    ExpectedInterfaceSelector,
    ProfileStructuralIntent,
    SelectorKind,
    StructuralConfig,
)
from .interface_identity import InterfaceIdentity
from .interface_inventory import (
    InterfaceInventoryError,
    parse_ip_link_inventory,
)
from .forwarding_gate import (
    ForwardingGateExecutionResult,
    ForwardingGateExecutionStatus,
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .linux_forwarding_gate import (
    LinuxForwardingGateBackend,
    LinuxForwardingGateError,
)
from .nft_namespace_inventory import (
    NG3_NFT_FAMILY,
    NG3_NFT_OWNER_COMMENT,
    NG3_NFT_TABLE,
    LinuxNftNamespaceBackend,
    NftNamespaceInventoryError,
    NftNamespaceObject,
    NftNamespaceObservation,
    NftNamespaceStatus,
    parse_nft_namespace_ruleset,
)
from .nft_payload_scaffold import (
    PAYLOAD_FORWARD_CHAIN,
    PAYLOAD_FORWARD_COMMENT,
    PAYLOAD_NFT_SCAFFOLD,
    PAYLOAD_POSTROUTING_CHAIN,
    PAYLOAD_POSTROUTING_COMMENT,
    NftBaseChainSpec,
    NftPayloadScaffoldComparison,
    NftPayloadScaffoldConflict,
    NftPayloadScaffoldError,
    compare_payload_nft_scaffold,
)
from .nft_scaffold_executor import (
    PayloadNftScaffoldPrepareResult,
    PayloadNftScaffoldPrepareStatus,
    prepare_payload_nft_scaffold_once,
)
from .linux_nft_scaffold import (
    LinuxNftScaffoldBackend,
    SubprocessNftRunner,
)
from .direct_device_route import (
    DirectDeviceRouteRealizationError,
    realize_direct_device_path_routes,
)
from .device_policy import (
    DeviceNatPolicyIntent,
    NatIntent,
)
from .payload_nat_desired import (
    PayloadMasqueradeSpec,
    PayloadNatDesiredState,
    PayloadNatProjectionError,
    build_payload_nat_desired_state,
)
from .payload_nat_observation import (
    PAYLOAD_NAT_RULE_COMMENT,
    ObservedPayloadMasquerade,
    PayloadNatComparison,
    PayloadNatObservationError,
    PayloadNatRuleConflict,
    compare_payload_nat,
)
from .payload_forward_observation import (
    PAYLOAD_FORWARD_NEW_COMMENT,
    PAYLOAD_FORWARD_RETURN_COMMENT,
    ObservedPayloadForwardRule,
    PayloadForwardObservation,
    PayloadForwardObservationError,
    PayloadForwardRemoteField,
    PayloadForwardRuleConflict,
    PayloadForwardRuleKind,
    observe_payload_forward,
)
from .payload_forward_desired import (
    PayloadForwardDesiredError,
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from .payload_forward_compare import (
    PayloadForwardComparison,
    PayloadForwardComparisonError,
    compare_payload_forward,
)
from .payload_nat_mutation import (
    PayloadNatMutationResult,
    PayloadNatMutationStatus,
    PayloadNatPhysicalSnapshot,
    converge_payload_nat_step_once,
)
from .linux_payload_nat import LinuxPayloadNatBackend
from .payload_profile import (
    PayloadProfileProjectionError,
    PayloadProfileRequest,
    build_payload_profile_requests,
)
from .payload_routing_desired import (
    ManagedRouteSpec,
    ManagedRouteType,
    ManagedRuleSpec,
    PayloadRoutingDesiredState,
    PayloadRoutingProjectionError,
    build_payload_routing_desired_state,
)
from .structural_routing_inventory import (
    ObservedManagedRoute,
    ObservedManagedRule,
    ReservedOwnerKind,
    ReservedPolicyConflict,
    StructuralRoutingInventoryError,
    StructuralRoutingObservation,
    parse_structural_routing_inventory,
)
from .payload_routing_compare import (
    PayloadRoutingComparison,
    PayloadRoutingComparisonError,
    compare_payload_routing,
)
from .network_policy_layout import (
    NetworkPolicyLayout,
    NetworkPolicyLayoutError,
    NetworkPolicyPlatformSpace,
    NumericResourcePool,
    PayloadDispatchRule,
    PayloadPolicyAllocation,
    ProbePolicyAllocation,
    ProbePolicyOwner,
    ProbeRoutingDemand,
    RouteMetricPlatformSpace,
    allocate_network_policy_layout,
)
from .linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from .profile_classification import (
    ProfileClassificationError,
    classify_inbound_profile,
    classify_outbound_profile,
)
from .route_priority import (
    RoutePriorityMove,
    RoutePriorityPlanError,
    plan_route_priority_moves,
)
from .route_priority_convergence import (
    RoutePriorityConvergenceError,
    RoutePriorityDeleteDuplicate,
    plan_route_priority_convergence,
)
from .route_priority_executor import (
    RoutePriorityExecutionResult,
    RoutePriorityExecutionStatus,
    RoutePrioritySnapshot,
    converge_route_priority_once,
)
from .route_priority_inventory import (
    RoutePriorityInventoryError,
    RoutePriorityPathRoute,
    parse_ip_route_priority_snapshot,
)
from .iproute_priority_backend import (
    IproutePriorityBackend,
    IproutePriorityBackendError,
    SubprocessCommandRunner,
)
from .route_priority_profile import (
    RoutePriorityDomainId,
    RoutePriorityDomainOutcome,
    RoutePriorityDomainRequest,
    RoutePriorityProfileResult,
    RoutePriorityProfileStatus,
    converge_route_priority_profile_once,
)
from .route_priority_realization import (
    RoutePriorityDomainRealization,
    RoutePriorityMetricSpace,
    RoutePriorityRealizationError,
)
from .route_priority_domain_builder import (
    RoutePriorityDomainBuildError,
    build_route_priority_domain_realizations,
)

__all__ = [
    "AvailabilityConfirmationState",
    "AvailabilityOutcome",
    "AvailabilityPriorityError",
    "BindingProjectionError",
    "ConfigError",
    "DeviceBindingIntent",
    "DeviceBindingProjection",
    "DeviceBindingState",
    "DeviceStructuralIntent",
    "DeviceNatPolicyIntent",
    "DirectDeviceRouteRealizationError",
    "Direction",
    "ExpectedInterfaceSelector",
    "ForwardingGateExecutionResult",
    "ForwardingGateExecutionStatus",
    "ForwardingGateState",
    "InterfaceIdentity",
    "InterfaceInventoryError",
    "IproutePriorityBackend",
    "IproutePriorityBackendError",
    "LinuxForwardingGateBackend",
    "LinuxForwardingGateError",
    "LogicalPathId",
    "ManagedRouteSpec",
    "ManagedRouteType",
    "ManagedRuleSpec",
    "NG3_NFT_FAMILY",
    "NG3_NFT_OWNER_COMMENT",
    "NG3_NFT_TABLE",
    "NftBaseChainSpec",
    "LinuxNftNamespaceBackend",
    "LinuxNftScaffoldBackend",
    "NatIntent",
    "NetworkPolicyLayout",
    "NetworkPolicyLayoutError",
    "NetworkPolicyPlatformSpace",
    "ObservedManagedRoute",
    "ObservedManagedRule",
    "NG3_LINUX_POLICY_PLATFORM",
    "NftNamespaceInventoryError",
    "NftPayloadScaffoldComparison",
    "NftPayloadScaffoldConflict",
    "NftPayloadScaffoldError",
    "NftNamespaceObject",
    "NftNamespaceObservation",
    "NftNamespaceStatus",
    "NumericResourcePool",
    "PAYLOAD_NAT_RULE_COMMENT",
    "PAYLOAD_FORWARD_NEW_COMMENT",
    "PAYLOAD_FORWARD_RETURN_COMMENT",
    "ObservedPayloadForwardRule",
    "PayloadForwardObservation",
    "PayloadForwardObservationError",
    "PayloadForwardRemoteField",
    "PayloadForwardRuleConflict",
    "PayloadForwardRuleKind",
    "PayloadForwardDesiredError",
    "PayloadForwardDesiredState",
    "PayloadForwardRuleSpec",
    "PayloadForwardComparison",
    "PayloadForwardComparisonError",
    "ObservedPayloadMasquerade",
    "PayloadNatComparison",
    "PayloadNatObservationError",
    "PayloadNatRuleConflict",
    "PayloadNatMutationResult",
    "PayloadNatMutationStatus",
    "PayloadNatPhysicalSnapshot",
    "LinuxPayloadNatBackend",
    "compare_payload_nat",
    "observe_payload_forward",
    "compare_payload_forward",
    "converge_payload_nat_step_once",
    "PAYLOAD_FORWARD_CHAIN",
    "PAYLOAD_FORWARD_COMMENT",
    "PAYLOAD_NFT_SCAFFOLD",
    "PAYLOAD_POSTROUTING_CHAIN",
    "PAYLOAD_POSTROUTING_COMMENT",
    "PathBinding",
    "PayloadDispatchRule",
    "PayloadNftScaffoldPrepareResult",
    "PayloadNftScaffoldPrepareStatus",
    "PayloadMasqueradeSpec",
    "PayloadNatDesiredState",
    "PayloadNatProjectionError",
    "PayloadPolicyAllocation",
    "PayloadProfileProjectionError",
    "PayloadProfileRequest",
    "PayloadRoutingComparison",
    "PayloadRoutingComparisonError",
    "PayloadRoutingDesiredState",
    "PayloadRoutingProjectionError",
    "ProbePolicyAllocation",
    "ProbePolicyOwner",
    "ProbeRoutingDemand",
    "ProfileClassificationError",
    "ProfileStructuralIntent",
    "ReservedOwnerKind",
    "ReservedPolicyConflict",
    "RouteMetricPlatformSpace",
    "RoutePriorityConvergenceError",
    "RoutePriorityDeleteDuplicate",
    "RoutePriorityDomainBuildError",
    "RoutePriorityDomainId",
    "RoutePriorityDomainOutcome",
    "RoutePriorityDomainRequest",
    "RoutePriorityDomainRealization",
    "RoutePriorityExecutionResult",
    "RoutePriorityExecutionStatus",
    "RoutePriorityInventoryError",
    "RoutePriorityMetricSpace",
    "RoutePriorityPathRoute",
    "RoutePrioritySnapshot",
    "RoutePriorityMove",
    "RoutePriorityPlanError",
    "RoutePriorityProfileResult",
    "RoutePriorityProfileStatus",
    "RoutePriorityRealizationError",
    "SelectorBindingState",
    "SelectorKind",
    "StructuralConfig",
    "StructuralRoutingInventoryError",
    "StructuralRoutingObservation",
    "SubprocessCommandRunner",
    "SubprocessNftRunner",
    "WaitingCandidate",
    "allocate_network_policy_layout",
    "apply_availability_evidence",
    "calculate_effective_path_order",
    "build_payload_nat_desired_state",
    "build_payload_profile_requests",
    "build_payload_routing_desired_state",
    "build_route_priority_domain_realizations",
    "classify_inbound_profile",
    "compare_payload_nft_scaffold",
    "compare_payload_routing",
    "converge_forwarding_gate_once",
    "classify_outbound_profile",
    "converge_route_priority_once",
    "converge_route_priority_profile_once",
    "parse_ip_link_inventory",
    "parse_nft_namespace_ruleset",
    "parse_ip_route_priority_snapshot",
    "parse_structural_routing_inventory",
    "plan_route_priority_convergence",
    "plan_route_priority_moves",
    "parse_structural_config",
    "prepare_payload_nft_scaffold_once",
    "project_device_bindings",
    "realize_direct_device_path_routes",
]

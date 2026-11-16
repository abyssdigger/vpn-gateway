"""Pure semantic compiler for Profile payload_forward permission.

This compiler realizes the accepted most-specific Profile selection into
disjoint positive NEW/RETURN rules under the default-drop payload_forward
chain. Device firewall and NAT semantics remain separate owner layers.
"""

from __future__ import annotations

from typing import Iterable

from .binding import LogicalPathId
from .interface_identity import InterfaceIdentity
from .payload_forward_desired import (
    PayloadForwardDesiredState,
    PayloadForwardRuleSpec,
)
from .payload_forward_observation import (
    PayloadForwardRemoteField,
    PayloadForwardRuleKind,
)
from .payload_profile import PayloadProfileRequest
from .profile_prefix_partition import (
    ProfilePrefixPartitionError,
    build_inbound_profile_partition,
    build_outbound_profile_partition,
)
from .route_priority_inventory import RoutePriorityPathRoute


class PayloadForwardCompileError(ValueError):
    pass


def compile_payload_forward_policy(
    profiles: Iterable[PayloadProfileRequest],
    path_routes: Iterable[RoutePriorityPathRoute],
    host_boundary: InterfaceIdentity,
) -> PayloadForwardDesiredState:
    """Compile semantic Profile permission to exact disjoint lower rules.

    OUTBOUND/BIDIRECTIONAL:
      host -> selected Profile path:
          NEW, daddr fragment
      selected Profile path -> host:
          RETURN, saddr fragment

    INBOUND/BIDIRECTIONAL, evaluated independently per current ingress path:
      selected ingress path -> host:
          NEW, saddr fragment
      host -> selected ingress path:
          RETURN, daddr fragment

    Zero-path Profiles generate no positive rules and therefore remain
    fail-closed under the payload_forward base-chain policy DROP.
    """
    if not isinstance(host_boundary, InterfaceIdentity):
        raise PayloadForwardCompileError(
            "host_boundary must be InterfaceIdentity"
        )

    current_profiles = tuple(profiles)
    profile_by_id: dict[str, PayloadProfileRequest] = {}
    required_paths: set[LogicalPathId] = set()
    for profile in current_profiles:
        if not isinstance(profile, PayloadProfileRequest):
            raise PayloadForwardCompileError(
                "profiles must contain PayloadProfileRequest"
            )
        if profile.profile_id in profile_by_id:
            raise PayloadForwardCompileError(
                f"duplicate Profile request {profile.profile_id!r}"
            )
        profile_by_id[profile.profile_id] = profile

        if len(set(profile.ordered_paths)) != len(profile.ordered_paths):
            raise PayloadForwardCompileError(
                f"Profile {profile.profile_id!r} repeats a logical path"
            )
        required_paths.update(profile.ordered_paths)

    route_by_path: dict[LogicalPathId, RoutePriorityPathRoute] = {}
    endpoint_owner: dict[InterfaceIdentity, LogicalPathId] = {}
    for route in path_routes:
        if not isinstance(route, RoutePriorityPathRoute):
            raise PayloadForwardCompileError(
                "path_routes must contain RoutePriorityPathRoute"
            )
        if route.path_id in route_by_path:
            raise PayloadForwardCompileError(
                f"duplicate route realization for {route.path_id!r}"
            )
        if route.endpoint == host_boundary:
            raise PayloadForwardCompileError(
                "host boundary cannot also be a payload VPN path endpoint"
            )
        previous = endpoint_owner.get(route.endpoint)
        if previous is not None and previous != route.path_id:
            raise PayloadForwardCompileError(
                "one current endpoint cannot realize multiple logical paths"
            )
        route_by_path[route.path_id] = route
        endpoint_owner[route.endpoint] = route.path_id

    if set(route_by_path) != required_paths:
        raise PayloadForwardCompileError(
            "physical path-route set does not exactly match current semantic payload paths"
        )

    rules: set[PayloadForwardRuleSpec] = set()

    try:
        outbound = build_outbound_profile_partition(current_profiles)
    except ProfilePrefixPartitionError as exc:
        raise PayloadForwardCompileError(str(exc)) from exc

    for fragment in outbound:
        profile = profile_by_id[fragment.profile_id]
        for path_id in profile.ordered_paths:
            endpoint = route_by_path[path_id].endpoint
            rules.add(
                PayloadForwardRuleSpec(
                    kind=PayloadForwardRuleKind.NEW,
                    ingress=host_boundary,
                    egress=endpoint,
                    remote_field=PayloadForwardRemoteField.DESTINATION,
                    remote_prefix=fragment.remote_prefix,
                )
            )
            rules.add(
                PayloadForwardRuleSpec(
                    kind=PayloadForwardRuleKind.RETURN,
                    ingress=endpoint,
                    egress=host_boundary,
                    remote_field=PayloadForwardRemoteField.SOURCE,
                    remote_prefix=fragment.remote_prefix,
                )
            )

    for path_id in sorted(required_paths):
        try:
            inbound = build_inbound_profile_partition(
                current_profiles,
                path_id,
            )
        except ProfilePrefixPartitionError as exc:
            raise PayloadForwardCompileError(str(exc)) from exc

        endpoint = route_by_path[path_id].endpoint
        for fragment in inbound:
            rules.add(
                PayloadForwardRuleSpec(
                    kind=PayloadForwardRuleKind.NEW,
                    ingress=endpoint,
                    egress=host_boundary,
                    remote_field=PayloadForwardRemoteField.SOURCE,
                    remote_prefix=fragment.remote_prefix,
                )
            )
            rules.add(
                PayloadForwardRuleSpec(
                    kind=PayloadForwardRuleKind.RETURN,
                    ingress=host_boundary,
                    egress=endpoint,
                    remote_field=PayloadForwardRemoteField.DESTINATION,
                    remote_prefix=fragment.remote_prefix,
                )
            )

    return PayloadForwardDesiredState(tuple(rules))

from __future__ import annotations

from dataclasses import dataclass

from .availability_routing import calculate_effective_path_order
from .availability_probe_state import (
    AvailabilityProbeState,
    AvailabilityProbeStateInfo,
)
from .interface_identity import InterfaceIdentity
from .probe_rules import AvailabilityProbeSetRequest
from .payload_rules import (
    PayloadProfileRequest,
    PayloadTrafficStateRequest,
)


@dataclass(frozen=True)
class ProfileAvailabilityEvidence:
    """Routing-relevant availability evidence for one Profile.

    confirmed_live=None means availability-derived routing preference is inactive
    for the Profile. An empty frozenset means it is active but no path currently
    has positive evidence.
    """

    profile_name: str
    confirmed_live: frozenset[InterfaceIdentity] | None

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("availability evidence requires profile_name")
        if self.confirmed_live is not None:
            if not isinstance(self.confirmed_live, frozenset):
                raise ValueError("confirmed_live must be frozenset or None")
            if any(
                not isinstance(path, InterfaceIdentity)
                for path in self.confirmed_live
            ):
                raise ValueError(
                    "confirmed_live must contain InterfaceIdentity values"
                )


@dataclass(frozen=True)
class ProfileProbeAssignment:
    """Runtime-derived association between one Profile and logical probes."""

    profile_name: str
    probe_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("probe assignment requires profile_name")
        if len(set(self.probe_ids)) != len(self.probe_ids):
            raise ValueError("probe assignment contains duplicate probe_id")
        if any(not probe_id for probe_id in self.probe_ids):
            raise ValueError("probe assignment requires non-empty probe_id")


class ProbeProfileEvidenceCalculator:
    """Project logical probe states into routing evidence per Profile."""

    def calculate(
        self,
        probe_request: AvailabilityProbeSetRequest,
        probe_states: tuple[AvailabilityProbeStateInfo, ...],
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> tuple[ProfileAvailabilityEvidence, ...]:
        probes_by_id = {
            probe.probe_id: probe
            for probe in probe_request.probes
        }
        states_by_id = {
            info.probe_id: info
            for info in probe_states
        }
        if len(states_by_id) != len(probe_states):
            raise ValueError("duplicate probe state for probe_id")

        profile_names = [item.profile_name for item in assignments]
        if len(set(profile_names)) != len(profile_names):
            raise ValueError("duplicate Profile probe assignment")

        result = []
        for assignment in assignments:
            missing = [
                probe_id
                for probe_id in assignment.probe_ids
                if probe_id not in probes_by_id
            ]
            if missing:
                raise ValueError(
                    f"Profile {assignment.profile_name!r} references "
                    "unknown probe_id: "
                    + ", ".join(sorted(missing))
                )

            enabled = [
                probes_by_id[probe_id]
                for probe_id in assignment.probe_ids
                if probes_by_id[probe_id].enabled
            ]

            if not enabled:
                result.append(
                    ProfileAvailabilityEvidence(
                        assignment.profile_name,
                        None,
                    )
                )
                continue

            confirmed_live = frozenset(
                probe.path
                for probe in enabled
                if (
                    states_by_id.get(probe.probe_id) is not None
                    and states_by_id[probe.probe_id].state
                    is AvailabilityProbeState.REACHABLE
                )
            )
            result.append(
                ProfileAvailabilityEvidence(
                    assignment.profile_name,
                    confirmed_live,
                )
            )

        return tuple(result)


class PayloadTrafficIntentCalculator:
    """Derive effective payload path order from explicit runtime state.

    The Calculator is externally stateless. RuntimeStateManager owns the previous
    configured/effective snapshots and passes them back explicitly.
    """

    def calculate(
        self,
        configured: PayloadTrafficStateRequest,
        *,
        previous_configured: PayloadTrafficStateRequest | None,
        current_effective: PayloadTrafficStateRequest | None,
        availability: tuple[ProfileAvailabilityEvidence, ...],
    ) -> PayloadTrafficStateRequest:
        evidence_by_name = {
            item.profile_name: item.confirmed_live
            for item in availability
        }
        if len(evidence_by_name) != len(availability):
            raise ValueError("duplicate Profile availability evidence")

        configured_by_name = {
            item.name: item
            for item in configured.profiles
        }
        unknown_evidence = set(evidence_by_name) - set(configured_by_name)
        if unknown_evidence:
            raise ValueError(
                "availability evidence references unknown Profile: "
                + ", ".join(sorted(unknown_evidence))
            )

        previous_by_name = (
            {}
            if previous_configured is None
            else {
                item.name: item
                for item in previous_configured.profiles
            }
        )
        current_by_name = (
            {}
            if current_effective is None
            else {
                item.name: item
                for item in current_effective.profiles
            }
        )

        effective_profiles = tuple(
            self._calculate_profile(
                profile,
                previous_by_name.get(profile.name),
                current_by_name.get(profile.name),
                evidence_by_name.get(profile.name),
            )
            for profile in configured.profiles
        )
        return PayloadTrafficStateRequest(effective_profiles)

    def _calculate_profile(
        self,
        configured: PayloadProfileRequest,
        previous_configured: PayloadProfileRequest | None,
        current_effective: PayloadProfileRequest | None,
        confirmed_live: frozenset[InterfaceIdentity] | None,
    ) -> PayloadProfileRequest:
        configured_paths = {
            path.identity: path
            for path in configured.ordered_paths
        }
        configured_order = tuple(configured_paths)

        current_matches_configured_shape = (
            current_effective is not None
            and current_effective.name == configured.name
            and current_effective.direction is configured.direction
            and current_effective.destinations == configured.destinations
            and {
                path.identity: path
                for path in current_effective.ordered_paths
            }
            == configured_paths
        )

        rebase = (
            previous_configured is None
            or previous_configured != configured
            or not current_matches_configured_shape
        )

        if rebase:
            current_order = configured_order
        else:
            assert current_effective is not None
            current_order = tuple(
                path.identity
                for path in current_effective.ordered_paths
            )

        if confirmed_live is None:
            effective_order = configured_order
            live_prefix_length = None
        else:
            if not confirmed_live <= set(configured_order):
                raise ValueError(
                    f"Profile {configured.name!r} availability evidence "
                    "contains non-eligible path"
                )
            effective_order = calculate_effective_path_order(
                configured_order,
                current_order,
                confirmed_live,
            )
            live_prefix_length = len(confirmed_live)

        return PayloadProfileRequest(
            name=configured.name,
            direction=configured.direction,
            destinations=configured.destinations,
            ordered_paths=tuple(
                configured_paths[identity]
                for identity in effective_order
            ),
            confirmed_live_prefix_length=live_prefix_length,
        )

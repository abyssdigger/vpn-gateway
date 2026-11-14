from __future__ import annotations

from typing import Protocol

from .linux_driver import LinuxDriverResult, LinuxNetworkVerification
from .interface_identity import InterfaceIdentity
from .linux_network import (
    LinuxNetworkDesired,
    compile_linux_network_desired,
    project_network_rules_to_interfaces,
)
from .linux_routing import LinuxRoutingAllocationState
from .network_rules import (
    ActionResult,
    NetworkRulesSpec,
    NetworkRulesState,
    StateKnowledge,
)
from .network_rules_composition import (
    OwnerRulesRegistry,
    OwnerToken,
    compose_network_rules,
)


class LinuxNetworkBackend(Protocol):
    def observe_interfaces(self) -> tuple[InterfaceIdentity, ...]:
        ...

    def materialize_structural(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxDriverResult:
        ...

    def verify_current(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxNetworkVerification:
        ...


class LinuxNetworkRulesAdapter:
    """Direct NetworkRulesAdapter over one shared dedicated Linux network domain."""

    def __init__(
        self,
        backend: LinuxNetworkBackend,
        *,
        local_interface: str,
    ) -> None:
        self._backend = backend
        self._local_interface = local_interface
        self._owners = OwnerRulesRegistry()
        self._routing_allocation = LinuxRoutingAllocationState()
        self._last_state: dict[OwnerToken, NetworkRulesState] = {}

    def apply(
        self,
        owner: object,
        spec: NetworkRulesSpec,
    ) -> ActionResult:
        token, candidate = self._owners.preview_replace(owner, spec)

        try:
            projected = self._project(candidate)
            projected_requested = self._rules_for_token(
                projected,
                token,
            )
        except Exception as exc:
            return ActionResult(
                False,
                f"cannot project candidate network rules: {exc}",
            )

        if projected_requested != spec:
            diagnostic = (
                "requested owner rules reference an unavailable concrete "
                "interface generation"
            )
            return self._reconcile_committed_after_rejected_candidate(
                token,
                diagnostic,
            )

        try:
            desired = compile_linux_network_desired(
                projected,
                self._routing_allocation,
                local_interface=self._local_interface,
            )
        except Exception as exc:
            return ActionResult(
                False,
                f"cannot compile candidate network rules: {exc}",
            )

        result = self._backend.materialize_structural(desired)
        if not result.success:
            self._mark_all_unknown(result.diagnostic)
            self._last_state[token] = self._unknown_state(result.diagnostic)
            return ActionResult(False, result.diagnostic)

        self._owners.replace(owner, spec)
        self._routing_allocation = desired.routing.allocation
        self._mark_states_from_projection(projected)
        return ActionResult(True)

    def renew_state(self, owner: object) -> ActionResult:
        token = self._owners.token(owner)
        if token is None:
            return ActionResult(False, "owner is not registered")

        try:
            projected = self._project(self._owners.snapshot())
            desired = compile_linux_network_desired(
                projected,
                self._routing_allocation,
                local_interface=self._local_interface,
            )
            verification = self._backend.verify_current(desired)
        except Exception as exc:
            diagnostic = f"network observation failed: {exc}"
            self._mark_all_unknown(diagnostic)
            return ActionResult(False, diagnostic)

        if not verification.ok:
            diagnostic = "; ".join(verification.errors)
            self._mark_all_unknown(diagnostic)
            return ActionResult(False, diagnostic)

        self._mark_states_from_projection(projected)
        return ActionResult(True)

    def get_last_state(self, owner: object) -> NetworkRulesState:
        token = self._owners.token(owner)
        if token is None:
            return self._unknown_state("owner is not registered")
        return self._last_state.get(
            token,
            self._unknown_state("owner has not been freshly observed"),
        )

    def cleanup(self, owner: object) -> ActionResult:
        if not self._owners.has_identity(owner):
            return ActionResult(True)

        candidate = self._owners.preview_remove(owner)

        try:
            projected = self._project(candidate)
            desired = compile_linux_network_desired(
                projected,
                self._routing_allocation,
                local_interface=self._local_interface,
            )
        except Exception as exc:
            return ActionResult(
                False,
                f"cannot compile cleanup network rules: {exc}",
            )

        result = self._backend.materialize_structural(desired)
        if not result.success:
            self._mark_all_unknown(result.diagnostic)
            return ActionResult(False, result.diagnostic)

        token = self._owners.token(owner)
        self._owners.remove(owner)
        if token is not None:
            self._last_state.pop(token, None)
        self._routing_allocation = desired.routing.allocation
        self._mark_states_from_projection(projected)
        return ActionResult(True)

    def _reconcile_committed_after_rejected_candidate(
        self,
        requested_token: OwnerToken,
        diagnostic: str,
    ) -> ActionResult:
        try:
            projected = self._project(self._owners.snapshot())
            desired = compile_linux_network_desired(
                projected,
                self._routing_allocation,
                local_interface=self._local_interface,
            )
        except Exception as exc:
            combined = diagnostic + f"; committed reconcile compile failed: {exc}"
            self._mark_all_unknown(combined)
            self._last_state[requested_token] = self._unknown_state(combined)
            return ActionResult(False, combined)

        result = self._backend.materialize_structural(desired)
        if not result.success:
            combined = diagnostic
            if result.diagnostic:
                combined += f"; committed reconcile failed: {result.diagnostic}"
            self._mark_all_unknown(combined)
            self._last_state[requested_token] = self._unknown_state(combined)
            return ActionResult(False, combined)

        self._routing_allocation = desired.routing.allocation
        self._mark_states_from_projection(projected)
        if requested_token not in self._last_state:
            self._last_state[requested_token] = NetworkRulesState(
                knowledge=StateKnowledge.KNOWN,
                rules=NetworkRulesSpec(),
                fresh=True,
                diagnostic=diagnostic,
            )
        return ActionResult(False, diagnostic)

    def _project(self, owners):
        interfaces = self._backend.observe_interfaces()
        return project_network_rules_to_interfaces(
            compose_network_rules(owners),
            interfaces,
        )

    @staticmethod
    def _rules_for_token(projected, token: OwnerToken) -> NetworkRulesSpec:
        for owned in projected.owners:
            if owned.owner == token:
                return owned.rules
        return NetworkRulesSpec()

    def _mark_states_from_projection(self, projected) -> None:
        empty = NetworkRulesSpec()
        projected_by_token = {
            owned.owner: owned.rules
            for owned in projected.owners
        }
        live_tokens: set[OwnerToken] = set()

        for token, _committed in self._owners.registered_rules():
            live_tokens.add(token)
            self._last_state[token] = NetworkRulesState(
                knowledge=StateKnowledge.KNOWN,
                rules=projected_by_token.get(token, empty),
                fresh=True,
            )

        self._last_state = {
            token: state
            for token, state in self._last_state.items()
            if token in live_tokens
        }

    def _mark_all_unknown(self, diagnostic: str | None) -> None:
        for token, _rules in self._owners.registered_rules():
            self._last_state[token] = self._unknown_state(diagnostic)

    @staticmethod
    def _unknown_state(diagnostic: str | None) -> NetworkRulesState:
        return NetworkRulesState(
            knowledge=StateKnowledge.UNKNOWN,
            rules=None,
            fresh=False,
            diagnostic=diagnostic,
        )

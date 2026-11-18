"""Bounded route/RPDB convergence phases for the NG3 ordinary-host boundary."""

from __future__ import annotations

from dataclasses import dataclass

from .host_underlay_route import HostUnderlayPin
from .linux_host_boundary_policy import HostBoundaryLinuxDesired
from .linux_host_boundary_routes import LinuxHostBoundaryRouteBackend


class HostBoundaryRouteConvergenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostBoundaryRoutePhaseResult:
    mutation_attempted: bool
    confirmed: bool


def prepare_host_boundary_route_dependencies_once(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryRoutePhaseResult:
    """Prepare pins + dormant return routing, but do not activate bootstrap capture."""
    _validate(backend, desired)
    managed_interface = _managed_interface(desired)
    applied: list[tuple[str, object]] = []
    mutation_attempted = False
    try:
        for pin in desired.underlay_pins:
            if pin.present or not pin.owned:
                continue
            mutation_attempted = True
            backend.add_underlay_pin(pin)
            fresh = backend.observe_underlay_pin(
                pin.endpoint,
                managed_interface=managed_interface,
                owner_protocol=pin.protocol,
            )
            if not _same_pin(pin, fresh) or not fresh.owned or not fresh.present:
                raise HostBoundaryRouteConvergenceError(
                    f"underlay pin postcondition failed for {pin.endpoint}"
                )
            applied.append(("pin", fresh))

        if desired.return_route is not None:
            if not backend.return_route_present(desired.return_route):
                mutation_attempted = True
                backend.add_return_route(desired.return_route)
                if not backend.return_route_present(desired.return_route):
                    raise HostBoundaryRouteConvergenceError(
                        "return route postcondition failed"
                    )
                applied.append(("return_route", desired.return_route))

        if desired.return_rule is not None:
            if not backend.return_rule_present(desired.return_rule):
                mutation_attempted = True
                backend.add_return_rule(desired.return_rule)
                if not backend.return_rule_present(desired.return_rule):
                    raise HostBoundaryRouteConvergenceError(
                        "return rule postcondition failed"
                    )
                applied.append(("return_rule", desired.return_rule))

        return HostBoundaryRoutePhaseResult(
            mutation_attempted=mutation_attempted,
            confirmed=True,
        )
    except Exception as exc:
        rollback_errors = _rollback_preparation(backend, applied)
        detail = str(exc)
        if rollback_errors:
            detail += "; rollback: " + "; ".join(rollback_errors)
        raise HostBoundaryRouteConvergenceError(detail) from exc


def activate_host_boundary_bootstrap_once(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryRoutePhaseResult:
    """Activate host capture only after all higher dependencies are already ready."""
    _validate(backend, desired)
    managed_interface = _managed_interface(desired)
    added = []
    mutation_attempted = False
    try:
        for route in desired.bootstrap_routes:
            if backend.bootstrap_route_present(route):
                continue
            mutation_attempted = True
            backend.add_bootstrap_route(route)
            if not backend.bootstrap_route_present(route):
                raise HostBoundaryRouteConvergenceError(
                    f"bootstrap route postcondition failed for {route.destination}"
                )
            added.append(route)

        # The decisive full-tunnel postcondition: every required external endpoint must
        # still resolve through the same ordinary path after capture is active.
        for pin in desired.underlay_pins:
            fresh = backend.observe_underlay_pin(
                pin.endpoint,
                managed_interface=managed_interface,
                owner_protocol=pin.protocol,
            )
            if not _same_pin(pin, fresh) or not fresh.present:
                raise HostBoundaryRouteConvergenceError(
                    f"underlay path changed after bootstrap activation for {pin.endpoint}"
                )

        return HostBoundaryRoutePhaseResult(
            mutation_attempted=mutation_attempted,
            confirmed=True,
        )
    except Exception as exc:
        rollback_errors = []
        for route in reversed(added):
            try:
                backend.delete_bootstrap_route(route)
                if backend.bootstrap_route_present(route):
                    rollback_errors.append(
                        f"bootstrap route {route.destination} still present"
                    )
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        detail = str(exc)
        if rollback_errors:
            detail += "; rollback: " + "; ".join(rollback_errors)
        raise HostBoundaryRouteConvergenceError(detail) from exc


def deactivate_host_boundary_bootstrap_once(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryRoutePhaseResult:
    """Stop ordinary-side capture before return-owner/dependency cleanup."""
    _validate(backend, desired)
    errors: list[str] = []
    mutation_attempted = False
    for route in reversed(desired.bootstrap_routes):
        try:
            if backend.bootstrap_route_present(route):
                mutation_attempted = True
                backend.delete_bootstrap_route(route)
                if backend.bootstrap_route_present(route):
                    errors.append(f"bootstrap route {route.destination} still present")
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise HostBoundaryRouteConvergenceError("; ".join(errors))
    return HostBoundaryRoutePhaseResult(
        mutation_attempted=mutation_attempted,
        confirmed=True,
    )


def cleanup_host_boundary_route_dependencies_once(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryRoutePhaseResult:
    """Remove dormant return route/rule and owned pins; never delete foreign replacements."""
    _validate(backend, desired)
    managed_interface = _managed_interface(desired)
    errors: list[str] = []
    mutation_attempted = False

    if desired.return_rule is not None:
        try:
            if backend.return_rule_present(desired.return_rule):
                mutation_attempted = True
                backend.delete_return_rule(desired.return_rule)
                if backend.return_rule_present(desired.return_rule):
                    errors.append("return rule still present")
        except Exception as exc:
            errors.append(str(exc))

    if desired.return_route is not None:
        try:
            if backend.return_route_present(desired.return_route):
                mutation_attempted = True
                backend.delete_return_route(desired.return_route)
                if backend.return_route_present(desired.return_route):
                    errors.append("return route still present")
        except Exception as exc:
            errors.append(str(exc))

    for original in reversed(desired.underlay_pins):
        if not original.owned:
            continue
        try:
            fresh = backend.observe_underlay_pin(
                original.endpoint,
                managed_interface=managed_interface,
                owner_protocol=original.protocol,
            )
            if fresh.owned and fresh.present:
                mutation_attempted = True
                backend.delete_underlay_pin(fresh)
                after = backend.observe_underlay_pin(
                    original.endpoint,
                    managed_interface=managed_interface,
                    owner_protocol=original.protocol,
                )
                if after.owned and after.present:
                    errors.append(f"underlay pin {original.endpoint} still present")
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        raise HostBoundaryRouteConvergenceError("; ".join(errors))
    return HostBoundaryRoutePhaseResult(
        mutation_attempted=mutation_attempted,
        confirmed=True,
    )


def cleanup_host_boundary_route_state_once(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> HostBoundaryRoutePhaseResult:
    """Compatibility composition: deactivate capture, then remove dependencies."""
    first = deactivate_host_boundary_bootstrap_once(backend, desired)
    second = cleanup_host_boundary_route_dependencies_once(backend, desired)
    return HostBoundaryRoutePhaseResult(
        mutation_attempted=first.mutation_attempted or second.mutation_attempted,
        confirmed=first.confirmed and second.confirmed,
    )


def _rollback_preparation(
    backend: LinuxHostBoundaryRouteBackend,
    applied: list[tuple[str, object]],
) -> list[str]:
    errors = []
    for kind, value in reversed(applied):
        try:
            if kind == "return_rule":
                backend.delete_return_rule(value)
            elif kind == "return_route":
                backend.delete_return_route(value)
            elif kind == "pin":
                backend.delete_underlay_pin(value)
        except Exception as exc:
            errors.append(str(exc))
    return errors


def _managed_interface(desired: HostBoundaryLinuxDesired) -> str:
    interfaces = {
        route.interface
        for route in desired.bootstrap_routes
    }
    if desired.return_route is not None:
        interfaces.add(desired.return_route.interface)
    if not interfaces:
        # No pins are possible without bootstrap capture, so an arbitrary non-empty
        # sentinel is sufficient for a no-underlay/no-routing empty desired state.
        if desired.underlay_pins:
            raise HostBoundaryRouteConvergenceError(
                "underlay pins exist without a managed boundary route"
            )
        return "__vpn_gate_unused__"
    if len(interfaces) != 1:
        raise HostBoundaryRouteConvergenceError(
            "host-boundary desired state references multiple managed interfaces"
        )
    return next(iter(interfaces))


def _same_pin(expected: HostUnderlayPin, actual: HostUnderlayPin) -> bool:
    return (
        expected.endpoint == actual.endpoint
        and expected.interface == actual.interface
        and expected.gateway == actual.gateway
        and expected.source == actual.source
    )


def _validate(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryLinuxDesired,
) -> None:
    if not isinstance(backend, LinuxHostBoundaryRouteBackend):
        raise ValueError("backend must be LinuxHostBoundaryRouteBackend")
    if not isinstance(desired, HostBoundaryLinuxDesired):
        raise ValueError("desired must be HostBoundaryLinuxDesired")

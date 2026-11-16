from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Protocol, Sequence

from .interface_inventory import parse_ip_link_inventory
from .route_priority import RoutePriorityMove
from .route_priority_convergence import RoutePriorityDeleteDuplicate
from .route_priority_executor import RoutePrioritySnapshot
from .route_priority_inventory import (
    RoutePriorityPathRoute,
    parse_ip_route_priority_snapshot,
)


class IproutePriorityBackendError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one command or raise on failure; return stdout text."""


class SubprocessCommandRunner:
    def run(self, argv: Sequence[str]) -> str:
        completed = subprocess.run(
            tuple(argv),
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


@dataclass(slots=True)
class IproutePriorityBackend:
    """One physical Linux route-key domain for priority convergence."""

    runner: CommandRunner
    namespace: str
    table: int
    owner_protocol: int
    destination: object
    path_routes: tuple[RoutePriorityPathRoute, ...]

    def __post_init__(self) -> None:
        from ipaddress import IPv4Network

        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")
        if type(self.table) is not int or not 1 <= self.table <= 0xFFFFFFFF:
            raise ValueError("table must be an integer in [1, 2^32-1]")
        if (
            type(self.owner_protocol) is not int
            or not 0 <= self.owner_protocol <= 255
        ):
            raise ValueError("owner_protocol must be an integer in [0, 255]")
        if not isinstance(self.destination, IPv4Network):
            raise ValueError("destination must be an IPv4Network")
        if not isinstance(self.path_routes, tuple) or not self.path_routes:
            raise ValueError("path_routes must be a non-empty tuple")
        if any(
            not isinstance(spec, RoutePriorityPathRoute)
            for spec in self.path_routes
        ):
            raise ValueError("path_routes must contain RoutePriorityPathRoute")

    def observe_route_priority(self) -> RoutePrioritySnapshot:
        before = parse_ip_link_inventory(
            self.runner.run(self._link_show_command())
        )
        route_json = self.runner.run(self._route_show_command())
        after = parse_ip_link_inventory(
            self.runner.run(self._link_show_command())
        )

        self._verify_relevant_interface_stability(before, after)

        return parse_ip_route_priority_snapshot(
            route_json,
            destination=self.destination,
            owner_protocol=self.owner_protocol,
            path_routes=self.path_routes,
            interfaces=after,
            protocol_filtered=True,
        )

    def delete_duplicate_route(
        self,
        step: RoutePriorityDeleteDuplicate,
    ) -> None:
        spec = self._spec(step.path_id)
        before = self.observe_route_priority()
        self._require_all_paths_present(before)
        self._require_unique_metric_ownership(before)

        metrics = before.routes[step.path_id]
        if step.metric not in metrics or len(metrics) <= 1:
            raise IproutePriorityBackendError(
                "duplicate delete is not safe in current authoritative state"
            )

        self.runner.run(
            self._route_mutation_command("del", spec, step.metric)
        )

        after = self.observe_route_priority()
        expected_after = {
            path_id: frozenset(metrics)
            for path_id, metrics in before.routes.items()
        }
        expected_after[step.path_id] = frozenset(
            metric
            for metric in before.routes[step.path_id]
            if metric != step.metric
        )
        self._require_exact_snapshot(
            after,
            expected_after,
            "duplicate-delete postcondition",
        )

    def move_route_priority(self, move: RoutePriorityMove) -> None:
        spec = self._spec(move.path_id)

        before = self.observe_route_priority()
        self._require_all_paths_present(before)
        self._require_unique_metric_ownership(before)
        if any(len(metrics) != 1 for metrics in before.routes.values()):
            raise IproutePriorityBackendError(
                "semantic move requires one current metric per logical path"
            )

        if before.routes[move.path_id] != frozenset((move.from_metric,)):
            raise IproutePriorityBackendError(
                "move source is not the single current route metric"
            )
        if any(
            move.to_metric in metrics
            for metrics in before.routes.values()
        ):
            raise IproutePriorityBackendError(
                "move destination metric is not free in current state"
            )

        self.runner.run(
            self._route_mutation_command("add", spec, move.to_metric)
        )

        after_add = self.observe_route_priority()
        expected_after_add = {
            path_id: frozenset(metrics)
            for path_id, metrics in before.routes.items()
        }
        expected_after_add[move.path_id] = frozenset(
            (move.from_metric, move.to_metric)
        )
        self._require_exact_snapshot(
            after_add,
            expected_after_add,
            "add-before-delete verification",
        )

        self.runner.run(
            self._route_mutation_command("del", spec, move.from_metric)
        )

        after_delete = self.observe_route_priority()
        expected_after_delete = {
            path_id: frozenset(metrics)
            for path_id, metrics in before.routes.items()
        }
        expected_after_delete[move.path_id] = frozenset((move.to_metric,))
        self._require_exact_snapshot(
            after_delete,
            expected_after_delete,
            "move postcondition",
        )

    def _verify_relevant_interface_stability(
        self,
        before: tuple[object, ...],
        after: tuple[object, ...],
    ) -> None:
        by_name_before = {
            endpoint.ifname: endpoint
            for endpoint in before
        }
        by_name_after = {
            endpoint.ifname: endpoint
            for endpoint in after
        }

        for spec in self.path_routes:
            name = spec.endpoint.ifname
            if by_name_before.get(name) != by_name_after.get(name):
                raise IproutePriorityBackendError(
                    f"relevant interface {name!r} changed during route observation"
                )
            if by_name_after.get(name) != spec.endpoint:
                raise IproutePriorityBackendError(
                    f"relevant interface {name!r} no longer matches bound identity"
                )

    def _require_unique_metric_ownership(
        self,
        snapshot: RoutePrioritySnapshot,
    ) -> None:
        owner_by_metric: dict[int, object] = {}
        for path_id, metrics in snapshot.routes.items():
            for metric in metrics:
                owner = owner_by_metric.get(metric)
                if owner is not None and owner != path_id:
                    raise IproutePriorityBackendError(
                        f"metric {metric} is owned by multiple logical paths"
                    )
                owner_by_metric[metric] = path_id

    def _require_exact_snapshot(
        self,
        snapshot: RoutePrioritySnapshot,
        expected: dict[object, frozenset[int]],
        context: str,
    ) -> None:
        if dict(snapshot.routes) != expected:
            raise IproutePriorityBackendError(
                f"{context} does not match authoritative whole-domain state"
            )
        self._require_all_paths_present(snapshot)
        self._require_unique_metric_ownership(snapshot)

    def _require_all_paths_present(
        self,
        snapshot: RoutePrioritySnapshot,
    ) -> None:
        missing = [
            path_id
            for path_id, metrics in snapshot.routes.items()
            if not metrics
        ]
        if missing:
            raise IproutePriorityBackendError(
                f"priority-only physical state has missing eligible paths: {missing!r}"
            )

    def _spec(self, path_id: object) -> RoutePriorityPathRoute:
        matches = [
            spec
            for spec in self.path_routes
            if spec.path_id == path_id
        ]
        if len(matches) != 1:
            raise IproutePriorityBackendError(
                f"unknown or ambiguous logical path {path_id!r}"
            )
        return matches[0]

    def _link_show_command(self) -> tuple[str, ...]:
        return (
            "ip",
            "-n",
            self.namespace,
            "-j",
            "link",
            "show",
        )

    def _route_show_command(self) -> tuple[str, ...]:
        return (
            "ip",
            "-n",
            self.namespace,
            "-j",
            "-N",
            "-4",
            "route",
            "show",
            "table",
            str(self.table),
            "proto",
            str(self.owner_protocol),
        )

    def _route_mutation_command(
        self,
        action: str,
        spec: RoutePriorityPathRoute,
        metric: int,
    ) -> tuple[str, ...]:
        if action not in ("add", "del"):
            raise ValueError("action must be 'add' or 'del'")
        if type(metric) is not int or metric < 0:
            raise ValueError("metric must be a non-negative integer")

        command = [
            "ip",
            "-n",
            self.namespace,
            "-4",
            "route",
            action,
            "unicast",
            str(self.destination),
            "table",
            str(self.table),
            "proto",
            str(self.owner_protocol),
            "metric",
            str(metric),
        ]

        if spec.gateway is not None:
            command.extend(("via", str(spec.gateway)))
        command.extend(("dev", spec.endpoint.ifname))
        if spec.onlink:
            command.append("onlink")

        return tuple(command)

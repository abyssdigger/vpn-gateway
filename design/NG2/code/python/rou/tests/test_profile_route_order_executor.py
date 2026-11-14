from ipaddress import IPv4Network
from threading import Event, Lock, Thread
import unittest

from rou.interface_identity import InterfaceIdentity
from rou.network_rules import RoutingDomainSpec, TerminalDisposition
from rou.profile_route_order_executor import ProfileRouteOrderExecutor


def _target(name: str) -> RoutingDomainSpec:
    path = InterfaceIdentity("vpns00", 10)
    return RoutingDomainSpec(
        name,
        (IPv4Network("10.0.0.0/8"),),
        (path,),
        TerminalDisposition.DROP,
        priority_prefix_length=1,
    )


class BlockingOperation:
    def __init__(self):
        self.first_entered = Event()
        self.second_entered = Event()
        self.release = Event()
        self._guard = Lock()
        self._entered = 0
        self._active = 0
        self.max_active = 0

    def __call__(self, target):
        with self._guard:
            self._entered += 1
            entered = self._entered
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        if entered == 1:
            self.first_entered.set()
        else:
            self.second_entered.set()
        self.release.wait(timeout=2)
        with self._guard:
            self._active -= 1
        return target.name


class ProfileRouteOrderExecutorTests(unittest.TestCase):
    def test_same_profile_execute_is_single_flight_until_operation_returns(self):
        executor = ProfileRouteOrderExecutor("corp")
        operation = BlockingOperation()
        target = _target("corp")

        first = Thread(target=executor.execute, args=(target, operation))
        second = Thread(target=executor.execute, args=(target, operation))

        first.start()
        self.assertTrue(operation.first_entered.wait(timeout=1))
        second.start()

        self.assertFalse(
            operation.second_entered.wait(timeout=0.1),
            "second Profile transaction entered before the first completed",
        )

        operation.release.set()
        first.join(timeout=2)
        second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertTrue(operation.second_entered.is_set())
        self.assertEqual(operation.max_active, 1)

    def test_different_profile_executors_have_independent_gates(self):
        first_entered = Event()
        second_entered = Event()
        release = Event()

        def first_operation(target):
            first_entered.set()
            release.wait(timeout=2)
            return target.name

        def second_operation(target):
            second_entered.set()
            release.wait(timeout=2)
            return target.name

        first = ProfileRouteOrderExecutor("a")
        second = ProfileRouteOrderExecutor("b")

        first_thread = Thread(
            target=first.execute,
            args=(_target("a"), first_operation),
        )
        second_thread = Thread(
            target=second.execute,
            args=(_target("b"), second_operation),
        )

        first_thread.start()
        second_thread.start()

        self.assertTrue(first_entered.wait(timeout=1))
        self.assertTrue(second_entered.wait(timeout=1))

        release.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertFalse(second_thread.is_alive())

    def test_rejects_target_for_another_profile(self):
        executor = ProfileRouteOrderExecutor("a")

        with self.assertRaisesRegex(ValueError, "does not match"):
            executor.execute(_target("b"), lambda target: target)


if __name__ == "__main__":
    unittest.main()

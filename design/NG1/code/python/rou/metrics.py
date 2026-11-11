from __future__ import annotations

from dataclasses import dataclass

from .domain import ActiveConfig, Profile

FIRST_NORMAL_METRIC = 1
UNAVAILABLE_METRIC = 65535
BLACKHOLE_METRIC = 65536
MAX_NORMAL_METRIC = UNAVAILABLE_METRIC - 1


class MetricLayoutError(ValueError):
    pass


@dataclass(frozen=True)
class ExpectedMetricRange:
    device_name: str
    expected_index: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start + 1


def compile_profile_metric_layout(config: ActiveConfig, profile: Profile) -> tuple[ExpectedMetricRange, ...]:
    if not profile.enabled:
        return ()

    cursor = FIRST_NORMAL_METRIC
    out: list[ExpectedMetricRange] = []

    for device_name in profile.device_order:
        device = config.devices[device_name]
        if not device.enabled:
            continue
        for index, expected in enumerate(device.expected_interfaces):
            end = cursor + expected.interface_quota - 1
            if end > MAX_NORMAL_METRIC:
                raise MetricLayoutError(
                    f"profile {profile.name!r} requires normal metric {end}, "
                    f"but normal metrics must be < {UNAVAILABLE_METRIC}"
                )
            out.append(ExpectedMetricRange(device_name, index, cursor, end))
            cursor = end + 1

    return tuple(out)


def compile_all_metric_layouts(config: ActiveConfig) -> dict[str, tuple[ExpectedMetricRange, ...]]:
    return {
        profile.name: compile_profile_metric_layout(config, profile)
        for profile in config.profiles.values()
        if profile.enabled
    }

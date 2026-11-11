from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.config import ConfigError, parse_active_config
from rou.metrics import (
    BLACKHOLE_METRIC,
    FIRST_NORMAL_METRIC,
    MAX_NORMAL_METRIC,
    UNAVAILABLE_METRIC,
    compile_all_metric_layouts,
)


class MetricLayoutTests(unittest.TestCase):
    def test_tail_order(self):
        self.assertEqual(FIRST_NORMAL_METRIC, 1)
        self.assertLess(MAX_NORMAL_METRIC, UNAVAILABLE_METRIC)
        self.assertLess(UNAVAILABLE_METRIC, BLACKHOLE_METRIC)

    def test_device_then_expected_interface_order(self):
        cfg = parse_active_config('''
[device.wg]
enabled = true
expected_interfaces = ["wg0"]

[device.oc]
enabled = true
expected_interfaces = ["oc-main", "vpns*/3", "oc-backup"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["wg", "oc"]
''')
        ranges = compile_all_metric_layouts(cfg)['corp']
        self.assertEqual(
            [(r.device_name, r.expected_index, r.start, r.end) for r in ranges],
            [
                ('wg', 0, 1, 1),
                ('oc', 0, 2, 2),
                ('oc', 1, 3, 5),
                ('oc', 2, 6, 6),
            ],
        )

    def test_disabled_device_in_order_consumes_no_metric_space(self):
        cfg = parse_active_config('''
[device.future]
enabled = false

[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["0.0.0.0/0"]
device_order = ["future", "oc"]
''')
        ranges = compile_all_metric_layouts(cfg)['corp']
        self.assertEqual([(r.device_name, r.start, r.end) for r in ranges], [('oc', 1, 2)])

    def test_shared_device_can_have_different_profile_ranges(self):
        cfg = parse_active_config('''
[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]

[device.wg]
enabled = true
expected_interfaces = ["wg0"]

[profile.a]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc", "wg"]

[profile.b]
enabled = true
direction = "outbound"
destinations = ["192.168.0.0/16"]
device_order = ["wg", "oc"]
''')
        layouts = compile_all_metric_layouts(cfg)
        self.assertEqual([(r.device_name, r.start, r.end) for r in layouts['a']], [('oc', 1, 2), ('wg', 3, 3)])
        self.assertEqual([(r.device_name, r.start, r.end) for r in layouts['b']], [('wg', 1, 1), ('oc', 2, 3)])

    def test_max_normal_capacity_fits(self):
        cfg = parse_active_config(f'''
[device.huge]
enabled = true
expected_interfaces = ["vpn*/{MAX_NORMAL_METRIC}"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["huge"]
''')
        ranges = compile_all_metric_layouts(cfg)['corp']
        self.assertEqual(ranges[-1].end, MAX_NORMAL_METRIC)

    def test_normal_capacity_cannot_consume_unavailable_metric(self):
        with self.assertRaisesRegex(ConfigError, 'normal metric'):
            parse_active_config(f'''
[device.huge]
enabled = true
expected_interfaces = ["vpn*/{UNAVAILABLE_METRIC}"]

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["huge"]
''')


if __name__ == '__main__':
    unittest.main()

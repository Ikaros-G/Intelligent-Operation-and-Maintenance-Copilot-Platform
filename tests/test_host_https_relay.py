import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "host_https_relay.py"


def load_relay_module():
    spec = importlib.util.spec_from_file_location("host_https_relay", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HostHttpsRelayTest(unittest.TestCase):
    def test_only_dashscope_https_target_is_allowed(self):
        relay = load_relay_module()

        self.assertTrue(relay.is_allowed_target("dashscope.aliyuncs.com", 443))
        self.assertTrue(relay.is_allowed_target("cls.tencentcloudapi.com", 443))
        self.assertFalse(relay.is_allowed_target("dashscope.aliyuncs.com", 80))
        self.assertFalse(relay.is_allowed_target("example.com", 443))

    def test_connect_target_parser_accepts_valid_authority(self):
        relay = load_relay_module()

        self.assertEqual(
            relay.parse_connect_target("dashscope.aliyuncs.com:443"),
            ("dashscope.aliyuncs.com", 443),
        )


if __name__ == "__main__":
    unittest.main()

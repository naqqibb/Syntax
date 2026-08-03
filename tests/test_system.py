import importlib.util
import unittest
from pathlib import Path


def load_system_module():
    module_path = Path(__file__).resolve().parents[1] / "SYSTEM"
    spec = importlib.util.spec_from_file_location("syntax_system", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperatorSystemTests(unittest.TestCase):
    def test_build_report_includes_operator_metrics(self):
        system_module = load_system_module()
        operator_system = system_module.OperatorSystem()

        report = operator_system.build_report()

        self.assertEqual(report["status"], "OPERATIONAL")
        self.assertGreaterEqual(report["active_incidents"], 0)
        self.assertIn(report["threat_level"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
        self.assertEqual(report["operator_mode"], "SYNTAX OPERATOR")


if __name__ == "__main__":
    unittest.main()

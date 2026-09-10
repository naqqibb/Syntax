import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path


def load_system_module():
    module_path = Path(__file__).resolve().parents[1] / "SYSTEM"
    # SYSTEM has no .py extension, so an explicit source loader is required
    # (spec_from_file_location alone cannot infer a loader here).
    loader = SourceFileLoader("syntax_system", str(module_path))
    spec = importlib.util.spec_from_loader("syntax_system", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class OperatorSystemTests(unittest.TestCase):
    def setUp(self):
        self.module = load_system_module()
        self.operator = self.module.OperatorSystem()

    def test_build_report_includes_operator_metrics(self):
        report = self.operator.build_report()
        self.assertEqual(report["status"], "OPERATIONAL")
        self.assertGreaterEqual(report["active_incidents"], 0)
        self.assertIn(report["threat_level"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
        self.assertEqual(report["operator_mode"], "SYNTAX OPERATOR")

    def test_print_report_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            self.operator.print_report("not a dict")

    def test_print_report_rejects_incomplete_report(self):
        with self.assertRaises(ValueError):
            self.operator.print_report({"status": "OPERATIONAL"})

    def test_print_report_accepts_generated_report(self):
        # A report produced by build_report must satisfy the validator.
        self.operator.print_report(self.operator.build_report())


if __name__ == "__main__":
    unittest.main()

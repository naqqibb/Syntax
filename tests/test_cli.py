"""End-to-end checks over the renderers and CLI entry points.

The report builders were already covered; the terminal renderers and argument
handling were not, and they are the paths most likely to break when a report
schema changes. These exercise them for real rather than mocking them out.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(module_file, module_name):
    loader = importlib.machinery.SourceFileLoader(module_name, str(ROOT / module_file))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so dataclasses can resolve the module.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


sanctions = load("SANCTIONS", "syntax_sanctions")
filings = load("FILINGS", "syntax_filings")
audit = load("AUDIT", "syntax_audit")


@contextlib.contextmanager
def captured_argv(argv):
    original = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = original


def run_main(module, args):
    """Run a module's main() with argv, returning (exit_code, stdout)."""
    buffer = io.StringIO()
    with captured_argv([module.__name__] + args):
        with contextlib.redirect_stdout(buffer):
            code = module.main()
    return code, buffer.getvalue()


class RendererTests(unittest.TestCase):
    def test_sanctions_renderer_emits_every_section(self):
        buffer = io.StringIO()
        tracker = sanctions.build_demo_tracker()
        with contextlib.redirect_stdout(buffer):
            tracker.print_report()
        output = buffer.getvalue()
        for marker in (
            "SANCTIONS EVASION TRACKER",
            "Evasion cases",
            "Monetary field sites",
            "Sinkhole dispositions",
            "SE-2025-0114",
            "AUTHORIZED",
        ):
            self.assertIn(marker, output)

    def test_filings_renderer_emits_every_section(self):
        buffer = io.StringIO()
        diagnosis = filings.build_demo_diagnosis()
        with contextlib.redirect_stdout(buffer):
            diagnosis.print_report()
        output = buffer.getvalue()
        for marker in (
            "IRS FILING CYPHER DIAGNOSIS",
            "Decoded filings",
            "Diagnostic findings",
            "Evasion signals emitted",
            "THRESHOLD_SPLIT",
            "US currency",
        ):
            self.assertIn(marker, output)

    def test_audit_renderer_emits_every_section(self):
        buffer = io.StringIO()
        portfolio = audit.build_demo_portfolio()
        with contextlib.redirect_stdout(buffer):
            portfolio.print_report()
        output = buffer.getvalue()
        for marker in (
            "WORLD BANK INTERIM AUDIT",
            "P178220",
            "FM risk",
            "DEBARRED_COUNTERPARTY",
            "Evasion signals emitted",
        ):
            self.assertIn(marker, output)

    def test_renderers_accept_a_prebuilt_report(self):
        # print_report(report) must not rebuild; a stale report still renders.
        tracker = sanctions.build_demo_tracker()
        report = tracker.build_report()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            tracker.print_report(report)
        self.assertIn(report["generated_at"], buffer.getvalue())

    def test_empty_diagnosis_renders_without_error(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            filings.FilingDiagnosis().print_report()
        self.assertIn("No findings raised.", buffer.getvalue())

    def test_empty_portfolio_renders_without_error(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            audit.AuditPortfolio().print_report()
        self.assertIn("Projects: 0", buffer.getvalue())


class CliTests(unittest.TestCase):
    def test_each_module_exits_zero_in_text_mode(self):
        for module in (sanctions, filings, audit):
            with self.subTest(module=module.__name__):
                code, output = run_main(module, [])
                self.assertEqual(code, 0)
                self.assertTrue(output.strip())

    def test_each_module_emits_parsable_json(self):
        for module in (sanctions, filings, audit):
            with self.subTest(module=module.__name__):
                code, output = run_main(module, ["--json"])
                self.assertEqual(code, 0)
                payload = json.loads(output)
                self.assertEqual(payload["status"], "OPERATIONAL")
                self.assertTrue(payload["module"].startswith("SYNTAX "))
                self.assertIn("generated_at", payload)

    def test_filings_codes_flag_prints_the_tables(self):
        code, output = run_main(filings, ["--codes"])
        self.assertEqual(code, 0)
        for filing_type in filings.FilingType:
            self.assertIn(filing_type.name, output)

    def test_unknown_flag_exits_nonzero(self):
        for module in (sanctions, filings, audit):
            with self.subTest(module=module.__name__):
                with self.assertRaises(SystemExit) as raised:
                    with contextlib.redirect_stderr(io.StringIO()):
                        run_main(module, ["--nope"])
                self.assertNotEqual(raised.exception.code, 0)


class SanctionsLoaderTests(unittest.TestCase):
    """The cold path of load_sanctions_module, which the cache normally skips."""

    def setUp(self):
        self.cached = sys.modules.pop("syntax_sanctions", None)

    def tearDown(self):
        if self.cached is not None:
            sys.modules["syntax_sanctions"] = self.cached

    def test_filings_loads_sanctions_from_disk_when_uncached(self):
        module = filings.load_sanctions_module()
        self.assertTrue(hasattr(module, "EvasionTypology"))
        self.assertIs(sys.modules["syntax_sanctions"], module)

    def test_audit_loads_sanctions_from_disk_when_uncached(self):
        module = audit.load_sanctions_module()
        self.assertTrue(hasattr(module, "EvasionCase"))

    def test_cached_module_is_returned_without_reloading(self):
        first = filings.load_sanctions_module()
        self.assertIs(filings.load_sanctions_module(), first)


class OperatorSystemCliTests(unittest.TestCase):
    """SYSTEM shipped with only its report builder covered."""

    def setUp(self):
        self.system = load("SYSTEM", "syntax_system_cli")

    def test_renderer_prints_the_operator_summary(self):
        buffer = io.StringIO()
        operator = self.system.OperatorSystem()
        with contextlib.redirect_stdout(buffer):
            operator.print_report()
        output = buffer.getvalue()
        self.assertIn("SYNTAX OPERATOR", output)
        self.assertIn("Status: OPERATIONAL", output)
        for component in operator.components:
            self.assertIn(component, output)

    def test_run_returns_the_report_it_printed(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            report = self.system.OperatorSystem().run()
        self.assertEqual(report["status"], "OPERATIONAL")
        self.assertIn(str(report["active_incidents"]), buffer.getvalue())

    def test_threat_ladder_maps_each_incident_count_to_its_tier(self):
        operator = self.system.OperatorSystem()
        expected = {0: "LOW", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
        for seed_size, tier in expected.items():
            with self.subTest(incidents=seed_size):
                operator._incident_seed = [("seeded", "HIGH")] * seed_size
                with unittest.mock.patch.object(
                    self.system.random, "randint", return_value=0
                ):
                    self.assertEqual(operator.build_report()["threat_level"], tier)

    def test_shipped_seed_can_only_ever_report_critical(self):
        # Documents a live defect: the shipped seed holds 4 incidents and
        # randint adds 0-3, so active_incidents is never below 4 and the
        # HIGH/MEDIUM/LOW rungs of the ladder are unreachable in production.
        # Pinned rather than corrected, since changing the seed or the
        # thresholds is a behavioural decision for the module's owner.
        operator = self.system.OperatorSystem()
        self.assertEqual(len(operator._incident_seed), 4)
        levels = {operator.build_report()["threat_level"] for _ in range(200)}
        self.assertEqual(levels, {"CRITICAL"})

    def test_main_exits_zero(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(self.system.main(), 0)
        self.assertTrue(buffer.getvalue().strip())


class CrossModuleTests(unittest.TestCase):
    """The three modules share one evidence chain; check it end to end."""

    def test_filings_and_audit_signals_score_in_one_case(self):
        case = sanctions.EvasionCase(
            case_id="SE-CHAIN-1",
            subject="Chained subject",
            target_regime="EMBARGOED-A",
        )
        for signal in filings.build_demo_diagnosis().to_sanctions_signals():
            case.add_signal(signal)
        filings_only = case.score()

        for signal in audit.build_demo_portfolio().to_sanctions_signals():
            case.add_signal(signal)
        combined = case.score()

        self.assertGreater(combined, filings_only)
        self.assertLessEqual(combined, 100.0)

    def test_both_bridges_resolve_against_one_typology_vocabulary(self):
        declared = {typology.name for typology in sanctions.EvasionTypology}
        mapped = {name for name, _ in filings.TYPOLOGY_BRIDGE.values()}
        mapped |= {name for name, _ in filings.SAR_INSTRUMENT_TYPOLOGY.values()}
        mapped |= {name for name, _ in audit.TYPOLOGY_BRIDGE.values()}
        self.assertTrue(mapped <= declared, mapped - declared)

    def test_provenance_prefixes_stay_distinct_across_sources(self):
        filing_sources = {
            source.split(":")[0]
            for signal in filings.build_demo_diagnosis().evasion_signals()
            for source in signal["sources"]
        }
        audit_sources = {
            source.split(":")[0]
            for signal in audit.build_demo_portfolio().evasion_signals()
            for source in signal["sources"]
        }
        self.assertEqual(filing_sources, {"irs-filing"})
        self.assertEqual(audit_sources, {"wb-audit"})
        self.assertFalse(filing_sources & audit_sources)

    def test_chained_evidence_cannot_authorize_a_sinkhole_on_its_own(self):
        # Filing and audit findings are corroborating threads, not a mandate:
        # the humanitarian and jurisdiction gates still govern the outcome.
        case = sanctions.EvasionCase(
            case_id="SE-CHAIN-2", subject="Chained subject", target_regime="N/A"
        )
        for signal in audit.build_demo_portfolio().to_sanctions_signals():
            case.add_signal(signal)

        authority = sanctions.SinkholeAuthority()
        decision = authority.evaluate(case, sanctions.SinkholeRequest(
            indicator="node.example",
            hosting_jurisdiction="RU",
            registrar_jurisdiction="RU",
            requesting_alliance=sanctions.Alliance.NATO,
        ))
        self.assertFalse(decision.approved)


if __name__ == "__main__":
    unittest.main()

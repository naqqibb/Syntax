import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path


def load_filings_module():
    module_path = Path(__file__).resolve().parents[1] / "FILINGS"
    loader = importlib.machinery.SourceFileLoader("syntax_filings", str(module_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so dataclasses can resolve the module.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


filings = load_filings_module()


def make_filing(**kwargs):
    defaults = dict(
        filing_id="F-1",
        filing_type=filings.FilingType.FORM_8300,
        subject="Test Subject",
        amount_usd=5_000.0,
        transaction_date="2025-03-01",
        filed_date="2025-03-05",
        cyphers={"method_of_payment": "A", "transaction_nature": "01"},
    )
    defaults.update(kwargs)
    return filings.Filing(**defaults)


def codes_from(findings):
    return {finding.code for finding in findings}


class FilingModelTests(unittest.TestCase):
    def test_decode_resolves_known_codes(self):
        decoded = make_filing().decode()
        self.assertEqual(decoded["method_of_payment"], "US currency")
        self.assertEqual(decoded["transaction_nature"], "Personal property purchase")

    def test_decode_marks_unknown_codes_rather_than_dropping_them(self):
        decoded = make_filing(cyphers={"method_of_payment": "Z"}).decode()
        self.assertIn("UNKNOWN CODE", decoded["method_of_payment"])

    def test_filing_lag_is_days_between_transaction_and_filing(self):
        filing = make_filing(transaction_date="2025-03-01", filed_date="2025-03-20")
        self.assertEqual(filing.filing_lag_days, 19)

    def test_jurisdictions_are_normalized_to_upper_case(self):
        filing = make_filing(subject_jurisdiction="us", account_jurisdiction="ae")
        self.assertEqual(filing.subject_jurisdiction, "US")
        self.assertEqual(filing.account_jurisdiction, "AE")

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            make_filing(amount_usd=-1.0)

    def test_malformed_date_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            make_filing(transaction_date="03/01/2025")


class CypherCheckTests(unittest.TestCase):
    def setUp(self):
        self.diagnostician = filings.FilingDiagnostician()

    def test_valid_filing_raises_no_cypher_findings(self):
        found = codes_from(self.diagnostician.diagnose([make_filing()]))
        self.assertNotIn(filings.FindingCode.UNKNOWN_CYPHER, found)
        self.assertNotIn(filings.FindingCode.MISSING_REQUIRED_CYPHER, found)

    def test_unknown_code_for_a_known_field_is_flagged(self):
        filing = make_filing(
            cyphers={"method_of_payment": "Z", "transaction_nature": "01"}
        )
        self.assertIn(
            filings.FindingCode.UNKNOWN_CYPHER,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_field_with_no_code_table_is_flagged(self):
        filing = make_filing(
            cyphers={
                "method_of_payment": "A",
                "transaction_nature": "01",
                "invented_field": "X",
            }
        )
        self.assertIn(
            filings.FindingCode.UNKNOWN_CYPHER,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_missing_required_field_is_flagged(self):
        filing = make_filing(cyphers={"method_of_payment": "A"})
        findings = self.diagnostician.diagnose([filing])
        self.assertIn(filings.FindingCode.MISSING_REQUIRED_CYPHER, codes_from(findings))

    def test_every_filing_type_has_a_table_for_each_required_field(self):
        for filing_type, required in filings.REQUIRED_FIELDS.items():
            table = filings.CYPHER_TABLES[filing_type]
            for name in required:
                self.assertIn(name, table, f"{filing_type.name} lacks '{name}'")
                self.assertTrue(table[name], f"{filing_type.name}.{name} is empty")

    def test_exchange_of_cash_on_a_negotiable_instrument_is_flagged(self):
        filing = make_filing(
            cyphers={"method_of_payment": "C", "transaction_nature": "07"}
        )
        self.assertIn(
            filings.FindingCode.CYPHER_AMOUNT_MISMATCH,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_structuring_sar_on_a_non_currency_instrument_is_flagged(self):
        filing = make_filing(
            filing_id="SAR-1",
            filing_type=filings.FilingType.SAR_111,
            amount_usd=80_000.0,
            cyphers={"activity_category": "STRUCT", "instrument_involved": "CVC"},
        )
        self.assertIn(
            filings.FindingCode.CYPHER_AMOUNT_MISMATCH,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_structuring_sar_on_currency_is_not_flagged_as_mismatch(self):
        filing = make_filing(
            filing_id="SAR-2",
            filing_type=filings.FilingType.SAR_111,
            amount_usd=80_000.0,
            cyphers={"activity_category": "STRUCT", "instrument_involved": "CUR"},
        )
        self.assertNotIn(
            filings.FindingCode.CYPHER_AMOUNT_MISMATCH,
            codes_from(self.diagnostician.diagnose([filing])),
        )


class ThresholdAndTimelinessTests(unittest.TestCase):
    def setUp(self):
        self.diagnostician = filings.FilingDiagnostician()

    def test_amount_just_under_threshold_raises_structuring_proximity(self):
        findings = self.diagnostician.diagnose([make_filing(amount_usd=9_400.0)])
        self.assertIn(filings.FindingCode.STRUCTURING_PROXIMITY, codes_from(findings))

    def test_amount_at_threshold_is_not_structuring(self):
        findings = self.diagnostician.diagnose([make_filing(amount_usd=10_000.0)])
        self.assertNotIn(filings.FindingCode.STRUCTURING_PROXIMITY, codes_from(findings))

    def test_far_below_threshold_is_informational_only(self):
        findings = self.diagnostician.diagnose([make_filing(amount_usd=500.0)])
        self.assertIn(filings.FindingCode.SUBTHRESHOLD_FILING, codes_from(findings))
        self.assertNotIn(filings.FindingCode.STRUCTURING_PROXIMITY, codes_from(findings))

    def test_filing_inside_the_window_is_not_late(self):
        filing = make_filing(transaction_date="2025-03-01", filed_date="2025-03-15")
        self.assertNotIn(
            filings.FindingCode.LATE_FILING,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_filing_past_the_window_is_late(self):
        filing = make_filing(transaction_date="2025-03-01", filed_date="2025-03-25")
        self.assertIn(
            filings.FindingCode.LATE_FILING,
            codes_from(self.diagnostician.diagnose([filing])),
        )

    def test_severely_late_filing_escalates_severity(self):
        filing = make_filing(transaction_date="2025-03-01", filed_date="2025-06-01")
        late = [
            finding
            for finding in self.diagnostician.diagnose([filing])
            if finding.code is filings.FindingCode.LATE_FILING
        ]
        self.assertEqual(late[0].severity, filings.Severity.HIGH)

    def test_account_in_another_jurisdiction_is_flagged(self):
        filing = make_filing(subject_jurisdiction="US", account_jurisdiction="AE")
        findings = self.diagnostician.diagnose([filing])
        conflict = [
            finding
            for finding in findings
            if finding.code is filings.FindingCode.JURISDICTION_CONFLICT
        ]
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].jurisdiction, "AE")

    def test_matching_jurisdictions_raise_nothing(self):
        filing = make_filing(subject_jurisdiction="US", account_jurisdiction="US")
        self.assertNotIn(
            filings.FindingCode.JURISDICTION_CONFLICT,
            codes_from(self.diagnostician.diagnose([filing])),
        )


class ThresholdSplitTests(unittest.TestCase):
    def setUp(self):
        self.diagnostician = filings.FilingDiagnostician()

    def split_findings(self, filing_list):
        return [
            finding
            for finding in self.diagnostician.diagnose(filing_list)
            if finding.code is filings.FindingCode.THRESHOLD_SPLIT
        ]

    def test_split_across_the_window_is_critical(self):
        group = [
            make_filing(filing_id="A", amount_usd=6_000.0, transaction_date="2025-03-01"),
            make_filing(filing_id="B", amount_usd=6_000.0, transaction_date="2025-03-05"),
        ]
        found = self.split_findings(group)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, filings.Severity.CRITICAL)

    def test_widest_qualifying_run_is_reported(self):
        group = [
            make_filing(filing_id="A", amount_usd=9_400.0, transaction_date="2025-03-03"),
            make_filing(filing_id="B", amount_usd=9_600.0, transaction_date="2025-03-09"),
            make_filing(filing_id="C", amount_usd=8_900.0, transaction_date="2025-03-14"),
        ]
        found = self.split_findings(group)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].filing_ids, ["A", "B", "C"])

    def test_filings_outside_the_window_do_not_aggregate(self):
        group = [
            make_filing(filing_id="A", amount_usd=6_000.0, transaction_date="2025-01-01"),
            make_filing(filing_id="B", amount_usd=6_000.0, transaction_date="2025-06-01"),
        ]
        self.assertEqual(self.split_findings(group), [])

    def test_different_subjects_do_not_aggregate(self):
        group = [
            make_filing(filing_id="A", subject="One", amount_usd=6_000.0),
            make_filing(filing_id="B", subject="Two", amount_usd=6_000.0),
        ]
        self.assertEqual(self.split_findings(group), [])

    def test_different_filing_types_do_not_aggregate(self):
        group = [
            make_filing(filing_id="A", amount_usd=6_000.0),
            make_filing(
                filing_id="B",
                filing_type=filings.FilingType.CTR_112,
                amount_usd=6_000.0,
                cyphers={"transaction_type": "A", "conductor_role": "01"},
            ),
        ]
        self.assertEqual(self.split_findings(group), [])

    def test_a_single_over_threshold_filing_is_not_a_split(self):
        group = [make_filing(filing_id="A", amount_usd=25_000.0)]
        self.assertEqual(self.split_findings(group), [])

    def test_group_with_only_one_sub_threshold_filing_is_not_a_split(self):
        group = [
            make_filing(filing_id="A", amount_usd=25_000.0, transaction_date="2025-03-01"),
            make_filing(filing_id="B", amount_usd=9_000.0, transaction_date="2025-03-04"),
        ]
        self.assertEqual(self.split_findings(group), [])


class ThresholdlessInstrumentTests(unittest.TestCase):
    def test_instrument_without_a_threshold_rule_raises_no_amount_findings(self):
        # Defensive branch: every shipped FilingType has a rule, so drop one to
        # confirm an instrument with no monetary threshold is simply skipped.
        original = dict(filings.REPORTING_THRESHOLDS)
        filings.REPORTING_THRESHOLDS.pop(filings.FilingType.FORM_926)
        try:
            filing = make_filing(
                filing_id="F926-1",
                filing_type=filings.FilingType.FORM_926,
                amount_usd=95_000.0,
                cyphers={"transfer_category": "CASH"},
            )
            found = codes_from(filings.FilingDiagnostician().diagnose([filing]))
            self.assertNotIn(filings.FindingCode.STRUCTURING_PROXIMITY, found)
            self.assertNotIn(filings.FindingCode.SUBTHRESHOLD_FILING, found)
            self.assertNotIn(filings.FindingCode.LATE_FILING, found)
        finally:
            filings.REPORTING_THRESHOLDS.clear()
            filings.REPORTING_THRESHOLDS.update(original)


class EvasionBridgeTests(unittest.TestCase):
    def test_findings_map_onto_declared_sanctions_typologies(self):
        sanctions = filings.load_sanctions_module()
        declared = {typology.name for typology in sanctions.EvasionTypology}
        mapped = {name for name, _ in filings.TYPOLOGY_BRIDGE.values()}
        mapped |= {name for name, _ in filings.SAR_INSTRUMENT_TYPOLOGY.values()}
        self.assertTrue(mapped <= declared, mapped - declared)

    def test_bridge_confidences_are_within_the_unit_interval(self):
        for _, confidence in list(filings.TYPOLOGY_BRIDGE.values()) + list(
            filings.SAR_INSTRUMENT_TYPOLOGY.values()
        ):
            self.assertTrue(0.0 <= confidence <= 1.0)

    def test_sar_instrument_code_emits_its_typology(self):
        diagnosis = filings.FilingDiagnosis()
        diagnosis.add(make_filing(
            filing_id="SAR-9",
            filing_type=filings.FilingType.SAR_111,
            amount_usd=90_000.0,
            cyphers={"activity_category": "ML", "instrument_involved": "BULL"},
        ))
        typologies = {signal["typology"] for signal in diagnosis.evasion_signals()}
        self.assertIn("GOLD_BULLION_FLIGHT", typologies)

    def test_unmapped_sar_instrument_emits_no_instrument_signal(self):
        diagnosis = filings.FilingDiagnosis()
        diagnosis.add(make_filing(
            filing_id="SAR-10",
            filing_type=filings.FilingType.SAR_111,
            amount_usd=90_000.0,
            cyphers={"activity_category": "ML", "instrument_involved": "NEG"},
        ))
        sources = [
            source
            for signal in diagnosis.evasion_signals()
            for source in signal["sources"]
        ]
        self.assertNotIn("irs-filing:SAR-10", sources)

    def test_signals_carry_filing_provenance(self):
        diagnosis = filings.build_demo_diagnosis()
        for signal in diagnosis.evasion_signals():
            self.assertTrue(signal["sources"])
            for source in signal["sources"]:
                self.assertTrue(source.startswith("irs-filing:"))

    def test_signals_build_real_sanctions_objects(self):
        sanctions = filings.load_sanctions_module()
        built = filings.build_demo_diagnosis().to_sanctions_signals()
        self.assertTrue(built)
        for signal in built:
            self.assertIsInstance(signal, sanctions.EvasionSignal)

    def test_diagnosed_filings_can_carry_a_case_into_an_actionable_tier(self):
        sanctions = filings.load_sanctions_module()
        case = sanctions.EvasionCase(
            case_id="SE-FILINGS-1",
            subject="Meridian Optics Trading FZE",
            target_regime="EMBARGOED-A",
        )
        for signal in filings.build_demo_diagnosis().to_sanctions_signals():
            case.add_signal(signal)
        self.assertGreater(case.score(), 0.0)
        self.assertIn(case.tier(), set(sanctions.CaseTier))


class DiagnosisReportTests(unittest.TestCase):
    def test_demo_report_is_json_serializable_and_internally_consistent(self):
        import json

        diagnosis = filings.build_demo_diagnosis()
        report = diagnosis.build_report()
        json.dumps(report)

        self.assertEqual(report["filings_reviewed"], len(report["filings"]))
        self.assertEqual(report["findings_total"], len(report["findings"]))
        self.assertEqual(
            report["findings_total"], sum(report["severity_counts"].values())
        )

    def test_findings_are_sorted_most_severe_first(self):
        findings = filings.build_demo_diagnosis().findings()
        ranks = [filings.SEVERITY_ORDER[finding.severity] for finding in findings]
        self.assertEqual(ranks, sorted(ranks))

    def test_demo_raises_the_expected_headline_findings(self):
        found = codes_from(filings.build_demo_diagnosis().findings())
        self.assertIn(filings.FindingCode.THRESHOLD_SPLIT, found)
        self.assertIn(filings.FindingCode.LATE_FILING, found)
        self.assertIn(filings.FindingCode.UNKNOWN_CYPHER, found)
        self.assertIn(filings.FindingCode.JURISDICTION_CONFLICT, found)

    def test_empty_diagnosis_reports_cleanly(self):
        diagnosis = filings.FilingDiagnosis()
        report = diagnosis.build_report()
        self.assertEqual(report["findings_total"], 0)
        self.assertEqual(report["evasion_signals"], [])


if __name__ == "__main__":
    unittest.main()

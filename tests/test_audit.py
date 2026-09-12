import importlib.machinery
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path


def load_audit_module():
    module_path = Path(__file__).resolve().parents[1] / "AUDIT"
    loader = importlib.machinery.SourceFileLoader("syntax_audit", str(module_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so dataclasses can resolve the module.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


audit = load_audit_module()


def make_da(opening=100_000.0, advances=50_000.0, spent=40_000.0, closing=110_000.0):
    return audit.DesignatedAccount(opening, advances, spent, closing)


def make_report(**kwargs):
    defaults = dict(
        project_id="P000001",
        period_start="2025-01-01",
        period_end="2025-03-31",
        submitted_date="2025-04-30",
        designated_account=make_da(),
        expenditures_by_category={"1": 40_000.0},
    )
    defaults.update(kwargs)
    return audit.InterimFinancialReport(**defaults)


def make_project(**kwargs):
    defaults = dict(project_id="P000001", name="Test Project", country="am")
    defaults.update(kwargs)
    project = audit.Project(**defaults)
    if not project.categories:
        project.add_category(audit.ExpenditureCategory("1", "Civil works", 1_000_000.0))
    return project


def codes_from(findings):
    return {finding.code for finding in findings}


class ModelTests(unittest.TestCase):
    def test_country_is_normalized(self):
        self.assertEqual(make_project().country, "AM")

    def test_designated_account_reconciliation_math(self):
        da = make_da(opening=100_000.0, advances=50_000.0, spent=40_000.0,
                     closing=110_000.0)
        self.assertEqual(da.expected_closing_usd, 110_000.0)
        self.assertEqual(da.reconciliation_gap_usd, 0.0)

    def test_submission_lag_is_days_past_period_end(self):
        report = make_report(period_end="2025-03-31", submitted_date="2025-05-15")
        self.assertEqual(report.submission_lag_days, 45)

    def test_period_start_after_end_is_rejected(self):
        with self.assertRaises(ValueError):
            make_report(period_start="2025-06-01", period_end="2025-03-31")

    def test_malformed_date_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            make_report(submitted_date="30/04/2025")

    def test_invalid_financing_percentage_is_rejected(self):
        with self.assertRaises(ValueError):
            audit.ExpenditureCategory("1", "Works", 100.0, financing_percentage=0.0)

    def test_negative_contract_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            audit.Contract("C-1", "S", "1", -5.0, "2025-01-01")


class DebarmentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.entry = audit.DebarmentEntry(
            name="Northbridge Civil Works Ltd",
            basis=audit.DebarmentBasis.COLLUSIVE_PRACTICE,
            from_date="2024-06-01",
            to_date="2027-06-01",
            cross_debarred=True,
        )
        self.registry = audit.DebarmentRegistry([self.entry])

    def test_normalization_ignores_punctuation_and_entity_suffixes(self):
        self.assertEqual(
            audit.DebarmentRegistry.normalize("Northbridge Civil Works, Ltd."),
            audit.DebarmentRegistry.normalize("northbridge civil works"),
        )

    def test_match_is_found_inside_the_debarment_period(self):
        hit = self.registry.match("northbridge civil works", date(2025, 2, 3))
        self.assertIs(hit, self.entry)

    def test_no_match_before_the_debarment_starts(self):
        self.assertIsNone(
            self.registry.match("Northbridge Civil Works Ltd", date(2024, 1, 1))
        )

    def test_no_match_after_the_debarment_ends(self):
        self.assertIsNone(
            self.registry.match("Northbridge Civil Works Ltd", date(2028, 1, 1))
        )

    def test_open_ended_debarment_stays_active(self):
        registry = audit.DebarmentRegistry([
            audit.DebarmentEntry(
                name="Permanent Exclusion SA",
                basis=audit.DebarmentBasis.FRAUDULENT_PRACTICE,
                from_date="2020-01-01",
            )
        ])
        self.assertIsNotNone(registry.match("Permanent Exclusion", date(2099, 1, 1)))

    def test_unrelated_supplier_does_not_match(self):
        self.assertIsNone(self.registry.match("Kestrel Infrastructure", date(2025, 2, 3)))

    def test_empty_supplier_name_does_not_match(self):
        self.assertIsNone(self.registry.match("   ", date(2025, 2, 3)))


class SplitDetectionTests(unittest.TestCase):
    def run_split(self, pairs, threshold=500_000.0, window=90):
        items = [
            audit.Contract(f"C-{i}", "S", "1", amount, day)
            for i, (amount, day) in enumerate(pairs)
        ]
        return audit.widest_qualifying_run(
            items,
            when=lambda c: c.signed_day,
            amount=lambda c: c.amount_usd,
            threshold=threshold,
            window_days=window,
        )

    def test_widest_run_is_returned(self):
        run = self.run_split([
            (180_000.0, "2025-01-14"),
            (195_000.0, "2025-02-11"),
            (165_000.0, "2025-03-18"),
        ])
        self.assertEqual([c.contract_id for c in run], ["C-0", "C-1", "C-2"])

    def test_items_outside_the_window_do_not_aggregate(self):
        self.assertEqual(
            self.run_split([(300_000.0, "2025-01-01"), (300_000.0, "2025-12-01")]), []
        )

    def test_an_over_threshold_item_is_excluded_from_runs(self):
        self.assertEqual(self.run_split([(900_000.0, "2025-01-01")]), [])

    def test_run_below_threshold_does_not_qualify(self):
        self.assertEqual(
            self.run_split([(100_000.0, "2025-01-01"), (100_000.0, "2025-01-15")]), []
        )

    def test_empty_input_is_handled(self):
        self.assertEqual(self.run_split([]), [])


class InterimAuditCheckTests(unittest.TestCase):
    def setUp(self):
        self.system = audit.InterimAuditSystem()

    def audit_with(self, project):
        return self.system.audit(project)

    def test_clean_project_raises_nothing(self):
        project = make_project()
        project.add_report(make_report())
        self.assertEqual(self.audit_with(project), [])

    def test_late_ifr_is_flagged_and_escalates(self):
        project = make_project()
        project.add_report(make_report(submitted_date="2025-06-20"))
        late = [
            f for f in self.audit_with(project)
            if f.code is audit.FindingCode.LATE_IFR_SUBMISSION
        ]
        self.assertEqual(late[0].severity, audit.Severity.HIGH)

    def test_ifr_inside_the_window_is_not_late(self):
        project = make_project()
        project.add_report(make_report(period_end="2025-03-31",
                                       submitted_date="2025-05-15"))
        self.assertNotIn(
            audit.FindingCode.LATE_IFR_SUBMISSION, codes_from(self.audit_with(project))
        )

    def test_unreconciled_designated_account_is_critical(self):
        project = make_project()
        project.add_report(make_report(designated_account=make_da(closing=188_000.0)))
        da = [
            f for f in self.audit_with(project)
            if f.code is audit.FindingCode.DA_UNRECONCILED
        ]
        self.assertEqual(da[0].severity, audit.Severity.CRITICAL)
        self.assertEqual(da[0].amount_usd, 78_000.0)

    def test_rounding_noise_does_not_break_reconciliation(self):
        project = make_project()
        project.add_report(make_report(designated_account=make_da(closing=110_000.5)))
        self.assertNotIn(
            audit.FindingCode.DA_UNRECONCILED, codes_from(self.audit_with(project))
        )

    def test_expenditure_outside_the_agreement_is_flagged(self):
        project = make_project()
        project.add_report(make_report(expenditures_by_category={"9": 35_000.0}))
        self.assertIn(
            audit.FindingCode.UNDISCLOSED_CATEGORY, codes_from(self.audit_with(project))
        )

    def test_ineligible_category_spend_is_critical(self):
        project = make_project()
        project.add_category(audit.ExpenditureCategory("4", "Land", 0.0, eligible=False))
        project.add_report(make_report(expenditures_by_category={"4": 85_000.0}))
        findings = self.audit_with(project)
        ineligible = [
            f for f in findings if f.code is audit.FindingCode.INELIGIBLE_EXPENDITURE
        ]
        self.assertEqual(ineligible[0].severity, audit.Severity.CRITICAL)

    def test_ineligible_spend_is_not_double_reported_as_an_overrun(self):
        project = make_project()
        project.add_category(audit.ExpenditureCategory("4", "Land", 0.0, eligible=False))
        project.add_report(make_report(expenditures_by_category={"4": 85_000.0}))
        self.assertNotIn(
            audit.FindingCode.CATEGORY_OVERRUN, codes_from(self.audit_with(project))
        )

    def test_cumulative_overrun_counts_prior_periods(self):
        project = make_project(cumulative_by_category={"1": 980_000.0})
        project.add_report(make_report(expenditures_by_category={"1": 40_000.0}))
        overrun = [
            f for f in self.audit_with(project)
            if f.code is audit.FindingCode.CATEGORY_OVERRUN
        ]
        self.assertEqual(overrun[0].amount_usd, 20_000.0)

    def test_financing_percentage_ceiling_is_enforced(self):
        project = make_project()
        project.add_category(audit.ExpenditureCategory(
            "2", "Goods", 100_000.0, financing_percentage=80.0
        ))
        project.add_report(make_report(expenditures_by_category={"2": 90_000.0}))
        self.assertIn(
            audit.FindingCode.FINANCING_PERCENTAGE_BREACH,
            codes_from(self.audit_with(project)),
        )

    def test_fully_financed_category_has_no_percentage_breach(self):
        project = make_project()
        project.add_report(make_report(expenditures_by_category={"1": 900_000.0}))
        self.assertNotIn(
            audit.FindingCode.FINANCING_PERCENTAGE_BREACH,
            codes_from(self.audit_with(project)),
        )

    def test_soe_above_the_ceiling_is_flagged(self):
        project = make_project()
        project.add_report(make_report(
            expenditures_by_category={"1": 100_000.0}, soe_total_usd=30_000.0
        ))
        self.assertIn(
            audit.FindingCode.SOE_CEILING_EXCEEDED, codes_from(self.audit_with(project))
        )

    def test_soe_within_the_ceiling_is_not_flagged(self):
        project = make_project()
        project.add_report(make_report(
            expenditures_by_category={"1": 100_000.0}, soe_total_usd=15_000.0
        ))
        self.assertNotIn(
            audit.FindingCode.SOE_CEILING_EXCEEDED, codes_from(self.audit_with(project))
        )

    def test_forecast_variance_beyond_tolerance_is_flagged(self):
        project = make_project()
        project.add_report(make_report(
            expenditures_by_category={"1": 40_000.0},
            forecast_by_category={"1": 100_000.0},
        ))
        self.assertIn(
            audit.FindingCode.FORECAST_VARIANCE_BREACH,
            codes_from(self.audit_with(project)),
        )

    def test_forecast_within_tolerance_is_not_flagged(self):
        project = make_project()
        project.add_report(make_report(
            expenditures_by_category={"1": 95_000.0},
            forecast_by_category={"1": 100_000.0},
        ))
        self.assertNotIn(
            audit.FindingCode.FORECAST_VARIANCE_BREACH,
            codes_from(self.audit_with(project)),
        )

    def test_zero_forecast_does_not_divide_by_zero(self):
        project = make_project()
        project.add_report(make_report(
            expenditures_by_category={"1": 40_000.0},
            forecast_by_category={"1": 0.0},
        ))
        self.assertNotIn(
            audit.FindingCode.FORECAST_VARIANCE_BREACH,
            codes_from(self.audit_with(project)),
        )

    def test_modified_opinion_severity_tracks_the_opinion_type(self):
        qualified = make_project(audit_opinion=audit.OpinionType.QUALIFIED)
        disclaimed = make_project(audit_opinion=audit.OpinionType.DISCLAIMER)
        self.assertEqual(
            self.audit_with(qualified)[0].severity, audit.Severity.HIGH
        )
        self.assertEqual(
            self.audit_with(disclaimed)[0].severity, audit.Severity.CRITICAL
        )

    def test_unmodified_opinion_raises_nothing(self):
        project = make_project(audit_opinion=audit.OpinionType.UNMODIFIED)
        self.assertNotIn(
            audit.FindingCode.MODIFIED_AUDIT_OPINION, codes_from(self.audit_with(project))
        )


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        self.registry = audit.DebarmentRegistry([
            audit.DebarmentEntry(
                name="Northbridge Civil Works Ltd",
                basis=audit.DebarmentBasis.COLLUSIVE_PRACTICE,
                from_date="2024-06-01",
                cross_debarred=True,
            )
        ])
        self.system = audit.InterimAuditSystem(registry=self.registry)

    def test_debarred_supplier_is_critical(self):
        project = make_project()
        project.add_contract(audit.Contract(
            "CW-201", "Northbridge Civil Works Ltd", "1", 640_000.0,
            "2025-02-03", prior_reviewed=True,
        ))
        debarred = [
            f for f in self.system.audit(project)
            if f.code is audit.FindingCode.DEBARRED_COUNTERPARTY
        ]
        self.assertEqual(debarred[0].severity, audit.Severity.CRITICAL)
        self.assertIn("cross-debarred", debarred[0].detail)

    def test_prior_reviewed_large_contract_raises_no_bypass(self):
        project = make_project()
        project.add_contract(audit.Contract(
            "GD-1", "Clean Supplier", "1", 900_000.0, "2025-02-03", prior_reviewed=True
        ))
        self.assertNotIn(
            audit.FindingCode.PRIOR_REVIEW_BYPASS, codes_from(self.system.audit(project))
        )

    def test_large_contract_without_prior_review_is_flagged(self):
        project = make_project()
        project.add_contract(audit.Contract(
            "GD-2", "Clean Supplier", "1", 720_000.0, "2025-02-03",
            method=audit.ProcurementMethod.DIRECT,
        ))
        self.assertIn(
            audit.FindingCode.PRIOR_REVIEW_BYPASS, codes_from(self.system.audit(project))
        )

    def test_limited_competition_just_under_threshold_is_flagged(self):
        project = make_project()
        project.add_contract(audit.Contract(
            "GD-3", "Clean Supplier", "1", 460_000.0, "2025-02-03",
            method=audit.ProcurementMethod.DIRECT,
        ))
        findings = [
            f for f in self.system.audit(project)
            if f.code is audit.FindingCode.PRIOR_REVIEW_BYPASS
        ]
        self.assertEqual(findings[0].severity, audit.Severity.MEDIUM)

    def test_open_competition_just_under_threshold_is_not_flagged(self):
        project = make_project()
        project.add_contract(audit.Contract(
            "GD-4", "Clean Supplier", "1", 460_000.0, "2025-02-03",
            method=audit.ProcurementMethod.RFB,
        ))
        self.assertNotIn(
            audit.FindingCode.PRIOR_REVIEW_BYPASS, codes_from(self.system.audit(project))
        )

    def test_splitting_is_grouped_by_supplier_and_category(self):
        project = make_project()
        project.add_category(audit.ExpenditureCategory("2", "Goods", 1_000_000.0))
        for index, (supplier, category) in enumerate(
            [("A Co", "1"), ("B Co", "1"), ("A Co", "2")], start=1
        ):
            project.add_contract(audit.Contract(
                f"C-{index}", supplier, category, 300_000.0, "2025-01-10"
            ))
        self.assertNotIn(
            audit.FindingCode.CONTRACT_SPLITTING, codes_from(self.system.audit(project))
        )

    def test_same_supplier_and_category_splits_are_flagged(self):
        project = make_project()
        for index, day in enumerate(["2025-01-14", "2025-02-11", "2025-03-18"], start=1):
            project.add_contract(audit.Contract(
                f"CW-{index}", "Kestrel Infrastructure LLC", "1", 185_000.0, day,
                method=audit.ProcurementMethod.RFQ,
            ))
        split = [
            f for f in self.system.audit(project)
            if f.code is audit.FindingCode.CONTRACT_SPLITTING
        ]
        self.assertEqual(len(split), 1)
        self.assertEqual(len(split[0].references), 3)
        self.assertEqual(split[0].severity, audit.Severity.CRITICAL)


class RiskRatingTests(unittest.TestCase):
    def finding(self, severity):
        return audit.AuditFinding(
            code=audit.FindingCode.LATE_IFR_SUBMISSION,
            severity=severity,
            detail="test",
            project_id="P1",
        )

    def test_no_findings_is_low_risk(self):
        self.assertIs(audit.rate_risk([]), audit.RiskRating.LOW)

    def test_one_critical_carries_to_high(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.CRITICAL)]),
            audit.RiskRating.HIGH,
        )

    def test_three_highs_carry_to_high(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.HIGH)] * 3),
            audit.RiskRating.HIGH,
        )

    def test_one_high_is_substantial(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.HIGH)]),
            audit.RiskRating.SUBSTANTIAL,
        )

    def test_volume_of_mediums_escalates_to_substantial(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.MEDIUM)] * 3),
            audit.RiskRating.SUBSTANTIAL,
        )

    def test_single_medium_is_moderate(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.MEDIUM)]),
            audit.RiskRating.MODERATE,
        )

    def test_isolated_low_stays_low(self):
        self.assertIs(
            audit.rate_risk([self.finding(audit.Severity.LOW)]), audit.RiskRating.LOW
        )


class EvasionBridgeTests(unittest.TestCase):
    def test_bridge_targets_are_declared_sanctions_typologies(self):
        sanctions = audit.load_sanctions_module()
        declared = {typology.name for typology in sanctions.EvasionTypology}
        mapped = {name for name, _ in audit.TYPOLOGY_BRIDGE.values()}
        self.assertTrue(mapped <= declared, mapped - declared)

    def test_bridge_confidences_are_within_the_unit_interval(self):
        for _, confidence in audit.TYPOLOGY_BRIDGE.values():
            self.assertTrue(0.0 <= confidence <= 1.0)

    def test_signals_carry_project_provenance(self):
        for signal in audit.build_demo_portfolio().evasion_signals():
            self.assertTrue(signal["sources"])
            for source in signal["sources"]:
                self.assertTrue(source.startswith("wb-audit:"))

    def test_debarment_produces_a_procurement_typology(self):
        typologies = {
            signal["typology"]
            for signal in audit.build_demo_portfolio().evasion_signals()
        }
        self.assertIn("FRONT_PROCUREMENT_NETWORK", typologies)
        self.assertIn("SHELL_LAYERING", typologies)

    def test_signals_build_real_sanctions_objects(self):
        sanctions = audit.load_sanctions_module()
        built = audit.build_demo_portfolio().to_sanctions_signals()
        self.assertTrue(built)
        for signal in built:
            self.assertIsInstance(signal, sanctions.EvasionSignal)

    def test_audit_signals_can_carry_a_case_into_an_actionable_tier(self):
        sanctions = audit.load_sanctions_module()
        case = sanctions.EvasionCase(
            case_id="SE-AUDIT-1", subject="P178220", target_regime="N/A"
        )
        for signal in audit.build_demo_portfolio().to_sanctions_signals():
            case.add_signal(signal)
        self.assertGreater(case.score(), 0.0)
        self.assertIn(case.tier(), set(sanctions.CaseTier))


class PortfolioReportTests(unittest.TestCase):
    def test_demo_report_is_json_serializable_and_consistent(self):
        import json

        report = audit.build_demo_portfolio().build_report()
        json.dumps(report)

        self.assertEqual(report["projects_reviewed"], len(report["projects"]))
        for entry in report["projects"]:
            self.assertEqual(entry["findings_total"], len(entry["findings"]))
            self.assertEqual(
                entry["findings_total"], sum(entry["severity_counts"].values())
            )

    def test_demo_project_rates_high_risk(self):
        report = audit.build_demo_portfolio().build_report()
        self.assertEqual(report["projects"][0]["risk_rating"], "High")
        self.assertEqual(report["high_risk_projects"], 1)

    def test_findings_are_sorted_most_severe_first(self):
        portfolio = audit.build_demo_portfolio()
        findings = portfolio.findings_for(portfolio.projects[0])
        ranks = [audit.SEVERITY_ORDER[f.severity] for f in findings]
        self.assertEqual(ranks, sorted(ranks))

    def test_demo_raises_the_expected_headline_findings(self):
        portfolio = audit.build_demo_portfolio()
        found = codes_from(portfolio.findings_for(portfolio.projects[0]))
        for expected in (
            audit.FindingCode.DEBARRED_COUNTERPARTY,
            audit.FindingCode.CONTRACT_SPLITTING,
            audit.FindingCode.DA_UNRECONCILED,
            audit.FindingCode.INELIGIBLE_EXPENDITURE,
            audit.FindingCode.UNDISCLOSED_CATEGORY,
            audit.FindingCode.LATE_IFR_SUBMISSION,
        ):
            self.assertIn(expected, found)

    def test_empty_portfolio_reports_cleanly(self):
        report = audit.AuditPortfolio().build_report()
        self.assertEqual(report["projects_reviewed"], 0)
        self.assertEqual(report["findings_total"], 0)
        self.assertEqual(report["evasion_signals"], [])


if __name__ == "__main__":
    unittest.main()

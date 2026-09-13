import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path


def load_sanctions_module():
    module_path = Path(__file__).resolve().parents[1] / "SANCTIONS"
    loader = importlib.machinery.SourceFileLoader("syntax_sanctions", str(module_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so dataclasses can resolve the module.
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


sanctions = load_sanctions_module()


def build_case(case_id="SE-TEST-1", signals=()):
    case = sanctions.EvasionCase(
        case_id=case_id,
        subject="Test subject",
        target_regime="EMBARGOED-A",
    )
    for signal in signals:
        case.add_signal(signal)
    return case


def signal(typology, confidence=0.8, jurisdiction="AE", sources=("src-a",), value=None):
    return sanctions.EvasionSignal(
        typology=typology,
        description="test signal",
        jurisdiction=jurisdiction,
        confidence=confidence,
        sources=list(sources),
        value_usd=value,
    )


def elevated_case(case_id="SE-TEST-ELEV"):
    return build_case(case_id, [
        signal(sanctions.EvasionTypology.DUAL_USE_REEXPORT, 0.85, "AE", ("customs", "manifest"), 4_200_000),
        signal(sanctions.EvasionTypology.FRONT_PROCUREMENT_NETWORK, 0.75, "TR", ("registry", "customs")),
        signal(sanctions.EvasionTypology.CORRESPONDENT_BANK_NESTING, 0.65, "AE", ("swift",), 3_100_000),
        signal(sanctions.EvasionTypology.TRADE_MISINVOICING, 0.60, "TR", ("price-ref",), 900_000),
    ])


class EvasionScoringTests(unittest.TestCase):
    def test_empty_case_scores_zero_and_tiers_as_noise(self):
        case = build_case()
        self.assertEqual(case.score(), 0.0)
        self.assertIs(case.tier(), sanctions.CaseTier.NOISE)

    def test_single_signal_cannot_reach_an_actionable_tier(self):
        case = build_case(signals=[
            signal(sanctions.EvasionTypology.DUAL_USE_REEXPORT, 1.0),
        ])
        self.assertNotIn(case.tier(), sanctions.ACTIONABLE_TIERS)

    def test_breadth_and_corroboration_raise_the_score(self):
        narrow = build_case("narrow", [
            signal(sanctions.EvasionTypology.DUAL_USE_REEXPORT, 0.8, sources=("src-a",)),
            signal(sanctions.EvasionTypology.DUAL_USE_REEXPORT, 0.8, sources=("src-a",)),
        ])
        broad = build_case("broad", [
            signal(sanctions.EvasionTypology.DUAL_USE_REEXPORT, 0.8, sources=("src-a",)),
            signal(sanctions.EvasionTypology.FRONT_PROCUREMENT_NETWORK, 0.8, sources=("src-b",)),
        ])
        self.assertGreater(broad.score(), narrow.score())

    def test_score_is_capped_at_one_hundred(self):
        case = build_case(signals=[
            signal(typology, 1.0, sources=(f"src-{index}",))
            for index, typology in enumerate(sanctions.EvasionTypology)
        ])
        self.assertLessEqual(case.score(), 100.0)
        self.assertIs(case.tier(), sanctions.CaseTier.ACUTE)

    def test_confidence_outside_unit_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            signal(sanctions.EvasionTypology.SHELL_LAYERING, 1.4)

    def test_case_aggregates_exposure_and_jurisdictions(self):
        case = elevated_case()
        self.assertEqual(case.exposure_usd, 8_200_000)
        self.assertEqual(case.jurisdictions, {"AE", "TR"})


class MonetaryEthnographyTests(unittest.TestCase):
    def test_parallel_premium_is_a_ratio_over_the_official_rate(self):
        observation = sanctions.MonetaryObservation(
            site="site", country="ua", official_rate=1.0, parallel_rate=1.5,
        )
        self.assertAlmostEqual(observation.parallel_premium, 0.5)
        self.assertEqual(observation.country, "UA")

    def test_barter_share_dominates_the_classification(self):
        observation = sanctions.MonetaryObservation(
            site="site", country="AM", official_rate=1.0, parallel_rate=2.0,
            dollarization_ratio=0.9, barter_share=0.4,
        )
        self.assertIs(observation.classify(), sanctions.MonetaryRegime.BARTER_REVERSION)

    def test_regime_ladder_selects_the_expected_bands(self):
        def regime(**kwargs):
            defaults = dict(site="s", country="XX", official_rate=1.0, parallel_rate=1.0)
            defaults.update(kwargs)
            return sanctions.MonetaryObservation(**defaults).classify()

        self.assertIs(regime(), sanctions.MonetaryRegime.STABLE_FIAT)
        self.assertIs(regime(dollarization_ratio=0.4), sanctions.MonetaryRegime.SOFT_DOLLARIZATION)
        self.assertIs(regime(dollarization_ratio=0.8), sanctions.MonetaryRegime.HARD_DOLLARIZATION)
        self.assertIs(regime(parallel_rate=1.6), sanctions.MonetaryRegime.PARALLEL_MARKET_DOMINANT)
        self.assertIs(regime(crypto_settlement_share=0.3), sanctions.MonetaryRegime.CRYPTO_SUBSTITUTION)
        self.assertIs(regime(scrip_in_circulation=True), sanctions.MonetaryRegime.SCRIP_AND_COUPON)

    def test_stress_index_is_bounded_and_monotonic_in_premium(self):
        calm = sanctions.MonetaryObservation(
            site="s", country="XX", official_rate=1.0, parallel_rate=1.0,
        )
        strained = sanctions.MonetaryObservation(
            site="s", country="XX", official_rate=1.0, parallel_rate=3.0,
        )
        self.assertGreaterEqual(calm.stress_index(), 0.0)
        self.assertLessEqual(strained.stress_index(), 100.0)
        self.assertGreater(strained.stress_index(), calm.stress_index())

    def test_field_note_reports_the_regime_and_observed_practice(self):
        observation = sanctions.MonetaryObservation(
            site="Market", country="AM", official_rate=1.0, parallel_rate=2.0,
            barter_share=0.35, remittance_dependency=0.5,
            practices=["diesel functions as the unit of account"],
        )
        note = observation.field_note()
        self.assertIn("barter reversion", note)
        self.assertIn("diesel functions as the unit of account", note)
        self.assertIn("remittance-dependent", note)

    def test_negative_rates_are_rejected(self):
        with self.assertRaises(ValueError):
            sanctions.MonetaryObservation(
                site="s", country="XX", official_rate=0.0, parallel_rate=1.0,
            )

    def test_every_ratio_field_is_bounds_checked(self):
        for name in (
            "dollarization_ratio",
            "barter_share",
            "crypto_settlement_share",
            "remittance_dependency",
        ):
            for bad in (-0.1, 1.1):
                with self.subTest(field=name, value=bad):
                    with self.assertRaises(ValueError):
                        sanctions.MonetaryObservation(
                            site="s", country="XX", official_rate=1.0,
                            parallel_rate=1.0, **{name: bad},
                        )


class AllianceRegistryTests(unittest.TestCase):
    def test_member_state_resolves_to_member(self):
        relation = sanctions.AllianceRegistry.relation(sanctions.Alliance.NATO, "de")
        self.assertIs(relation, sanctions.Relation.MEMBER)

    def test_partner_bloc_resolves_to_partner(self):
        relation = sanctions.AllianceRegistry.relation(sanctions.Alliance.NATO, "AE")
        self.assertIs(relation, sanctions.Relation.PARTNER)

    def test_unlisted_state_resolves_to_neutral(self):
        relation = sanctions.AllianceRegistry.relation(sanctions.Alliance.NATO, "ZW")
        self.assertIs(relation, sanctions.Relation.NEUTRAL)
        self.assertEqual(
            sanctions.AllianceRegistry.alliances_of("ZW"),
            [sanctions.Alliance.NON_ALIGNED],
        )

    def test_dual_membership_takes_the_most_restrictive_standing(self):
        # BY sits in both CSTO (adversarial to NATO) and SCO (contested).
        self.assertIn(
            sanctions.Alliance.SCO, sanctions.AllianceRegistry.alliances_of("BY")
        )
        relation = sanctions.AllianceRegistry.relation(sanctions.Alliance.NATO, "BY")
        self.assertIs(relation, sanctions.Relation.ADVERSARIAL)


class SinkholeAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.authority = sanctions.SinkholeAuthority()
        self.case = elevated_case()

    def request(self, **kwargs):
        defaults = dict(
            indicator="node.example",
            hosting_jurisdiction="DE",
            registrar_jurisdiction="US",
            requesting_alliance=sanctions.Alliance.NATO,
        )
        defaults.update(kwargs)
        return sanctions.SinkholeRequest(**defaults)

    def test_low_scoring_case_is_held_regardless_of_jurisdiction(self):
        weak = build_case("weak", [signal(sanctions.EvasionTypology.HAWALA_SETTLEMENT, 0.3)])
        decision = self.authority.evaluate(weak, self.request())
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.HELD_INSUFFICIENT_EVIDENCE)
        self.assertFalse(decision.approved)

    def test_member_jurisdiction_is_authorized_with_conditions(self):
        decision = self.authority.evaluate(self.case, self.request())
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.AUTHORIZED)
        self.assertTrue(decision.approved)
        self.assertTrue(decision.conditions)

    def test_partner_jurisdiction_requires_coalition_concurrence(self):
        decision = self.authority.evaluate(
            self.case, self.request(hosting_jurisdiction="AE", registrar_jurisdiction="AE")
        )
        self.assertIs(
            decision.outcome,
            sanctions.SinkholeOutcome.AUTHORIZED_WITH_COALITION_CONCURRENCE,
        )
        self.assertTrue(decision.approved)

    def test_neutral_jurisdiction_goes_to_legal_process(self):
        decision = self.authority.evaluate(
            self.case, self.request(hosting_jurisdiction="ZW", registrar_jurisdiction="ZW")
        )
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.REFERRED_TO_LEGAL_PROCESS)

    def test_adversarial_jurisdiction_is_denied(self):
        decision = self.authority.evaluate(
            self.case, self.request(hosting_jurisdiction="RU", registrar_jurisdiction="RU")
        )
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.DENIED_JURISDICTION)
        self.assertIs(decision.relation, sanctions.Relation.ADVERSARIAL)

    def test_member_registrar_opens_a_registry_path_for_denied_hosting(self):
        decision = self.authority.evaluate(
            self.case, self.request(hosting_jurisdiction="RU", registrar_jurisdiction="US")
        )
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.REFERRED_TO_LEGAL_PROCESS)
        self.assertTrue(
            any("registrar" in condition.lower() for condition in decision.conditions)
        )

    def test_humanitarian_exposure_outranks_a_friendly_jurisdiction(self):
        decision = self.authority.evaluate(
            self.case, self.request(civilian_payment_share=0.4)
        )
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.DENIED_HUMANITARIAN)
        self.assertFalse(decision.approved)

    def test_cleared_humanitarian_review_restores_the_jurisdiction_path(self):
        decision = self.authority.evaluate(
            self.case,
            self.request(civilian_payment_share=0.4, humanitarian_review_cleared=True),
        )
        self.assertIs(decision.outcome, sanctions.SinkholeOutcome.AUTHORIZED)

    def test_civilian_share_outside_unit_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            self.request(civilian_payment_share=1.7)


class TrackerTests(unittest.TestCase):
    def test_unknown_case_cannot_be_sinkholed(self):
        tracker = sanctions.SanctionsEvasionTracker()
        with self.assertRaises(KeyError):
            tracker.request_sinkhole("missing", sanctions.SinkholeRequest(
                indicator="x.example",
                hosting_jurisdiction="DE",
                registrar_jurisdiction="DE",
                requesting_alliance=sanctions.Alliance.NATO,
            ))

    def test_cases_are_prioritized_by_score(self):
        tracker = sanctions.SanctionsEvasionTracker()
        tracker.track(build_case("weak", [signal(sanctions.EvasionTypology.HAWALA_SETTLEMENT, 0.2)]))
        tracker.track(elevated_case("strong"))
        self.assertEqual(
            [case.case_id for case in tracker.prioritized_cases()], ["strong", "weak"]
        )

    def test_ethnographic_corroboration_only_counts_touched_jurisdictions(self):
        tracker = sanctions.SanctionsEvasionTracker()
        case = tracker.track(elevated_case())
        tracker.observe(sanctions.MonetaryObservation(
            site="off-case site", country="ZW", official_rate=1.0, parallel_rate=2.0,
        ))
        self.assertEqual(tracker.corroborated_by_ethnography(case), [])

        tracker.observe(sanctions.MonetaryObservation(
            site="on-case site", country="AE", official_rate=1.0, parallel_rate=1.4,
            dollarization_ratio=0.6,
        ))
        corroborated = tracker.corroborated_by_ethnography(case)
        self.assertIn(sanctions.EvasionTypology.TRADE_MISINVOICING, corroborated)

    def test_demo_report_is_json_serializable_and_counts_agree(self):
        tracker = sanctions.build_demo_tracker()
        report = tracker.build_report()

        import json
        json.dumps(report)

        self.assertEqual(report["tracked_cases"], len(report["cases"]))
        self.assertEqual(report["sinkhole_decisions"], len(report["decisions"]))
        self.assertEqual(
            report["sinkhole_approved"],
            sum(1 for decision in report["decisions"] if decision["approved"]),
        )
        self.assertGreaterEqual(report["actionable_cases"], 1)


if __name__ == "__main__":
    unittest.main()

import unittest

import main as rfqdiff


class DecisionExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quotes = [
            {
                "name": "Supplier A",
                "currency": "EUR",
                "price": 84200,
                "lead_time_weeks": 8,
                "payment_days": 30,
            },
            {
                "name": "Supplier B",
                "currency": "EUR",
                "price": 79400,
                "lead_time_weeks": 14,
                "payment_days": 0,
            },
        ]

    def test_score_breakdown_exposes_weighted_criterion_contributions(self) -> None:
        scored = rfqdiff.score_quotes(self.quotes)
        winner = scored[0]
        runner_up = scored[1]

        self.assertEqual(winner["name"], "Supplier A")
        self.assertEqual(
            winner["score_breakdown"],
            {"price": 47.1, "lead_time": 30.0, "payment_terms": 20.0},
        )
        self.assertEqual(winner["score"], 97.1)

        self.assertEqual(runner_up["name"], "Supplier B")
        self.assertEqual(
            runner_up["score_breakdown"],
            {"price": 50.0, "lead_time": 17.1, "payment_terms": 0.0},
        )
        self.assertEqual(runner_up["score"], 67.1)

    def test_build_result_explains_winner_runner_up_and_margin(self) -> None:
        scored = rfqdiff.score_quotes(self.quotes)
        payload = rfqdiff.build_result(scored, "EUR")
        summary = payload["decision_summary"]
        explanation = payload["decision_explanation"]

        self.assertEqual(summary["recommended_supplier"], {"name": "Supplier A", "score": 97.1})
        self.assertEqual(summary["runner_up"], {"name": "Supplier B", "score": 67.1})
        self.assertEqual(summary["score_margin"], 30.0)

        self.assertEqual(explanation["winner"], "Supplier A")
        self.assertEqual(explanation["runner_up"], "Supplier B")
        self.assertEqual(explanation["score_margin"], 30.0)
        self.assertEqual(
            explanation["winner_score_breakdown"],
            {"price": 47.1, "lead_time": 30.0, "payment_terms": 20.0},
        )
        self.assertEqual(
            explanation["criterion_leaders"],
            {
                "price": "Supplier B",
                "lead_time": "Supplier A",
                "payment_terms": "Supplier A",
            },
        )

    def test_custom_weights_are_reflected_in_score_breakdown(self) -> None:
        weights = {"price": 0.2, "lead_time": 0.2, "payment_terms": 0.6}
        scored = rfqdiff.score_quotes(self.quotes, weights)
        supplier_a = next(item for item in scored if item["name"] == "Supplier A")

        self.assertEqual(
            supplier_a["score_breakdown"],
            {"price": 18.9, "lead_time": 20.0, "payment_terms": 60.0},
        )
        self.assertEqual(supplier_a["score"], 98.9)

    def test_single_supplier_result_has_no_runner_up_or_margin(self) -> None:
        quote = [
            {
                "name": "Supplier A",
                "currency": "EUR",
                "price": 100,
                "lead_time_weeks": 4,
                "payment_days": 30,
            }
        ]
        scored = rfqdiff.score_quotes(quote)
        payload = rfqdiff.build_result(scored, "EUR")

        self.assertIsNone(payload["decision_summary"]["runner_up"])
        self.assertIsNone(payload["decision_summary"]["score_margin"])
        self.assertIsNone(payload["decision_explanation"]["runner_up"])
        self.assertIsNone(payload["decision_explanation"]["score_margin"])


if __name__ == "__main__":
    unittest.main()

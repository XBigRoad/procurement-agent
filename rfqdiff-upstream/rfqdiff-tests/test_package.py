import tempfile
import unittest
from pathlib import Path

import rfqdiff


class PackageTests(unittest.TestCase):
    def test_public_version(self):
        self.assertEqual(rfqdiff.__version__, "0.2.0")
        self.assertEqual(rfqdiff.VERSION, "0.2")

    def test_public_scoring_api(self):
        quotes = [
            {"name": "A", "currency": "EUR", "price": 100, "lead_time_weeks": 4, "payment_days": 30},
            {"name": "B", "currency": "EUR", "price": 120, "lead_time_weeks": 5, "payment_days": 0},
        ]
        scored = rfqdiff.score_quotes(quotes)
        self.assertEqual(scored[0]["name"], "A")

    def test_public_tabular_loading_api(self):
        csv_content = (
            "name,currency,price,lead_time_weeks,payment_days\n"
            "A,EUR,100,4,30\n"
            "B,EUR,120,5,0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.csv"
            path.write_text(csv_content, encoding="utf-8")
            quotes = rfqdiff.load_quotes(path)

        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0]["name"], "A")

    def test_public_report_export_api(self):
        quotes = [
            {"name": "A", "currency": "EUR", "price": 100, "lead_time_weeks": 4, "payment_days": 30},
            {"name": "B", "currency": "EUR", "price": 120, "lead_time_weeks": 5, "payment_days": 0},
        ]
        scored = rfqdiff.score_quotes(quotes)
        payload = rfqdiff.build_result(scored, "EUR")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comparison.csv"
            rfqdiff.write_report(payload, path)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

import main as rfqdiff


class LoadQuoteTests(unittest.TestCase):
    def test_load_quote_accepts_valid_input(self) -> None:
        quote = {
            "name": "Supplier A",
            "currency": "EUR",
            "price": 100,
            "lead_time_weeks": 4,
            "payment_days": 30,
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quote.json"
            path.write_text(json.dumps(quote), encoding="utf-8")
            loaded = rfqdiff.load_quote(path)

        self.assertEqual(loaded["name"], quote["name"])
        self.assertEqual(loaded["currency"], quote["currency"])
        self.assertEqual(loaded["price"], quote["price"])
        self.assertEqual(loaded["lead_time_weeks"], quote["lead_time_weeks"])
        self.assertEqual(loaded["payment_days"], quote["payment_days"])
        self.assertEqual(loaded["rfqdiff_source"]["format"], "json")

    def test_load_quote_accepts_currency_normalizer_metadata(self) -> None:
        quote = {
            "name": "Supplier A",
            "currency": "EUR",
            "price": 100,
            "lead_time_weeks": 4,
            "payment_days": 30,
            "normalization": {
                "tool": "currency-normalizer",
                "original_currency": "USD",
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quote.json"
            path.write_text(json.dumps(quote), encoding="utf-8")
            loaded = rfqdiff.load_quote(path)

        self.assertEqual(loaded["normalization"]["tool"], "currency-normalizer")

    def test_load_quote_rejects_missing_required_field(self) -> None:
        quote = {
            "name": "Supplier A",
            "currency": "EUR",
            "price": 100,
            "lead_time_weeks": 4,
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quote.json"
            path.write_text(json.dumps(quote), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "payment_days"):
                rfqdiff.load_quote(path)

    def test_load_csv_quotes_accepts_multiple_suppliers(self) -> None:
        csv_content = (
            "name,currency,price,lead_time_weeks,payment_days\n"
            "Supplier A,eur,84200,8,30\n"
            "Supplier B,EUR,79400,14,0\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.csv"
            path.write_text(csv_content, encoding="utf-8")
            loaded = rfqdiff.load_quotes(path)

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["name"], "Supplier A")
        self.assertEqual(loaded[0]["currency"], "EUR")
        self.assertEqual(loaded[0]["price"], 84200)
        self.assertEqual(loaded[1]["payment_days"], 0)

    def test_load_xlsx_quotes_accepts_multiple_suppliers(self) -> None:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(
                ["name", "currency", "price", "lead_time_weeks", "payment_days"]
            )
            worksheet.append(["Supplier A", "EUR", 84200, 8, 30])
            worksheet.append(["Supplier B", "EUR", 79400, 14, 0])
            workbook.save(path)
            workbook.close()

            loaded = rfqdiff.load_quotes(path)

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[1]["name"], "Supplier B")
        self.assertEqual(loaded[1]["price"], 79400)

    def test_load_tabular_quotes_rejects_missing_required_column(self) -> None:
        csv_content = (
            "name,currency,price,lead_time_weeks\n"
            "Supplier A,EUR,84200,8\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.csv"
            path.write_text(csv_content, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "payment_days"):
                rfqdiff.load_quotes(path)

    def test_load_quotes_rejects_unsupported_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.txt"
            path.write_text("unsupported", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported quotation format"):
                rfqdiff.load_quotes(path)


class CurrencyValidationTests(unittest.TestCase):
    def test_validate_currencies_accepts_single_currency(self) -> None:
        quotes = [
            {"currency": "eur"},
            {"currency": "EUR"},
        ]
        self.assertEqual(rfqdiff.validate_currencies(quotes), "EUR")

    def test_validate_currencies_rejects_mixed_currencies(self) -> None:
        quotes = [
            {"currency": "EUR"},
            {"currency": "USD"},
        ]
        with self.assertRaisesRegex(ValueError, "currency-normalizer"):
            rfqdiff.validate_currencies(quotes)


class WeightValidationTests(unittest.TestCase):
    def test_validate_weights_accepts_explicit_profile(self) -> None:
        weights = {
            "price": 0.60,
            "lead_time": 0.25,
            "payment_terms": 0.15,
        }
        self.assertEqual(rfqdiff.validate_weights(weights), weights)

    def test_validate_weights_rejects_incomplete_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "payment_terms"):
            rfqdiff.validate_weights({"price": 0.7, "lead_time": 0.3})

    def test_validate_weights_rejects_unsupported_criteria(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported"):
            rfqdiff.validate_weights(
                {
                    "price": 0.5,
                    "lead_time": 0.3,
                    "payment_terms": 0.1,
                    "relationship": 0.1,
                }
            )

    def test_validate_weights_rejects_total_other_than_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            rfqdiff.validate_weights(
                {"price": 0.5, "lead_time": 0.3, "payment_terms": 0.3}
            )

    def test_load_weights_reads_json_profile(self) -> None:
        weights = {"price": 0.4, "lead_time": 0.4, "payment_terms": 0.2}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.json"
            path.write_text(json.dumps(weights), encoding="utf-8")
            loaded = rfqdiff.load_weights(path)

        self.assertEqual(loaded, weights)


class ScoringTests(unittest.TestCase):
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

    def test_score_quotes_ranks_expected_supplier_first(self) -> None:
        scored = rfqdiff.score_quotes(self.quotes)

        self.assertEqual(scored[0]["name"], "Supplier A")
        self.assertEqual(scored[0]["score"], 97.1)
        self.assertEqual(scored[1]["name"], "Supplier B")

    def test_score_quotes_handles_zero_payment_days_for_all_suppliers(self) -> None:
        quotes = [
            {
                "name": "Supplier A",
                "currency": "EUR",
                "price": 100,
                "lead_time_weeks": 4,
                "payment_days": 0,
            },
            {
                "name": "Supplier B",
                "currency": "EUR",
                "price": 120,
                "lead_time_weeks": 5,
                "payment_days": 0,
            },
        ]

        scored = rfqdiff.score_quotes(quotes)
        self.assertEqual(scored[0]["name"], "Supplier A")
        self.assertEqual(scored[0]["score"], 100.0)

    def test_custom_weights_can_change_recommendation(self) -> None:
        quotes = [
            {
                "name": "Supplier A",
                "currency": "EUR",
                "price": 100,
                "lead_time_weeks": 4,
                "payment_days": 0,
            },
            {
                "name": "Supplier B",
                "currency": "EUR",
                "price": 150,
                "lead_time_weeks": 8,
                "payment_days": 60,
            },
        ]
        default_scored = rfqdiff.score_quotes(quotes)
        custom_weights = {
            "price": 0.10,
            "lead_time": 0.10,
            "payment_terms": 0.80,
        }
        custom_scored = rfqdiff.score_quotes(quotes, custom_weights)

        self.assertEqual(default_scored[0]["name"], "Supplier A")
        self.assertEqual(custom_scored[0]["name"], "Supplier B")

    def test_build_result_is_pipeline_ready(self) -> None:
        scored = rfqdiff.score_quotes(self.quotes)
        payload = rfqdiff.build_result(scored, "EUR")

        self.assertEqual(payload["tool"], "rfqdiff")
        self.assertEqual(payload["version"], "0.2")
        self.assertEqual(payload["recommended_supplier"], "Supplier A")
        self.assertEqual(payload["suppliers"][0]["score"], 97.1)
        self.assertEqual(payload["weights"], rfqdiff.WEIGHTS)
        json.dumps(payload)

    def test_build_result_records_custom_weights(self) -> None:
        weights = {"price": 0.4, "lead_time": 0.4, "payment_terms": 0.2}
        scored = rfqdiff.score_quotes(self.quotes, weights)
        payload = rfqdiff.build_result(scored, "EUR", weights)

        self.assertEqual(payload["weights"], weights)

    def test_write_json_round_trip(self) -> None:
        scored = rfqdiff.score_quotes(self.quotes)
        payload = rfqdiff.build_result(scored, "EUR")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rfq.json"
            rfqdiff.write_json(payload, path)
            reloaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(reloaded["tool"], "rfqdiff")
        self.assertEqual(reloaded["suppliers"][0]["name"], "Supplier A")


if __name__ == "__main__":
    unittest.main()

import csv
import json
import tempfile
import unittest
from pathlib import Path

import main as rfqdiff


class QuotationProvenanceTests(unittest.TestCase):
    def test_json_quote_records_file_hash_and_format(self) -> None:
        quote = {
            "name": "Supplier A",
            "currency": "EUR",
            "price": 100,
            "lead_time_weeks": 4,
            "payment_days": 30,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplier-a.json"
            path.write_text(json.dumps(quote), encoding="utf-8")
            expected_hash = rfqdiff.file_sha256(path)
            loaded = rfqdiff.load_quote(path)

        source = loaded["rfqdiff_source"]
        self.assertEqual(source["file"], "supplier-a.json")
        self.assertEqual(source["format"], "json")
        self.assertEqual(source["sha256"], expected_hash)
        self.assertEqual(len(source["sha256"]), 64)
        self.assertNotIn("row", source)
        self.assertNotIn("sheet", source)

    def test_csv_quotes_record_rows_and_shared_hash(self) -> None:
        csv_content = (
            "name,currency,price,lead_time_weeks,payment_days\n"
            "Supplier A,EUR,100,4,30\n"
            "Supplier B,EUR,120,5,0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.csv"
            path.write_text(csv_content, encoding="utf-8")
            expected_hash = rfqdiff.file_sha256(path)
            loaded = rfqdiff.load_quotes(path)

        self.assertEqual(loaded[0]["rfqdiff_source"]["row"], 2)
        self.assertEqual(loaded[1]["rfqdiff_source"]["row"], 3)
        self.assertEqual(loaded[0]["rfqdiff_source"]["format"], "csv")
        self.assertEqual(loaded[0]["rfqdiff_source"]["sha256"], expected_hash)
        self.assertEqual(loaded[1]["rfqdiff_source"]["sha256"], expected_hash)

    def test_xlsx_quotes_record_sheet_row_and_hash(self) -> None:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quotes.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "Commercial Quotes"
            worksheet.append(
                ["name", "currency", "price", "lead_time_weeks", "payment_days"]
            )
            worksheet.append(["Supplier A", "EUR", 100, 4, 30])
            worksheet.append(["Supplier B", "EUR", 120, 5, 0])
            workbook.save(path)
            workbook.close()

            expected_hash = rfqdiff.file_sha256(path)
            loaded = rfqdiff.load_quotes(path)

        source = loaded[0]["rfqdiff_source"]
        self.assertEqual(source["file"], "quotes.xlsx")
        self.assertEqual(source["format"], "xlsx")
        self.assertEqual(source["sheet"], "Commercial Quotes")
        self.assertEqual(source["row"], 2)
        self.assertEqual(source["sha256"], expected_hash)
        self.assertEqual(loaded[1]["rfqdiff_source"]["row"], 3)

    def test_reserved_provenance_field_is_rejected(self) -> None:
        quote = {
            "name": "Supplier A",
            "currency": "EUR",
            "price": 100,
            "lead_time_weeks": 4,
            "payment_days": 30,
            "rfqdiff_source": {"file": "spoofed.json"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quote.json"
            path.write_text(json.dumps(quote), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reserved field"):
                rfqdiff.load_quote(path)

    def test_csv_report_carries_source_provenance(self) -> None:
        csv_content = (
            "name,currency,price,lead_time_weeks,payment_days\n"
            "Supplier A,EUR,100,4,30\n"
            "Supplier B,EUR,120,5,0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "quotes.csv"
            report_path = Path(directory) / "report.csv"
            source_path.write_text(csv_content, encoding="utf-8")
            quotes = rfqdiff.load_quotes(source_path)
            scored = rfqdiff.score_quotes(quotes)
            payload = rfqdiff.build_result(scored, "EUR")
            rfqdiff.write_report(payload, report_path)

            with report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(rows[0]["source_file"], "quotes.csv")
        self.assertEqual(rows[0]["source_format"], "csv")
        self.assertEqual(rows[0]["source_row"], "2")
        self.assertEqual(len(rows[0]["source_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

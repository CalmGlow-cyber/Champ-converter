import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from excel_io import export_xlsx, import_xlsx
from models import canonical, merge_rows, parse_date, validate


MATCH = {
    "Giornata": 5, "Data": "13/11/2026", "Casa": "Polisportiva San Giorgio",
    "Gol casa": 4, "Gol ospite": 2, "Ospite": "TNT A",
}


class ModelTests(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2026-11-13"), "13/11/2026")
        self.assertEqual(parse_date("13-11-26"), "13/11/2026")

    def test_validation(self):
        self.assertEqual(validate(MATCH), [])
        bad = dict(MATCH, Data="", **{"Gol casa": None})
        self.assertEqual(len(validate(bad)), 2)

    def test_no_duplicate_after_week(self):
        copy = dict(MATCH, Casa="  POLISPORTIVA-SAN GIORGIO ")
        combined, added, updated = merge_rows([MATCH], [copy])
        self.assertEqual(len(combined), 1)
        self.assertEqual((added, updated), (0, 1))

    def test_score_update(self):
        changed = dict(MATCH, **{"Gol casa": 5})
        combined, added, updated = merge_rows([MATCH], [changed])
        self.assertEqual((added, updated), (0, 1))
        self.assertEqual(combined[0]["Gol casa"], 5)

    def test_return_round_is_distinct(self):
        reverse = dict(MATCH, Giornata=18, Casa="TNT A", Ospite="Polisportiva San Giorgio")
        combined, added, _ = merge_rows([MATCH], [reverse])
        self.assertEqual(len(combined), 2)
        self.assertEqual(added, 1)

    def test_api_aliases(self):
        api = dict(giornata=5, data="13/11/2026", casa="Polisportiva San Giorgio", gol_casa=4, gol_ospite=2, ospite="TNT A")
        self.assertEqual(canonical(api), MATCH)


class ExcelTests(unittest.TestCase):
    def test_xlsx_roundtrip(self):
        payload = export_xlsx([MATCH])
        self.assertTrue(payload.startswith(b"PK"))
        result = import_xlsx(payload)
        self.assertEqual(result, [MATCH])

    def test_empty_template(self):
        self.assertEqual(import_xlsx(export_xlsx([])), [])

    def test_accented_teams_and_two_rows(self):
        extra = {"Giornata": 6, "Data": "20/11/2026", "Casa": "Città di Legnano", "Gol casa": 1, "Gol ospite": 1, "Ospite": "Union Oratori Castellanza"}
        self.assertEqual(import_xlsx(export_xlsx([MATCH, extra])), [MATCH, extra])

    def test_incomplete_rejected(self):
        with self.assertRaises(ValueError):
            export_xlsx([dict(MATCH, Data="")])


if __name__ == "__main__":
    unittest.main()

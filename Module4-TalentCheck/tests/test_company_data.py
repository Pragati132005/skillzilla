import json
import os
import tempfile
import unittest

from tests.helpers import ROOT  # noqa: F401
from talent_check.company_data import (CellError, directory_to_snapshot, load_company_csv, load_company_json,
                                       normalise_company_name, parse_cell, records_from_rows)
from talent_check.errors import AmbiguousCompanyError, CompanyDataError, CompanyNotFoundError

CSV = os.path.join(ROOT, "data", "staging_company_skill_levels_rows.csv")


class ParseCell(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_cell("5-AP"), (5, "AP"))
        self.assertEqual(parse_cell("5 - AP"), (5, "AP"))      # software_engineering column uses spaces
        self.assertEqual(parse_cell(" 10-ev "), (10, "EV"))
        self.assertEqual(parse_cell("7"), (7, None))
        self.assertEqual(parse_cell(7), (7, None))
        self.assertEqual(parse_cell(7.0), (7, None))

    def test_blank_values(self):
        for v in (None, "", "  ", "N/A", "null", "NaN", float("nan")):
            self.assertIsNone(parse_cell(v), v)

    def test_invalid(self):
        for v in ("0-AP", "11-AP", "5-ZZ", "abc", "5.5", True, -3, "5--AP"):
            with self.assertRaises(CellError, msg=repr(v)):
                parse_cell(v)


class Loading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load_company_csv(CSV)

    def test_all_rows_and_cells_valid(self):
        self.assertEqual(len(self.d), 116)
        for rec in self.d.by_id.values():
            self.assertEqual(len(rec.levels), 12)
            self.assertTrue(all(v is not None for v in rec.levels.values()), rec.name)
            self.assertEqual(rec.warnings, [])

    def test_mojibake_repaired(self):
        self.assertEqual(self.d.resolve(company_id=93).name, "Byju’s")

    def test_duplicate_zs_flagged_and_id_lookup_works(self):
        self.assertTrue(any("ZS Associates" in w for w in self.d.warnings))
        self.assertEqual(self.d.resolve("ZS Associates").id, 102)
        self.assertEqual(self.d.resolve(company_id=33).id, 33)

    def test_trailing_space_names(self):
        self.assertEqual(self.d.resolve("Barclays").name, "Barclays PLC")

    def test_snapshot_round_trip(self):
        rows = directory_to_snapshot(self.d)
        again = records_from_rows(rows)
        self.assertEqual({r.id: r.levels for r in again.by_id.values()},
                         {r.id: r.levels for r in self.d.by_id.values()})
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "snap.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"companies": rows}, fh)
            self.assertEqual(len(load_company_json(p)), 116)

    def test_bad_files(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "bad.csv")
            with open(p, "w") as fh:
                fh.write("id,companies,coding\n1,X,5-AP\n")
            with self.assertRaises(CompanyDataError):
                load_company_csv(p)
            with self.assertRaises(CompanyDataError):
                load_company_csv(os.path.join(t, "missing.csv"))
            q = os.path.join(t, "bad.json")
            with open(q, "w") as fh:
                fh.write("{not json")
            with self.assertRaises(CompanyDataError):
                load_company_json(q)

    def test_bad_rows_are_skipped_with_warnings(self):
        good = {"id": 1, "companies": "Good Co", "coding": "5-AP"}
        rows = [good, {"id": 2, "companies": "", "coding": "5-AP"}, "junk",
                {"id": 3, "companies": "Broken Co", "coding": "99-AP", "operating_system": "4-AS"}]
        d = records_from_rows(rows)
        self.assertEqual(sorted(r.name for r in d.by_id.values()), ["Broken Co", "Good Co"])
        broken = d.resolve("Broken Co")
        self.assertIsNone(broken.levels["COD"])
        self.assertEqual(broken.levels["OS"], (4, "AS"))
        self.assertTrue(any("99" in w for w in d.warnings))
        with self.assertRaises(CompanyDataError):
            records_from_rows([{"id": 1, "companies": "None Co"}])


class Resolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load_company_csv(CSV)

    def test_jd_companies_from_the_pack(self):
        self.assertEqual(self.d.resolve("Google LLC").id, 4)
        self.assertEqual(self.d.resolve("Microsoft Corporation").id, 78)
        self.assertEqual(self.d.resolve("Oracle Financial Services").id, 24)
        self.assertEqual(self.d.resolve("oracle financial services software limited").id, 24)

    def test_ambiguous_oracle(self):
        with self.assertRaises(AmbiguousCompanyError) as cm:
            self.d.resolve("Oracle")
        self.assertEqual({c["id"] for c in cm.exception.details}, {3, 24})

    def test_not_found_with_suggestions_and_empty(self):
        with self.assertRaises(CompanyNotFoundError):
            self.d.resolve("Nonexistent Corp")
        with self.assertRaises(CompanyNotFoundError):
            self.d.resolve("")
        with self.assertRaises(CompanyNotFoundError):
            self.d.resolve(company_id=99999)
        with self.assertRaises(CompanyNotFoundError):
            self.d.resolve(company_id="abc")
        with self.assertRaises(CompanyNotFoundError):
            self.d.resolve(None)

    def test_id_forms_and_aliases(self):
        self.assertEqual(self.d.resolve(company_id="4").id, 4)
        self.assertEqual(self.d.resolve("4").id, 4)
        self.assertEqual(self.d.resolve(4).id, 4)
        self.assertEqual(self.d.resolve("IBM").id, 25)
        self.assertEqual(self.d.resolve("  GOOGLE  ").id, 4)

    def test_normalise(self):
        self.assertEqual(normalise_company_name("Google LLC (Subsidiary of Alphabet Inc.)"), "google")
        self.assertEqual(normalise_company_name("Larsen & Toubro Infotech Limited"), "larsen toubro infotech")

    def test_list_filter(self):
        names = [c["name"] for c in self.d.list("oracle")]
        self.assertEqual(len(names), 2)
        self.assertEqual(len(self.d.list("", limit=5)), 5)


if __name__ == "__main__":
    unittest.main()

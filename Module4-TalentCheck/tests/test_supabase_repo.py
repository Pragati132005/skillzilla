import csv
import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from tests.helpers import ROOT, make_service, offline_settings
from talent_check.errors import SupabaseError
from talent_check.repository import DataRepository
from talent_check.supabase_client import fetch_table

CSV = os.path.join(ROOT, "data", "staging_company_skill_levels_rows.csv")


def csv_rows():
    with open(CSV, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Fetch(unittest.TestCase):
    def test_pagination_headers_and_auth(self):
        rows = csv_rows()
        seen = []

        def fake(req, timeout=None):
            seen.append(req)
            rng = req.get_header("Range")
            a, b = [int(x) for x in rng.split("-")]
            return FakeResp(rows[a:b + 1])

        with mock.patch("urllib.request.urlopen", fake):
            got = fetch_table("https://x.supabase.co", "KEY", "staging_company_skill_levels", page_size=50)
        self.assertEqual(len(got), 116)
        self.assertEqual(len(seen), 3)                                   # 50 + 50 + 16
        self.assertEqual(seen[0].get_header("Apikey"), "KEY")
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer KEY")
        self.assertIn("/rest/v1/staging_company_skill_levels?select=*", seen[0].full_url)

    def test_exact_page_boundary_terminates(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(1)
            return FakeResp([{"id": 1}] * 2 if len(calls) == 1 else [])

        with mock.patch("urllib.request.urlopen", fake):
            self.assertEqual(len(fetch_table("https://x.co", "K", "t", page_size=2)), 2)
        self.assertEqual(len(calls), 2)

    def test_errors_are_typed(self):
        def http(code):
            def fake(req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b'{"message":"nope"}'))
            return fake

        for code, word in ((401, "API key"), (403, "Row Level Security"), (404, "not found")):
            with mock.patch("urllib.request.urlopen", http(code)):
                with self.assertRaises(SupabaseError) as cm:
                    fetch_table("https://x.co", "K", "t")
                self.assertIn(word, cm.exception.message)
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
            with self.assertRaises(SupabaseError):
                fetch_table("https://x.co", "K", "t")
        with mock.patch("urllib.request.urlopen", lambda r, timeout=None: FakeResp({"message": "obj"})):
            with self.assertRaises(SupabaseError):
                fetch_table("https://x.co", "K", "t")

    def test_input_validation(self):
        with self.assertRaises(SupabaseError):
            fetch_table("", "", "t")
        with self.assertRaises(SupabaseError):
            fetch_table("http://evil.example", "K", "t")
        with self.assertRaises(SupabaseError):
            fetch_table("https://x.co", "K", "t; drop table x")


class Repo(unittest.TestCase):
    def sb(self, **over):
        return offline_settings(supabase_url="https://x.supabase.co", supabase_key="K", source="auto", **over)

    def test_uses_supabase_when_configured(self):
        repo = DataRepository(self.sb())
        with mock.patch("urllib.request.urlopen", lambda r, timeout=None: FakeResp(csv_rows())):
            d, src = repo.get_directory()
        self.assertEqual(src, "supabase:staging_company_skill_levels")
        self.assertEqual(len(d), 116)

    def test_numeric_json_cells_from_supabase_work(self):
        rows = [{"id": 1, "companies": "Num Co", **{k: 5 for k in csv_rows()[0] if k not in ("id", "companies")}}]
        repo = DataRepository(self.sb())
        with mock.patch("urllib.request.urlopen", lambda r, timeout=None: FakeResp(rows)):
            d, _ = repo.get_directory()
        self.assertEqual(d.resolve("Num Co").levels["COD"], (5, None))

    def test_fallback_to_csv_is_labelled(self):
        repo = DataRepository(self.sb())
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            d, src = repo.get_directory()
        self.assertIn("fallback", src)
        self.assertEqual(len(d), 116)
        self.assertIsNotNone(repo.last_error)

    def test_strict_mode_does_not_hide_failures(self):
        repo = DataRepository(self.sb(strict_source=True))
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(SupabaseError):
                repo.get_directory()

    def test_source_supabase_never_falls_back(self):
        repo = DataRepository(offline_settings(supabase_url="https://x.co", supabase_key="K", source="supabase"))
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(SupabaseError):
                repo.get_directory()

    def test_stale_cache_beats_snapshot_and_ttl_caches(self):
        t = [0.0]
        repo = DataRepository(self.sb(cache_ttl=10.0), clock=lambda: t[0])
        calls = []

        def ok(r, timeout=None):
            calls.append(1)
            return FakeResp(csv_rows())

        with mock.patch("urllib.request.urlopen", ok):
            repo.get_directory()
            repo.get_directory()
        self.assertEqual(len(calls), 1)                                  # cached
        t[0] = 100.0
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            _, src = repo.get_directory()
        self.assertIn("stale cache", src)

    def test_csv_mode_ignores_supabase(self):
        repo = DataRepository(offline_settings(supabase_url="https://x.co", supabase_key="K", source="csv"))
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("must not call network")):
            _, src = repo.get_directory()
        self.assertTrue(src.startswith("csv:"))

    def test_unconfigured_auto_uses_csv(self):
        _, src = DataRepository(offline_settings(source="auto")).get_directory()
        self.assertTrue(src.startswith("csv:"))

    def test_broken_json_snapshot_falls_back_to_csv(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            shutil.copy(CSV, t)
            shutil.copy(os.path.join(ROOT, "data", "skill_level_rubric.csv"), t)
            with open(os.path.join(t, "talent_check_company_skillsets.json"), "w") as fh:
                fh.write("[]")
            d, src = DataRepository(offline_settings(data_dir=t)).get_directory()
        self.assertTrue(src.startswith("csv:"))
        self.assertTrue(any("ignored" in w for w in d.warnings))

    def test_rubric_loads(self):
        rb = make_service().repo.get_rubric()
        self.assertEqual(sum(len(v) for v in rb.topics.values()), 120)


if __name__ == "__main__":
    unittest.main()

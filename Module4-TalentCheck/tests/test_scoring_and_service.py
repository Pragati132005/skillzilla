import json
import unittest

from tests.helpers import load_samples, make_service
from talent_check.company_data import records_from_rows
from talent_check.config import CATEGORY_ORDER, CODE_TO_COLUMN
from talent_check.errors import AmbiguousCompanyError, CompanyNotFoundError, ProfileError
from talent_check.level_estimator import CategoryEstimate, estimate_levels
from talent_check.profile_adapter import normalise_profile
from talent_check.scoring import compare, readiness_label

SVC = make_service()
SAMPLES = load_samples()
DIRECTORY, _ = SVC.repo.get_directory()


def company(**cells):
    row = {"id": 1, "companies": "Test Co"}
    for code in CATEGORY_ORDER:
        row[CODE_TO_COLUMN[code]] = cells.get(code)
    return records_from_rows([row]).resolve("Test Co")


def est(**levels):
    out = {}
    for code in CATEGORY_ORDER:
        e = CategoryEstimate(code=code)
        if code in levels:
            lv, bloom = levels[code]
            e.level, e.level_exact, e.has_evidence, e.bloom = lv, float(lv), True, bloom
        out[code] = e
    return out


EMPTY = normalise_profile({"skills": []})


class HandComputed(unittest.TestCase):
    def test_formula(self):
        # COD req 8 cand 4 (AP vs AP)  -> 0.5 ; DSA req 4 cand 6 (surplus capped) -> 1.0
        c = company(COD="8-AP", DSA="4-AP")
        r = compare(EMPTY, est(COD=(4, 2), DSA=(6, 2)), c)
        self.assertEqual(r["readiness_score"], round(100 * (8 * 0.5 + 4 * 1.0) / 12, 1))
        by = {g["category_code"]: g for g in r["skillset_gap"]}
        self.assertTrue(by["COD"]["gap"])
        self.assertFalse(by["DSA"]["gap"])
        self.assertEqual(by["COD"]["gap_size"], 4)
        self.assertIsNone(by["OOD"]["required_level"])
        self.assertFalse(by["OOD"]["gap"])
        self.assertEqual(by["OOD"]["status"], "no_requirement")

    def test_depth_factor(self):
        c = company(COD="5-CR")
        full = compare(EMPTY, est(COD=(5, 5)), c)["readiness_score"]
        shallow = compare(EMPTY, est(COD=(5, 1)), c)["readiness_score"]
        self.assertEqual(full, 100.0)
        self.assertAlmostEqual(shallow, 100 * (0.9 + 0.1 * 0.2), places=1)

    def test_no_evidence_counts_zero_not_one(self):
        r = compare(EMPTY, est(), company(COD="5-AP"))
        self.assertEqual(r["readiness_score"], 0.0)
        g = r["skillset_gap"][0]
        self.assertEqual((g["candidate_level"], g["status"]), (0, "no_evidence"))

    def test_company_with_no_requirements_does_not_divide_by_zero(self):
        c2 = company(COD="5-AP")  # an all-blank row is rejected at load time, so blank it afterwards
        c2.levels = {k: None for k in CATEGORY_ORDER}
        r = compare(EMPTY, est(COD=(5, 2)), c2)
        self.assertEqual(r["readiness_score"], 0.0)

    def test_labels(self):
        self.assertEqual([readiness_label(x) for x in (100, 80, 79.9, 60, 40, 39.9, 0)],
                         ["Ready", "Ready", "Almost ready", "Almost ready", "Developing", "Early stage",
                          "Early stage"])

    def test_critical_gaps_flagged(self):
        r = compare(EMPTY, est(COD=(2, 2)), company(COD="8-AP", DSA="3-AP"))
        self.assertEqual(r["critical_gaps"][0]["category_code"], "COD")


class EndToEnd(unittest.TestCase):
    def test_contract_shape_for_every_company_and_candidate(self):
        for name, p in SAMPLES.items():
            for cid in sorted(DIRECTORY.by_id):
                r = SVC.run(p, company_id=cid)
                self.assertEqual({"company", "skillset_gap", "readiness_score"} <= set(r), True)
                self.assertEqual([g["category_code"] for g in r["skillset_gap"]], CATEGORY_ORDER)
                self.assertTrue(0.0 <= r["readiness_score"] <= 100.0, (name, cid))
                for g in r["skillset_gap"]:
                    self.assertIsInstance(g["required_level"], int)
                    self.assertIsInstance(g["candidate_level"], int)
                    self.assertIsInstance(g["gap"], bool)
                    self.assertEqual(g["gap"], g["candidate_level"] < g["required_level"])
                json.dumps(r)  # fully serialisable

    def test_results_differ_per_candidate(self):
        scores = {n: SVC.run(p, "Google")["readiness_score"] for n, p in SAMPLES.items()}
        self.assertEqual(len(set(scores.values())), 4, scores)
        self.assertEqual(max(scores, key=scores.get), "Rohan")           # strongest all-rounder
        self.assertEqual(min(scores, key=scores.get), "Priya")

    def test_entry_level_candidate_fits_lower_bar_companies_better(self):
        priya = SAMPLES["Priya"]
        high = SVC.run(priya, "Google")["readiness_score"]
        ofss = SVC.run(priya, "Oracle Financial Services")["readiness_score"]
        low = SVC.run(priya, "Infosys")["readiness_score"]
        self.assertGreater(ofss, high)
        self.assertGreater(low, ofss)

    def test_data_candidate_vs_systems_candidate_gap_pattern(self):
        k = {g["category_code"]: g for g in SVC.run(SAMPLES["Karthik"], "Microsoft")["skillset_gap"]}
        a = {g["category_code"]: g for g in SVC.run(SAMPLES["Ananya"], "Microsoft")["skillset_gap"]}
        self.assertTrue(a["OS"]["candidate_level"] > k["OS"]["candidate_level"])
        self.assertTrue(k["SQL"]["candidate_level"] > a["SQL"]["candidate_level"])

    def test_idempotent(self):
        p = SAMPLES["Rohan"]
        self.assertEqual(SVC.run(p, "Microsoft"), SVC.run(json.loads(json.dumps(p)), "Microsoft"))

    def test_input_not_mutated(self):
        p = SAMPLES["Ananya"]
        before = json.dumps(p, sort_keys=True)
        SVC.run(p, "Google")
        self.assertEqual(before, json.dumps(p, sort_keys=True))

    def test_errors_propagate_typed(self):
        with self.assertRaises(AmbiguousCompanyError):
            SVC.run(SAMPLES["Rohan"], "Oracle")
        with self.assertRaises(CompanyNotFoundError):
            SVC.run(SAMPLES["Rohan"], "Nope Inc")
        with self.assertRaises(ProfileError):
            SVC.run({"name": "x"}, "Google")

    def test_duplicate_company_warning_surfaces(self):
        r = SVC.run(SAMPLES["Rohan"], "ZS Associates")
        self.assertTrue(any("Duplicate company" in w for w in r["warnings"]))

    def test_next_steps_come_from_the_rubric(self):
        r = SVC.run(SAMPLES["Priya"], "Google")
        self.assertTrue(r["next_steps"])
        self.assertTrue(all(s["focus_topics"] for s in r["next_steps"]))


if __name__ == "__main__":
    unittest.main()

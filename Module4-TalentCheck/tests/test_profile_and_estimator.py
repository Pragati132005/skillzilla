import copy
import json
import unittest

from tests.helpers import load_samples, make_service
from talent_check.config import CATEGORY_ORDER
from talent_check.errors import ProfileError
from talent_check.level_estimator import estimate_levels
from talent_check.profile_adapter import normalise_category, normalise_profile, parse_cgpa

SVC = make_service()
RUBRIC = SVC.repo.get_rubric()


def lvl(profile, code="COD"):
    return estimate_levels(normalise_profile(profile), RUBRIC)[code]


def sk(name, cat="COD", ev="", conf="medium"):
    return {"skill_name": name, "category_code": cat, "evidence": ev, "confidence": conf}


class ProfileInput(unittest.TestCase):
    def test_rejects_garbage(self):
        for bad in (None, 5, [], "not json", "[1]", {"name": "x"}, {"skills": "Java"}):
            with self.assertRaises(ProfileError, msg=repr(bad)):
                normalise_profile(bad)

    def test_accepts_json_string_wrapper_and_plain_strings(self):
        p = normalise_profile(json.dumps({"profile": {"name": "A", "skills": ["Java", {"skill_name": "SQL"}]}}))
        self.assertEqual(p.skill_count, 2)

    def test_dirty_skill_entries_are_tolerated(self):
        p = normalise_profile({"skills": [None, 5, {"x": 1}, {"skill_name": "  "}, sk("Java"), sk("java", ev="more")]})
        self.assertEqual(p.skill_count, 1)
        self.assertTrue(any("Duplicate" in w for w in p.warnings))

    def test_empty_profile_scores_zero_everywhere(self):
        est = estimate_levels(normalise_profile({"skills": []}), RUBRIC)
        self.assertTrue(all(e.level == 0 and not e.has_evidence for e in est.values()))

    def test_category_aliases(self):
        self.assertEqual(normalise_category("devops"), "CLOUD")
        self.assertEqual(normalise_category("sql"), "SQL")
        self.assertEqual(normalise_category(" Coding "), "COD")
        self.assertEqual(normalise_category("weird"), "OTHER")
        self.assertEqual(normalise_category(None), "OTHER")

    def test_cgpa(self):
        self.assertAlmostEqual(parse_cgpa("B.Tech — CGPA 8.6 / 10"), 0.86)
        self.assertAlmostEqual(parse_cgpa("GPA 3.4/4"), 0.85)
        self.assertAlmostEqual(parse_cgpa("82%"), 0.82)
        self.assertIsNone(parse_cgpa("no grades here"))
        self.assertIsNone(parse_cgpa("CGPA 14 / 10"))

    def test_huge_input_is_bounded(self):
        big = {"skills": [sk(f"Skill{i}") for i in range(2000)], "projects": ["x " * 5000] * 500}
        p = normalise_profile(big)
        self.assertLessEqual(p.skill_count, 500)


class Distinguishing(unittest.TestCase):
    """The core requirement: the same word ('low'/'basic') must not mean the same level for everyone."""

    def test_low_vs_low_separated_by_evidence(self):
        a = {"skills": [sk("Java", ev="basic Java", conf="low")]}
        b = copy.deepcopy(a)
        b["projects"] = ["Built a library management app in Python with file handling"]
        b["skills"].append(sk("Python", ev="Built a library management app in Python with file handling"))
        c = copy.deepcopy(a)
        c["internships"] = ["Intern: wrote unit tests in Java and fixed bugs on a production service"]
        la, lb, lc = lvl(a).level, lvl(b).level, lvl(c).level
        self.assertLess(la, lb)
        self.assertLess(lb, lc)

    def test_same_evidence_same_level_and_deterministic(self):
        a = {"skills": [sk("Java", ev="basic Java", conf="low")]}
        self.assertEqual(lvl(a).level_exact, lvl(copy.deepcopy(a)).level_exact)

    def test_confidence_orders_levels(self):
        lo = lvl({"skills": [sk("Python", conf="low")]}).level_exact
        me = lvl({"skills": [sk("Python", conf="medium")]}).level_exact
        hi = lvl({"skills": [sk("Python", conf="high")]}).level_exact
        self.assertLess(lo, me)
        self.assertLess(me, hi)

    def test_hedge_lowers_and_strength_raises(self):
        basic = lvl({"skills": [sk("SQL", "SQL", "basic SQL")]}, "SQL").level_exact
        plain = lvl({"skills": [sk("SQL", "SQL", "SQL")]}, "SQL").level_exact
        used = lvl({"skills": [sk("SQL", "SQL", "Designed a normalized schema with indexes and joins")]}, "SQL").level_exact
        self.assertLess(basic, plain)
        self.assertLess(plain, used)

    def test_monotonic_adding_evidence_never_lowers(self):
        base = {"skills": [sk("Python", ev="Built a Flask API")]}
        prev = lvl(base).level_exact
        extras = [{"projects": ["Implemented BFS and Dijkstra in Python for a routing tool"]},
                  {"internships": ["Backend intern shipped an API in Python"]},
                  {"hackathons": ["Winner, hackathon - built a Python service"]},
                  {"certifications": ["Python certification"]}]
        cur = copy.deepcopy(base)
        for e in extras:
            for k, v in e.items():
                cur.setdefault(k, []).extend(v)
            now = lvl(cur).level_exact
            self.assertGreaterEqual(now, prev)
            prev = now

    def test_volume_and_outcome_matter(self):
        few = lvl({"skills": [sk("DSA", "DSA")], "achievements": ["Solved 40 problems on LeetCode"]}, "DSA").level_exact
        many = lvl({"skills": [sk("DSA", "DSA")], "achievements": ["Solved 500+ problems on LeetCode"]}, "DSA").level_exact
        self.assertLess(few, many)

    def test_untagged_other_skill_is_still_credited_by_keywords(self):
        e = lvl({"skills": [sk("Docker", "OTHER", "containerised the app")]}, "CLOUD")
        self.assertTrue(e.has_evidence)

    def test_levels_bounded_and_realistic_for_students(self):
        for name, p in load_samples().items():
            for code, est in estimate_levels(normalise_profile(p), RUBRIC).items():
                self.assertTrue(0 <= est.level <= 10)
                self.assertLessEqual(est.level, 9, f"{name} {code} unrealistically high")
                self.assertEqual(est.has_evidence, est.level >= 1)

    def test_sample_candidates_have_distinct_profiles(self):
        s = {n: {c: e.level for c, e in estimate_levels(normalise_profile(p), RUBRIC).items()}
             for n, p in load_samples().items()}
        self.assertGreater(s["Karthik"]["SQL"], s["Ananya"]["SQL"])      # data person beats systems person on SQL
        self.assertGreater(s["Ananya"]["OS"], s["Karthik"]["OS"])
        self.assertGreater(s["Ananya"]["NETW"], s["Priya"]["NETW"])
        self.assertGreater(s["Karthik"]["AI"], s["Ananya"]["AI"])
        self.assertGreater(s["Rohan"]["DSA"], s["Priya"]["DSA"])
        self.assertGreater(s["Rohan"]["SYSD"], s["Priya"]["SYSD"])
        self.assertGreater(s["Priya"]["SQL"], 0)
        vectors = {tuple(v[c] for c in CATEGORY_ORDER) for v in s.values()}
        self.assertEqual(len(vectors), 4)


if __name__ == "__main__":
    unittest.main()

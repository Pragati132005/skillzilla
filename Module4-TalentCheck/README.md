# RADIX Talent Match — Module 4: Talent Check

Takes the **saved profile from Module 3 (Profile Builder)** + a **selected company** and returns a
**readiness score (0-100)** and a **per-skillset gap breakdown** across the 12 RADIX skillsets.
Plain Python, standard library only (no `pip install` needed). Python 3.9+ (developed and tested on 3.12).

```
Profile Builder (React)  ──POST /api/talent-check──▶  Talent Check API  ──▶  Supabase (company levels)
        ▲                                                   │
        └──────────── readiness_score + skillset_gap ◀──────┘
```

## Quick start
```bash
cp .env.example .env                      # fill SUPABASE_URL / SUPABASE_KEY
python -m talent_check check-data         # proves the data source works (prints source, row count, warnings)
python -m talent_check run --profile samples/profiles/rohan_verma.json --company "Google"
python -m talent_check serve              # API on http://127.0.0.1:8010
python -m unittest discover -s tests -t . # 66 tests
python scripts/demo_matrix.py             # 4 sample candidates x 4 companies
```

## Supabase (company skill levels)
* `SUPABASE_COMPANY_TABLE` defaults to **`staging_company_skill_levels`** (the name implied by the CSV file name
  `staging_company_skill_levels_rows.csv`). **If your table is named differently, set the variable** — a wrong name gives
  a clear `table '…' not found` error.
* Needed columns: `id, companies, coding, data_structures_and_algorithms, object_oriented_programming_and_design,
  aptitude_and_problem_solving, communication_skills, ai_native_engineering, devops_and_cloud, sql_and_design,
  software_engineering, system_design_and_architecture, computer_networking, operating_system`; cells like `5-AP` or `5 - AP`.
* The key needs `SELECT` on the table (anon key + an RLS read policy, or the service-role key **on the server only**).
* Source order: Supabase → last good cached copy (stale) → bundled CSV. Every response carries `data_source`, so you can
  see which one served it. Set `TALENT_CHECK_STRICT_SOURCE=1` for the demo: no silent fallback.
* Rubric (`data/skill_level_rubric.csv` = the STAGIN_1.CSV file): bundled; set `SUPABASE_RUBRIC_TABLE` to read it from Supabase too.
* `python -m talent_check export-snapshot` writes `talent_check_company_skillsets.json` (the offline snapshot the brief mentions).

## API
`POST /api/talent-check` body `{"profile": {...Module 3 profile...}, "company": "Google LLC"}` or `{"profile": {...}, "company_id": 4}`
`GET /api/companies?q=goo`, `GET /api/companies/<id>`, `GET /health`.

Response = the contract from the brief **plus extras** (Module 3 may ignore extras):
```jsonc
{
  "company": "Google LLC (Subsidiary of Alphabet Inc.)",
  "readiness_score": 63.1,
  "skillset_gap": [ { "category_code": "COD", "required_level": 8, "candidate_level": 8, "gap": false,
                      "candidate_level_exact": 7.95, "required_depth": "CR", "candidate_depth": "CR",
                      "gap_size": 0, "status": "met|gap|no_evidence|no_requirement",
                      "evidence": [ {"text": "...", "source": "project", "implied_level": 7.4} ] }, ... 12 entries ],
  "readiness_label": "Almost ready", "critical_gaps": [...], "strengths": [...],
  "next_steps": [ {"category_code": "OS", "target_level": 5, "focus_topics": ["Deadlock prevention ...", ...]} ],
  "data_source": "supabase:staging_company_skill_levels", "warnings": [...], "scoring_version": "1.0.0"
}
```
Errors are always `{"error": {"code", "message", "details"}}` with 400 / 404 `company_not_found` / 409 `ambiguous_company`
(details lists the candidates, e.g. "Oracle") / 413 / 422 `invalid_profile` / 503 `supabase_error`.

### Two deliberate deviations from the brief's sketch — tell the team
1. `candidate_level` is **0** (not 1) when the profile has no evidence at all for a skillset (`status: "no_evidence"`). A 1 would claim a skill the candidate never showed.
2. `required_level` is `null` if a company row has an empty/invalid cell (`status: "no_requirement"`, never a gap, excluded from the score).

## What Module 3 must send
The contract profile (`name, email, education, skills[], hackathons[], internships[], certifications[], preferred_roles[], cv_file`).
Each skill: `{skill_name, category_code, evidence, confidence}`. **The more of the resume's own wording Module 2/3 keeps in `evidence`
(and in optional `projects[]`, `achievements[]`), the more accurately levels are separated.** Strings or objects are both accepted in the lists;
`education` containing `CGPA 8.6 / 10` is read automatically. Unknown/missing category codes fall back to `OTHER` (still credited by keywords).

## How a level is decided (the "low is not always 2" requirement)
`talent_check/level_estimator.py`. Every claim becomes an evidence unit; each unit is valued on the rubric's 1-10 scale:
keyword tier from the rubric (Docker = DevOps L4, BFS/DFS = DSA L7 …) × *used vs only listed* (70 %) − hedges ("basic", "exposure")
+ source strength (internship, hackathon winner/finalist, certificate) + confidence (high/medium/low). The skillset level is the best unit,
minus a penalty when only one unit supports it, plus a small breadth bonus, capped just above the best thing shown.
Two people who both write "basic Java" tie **only if everything else ties**; an extra project or an internship moves the level (tested:
a lone "basic Java" = 2, + a Python project = 4, + a production internship = 6). More evidence can never lower a level (tested).
Volume claims ("500+ problems") scale DSA/Coding/Aptitude. Depth verbs (built → designed → evaluated) feed the Bloom-style depth code.

## How "ready" is decided (`talent_check/scoring.py`)
`attainment = min(candidate/required, 1) × depth_factor`; `readiness = 100 × Σ(required × attainment) / Σ(required)`.
Higher-bar skillsets weigh more; a surplus never offsets a shortfall; a **gap** is `candidate_level < required_level` using the integer
levels shown in the UI, so anyone can recompute the score by hand. Labels: ≥80 Ready, ≥60 Almost ready, ≥40 Developing, else Early stage.
All constants are in `config.ScoringConfig`.

## Data problems found in the supplied CSV (all handled, all tested)
* `software_engineering` cells use `5 - AP` (spaces) while others use `5-AP`.
* `Byju’s` arrives as mojibake (`Byjuâ€™s`) — repaired; same for the rubric's `1NFâ€“3NF`.
* **`ZS Associates, Inc.` appears twice (ids 33 and 102) with different values.** Name lookups use the latest id (102) and
  every such response carries a warning; pass `company_id` to choose. Please fix the table.
* Trailing spaces in names (`Barclays PLC `), empty/invalid cells, out-of-range levels, unknown depth codes, numeric cells, NaN.
* Company names: `Oracle` is ambiguous (Oracle India vs Oracle Financial Services) → 409 with both options rather than a guess.

## Honest limits
* The Supabase connector is unit-tested with a mocked HTTP layer (this build environment had no network). Run `check-data` once with your real
  `.env` to confirm table name, key and RLS before integration.
* Level estimation is rule-based (keywords + rubric), by design: the brief asks for plain code here. It cannot understand claims phrased with
  no recognisable keywords; unrecognised skills tagged by Module 3 only get a modest default credit.
* The company table's "AI Native Engineering" is AI-assisted development; the brief's `AI` category also covers ML for data roles, so ML evidence
  is credited to it. Revisit if the company data is meant strictly.
* CGPA gives at most ±0.25 level on foundational CS skillsets (`use_cgpa=False` to switch off).

## Layout
`talent_check/` (company_data, supabase_client, repository, rubric, profile_adapter, lexicon, level_estimator, scoring, service, server, cli) ·
`data/` (company CSV, rubric CSV) · `samples/profiles/` (4 candidates in Module 3 format) · `tests/` · `docs/INTEGRATION.md`

# Integrating with Module 3 (Profile Builder)

1. Start the API: `python -m talent_check serve` (set `TALENT_CHECK_CORS_ORIGINS` to the React dev origin).
2. From React, after the profile is saved:
```js
const res = await fetch("http://127.0.0.1:8010/api/talent-check", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ profile: savedProfile, company: selectedCompanyName }),   // or company_id
});
const data = await res.json();
if (!res.ok) { /* data.error.code: ambiguous_company -> show data.error.details as a picker */ }
else { /* data.readiness_score, data.skillset_gap[], data.next_steps[] */ }
```
3. Company dropdown: `GET /api/companies` → `[{id, name}]`; send `company_id` (unambiguous).
4. Python-to-Python (same process): `from talent_check import run_talent_check; run_talent_check(profile, company="Google")`.

Checklist before the joint demo: `check-data` shows `supabase:` as data_source · Module 3's saved JSON runs through `run` without warnings ·
no `warnings` about missing evidence for skills the resume clearly lists (if so, Module 2/3 is not tagging them — fix there).

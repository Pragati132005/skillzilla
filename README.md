<<<<<<< HEAD
# SKILLZILLA — RADIX Talent Match Portal

This repository contains the five RADIX modules and the Module 3 React portal. In local development, the portal calls the module APIs through Vite's `/api/...` proxy routes. The services remain separate processes, but one launcher starts them together.

## Local setup (Windows PowerShell)

### Requirements
- Python 3.11 or newer with the `py` launcher
- Node.js 20 LTS or newer (npm included)
- PostgreSQL database for profile persistence

### 1. Install dependencies once

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-all-services.ps1
```

This creates a separate `.venv` for each Python service and installs its own `requirements.txt`, then runs `npm ci` for Module 3.

### 2. Configure environment variables

Create `profilebackend/.env` from `profilebackend/.env.example` and set `DATABASE_URL` to your PostgreSQL connection string. Do not commit `.env` files.

Optional live LLM settings can be configured separately using the relevant module's `.env.example` files. Module 4 can use its local CSV benchmark data when configured for CSV mode; if you use Supabase mode, configure its `.env` with the correct Supabase project credentials and table names.

### 3. Start the complete local portal

```powershell
.\start-all-services.ps1
```

The launcher starts:

| Component | Port | Health endpoint |
|---|---:|---|
| Module 1 — JD Analytics | 8020 | `http://127.0.0.1:8020/health` |
| Module 2 — Resume Parser | 8000 | `http://127.0.0.1:8000/health` |
| Module 3 — React Portal | 5173 | `http://127.0.0.1:5173` |
| Module 4 — Talent Check | 8010 | `http://127.0.0.1:8010/health` |
| Module 5 — Skill Matching | 8030 | `http://127.0.0.1:8030/health` |
| Profile Persistence | 8040 | `http://127.0.0.1:8040/health` |

Open **http://localhost:5173**. The launcher checks backend health and writes stdout/stderr logs to `.run/logs/`.

To stop the processes started by the launcher:

```powershell
.\stop-all-services.ps1
```

If a port is already occupied, stop the old process or change the port consistently in the launcher and `Module3-ProfileBuilder/JSScandidateportal-profilebuilder/vite.config.ts`.

### Useful options

```powershell
.\start-all-services.ps1 -SkipFrontend
.\start-all-services.ps1 -SkipProfileBackend
.\start-all-services.ps1 -NoHealthWait
```

`-SkipProfileBackend` is only for debugging. Profile saving/loading will not work without the persistence API.

## API routing in local development

Module 3's Vite development server proxies:

- `/api/module1/*` → Module 1 on port 8020
- `/api/module2/*` → Module 2 on port 8000
- `/api/module4/*` → Module 4 on port 8010
- `/api/module5/*` → Module 5 on port 8030
- `/api/profiles/*` and `/api/backend-health` → Profile Persistence on port 8040

This proxy is a **development-only** feature. It does not run on Vercel production hosting.

## Deployment architecture

For production, deploy the React/Vite frontend to Vercel and deploy the Python APIs as persistent services (or consolidate them behind a single FastAPI gateway on a Python-capable host). Configure the frontend's `VITE_*_API_URL` variables to public HTTPS API base URLs, and configure database/API secrets in the backend host's environment settings. Do not put database credentials, Gemini keys, or Supabase service-role keys in Vite variables: every `VITE_*` value is exposed to browser code.

The current repository has a local multi-service launcher and Vite development proxies. A Vercel deployment is **not** completed merely by deploying Module 3; the Python services and PostgreSQL database must also be deployed and their public URLs configured.

## Security

- `.env`, `.venv`, `node_modules`, `.run`, and Python cache directories are local-only.
- Use `.env.example` files as templates; never commit credentials.
- Rotate any credential that has accidentally been shared in an archive or public repository.
=======
# RADIX Talent Match — JSS Candidate Portal

## 9. How to Run Our Code

Evaluators should be able to run your tool from `Code.zip` using only these steps.

| Field | Instructions / Values |
| :--- | :--- |
| **Prerequisites** | **Python**: 3.10+ (tested on Python 3.12 / 3.13 / 3.14)<br>**Node.js**: 18.0+ (tested on Node.js v20 / v22 / v25) & `npm` |
| **Setup commands** | **Install all dependencies:**<br>`cd Module1-JDAnalyzer/radix-jd-analytics-main && pip install -r requirements.txt`<br>`cd ../../Module2-ResumeParser/role2_resume_parsing && pip install -r requirements.txt`<br>`cd ../../Module4-TalentCheck && pip install -r requirements.txt`<br>`cd ../Module5-SkillMatch/role5 && pip install -r requirements.txt`<br>`cd ../../profilebackend && pip install -r requirements.txt`<br>`cd ../Module3-ProfileBuilder/JSScandidateportal-profilebuilder && npm install` |
| **Environment variables** | • `GEMINI_API_KEY` *(optional — for live LLM extraction; offline rule-based & replay fallbacks run automatically without keys)*<br>• `DATABASE_URL` *(PostgreSQL connection string for candidate profile persistence)*<br>• `TALENT_CHECK_SOURCE_MODE=csv` *(defaults to local benchmark dataset)*<br>• `ROLE5_API_BASE_URL` *(optional — proxied by Vite by default)* |
| **Start command(s)** | **Windows PowerShell (One-Click Start):**<br>`powershell -ExecutionPolicy Bypass -File .\start-all-services.ps1`<br><br>**Manual Start (Individual Terminals):**<br>1. **Module 3 (Web UI):** `cd Module3-ProfileBuilder/JSScandidateportal-profilebuilder && npm run dev` *(Runs on `http://localhost:5173`)*<br>2. **Profile Backend:** `python -m uvicorn profilebackend.main:app --host 127.0.0.1 --port 8040`<br>3. **Module 1 (JD Analytics):** `cd Module1-JDAnalyzer/radix-jd-analytics-main && python -m uvicorn src.api:app --host 127.0.0.1 --port 8020`<br>4. **Module 2 (Resume Parser):** `cd Module2-ResumeParser/role2_resume_parsing && python -m uvicorn resume_parser.api:app --host 127.0.0.1 --port 8000`<br>5. **Module 4 (Talent Check):** `cd Module4-TalentCheck && python -m uvicorn talent_check.api:app --host 127.0.0.1 --port 8010`<br>6. **Module 5 (Skill Match):** `cd Module5-SkillMatch/role5 && python -m uvicorn app.main:app --host 127.0.0.1 --port 8030` |
| **Sample data location** | • **Job Descriptions (JDs):** `Module1-JDAnalyzer/radix-jd-analytics-main/data/sample_jds/`<br>• **Candidate Resumes:** `Module2-ResumeParser/role2_resume_parsing/data/resumes/` & `Module3-ProfileBuilder/JSScandidateportal-profilebuilder/priya_menon.parse.json`<br>• **Company Benchmark Datasets:** `Module4-TalentCheck/data/staging_company_skill_levels.csv` & `staging_skill_topics.csv`<br>• **Role 1 & Role 3 Integration Fixtures:** `Module5-SkillMatch/role5/sample_data/` |

## Role 5 Skill-Matching integration

The portal should call the deployed Role 5 API after it has received the Role 1
JD Analytics result and the Role 3 Candidate Profiling result.

Set the portal environment variable below to the public URL of the deployed
Role 5 service (do not include a trailing slash):

```text
ROLE5_API_BASE_URL=https://<your-role5-host>
```

Send the integration request to:

```text
POST ${ROLE5_API_BASE_URL}/api/v1/skill-match
Content-Type: application/json
```

```json
{
  "role1": "<the complete Role 1 JD Analytics JSON object>",
  "role3": "<the complete Role 3 Candidate Profiling JSON object>"
}
```

`role1_jd_analytics` and `role3_candidate_profiling` are equivalent accepted
field names. The service health endpoint is
`${ROLE5_API_BASE_URL}/health` (also available at `/api/v1/health`).

The Role 5 service accepts browser-originated requests, so no proxy is needed
solely for CORS. Handle non-2xx responses in the portal and display the API's
JSON validation message when present.
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131

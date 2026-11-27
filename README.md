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

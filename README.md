# CareerOS — Intelligent Career Command Center

Open-source, self-hostable career intelligence for students, job seekers and educators.
The backend ships a working matching engine, resume builder (LaTeX → PDF), opportunity
discovery pipeline, application tracker, and candidate profile graph. PostgreSQL with
pgvector for embeddings. No paid services required to run it.

## Features

- **Overview** — KPI snapshot of your pipeline (applications, interviews, responses, offers) and "Needs you today" recommendations.
- **Applications board** — Kanban, table, timeline and calendar views over a single record set; AI-assisted follow-up drafts and scheduling.
- **Resume Studio** — LaTeX-templated master + tailored variants; one-click PDF rebuild against your real profile; ATS-labeled quality audit.
- **Discover** — Filtered opportunity feed with full-text and vector hybrid match scoring, ranking snapshots, and a saved/applied list.
- **Interviews** — Question practice with local AI evaluation; on/off methodology (Groq or Ollama — see AI providers below).
- **Career Insights** — Sankey flow, conversion analysis, source efficacy.
- **Backup drill** — operator-initiated snapshot of the database and résumé artifacts, with a manifest and SHA-256 checksums. Snapshots are **unencrypted**; checksums verify integrity, not confidentiality. No scheduler or off-box target is bundled.

## Prerequisites

- **Docker** (Engine 24+)
- **Docker Compose v2**
- Enough disk for Postgres + LaTeX toolchain (~2 GB) and node_modules during build.
- An empty port **8080** (frontend nginx) and **8005** (backend) for host ports, or overrides via `CAREEROS_FRONTEND_PORT` / `CAREEROS_BACKEND_PORT`.

## Quickstart

```bash
git clone <repository-url> careeros
cd careeros
cp .env.example .env
# Generate and replace the empty required values before starting:
#   python3 -c "import secrets; print(secrets.token_hex(32))"
#   POSTGRES_PASSWORD, SECRET_KEY, CAREEROS_TOKEN_SECRET
# The stack refuses to start while any of them is blank.
docker compose up -d --build
```

Then open **http://localhost:8080**. The first user to complete onboarding claims the instance. There is no default credential and no sign-up/account system — single tenant, self-hosted.

## What ships

- `frontend/` — React + Vite + TypeScript SPA served by nginx (single build artifact)
- `backend/`  — FastAPI + SQLAlchemy + Google Calendar/email/AI adapters (all optional)
- `backend/storage/resumes/` — your PDFs and TeX (never committed; lives in the `resume_storage` volume)
- `deploy/`     — Dockerfiles + `nginx.conf` + optional TLS reference (`nginx.tls.conf`)
- `.github/workflows/ci.yml` — 5-job CI (backend suite on a synthetic disposable DB, frontend, security, Docker boot validation, release gate). The project does not ship CI secrets — all defaults are synthetic.

## Configuration

All config is via `.env` plus the Docker Compose network. See `.env.example` for the full list of supported variables. Never commit `.env`. The self-host path uses a **bundled** Postgres (`pgvector/pgvector:pg17, port internal only`).

Frontend nginx reverse-proxies `/api/*` to the backend automatically; no CORS or sub-path mounting is required.

## AI providers

*Everything in CareerOS runs without any AI key.* AI is an enhancement, not a dependency:

- **Groq** (`GROQ_API_KEY`) — the matching-engine explanations, interview-question authoring and some Resume Studio features.
- **Ollama** (`OLLAMA_BASE_URL`, default tries `http://host.docker.internal:11434`) — local inference for text classification and everyday chat.

Leave both unset for a fully local instance; features fall back gracefully with explicit "AI unavailable" messaging (not errors).

---

### Backup warning

This application holds **your** personal data (resumes, job applications, interview notes, career profiles — all PII). Backups, snapshots and restores are **your** operational responsibility. The repo ships operator-controlled scripts, never an automatic scheduler. Before upgrading the running container, snapshot Postgres with:

```bash
docker compose exec -T db pg_dump -U careeros -d careeros > careeros_$(date +%F).sql
```

Restore drills are documented in `docs/self-hosting.md` and exercised in `tests/test_backup_restore.py`.

---

## Troubleshooting

- `Embedding must come from pgvector >= 0.8` → confirm `CREATE EXTENSION vector;` succeeded in the bundled db before migrations ran (the bundled bootstrap creates it automatically).
- Port 8080 already bound → `CAREEROS_FRONTEND_PORT=8082 docker compose up -d` or kill whatever holds 8080.
- First run appears "empty" → that's expected; complete the onboarding wizard.
- Frontend shows "CareerOS backend is temporarily unreachable" → `docker compose logs backend` and confirm `/api/ready` is `200`.
- PostgreSQL migration `ERROR: type "vector" does not exist` → you ran a manual `psql CREATE TABLE` against the db before bootstrap; use the bundled compose flow instead.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). Third-party
dependencies retain their own licenses; the audit and dependency-license
review are recorded in `docs/opensource-audit.md`.

## Not yet production-ready for your data

Bring this offline community helm with care: review `SECURITY.md`, do not expose a self-hosted instance publicly without deliberate hardening, and rehearse a backup + restore before entrusting your personal data to it.

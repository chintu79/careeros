# CareerOS — Open-Source & Self-Hosting Audit (Phase 1, 2026-11-12)

Scope: the local working tree with `careeros-push` mirror as the public artifact.
Out of scope: production data, resume contents of live users, credentials (never read).

## 1. Headline findings (severity-ordered)

### P0 — live credentials committed to the developer example file
The env template shipped with populated values for: `DATABASE_URL` (a managed Postgres URL with inline password), `GROQ_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`. The file was tracked from project init.

`deploy/.env.production.example` also carried a populated `DATABASE_URL`.

**Remediation applied in this phase** — production-shaped example values replaced with inert placeholders in both files. The push mirror was scrubbed the same way before the public release branch was cut.

**Note:** history is not rewritten. The public remote may still serve the affected values from older commits. **Operator action required:** inspect the public tree, rotate the hosted-DB credential and the Adzuna credentials, and decide whether a history rewrite or force-push is acceptable. Branch protection on `main` means a direct scrub requires either temporary relaxation of protection or a reviewed scrub PR — not an action an agent may take alone.

### P0 — hardcoded default signing secret in source
`backend/app/config.py` shipped a hardcoded default `SECRET_KEY` for all environments. Any instance booting without `SECRET_KEY` set signs tokens with a publicly known key — trivial token forgery.

**Remediation (applied this phase):** default reduced to `""`; `validate_security_configuration()` hard-fails in production when the secret is missing/weak; conftest sets a synthetic test-only secret; all tests green required before merge.

### P1 — restore tooling vs managed-Postgres-only code
* No code requires Supabase SDKs; the backend is plain SQLAlchemy (PostgreSQL only). Supabase is only a host today, not a dependency.
* Migrations live in `backend/app/services/database_migration.py`; `run_database_migrations` behind `CAREEROS_RUN_MIGRATIONS=1` (default off). Self-hosting flow requires an explicit migration step or first-boot migration.

### P1 — hardcoded developer ports and origins
`frontend/vite.config.ts` pins port `5174` and proxies `/api` to `http://127.0.0.1:8005`. `VITE_API_BASE_URL` is decoupled. Production bundle no longer contains absolute API host — same-origin via nginx. Dev proxy remains a dev convenience only.

`CORS` default in `config.py` is developer origins — must remain env-configured (never `*`).

### P1 — no bundled Postgres in default compose (fixed)
Root-level `docker-compose.yml` now adds PostgreSQL 17 + pgvector + `backend` + `frontend` + named `pgdata` volume; nginx reverse proxy ships in the frontend image.

### P1 — resume storage PII as development artifact
`backend/storage/resumes/` contains 2,697 live-user files (~35 MB) in the dev tree — never committed (gitignored), present only on the single workstation as production user data. Self-hosting default starts empty.

### P2 — AI provider wiring
All AI integrations are optional. The deterministic path (matching, ranking, extraction) runs fully offline. Groq/Ollama are enhancements only; absence is not an error.

### P2 — GitGuardian in CI
The public CI reports findings on every PR. Any remaining secret-shaped strings in the tree must be identified and replaced with placeholders; the local scanner (`.github/scripts/secret_scan.py`) is advisory only and does not replace the GitGuardian gate on `main`.

## 2. Public-tree hygiene (careeros-push)

- Env templates (dev + production examples) contain placeholders only; verified before the release branch was cut.
- PII scrub applied across source/tests/e2e: personal name → synthetic placeholder, college → generic placeholder, emails/phones/URLs → example.com placeholders.
- Docs package added: README (self-host quickstart), SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, ROADMAP.md, docs/self-hosting.md, docs/troubleshooting.md.
- LICENSE choice and publish/visibility change remain **operator decisions** — not taken by the agent.

## 3. Outstanding operator actions

1. Rotate the hosted-DB credential and Adzuna credentials that appeared in example files historically.
2. Decide on git history rewrite for the public remote (or accept and document the exposure).
3. Choose a license (MIT/Apache-2.0/AGPL-3.0) and approve adding `LICENSE`.
4. Approve PR #2 (public release branch) and merge to `main`.
5. P0-05 (production restore drill) remains blocked by the free Supabase tier — operator choice, not agent action.

## 4. Verification performed

- Fresh-install proof on a disposable clone: clone → env from templates → `docker compose up -d --build` → all three services healthy; nginx serves SPA (200) and proxies API (200).
- Token minting bootstrap: open only pre-onboarding-completion; hard-closed after `onboarding_status=completed` + `onboarding_step>=6`.
- 566 backend tests pass; frontend vitest 83/83 green; local secret scan clean.
- Live production backend (PID 2739463, :8005) and frontend (:5174) never touched; resume storage never read or modified.

# CareerOS — Open-Source & Self-Hosting Audit (Phase 1, 2026-11-11)

Scope: the local working tree with `careeros-push` mirror as the public artifact.
Out of scope: production data, resume contents of live users, credentials (never read).

## 1. Headline findings (severity-ordered)

### P0 — live credentials committed to the developer example file
The env template shipped with populated values for: `DATABASE_URL` (a loopback Supabase CLI DSN using the CLI's default local credentials — not a hosted/cloud credential), `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`. Fingerprint re-verification (2026-11-11) confirms these three; no real `GROQ_API_KEY` was confirmed in history.

`deploy/.env.production.example` also carried a populated `DATABASE_URL`.

**Remediation applied in this phase** — production-shaped example values replaced with inert placeholders in both files. The push mirror was scrubbed the same way before the public release branch was cut.

**Note:** history is not rewritten — the operator decision is to preserve existing history. The public remote may still serve the affected values from older commits. **Operator action required:** revoke the Adzuna pair in the Adzuna developer portal (retiring the integration does not revoke credentials), and bind the local Supabase DB port to loopback using the commands in §5. No history rewrite will be performed.

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
- Apache License 2.0 adopted (operator decision): root `LICENSE` added and `frontend/package.json` declares `Apache-2.0`. Publish/visibility change remains an **operator decision** — not taken by the agent.

## 3. Outstanding operator actions

1. Revoke the Adzuna credentials that appeared in example files historically. The integration is retired in v3.1.0 and the code no longer reads these values, but removing code does not revoke credentials.
2. Bind the local Supabase DB port to loopback using the operator-run commands in §5.
3. Approve PR #2 (public release branch) and merge to `main`.
4. P0-05 (production restore drill) remains blocked by the free Supabase tier — operator choice, not agent action.

Git history is preserved by operator decision; no rewrite or force-push was performed.

## 4. Verification performed

- Fresh-install proof on a disposable clone: clone → env from templates → `docker compose up -d --build` → all three services healthy; nginx serves SPA (200) and proxies API (200).
- Disposable self-host re-validation (2026-11-11): 3/3 services healthy; `/api/health` and `/api/ready` 200; first-run token mint 200 with `mode=production`; authenticated `GET /api/candidate` 200; backend+frontend restart keeps health/ready 200; `pgdata` and `resume_storage` volumes persist; backend logs contain no secret-shaped lines.
- Token minting bootstrap: open only pre-onboarding-completion; hard-closed after `onboarding_status=completed` + `onboarding_step>=6`.
- 559 backend tests pass (1 skipped) in local synthetic mode, including the Adzuna-retirement regressions; frontend vitest 83/83 green; local secret scan clean.
- `docker compose config` validates; local Supabase CLI accepts a read-only loopback query (`select 1`) at `127.0.0.1:54322`. The current host publish remains `0.0.0.0` until the operator runs the §5 change.
- Live production backend (PID 2739463, :8005) and frontend (:5174) never touched; resume storage never read or modified.

## 5. Local Supabase CLI port binding (operator-run)

The public repository does not ship a `supabase/config.toml`; the local stack on this workstation is managed by the Supabase CLI in an operator-side project directory (outside this repository). Its `[db] port = 54322` sets the port only — there is no host-IP setting — and the running container publishes `0.0.0.0:54322 -> 5432/tcp` (verified with `docker inspect`: empty `HostIp`). This is a **local-development** exposure, not a hosted Supabase configuration.

Official Supabase guidance for loopback-only local ports is a custom Docker bridge network with a host-binding option. The exact operator-run change (requires stopping and starting the local stack; not performed by the release session, and it does not touch any hosted project):

```bash
cd <your-supabase-project>        # directory containing supabase/config.toml
docker network create \
  -o 'com.docker.network.bridge.host_binding_ipv4=127.0.0.1' \
  careeros-local-loopback

npx supabase stop          # local stack only
npx supabase start --network-id careeros-local-loopback

# verify: expect only 127.0.0.1:54322, no 0.0.0.0/[::] entries
docker port supabase_db_<project-id>
psql 'postgresql://postgres:postgres@127.0.0.1:54322/postgres' -c 'select 1'
```

Internal Docker-network connectivity is preserved: Supabase services address the database as `db:5432` on the shared network, so only the host publication changes. Application configuration that uses `127.0.0.1:54322` continues to work. On Docker Desktop (macOS/Windows) the bridge option is reported not to restrict published ports; on Linux Docker Engine it does.

## 6. Dependency licensing review (direct dependencies)

- Frontend runtime: `react`, `react-dom` (MIT), `lucide-react` (ISC). No GPL/AGPL runtime dependency.
- Backend direct dependencies: MIT/BSD/Apache-2.0, with one **LGPL-3.0-only** dependency: `psycopg` (PostgreSQL driver). It is installed unmodified from PyPI and dynamically imported, not vendored or statically linked. Anyone distributing a binary bundle that includes it must meet LGPL-3.0 obligations (license text and corresponding source availability). This is a distribution consideration, not an incompatibility with Apache-2.0.
- `cryptography` is dual-licensed Apache-2.0 OR BSD-3-Clause; `pillow` is MIT-CMU; `reportlab` is BSD.
- Fonts (Geist, Geist Mono, Inter) are loaded at runtime from Google Fonts under the SIL Open Font License; no font files are bundled. The bundled `frontend/public/vite.svg` is the Vite logo from the MIT-licensed Vite project.
- No third-party copyright notices were modified. No NOTICE file was added: the repository vendors no third-party code requiring one.

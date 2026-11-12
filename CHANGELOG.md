# Changelog

All notable changes to CareerOS are documented here. Date-ordered; minor releases.

## [3.1.0] — 2026-11-11 (unreleased)

### Added
- Self-hosting one-command installation: root-level `docker-compose.yml` bundling PostgreSQL 17 + pgvector, FastAPI backend (non-root container), React frontend served by nginx.
- First-run bootstrap flow: pre-onboarding instances accept token minting; onboarding completion permanently closes the bootstrap window.
- `backend/ops/bootstrap.py` — idempotent schema initializer with `pgvector` extension guard and no-op-if-initialized.
- `CAREEROS_BACKEND_PORT` / `CAREEROS_FRONTEND_PORT` overrides for the self-host Compose.
- Public-repo hygiene: `SECURITY.md`, `CONTRIBUTING.md`, `docs/opensource-audit.md`.
- Apache License 2.0 (`LICENSE`); `frontend/package.json` declares the same license.

### Changed
- Never-inherited-iOS `SECRET_KEY` default removed; the signing secret is now env-provided only.
- `.env.example` ships placeholder values only (never live credentials).
- Compose files label projects `interniq/careeros`.
- Local Supabase CLI port-binding guidance documented for loopback-only exposure.

### Removed
- Adzuna integration: connector, scheduler branch, UI credential fields, configuration variables, and default source entry. Existing `Adzuna` source rows are marked unsupported. Adzuna credentials exposed in Git history still require revocation in the provider portal; removing the integration does not revoke them.

### Fixed
- First-run onboarding deadlock in production-mode self-host (token endpoint refused all mints until any candidate profile existed; it now allows minting until onboarding reaches completion).
- Example file tree no longer contains developer-side credentials.

## [3.0.9] — 2026-11-10

- Off-box encrypted backup workflow (gpg AES256), full-inventory restore drill on synthetic data.
- Supervised deployment scripts with readiness gate and rollback.
- Recovery drill and failure-matrix verification across CI.

## [3.0.8] — 2026-11-10

- `react-hooks/exhaustive-deps` resolved; shared artifact storage dir for backend tests; lint baseline preserved (advisory).

## [3.0.7] — 2026-11-10

- GitHub Actions CI with synthetic disposable DB fork; public narrowed source pushed to `chintu79/careeros` (public).
- Branch protection recommendation documented; pending explicit operator approval.

## [3.0.6] — 2026-11-10

- Observability floor: structured JSON logs, request-id propagation, bounded readiness, structured diagnostics at `/api/internal/metrics`.

## [3.0.5] — 2026-11-10

- Backup and restore tooling with manifest verification on synthetic forks (80-file inventory).
- Disposable fork lifecycle teardown is strict.

## [3.0.4] — 2026-11-09

- Migration guard hardening; `pg_dump`-based fork lifecycle; `test_iteration_2_*` test isolation on fork infrastructure.

## [3.0.2] — 2026-11-09

- AI workflow auth (S-001), rate limiting (S-004), error sanitization (S-001 related), uploads magique-byte check, CORS cleanup.

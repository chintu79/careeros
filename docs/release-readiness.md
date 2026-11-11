# CareerOS — v3.1.0 Release Readiness

## Definition of done

A new user can `git clone`, `cp .env.example .env`, set three secrets,
`docker compose up -d --build`, and get a working instance through onboarding
and opportunity browsing without any production infrastructure.

## Verified so far (working tree)

- Docker Compose v2 self-hosting stack builds and reaches
  `Up (healthy)` for all three services on a disposable clone.
- Fresh install (clone-equivalent) → migrations run → onboarding completes →
  opportunities page loads → token minting open until onboarding completes →
  hard-closes on `completed`+`step 6`.
- LaTeX/PDF generation path present (as in prior versions).
- 566 backend tests pass against a disposable test fork.
- All forks and volumes cleaned up afterward.

## What must not leak

- `.env` / `.env.*` except templates (`.env.example`, `.env.production.example` — placeholders only).
- `backend/storage/resumes/` (candidate PII).
- Historical tracked files should be re-audited — Phase 1 flagged that the
  pre-3.1.0 tree likely contained developer credentials in the example files.
  Rotation NOT performed — a human must confirm whether any leaked value was ever live,
  and rotate accordingly.

## Required human decisions

1. Rotate (or explicitly declare safe) any credentials that ever appeared in
   `.env.example` / `.env.production.example` in any pushed commit.
2. License choice: MIT / Apache-2.0 / AGPL-3.0 — do not change without explicit approval.
3. README target and launch content: no screenshots yet — add them or launch without them.
4. Final `LICENSE` file (not committed unless explicitly approved).
5. Publish: push tag + release, or merge and announce manually.

## Known opinions

- Multi-user tenancy is out of scope. Do not run this as a public service.
- AI providers are optional; the deterministic path works fully offline.
- S3-compatible artifact storage is out of scope for now; local volume only.
- No leakage paths identified in tracked files beyond `.env.example` — which now holds placeholders.

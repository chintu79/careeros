# Contributing

Thanks for your interest. CareerOS is a personal project first and open source by preference — contributions are welcome but not required.

## Setup

```bash
# Prerequisites:
#   - Python 3.12+ with venv
#   - Node.js 22+
#   - Docker Desktop (for the DB and self-host flow)
#   - PostgreSQL client tools (psql)

git clone <repository-url> careeros
cd careeros
python -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci

# Backend tests create their own disposable synthetic database on the server in
# DATABASE_URL: empty -> migrate -> deterministic seed. The configured database
# is never cloned, so operator rows are never read. The role needs CREATEDB.
backend/venv/bin/pytest tests/ -q

# Frontend
npm --prefix frontend run test    # vitest
npm --prefix frontend run build
```

## Rules of the road

- **Never commit `.env` or real credentials.** The repository ships `.env.example` only.
- **Never commit resume artifacts** — they live in `backend/storage/resumes/` by default and are gitignored.
- **No new dependencies without justification.** The backend server is intentionally dependency-light.
- **Do not weaken tests.** If a security assertion fails, the code is wrong, not the test.
- **No proofs of concept in `scripts/`.** If you want to test an idea, write a proper pull request or an ADR.

## Conventions

- The CI is the contract: branch protection requires all five checks green, plus one approving review, before merge.
- Tests use synthetic data only.
- Migrations run through `backend/ops/migrate.py` with the completion report; free-form SQL is not allowed.

## Opening a pull request

1. Fork → branch → commit.
2. Ensure `npm run lint` and `pytest` stay green.
3. Write a clear problem statement; include a test that fails without the fix.
4. Do **not** include business data, real resumes, or private information of any kind.

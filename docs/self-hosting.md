# Self-hosting CareerOS

A minimal, reproducible install for a single user on your machine.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- An empty `8080` port (override with `CAREEROS_FRONTEND_PORT`)
- Optional: an Ollama daemon on the host (`host.docker.internal:11434` is wired into the backend for this flow)

## Install (one-time)

```bash
git clone <repository-url> careeros
cd careeros

# minimum configuration
cp .env.example .env
.edit_me_required \
  POSTGRES_PASSWORD="$(openssl rand -hex 12)" \
  SECRET_KEY="$(openssl rand -hex 32)" \
  CAREEROS_TOKEN_SECRET="$(openssl rand -hex 32)"

# build + start (first build downloads base images ~800 MB – 1.2 GB)
docker compose up -d --build

# check
docker compose ps
curl -I http://localhost:8080/        # HTTP/1.1 200
curl -I http://localhost:8080/api/health  # HTTP/1.1 200

# open the app in a browser
xdg-open http://localhost:8080/
```

The first user to reach onboarding completes it and permanently claims the instance; subsequent token minting is gated with verified identity as before.

## Required environment variables

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | 24+ chars recommended; bundled Postgres image is internal-only (not published) |
| `SECRET_KEY` | yes | 32+ chars; signs all tokens |
| `CAREEROS_TOKEN_SECRET` | yes | 32+ chars; vault encryption for connector secrets |
| `CAREEROS_TOKEN_TTL` | no | seconds, default 86400 |
| `CAREEROS_ALLOWED_ORIGINS` | no | default `http://localhost:8080,http://127.0.0.1:8080`; do not set `*` |
| `CAREEROS_FRONTEND_PORT` | no | host port for nginx, default 8080 |
| `CAREEROS_BACKEND_PORT` | no | host port for backend, default 8005 (only needed if you want direct access) |
| `SEED_DEMO_DATA` | no | do **not** enable in a real install |
| `GROQ_API_KEY` | no | AI-enhanced writing; absent → AI features disabled gracefully |
| `OLLAMA_BASE_URL` | no | defaults to `http://host.docker.internal:11434` |
| `ADZUNA_APP_ID`/`KEY` | no | optional opportunity source |

## Restart & upgrade

```bash
# stop gracefully
docker compose down

# upgrade: pull latest, rebuild images, restart
git pull
docker compose up -d --build

# resume storage persists in the named volume `resume_storage`
```

Schema changes run automatically on first boot if `CAREEROS_RUN_MIGRATIONS=1` (the default). On upgrade from an older release, explicitly run `docker compose exec backend python -m backend.ops.migrate` under the migration instructions in the release notes.

## Backup

```bash
# Postgres SQL dump (non-destructive)
docker compose exec -T db pg_dump -U careeros -d careeros > careeros_$(date +%F).sql

# Resume artifacts — copy the persistent volume to a safe location
docker run --rm -v resume_storage:/data -v /tmp:/backup alpine:latest tar -C /data -czf /backup/careeros-resumes-$(date +%F).tgz .

# Encrypted off-box backup via the repository's tooling (operator-controlled only):
python -m backend.ops.backup_offbox --create --source <path> --dest /mnt/offbox --keep-last 7
```

## Restore

```bash
docker compose down           # stop, keep volume as-is if intact; use -v to wipe and restore fully
git checkout <same-commit-as-backup>
docker compose build backend   # resumes
docker compose up -d --no-deps db backend
cat careeros_2026-11-10.sql | docker compose exec -T db psql -U careeros -d careeros
docker compose up -d
```

## Air-gapped / offline-ish

Ollama is the only local AI option; everything deterministic (matching, extraction, ranking) runs offline on Postgres with no external call.

## Non-goals

CareerOS in single-tenant mode has no multi-user isolation and no delegated administration. Do not run it as a public service for multiple users.

## Help

See `docs/self-hosting.md` (this file), `README.md`, `SECURITY.md`. Open issues only for reproducible bugs; security findings go through `SECURITY.md`.

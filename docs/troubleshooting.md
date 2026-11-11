# Troubleshooting

## Startup

| Symptom | Probable cause | Fix |
|---|---|---|
| `dependency failed to start: container careeros-backend-1 is unhealthy` | migrations failed (unused `pgvector` extension) | `docker compose logs backend`; ensure nothing else holds port 8005; confirm pgvector built and running |
| `type "vector" does not exist` | bootstrap ran against a pre-initialized DB without pgvector | drop the bundled `pgdata` volume: `docker compose down -v && docker compose up -d --force-recreate`; note the volume is wiped |
| `POSTGRES_PASSWORD: unauthorized` | bundled Postgres refuses the bootstrapping credential | `.env` lacks a valid `POSTGRES_PASSWORD`; check `docker compose config` output |
| `psql: error: FATAL: password authentication failed` | `.env` was not copied, or wrong file picked | confirm `.env` sits in the same directory as `docker-compose.yml` |
| Port already in use | host service on 8005 or 8080 | `CAREEROS_BACKEND_PORT=8010 CAREEROS_FRONTEND_PORT=8081 docker compose up -d` |

## Runtime

| Symptom | Probable cause | Fix |
|---|---|---|
| "CareerOS temporarily unreachable" banner on every page | backend health check failing | `curl -I http://localhost:8080/api/health` → 200 expected; backend logs will show actual reason |
| Resume preview 401 | stale token TTL (>24h) | `TOKEN_VERSION` bump once; log in again |
| "AI unavailable" everywhere | no Groq key + no Ollama reachable | expected when both are unset; set one |
| Onboarding loops back to step 1 | browser cache | hard reload (`Ctrl+Shift+R`); check `docker compose logs frontend` |
| Resume preview blocked | download size > nginx `client_max_body_size` | not configurable in one place; use the backend endpoint directly |

## Data

| Symptom | Probable cause | Fix |
|---|---|---|
| `/tmp/careeros-fork-lifecycle/` marker leaks | tombstoned test forks | `python -m backend.app.testing.fork_lifecycle --reconcile-markers --confirm` |
| Files missing from Resume Studio preview | artifact volume lost or path wrong | `docker volume inspect resume_storage`; verify path listing inside container |

## Notify

Issues go in GitHub Issues; security findings → `SECURITY.md`.

# Roadmap

## Near term (what the first release should ship, honestly)

- [x] Self-host onboarding completes end-to-end on a clean clone (docker compose up)
- [x] ATS quality audit for resume PDF generation
- [x] Skills-evidence extraction across repos and resumes
- [x] Backup & restore tooling produced and exercised on disposable forks
- [ ] First-published release on GitHub
- [ ] Documented upgrade path from v3.x line (migration discipline proof)
- [ ] S3-compatible resume artifact storage (optional; not mandatory)

## Mid term

- [ ] Multi-user isolation inside one instance (proper tenant boundaries)
  - every candidate-owned read scoped by `user_id`
  - secrets per-user vault
  - per-user rate-limit budgets
  - admin "system" endpoint separation
- [ ] Optional Ollama first-run download of default model (ai bootstrap)
- [ ] Deterministic scoring verification tests across all match variants
- [ ] Scheduled backup to off-box storage with explicit confirmation and age-based alerting
- [ ] Restore drill harness against a full clone of a populated instance

## Non-goals

- No Kubernetes operator. No service mesh. No "enterprise SSO" PR.
- No migration of any user's existing data from any hosted service.
- No guarantee of accuracy or fairness in automated scoring — the ranking is a heuristic assist, not a hiring signal. Both candidates and operators must be aware.
- No monetization gate on the core self-hosted path; keep it usable by anyone with Docker.

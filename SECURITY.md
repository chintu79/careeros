# Security

## Reporting a vulnerability

Please do **not** open a public issue for security findings. Email the maintainer with details and a minimal reproduction. Expect acknowledgement within a week; fixes land before disclosure.

## Scope

CareerOS stores personally identifying information (resumes, contact details and application history). A self-hosted instance is single-tenant — running it for multiple users without additional isolation engineering is **out of scope** and not recommended.

## Authentication model

- Bearer tokens (HMAC-SHA256), TTL up to 24 h, revocable by bumping `TOKEN_VERSION`. There are no user accounts inside the DB — tokens are identity.
- Empty instances (zero candidate profiles) accept token minting for user_id=1 during the bootstrap window. The window closes permanently once onboarding is marked completed.
- Defaults: no admin dashboard, no unauthenticated write endpoints, rate limiting is on by default.

## Hardening checklist for self-hosting

1. **You are the admin.** The single-tenant model is deliberate; do not multi-tenant this.
2. **Tailscale/VPN first.** Do not expose an instance publicly without a reverse proxy with explicit TLS and IP restrictions.
3. **Set strong secrets.** `openssl rand -hex 32`. Never reuse the template placeholders.
4. **Back up before upgrade.** Rehearsed restore is the only safe upgrade.
5. **Restrict CORS.** Never `*`; same-origin default covers nginx deployments.
6. **Rotate token secrets.** `TOKEN_VERSION` bump invalidates outstanding tokens immediately.

## Known design limitations (be aware)

- No in-app password/RBAC yet; the single-tenant model keeps this out of scope deliberately.
- Resume artifacts live on disk in a volume; fsync behavior is filesystem-dependent and is verified in tests.
- AI providers (Groq, Ollama) send profile content off-box when enabled; disable both to remain fully local.

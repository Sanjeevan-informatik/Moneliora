# Deployment and operations

[Back to README](../README.md)

## Choose a deployment mode

The [hosted live demo](https://moneliora-live-demo.sanjeevanvive.chatgpt.site) is an owner-private static export. It contains no FastAPI server or customer database. See [hosted demo maintenance](HOSTED_DEMO.md) to update that deployment.

For a hosted FastAPI preview, use the [Render blueprint](../render.yaml) or an equivalent Python host with these commands:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
```

The host supplies `PORT`. Configure `MONELIORA_PUBLIC_PREVIEW=true` and `MONELIORA_SECURE_COOKIES=true`, set `MONELIORA_ORIGIN` to the public HTTPS origin, and use `/api/health` for health checks. The blueprint enables preview mode and selects PayPal sandbox mode. Do not add payment or market-data secrets to an educational preview.

Preview mode blocks customer and billing APIs while allowing health, the read-only offer catalog, and optional quote status/snapshot reads. The visible portfolio continues to use fictional EUR prices. Account, consultation, market-data, and payment screens are hidden.

Connect the intended GitHub branch to the host and verify which commit was deployed. A GitHub merge alone does not publish the separately hosted static demo. Configure storage and restart behaviour for the selected host; do not rely on a prototype database for real customer records.

## Environment configuration

Settings are read from process environment variables; the application does not automatically load `.env` files. [.env.example](../.env.example) documents common names and placeholders. Configure actual values through the host's environment or your shell, and keep credentials out of source control.

| Variable | Purpose |
| --- | --- |
| `MONELIORA_PUBLIC_PREVIEW` | Set to `true` to block customer and billing APIs. |
| `MONELIORA_ORIGIN` | Expected frontend origin; use the public HTTPS origin when hosted. |
| `MONELIORA_SECURE_COOKIES` | Use `true` behind correctly configured HTTPS. |
| `MONELIORA_DB` | Database location; use durable private storage for configured backend workflows. |
| `MONELIORA_ADMIN_TOKEN` | Random administrative secret of at least 32 characters; never expose it in URLs or frontend code. |
| `MONELIORA_PILOT_ENABLED` | Optional pilot intake, closed by default and subject to further required configuration. |
| `MONELIORA_PILOT_ONLY` | Limits the backend to free tools and pilot workflows, blocking legacy account, consultation, booking, and billing APIs. |

For pilot intake, follow the complete [pilot operations configuration](PILOT_OPERATIONS.md), including seller identity and document URLs. Setting one flag is insufficient. For provider credentials and account prototypes, see [integrations](INTEGRATIONS.md).

## Existing backend controls

- Content Security Policy, restrictive framing, referrer and permissions policies, and security response headers.
- Validated request types and lengths, parameterized database queries, bounded request-body reads, and in-process rate limiting.
- Administrative API access disabled unless an adequately sized token is configured.
- Account prototype with Argon2 password hashing, HttpOnly session cookies, CSRF controls, lockout, and optional authenticator MFA.
- Preview and pilot-only policies that restrict which APIs can be reached.
- Regression tests and dependency auditing in [CI](../.github/workflows/security.yml).

These controls describe the FastAPI backend. The static demo has a separate hosting environment and does not run backend middleware.

## Retention and administration

Legacy consultation requests use a 90-day retention cleanup triggered during submission. Pilot requests expire after 30 days; cleanup runs on creation and operator listing. To enforce pilot cleanup during quiet periods, schedule `python -m moneliora.maintenance` with the same database environment. That command does not clean up account or consultation records. No scheduled job is provisioned automatically.

Use the `X-Admin-Token` header for direct administrative API access. Never put a real token in query parameters, frontend source, browser localStorage, shared logs, or example commands. The pilot operator page holds its token only in tab memory. See [pilot operations](PILOT_OPERATIONS.md) for routes and stage meanings.

## Before collecting customer data or payments

The backend remains a prototype. Complete environment-specific testing, independent security assessment, and relevant legal review before enabling customer workflows. The remaining work includes:

- HTTPS termination, trusted proxy configuration, correct secure-cookie handling, and verification of HSTS behaviour.
- Managed administrator identity and role-based access, email verification, password reset, and safe MFA recovery.
- Durable encrypted storage and backups, tested restoration, database migrations, scheduled retention, and data-subject processes.
- Shared rate limiting across workers, ingress body-size limits, bot controls, monitoring, alerts, and incident procedures.
- Confirmed operator identity, privacy and legal notices, consent records, consumer processes, and review of the service's regulatory scope.
- Provider sandbox and failure-path testing, payment reconciliation, webhook replay handling, refunds, cancellations, and licensed market-data use.

Keep preview mode enabled until the intended deployment has been assessed. For the separate service experiment, use the documented pilot-only configuration to avoid exposing unrelated legacy APIs. See [integration limitations](INTEGRATIONS.md) for provider-specific work.

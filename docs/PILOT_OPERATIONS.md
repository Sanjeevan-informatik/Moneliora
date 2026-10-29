# Pilot operations

Pilot interest intake is disabled by default. `/api/offers` is a read-only catalog and can be viewed in preview mode. Hypothesis prices never become checkout prices through this configuration.

## Enable only the intended request flow

Set these in the host environment after providing real operator details and documents:

```text
MONELIORA_PUBLIC_PREVIEW=false
MONELIORA_PILOT_ENABLED=true
MONELIORA_PILOT_ONLY=true
MONELIORA_ORIGIN=https://your-real-domain
MONELIORA_SELLER_NAME=Your actual seller identity
MONELIORA_PRIVACY_URL=https://your-real-domain/privacy
MONELIORA_TERMS_URL=https://your-real-domain/terms
MONELIORA_LEGAL_URL=https://your-real-domain/legal
MONELIORA_ADMIN_TOKEN=<at least 32 characters of randomly generated secret>
MONELIORA_DB=<durable private database path>
```

The application checks required configuration and HTTPS URL syntax, not the legal adequacy or content of those documents. Keep `MONELIORA_PILOT_ONLY=true` for the service experiment: this blocks existing account, consultation and billing APIs while allowing the catalog, pilot intake and protected pilot administration. Without pilot-only mode, turning preview off also exposes the legacy API surfaces. Complete operational, privacy and security checks before accepting real customer data.

No payment API key is required for an interest request. The operator must agree final price, scope and availability separately. The prototype does not send confirmation emails or create calendar events.

## Review and handle requests

Open `/operator` on a trusted device and enter the configured token to review counts, update stages or delete requests. The token stays only in tab memory; Lock or reload clears it. No emails are sent. The console requires HTTPS in public use.

For direct API access, use the `X-Admin-Token` header, never a query parameter or browser localStorage. Keep commands containing real secrets out of shared terminals and logs.

- `GET /api/admin/pilot`: latest 100 requests, aggregate stage counts and retention period.
- `PATCH /api/admin/pilot/{id}` with JSON `{"stage":"contacted"}`: update stage.
- Valid stages: `new`, `contacted`, `qualified`, `completed`, `declined`.
- `DELETE /api/admin/pilot/{id}`: remove a request.

There is intentionally no `paid` stage: the request service does not verify payments. `completed` means the operator marked delivery complete, not that a payment provider confirmed revenue. These routes remain blocked in public preview.

Duplicate email/offer requests within 24 hours return the same generic acknowledgment without creating duplicate records or revealing whether an email already exists. They still count toward the per-IP submission limit. Request data is plain SQLite data; configure encrypted storage/backups and limit access.

## Retention

Pilot requests expire 30 days after creation, regardless of stage. Cleanup runs on creation and operator listing. Schedule `python -m moneliora.maintenance` daily with the same `MONELIORA_DB` environment to enforce cleanup during quiet periods. The command does not remove consultation/account records, whose separate retention requirements still apply. No scheduled job is provisioned automatically.

## Launch acceptance

Verify unavailable and enabled states, real privacy/terms links, a synthetic inquiry, duplicate submission, admin auth/stage update/deletion, preview restrictions, retention, mobile layout and recovery after API errors. Delete synthetic records. Before any separately collected payment, confirm the actual service can be delivered and the merchant/customer processes are ready.

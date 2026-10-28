# Moneliora

A responsive investment **education and virtual-trading** web app. It is **not a broker** and does not accept deposits, execute securities trades, provide live market quotations or give personal investment advice.

## Features
- Searchable stock explorer with sector filters, one-click virtual order preselection and explicitly fictional prices (not a live market feed)
- Friendly guided onboarding, progress tracker, plain-language lessons, FAQ and quick quiz
- Mobile-first layouts, semantic navigation, screen-reader announcements and keyboard focus states
- Watchlist saved in browser localStorage and hypothetical downside calculator
- €5,000 starting virtual portfolio with simulated buy/sell, positions and trade history (saved in browser localStorage; reset requires confirmation)
- Compound growth calculator with monthly contributions and hypothetical positive/negative returns
- Broker transaction cost calculator with order fees and estimated spread
- Consultation-request form persisted in SQLite; requests are **not bookings**
- Admin-only API for listing and deleting consultation requests
- Responsive frontend, no third-party scripts, no analytics trackers

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 . For public hosting, set `MONELIORA_ORIGIN` to the public HTTPS origin and generate `MONELIORA_ADMIN_TOKEN` as a long random secret **outside source control**. Never expose it to the browser or put it in URLs. Configure persistent encrypted storage, secure backups and trusted reverse-proxy networking.

Example admin call (local administrator only):

```bash
curl -H "X-Admin-Token: <secret>" http://127.0.0.1:8000/api/admin/consultations
```

## Security posture
- Strict CSP (no inline scripts/styles, third-party scripts or framing)
- Secure response headers, restrictive referrer and permissions policies
- Server-side validated request types/lengths and automatic 90-day deletion during consultation submission
- Parameterized database queries and per-client rate limiting (single-process only)
- Privileged API disabled unless admin secret is configured and at least 32 characters
- Browser-only paper portfolio: no exchange orders, API keys or sensitive bank credentials
- CI tests plus Python dependency auditing

## Known limits — NOT production hardened yet
- Rate limiting is in process; public deployment needs shared Redis/proxy limits, bot defenses, trusted ingress, strict request size limits and alerts.
- Admin uses a static high-entropy secret, not MFA. Replace with managed identity and RBAC before handling real client volumes.
- SQLite retention cleanup runs only after a new request. Add a scheduled deletion job and documented data subject processes.
- No account registration, server-stored portfolios, billing, real price API, payments or regulated trading. Browser storage is device-local, not encrypted, and can be cleared by the browser.
- No external penetration test, audited threat model, WAF, backups, consent versioning, legal texts, operational monitoring, or deployment validation.
- HSTS depends on the incoming scheme; ensure correct HTTPS termination at the reverse proxy.
- Market prices are deliberately fictional and fixed (paper-trading gains or losses are not market-realistic). Calculators do not account for full taxation or every trading cost.
- Check legal obligations in Germany including GDPR, Impressum, consumer protection and BaFin regulatory perimeter before release.

## Test
```bash
pytest -q
```

Only publish after a full code review, environment-specific testing, independent security assessment and legal review.

## New account and booking prototype (feature/accounts-bookings-integrations)
- Email/password accounts with Argon2 hashes, HttpOnly session cookies, CSRF protection, account lockout and optional TOTP authenticator MFA.
- Account-isolated demo portfolio snapshots, saved watchlists and recent paper trades.
- Logged-in educational booking requests and self-service cancellation; admin approval interface (admin role must be assigned by a trusted operator, never through a public form).
- Optional Twelve Data daily-history endpoint, currently limited to NVDA, MSFT, AAPL and TSLA in the provider's native USD units. It is not live and not connected to paper-trading demo prices.
- Optional Stripe hosted subscription checkout with signed, idempotent webhook processing. Both providers require your own credentials and deployment settings.

Add optional values in the hosting environment, **never commit credentials**:
```text
MONELIORA_TWELVE_DATA_KEY=
MONELIORA_STRIPE_SECRET_KEY=
MONELIORA_STRIPE_PRICE_ID=
MONELIORA_STRIPE_WEBHOOK_SECRET=
MONELIORA_PUBLIC_URL=https://your-domain.example
MONELIORA_SECURE_COOKIES=true
MONELIORA_ORIGIN=https://your-domain.example
```

**Before launch:** Enable HTTPS/TLS termination; configure managed database encryption, backups, email verification and password reset, safe MFA recovery, rate limiting shared across workers, anti-bot protection, email delivery, consent/privacy workflows, retention jobs, request-body enforcement at the proxy, observability, provider licensing, Stripe customer portal and financial/legal review. Stripe subscription handling is an integration scaffold, not a complete billing ledger; verify asynchronous payment handling, entitlement reconciliation and failed-payment behavior. The demo uses local SQLite and should not be entrusted with real customer data. Real orders and personalised investment advice remain disabled. Test using synthetic details only.

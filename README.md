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


## Quotes and charts (feature/market-quotes-charts)

The **Market charts** page has latest-available quotes and 1D / 5D / 1M / 3M / 1Y close-price charts for AAPL, MSFT, NVDA, and TSLA.

To enable the feature, set the server-side environment variable `MONELIORA_TWELVE_DATA_KEY` to an API key authorised for the selected market data. **Never put it in JavaScript, query strings visible to the browser, or GitHub secrets exposed to public workflows.** The server alone talks to Twelve Data. Without the key, users see an explicit unavailable state.

- `GET /api/quotes/status`: available symbols, setup status and disclaimers.
- `GET /api/quotes/latest/{symbol}`: latest provider quote (cached for 75 seconds).
- `GET /api/quotes/chart/{symbol}?range=1M`: historical closing prices (cached according to timeframe).
- The browser polls the quote every 75 seconds only while visible, and redraws the historical chart on selection changes.
- Chart values use provider-native **USD**. The separate practice portfolio continues using **fictional EUR** example prices. Market feed never controls virtual buy/sell prices.
- **Not guaranteed real-time:** exchange licensing, feed entitlements, provider-plan delay, exchange sessions, credit limits and quote timestamps determine actual freshness. The UI never fabricates prices when the provider is not configured.
- For public commercial display, independently confirm Twelve Data's exchange-specific commercial display/redistribution rights, pricing and rate limits. A consumer API key alone may not permit redistribution to your web visitors.

Run `node --check static/market.js` and `pytest -q` before merging.


## PayPal subscriptions (feature/paypal-subscriptions)

PayPal is optional and **disabled until configured**. Configure a PayPal Business developer sandbox account, create a Product and recurring Billing Plans, set the PayPal client ID, secret and exact webhook ID in the server environment according to `.env.example`. Set webhook URL to `https://YOUR-DOMAIN/api/paypal/webhook` and subscribe it to subscription lifecycle events. For local tests, webhook delivery requires a secure publicly reachable development tunnel.

Customers must sign in. They can choose Premium or Pro, approve the displayed price on PayPal, manually verify the actual provider status and cancel. The app does not create billing plans or set the price: the merchant's PayPal plan determines the amount and cadence. **Do not enable real payments without approved prices, legal terms and tests.** The client-side success return does **not** activate any entitlement; subscriptions are verified against PayPal using account-specific plan IDs and a unique checkout intent. Signed webhook notifications are checked with PayPal before reconciliation. Provider errors deliberately remain ambiguous and may require manual reconciliation. Existing Stripe subscriptions block PayPal checkouts and vice versa where known.

### Operational and security gaps
- First-party PayPal merchant configuration and webhook credentials are required; no keys included.
- Sandbox tests simulate network responses and do not establish end-to-end PayPal certification. Run real sandbox approval, renewal, payment failure, refund, cancellation and webhook replay tests.
- Subscription and webhook calls use SQLite; a production deployment needs durable queues, distributed locking, retries, manual reconciliation, alerts, support/return handling and refunds/chargebacks handling.
- The PayPal environment defaults to sandbox. Live mode additionally requires HTTPS; all bank and billing details stay with PayPal.
- Confirm tax/VAT and consumer withdrawal rules, subscription terms and all existing GDPR/security requirements before collecting real payments.

## Public educational preview deployment
A safe demo deployment blueprint is provided in `render.yaml`. It sets `MONELIORA_PUBLIC_PREVIEW=true`, which **disables every API except the health endpoint** and hides account, consultation, market-data and payment screens. All visible stock prices remain fictional and portfolio state is kept only in the visitor's browser.

Connect the GitHub repository to a hosting provider, select the `feature/public-preview-deployment` branch and deploy using the Render Blueprint (or manually configure equivalent Python runtime, build and start commands). The branch must be merged before auto-deployment from `main`. Set `MONELIORA_PUBLIC_PREVIEW=true` at the host; never upload payment or stock API keys to the preview environment. HTTPS is required for public serving. Render free-tier storage is ephemeral; the public demo intentionally does not persist server-side customer data.

**Do not turn off preview mode in production yet.** Real subscriptions, user registration and personal details require an external security review, verified merchant accounts, database migrations, encrypted backups, legal notices, webhook replay testing, reconciled entitlements, account recovery and a production deployment review.

## Money plan and business lab

The public preview now includes a browser-only planning workspace:

- Monthly cash flow, reserve coverage and a user-selected emergency reserve target.
- Three adjustable goal scenarios, with effective annual returns, proportional annual fees, fixed month-end contributions and inflation-adjusted purchasing power. A chart, accessible end-value table and annual CSV export use the same calculation engine.
- Debt payoff comparison with extra payments and explicit handling of payments that do not reduce principal.
- Single-product business contribution margin, break-even units, operating cash runway and a 20% sales-reduction stress test.
- Optional device-local saving and deletion. Inputs are not sent to the server; saved plans are unencrypted and accessible to anyone using the browser. Goal savings and cash reserves are separate inputs and should not double-count the same money.
- Paper-portfolio concentration context, improved text contrast and scrollable desktop navigation.

All example values are illustrative, not recommended allocations, market forecasts or tax advice. These tools do not establish investment suitability. Model assumptions and educational source links are available alongside the results. Existing accounts, billing and provider integrations retain their existing deployment restrictions.

### Developer verification

```bash
python -m pytest -q
node --test tests/finance.test.cjs
node --check static/planner.js
node --check static/finance.js
```

Node 22+ is used in CI. Pure financial-model tests cover zero and negative returns, fee drag, inflation, invalid values, non-amortizing loans and nonpositive business margins. Python tests isolate databases and verify unique HTML IDs plus configured/unconfigured market snapshot behavior.

Optional browser smoke test (with Playwright and its Chromium browser installed): start Uvicorn, then run `node tests/browser_smoke.cjs`. Set `MONELIORA_TEST_URL` to test another local port. It exercises explorer filtering, virtual trades, watchlists, planner validation, save/reload/delete, corrupt saved data, CSV downloads and desktop/mobile overflow.

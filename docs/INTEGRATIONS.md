# Optional backend integrations

[Back to README](../README.md)

These are configurable backend prototypes. They are not connected in the hosted static demo, and customer/account/billing APIs are blocked in educational preview mode. Keep all credentials server-side and outside source control. Use synthetic details for testing.

## Accounts and booking requests

- Email/password accounts with Argon2 hashes, HttpOnly session cookies, CSRF protection, account lockout, and optional TOTP authenticator MFA.
- Account-isolated demo portfolio snapshots, saved watchlists, and recent paper trades.
- Logged-in educational booking requests and self-service cancellation.
- Administrative approval controls; an administrator role must be assigned by a trusted operator, never through a public registration form.

A request is not a confirmed booking or payment. The separate [pilot interest flow](PILOT_OPERATIONS.md) does not create an account, subscription, entitlement, or revenue record.

Before real customer use, complete email verification, password reset, safe MFA recovery, managed identity controls, and the storage and operational work listed in [deployment](DEPLOYMENT.md).

## Twelve Data quotes and charts

Configure `MONELIORA_TWELVE_DATA_KEY` in the server environment with an API key authorised for the selected data. The server talks to Twelve Data; the key must not appear in browser JavaScript or URLs. Without configuration, the UI reports the feed as unavailable.

The market integration supports AAPL, MSFT, NVDA, and TSLA, with latest-available quotes and 1D / 5D / 1M / 3M / 1Y close-price chart ranges.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/quotes/status` | Supported symbols, setup status, and disclaimers. |
| `GET /api/quotes/latest/{symbol}` | Latest provider quote, cached for 75 seconds. |
| `GET /api/quotes/chart/{symbol}?range=1M` | Historical closing prices, with caching by timeframe. |

The browser polls a quote every 75 seconds only while visible and redraws charts when the selection changes. Chart values use provider-native **USD**. The practice portfolio uses separate, fixed fictional **EUR** prices; provider data never controls virtual buy/sell prices.

Quotes are not guaranteed to be real-time. Exchange entitlements, plan limits, provider delay, market sessions, and timestamps determine freshness. For commercial display, verify the required exchange-specific display and redistribution rights. Possessing an API key alone does not establish permission to redistribute the data.

## Stripe subscriptions

The account module contains an optional hosted subscription checkout and signed, idempotent webhook processing. Configure these values in the hosting environment:

```text
MONELIORA_STRIPE_SECRET_KEY=
MONELIORA_STRIPE_PRICE_ID=
MONELIORA_STRIPE_WEBHOOK_SECRET=
MONELIORA_PUBLIC_URL=https://your-domain.example
MONELIORA_SECURE_COOKIES=true
MONELIORA_ORIGIN=https://your-domain.example
```

The integration is not a complete billing ledger. Validate asynchronous payments, entitlement reconciliation, failed-payment behaviour, customer self-service, and operational recovery before use. Merchant configuration and final prices must be established separately.

## PayPal subscriptions

PayPal is disabled until configured and defaults to sandbox mode. Create a sandbox Product and recurring Billing Plans through a PayPal Business developer account, then configure the variables listed in [.env.example](../.env.example):

```text
MONELIORA_PAYPAL_MODE=sandbox
MONELIORA_PAYPAL_CLIENT_ID=
MONELIORA_PAYPAL_CLIENT_SECRET=
MONELIORA_PAYPAL_WEBHOOK_ID=
MONELIORA_PAYPAL_PREMIUM_PLAN_ID=
MONELIORA_PAYPAL_PRO_PLAN_ID=
MONELIORA_PUBLIC_URL=https://your-domain.example
```

Configure the webhook at `https://YOUR-DOMAIN/api/paypal/webhook` for subscription lifecycle events. Local webhook tests require a securely reachable HTTPS endpoint.

Signed-in customers can choose Premium or Pro, approve the provider's displayed price, verify the provider status, and cancel. Moneliora does not create billing plans or set their prices; the merchant's PayPal plan determines the amount and billing cadence.

The browser success return does not activate an entitlement. Subscriptions are checked with PayPal using account-specific plan IDs and a unique checkout intent. Webhook notifications are verified with PayPal before reconciliation. Provider errors can require manual reconciliation. Known existing Stripe subscriptions block PayPal checkout and vice versa.

## Payment validation and operational gaps

Mock tests do not establish end-to-end provider certification. Test real sandbox approval, renewal, payment failure, refunds, cancellation, duplicate events, and webhook replay before enabling real payments.

The prototypes use SQLite and need durable queues, distributed locking, retries, reconciliation, alerting, and support processes for production operation. PayPal live mode also requires HTTPS; provider pages handle bank and billing information.

Confirm actual prices, service scope, merchant readiness, subscription terms, tax handling, consumer withdrawal processes, privacy requirements, and refunds/chargebacks before taking money. None of these integrations executes securities trades or provides personal investment advice.

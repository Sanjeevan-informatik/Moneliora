# Architecture

## Entry points

- `main.py`: stable deployment entry point, exposes `app`.
- `moneliora/application.py`: assembles the FastAPI application and routers.
- `moneliora/settings.py`: immutable application and pilot settings.
- `moneliora/middleware.py`: security headers, origin/JSON rules, preview API policy and bounded body reads.

## Boundaries

- `routes/pages.py`: public landing page `/`, free studio `/studio`, launch lab `/launch`, health endpoint.
- `routes/consultations.py`: existing educational requests and protected administration.
- `routes/pilot.py`: public offer catalog, optional interest intake and authenticated operator workflow.
- `services/pilot.py`: parameterized SQLite operations, deduplication, stage transitions and retention.
- `accounts.py`: existing accounts, sessions, booking and Stripe integration. This module remains internally coupled and is a future decomposition target; this change preserves its tested behavior.
- `integrations/`: Twelve Data quotes/snapshots and PayPal. Provider configuration remains environment-based and credentials remain server-side.
- `static/finance.js`, `static/launch-model.js`: deterministic calculation models, independent of the DOM.
- `static/planner.js`, `static/launch.js`: UI adapters and opt-in browser persistence.
- `static/landing.*`, `static/site.css`: acquisition site and availability-aware interest flow.
- `static/workbook.*`: printable, session-local action worksheet.

The studio retains its existing scripts, storage keys and features. Old root hash links redirect to `/studio` while preserving the query string and hash. Existing payment-return links therefore keep their query parameters.

## Important boundaries

The pilot inquiry is not a checkout. It creates no subscription, entitlement, booking or revenue record. Public preview always blocks submissions, regardless of the pilot setting. The new catalog exposes no credentials. Existing Stripe/PayPal functionality is not activated by the pilot configuration. Set `MONELIORA_PILOT_ONLY=true` to limit the deployment to free tools, pilot intake and protected pilot operations; this blocks legacy accounts, bookings, consultations and billing APIs.

A custom `Settings` instance configures page, security and request services. Existing account/provider modules still read some configuration at import time; use a separate process/environment for separate provider/account deployments. Do not treat the factory as full multi-tenant isolation.

SQLite storage and in-process rate limits suit a small controlled prototype. Production scaling requires shared rate limiting, durable operational monitoring, backups, identity controls and provider testing already listed in README. Modular source layout is not a security certification.

## Validation

Run `python -m pytest -q`, `node --test tests/*.test.cjs`, JavaScript syntax checks and the optional Chromium smoke suites. Existing account, MFA, billing-mock and market tests remain in the regression suite. Pilot tests cover disabled/partial configuration, preview restrictions, authorization, consent, deduplication, stage validation, retention and chunked request size limits.

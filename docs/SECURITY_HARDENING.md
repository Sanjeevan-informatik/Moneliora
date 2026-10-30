# Security and data-integrity review

[Back to README](../README.md)

This review checks the reported findings against the current Moneliora source. The application remains an educational prototype; passing regression tests is not an independent security certification.

| Reported concern | Finding and change |
| --- | --- |
| Fallback signing secret and custom JWT validation | No JWT implementation or fallback signing secret exists in this version. Authentication uses random opaque cookies with SHA-256 token hashes stored server-side. The example admin secret is now empty, and recognisable placeholder secrets are rejected. |
| Missing revocation | Logout and new login already revoked server-side sessions. Tests now verify replay rejection, expiry, cookie flags, and session/CSRF rotation when MFA changes. |
| Login rate limiting | The old in-memory IP/email-pair limit did not aggregate password spraying and was independent per worker. Atomic SQLite counters now limit login attempts separately by client IP and account identifier across workers sharing the database. |
| Failed-login audit rollback | The old implementation had no authentication audit table. Login failures, successes, throttling, logout, registration and MFA outcomes now have durable events. Failure transactions commit before HTTP errors are raised. |
| Currency precision | Saved account snapshots used floats in JSON, not SQLite REAL currency columns. Snapshots and virtual-order balances now use integer EUR cents; legacy decimal values are validated with Decimal. Analytical return/FX/chart values remain numerical approximations, not a financial ledger. |
| Pagination | Bookings, admin bookings, consultations, pilot inquiries and audit events now have bounded keyset pagination. Account and operator interfaces provide controls for older records. |
| SQLite locking | Shared connections enable WAL, foreign keys, a 10-second busy timeout and full synchronization, and close on success or failure. Multi-step booking capacity, login-counter and Stripe webhook changes use explicit writer transactions. |
| Frontend tokens and CSP | Session tokens were already in HttpOnly cookies, not localStorage. CSRF values and the operator token stay in tab memory. The existing restrictive CSP and no-store policy remain, with explicit object blocking and rejection of cross-site writes using Fetch Metadata. |

## Authentication and audit behaviour

- Login allows up to 30 attempts per client IP and 8 per normalised account identifier in a 15-minute window. Registration and MFA confirmation/disable use limits of 8 per IP and account per window. The next attempt returns HTTP 429 with `Retry-After`.
- Buckets persist across worker restarts. Failed attempts against a known account also retain the existing account lockout. Unknown accounts perform a dummy Argon2 verification to reduce timing differences.
- The app uses the server-observed client address. Configure trusted proxy handling at the hosting layer; arbitrary `X-Forwarded-For` headers must not establish identity. Shared-NAT users share an IP quota.
- Audit rows contain event type, timestamp, optional user ID, and hashes of identifiers/client addresses. Hashes are pseudonymous, not anonymous. Passwords, OTPs, cookies, CSRF tokens and admin secrets are never audit fields.
- Authentication audit rows expire after 30 days. Cleanup runs during authentication throttling, audit listing, and `python -m moneliora.maintenance`. Schedule maintenance for quiet periods. Repeated throttled requests generate at most one throttled event per exhausted bucket/window.
- `GET /api/admin/audit` requires an authenticated account with the administrator role. It is blocked in preview and pilot-only modes. Audit storage is local SQLite, not a tamper-proof external log service.
- Session cookies use HttpOnly, SameSite=Strict and Secure on HTTPS or configured secure deployments. Session tokens are random, expire after 12 hours and are checked against server-side storage on every authenticated request.
- MFA changes invalidate old sessions and return a fresh CSRF token with the new cookie. The account UI adopts the rotated token. Browser-local portfolio and planning data contain no authentication tokens.

## Money schema and migration

`GET /api/account/state` now returns `schema_version: 2`, `cash_cents` and `trades[].amount_cents`. The database stores those values as JSON integers. External clients consuming this endpoint must support this schema.

Legacy PUT requests using `cash` and `amount` in euros remain accepted when each amount has at most two decimal places. Reads validate and migrate legacy stored snapshots without replacing a concurrently saved newer value. Invalid or ambiguous inputs, non-finite values, fractional cents and out-of-range balances are rejected; malformed saved snapshots return HTTP 409 and remain available for operator recovery.

The browser upgrades old paper-portfolio snapshots when loading them and writes cents on the next save/trade. Provider-linked virtual order totals use decimal parsing and round half away from zero once at the order boundary. Portfolio estimates and educational calculators are not bank balances, entitlements, or authoritative payment records. Client-editable snapshots cannot establish financial ownership.

## Pagination contract

All paginated endpoints accept `limit` from 1 to 100 and return `has_more`, `next_cursor` and `limit` alongside their existing collection field. Pass the returned cursor unchanged to retrieve the next page.

Numeric booking, consultation and audit IDs sort descending. Pilot pages sort by creation time and ID, with both values encoded in a cursor so equal timestamps and deletion of the boundary row do not lose the next page. Cursors are not credentials; every request still requires its normal authorization. Pilot counts describe all retained requests, not just the current page.

## Operational limits

WAL permits readers alongside a writer; SQLite still has only one writer at a time. Use local durable storage, retain the WAL/SHM files as part of the database environment, and use SQLite's backup API or a consistent backup procedure. WAL is unsuitable for a database shared over a network filesystem. Sustained write concurrency needs a separately planned database migration and distributed edge abuse controls.

Consultation and pilot submission throttles remain in-process; authentication limits now use the shared database. The database, audit records and MFA secrets still need encrypted storage, access controls, retention operations and production monitoring. The operator still uses a configured admin token; managed operator identity remains future work. See [deployment](DEPLOYMENT.md) and [integration limitations](INTEGRATIONS.md).

References: [Python SQLite transaction contexts](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager), [SQLite WAL](https://sqlite.org/wal.html), [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OWASP logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html), and [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

# Moneliora

**Financial planning, investment education, and business scenario modelling.**

Explore your cash flow, compare savings goals, practise investing with virtual money, and test the numbers behind a business idea. Moneliora combines a responsive browser workspace with an optional FastAPI backend.

## Live demo

### [Open the Moneliora live demo →](https://moneliora-live-demo.sanjeevanvive.chatgpt.site)

> **Access:** the hosted demo is private to the owner's signed-in ChatGPT account. Other visitors do not currently have public access.

Try the planners, virtual portfolio, launch lab, printable worksheet, and sample operator dashboard. The demo uses fictional stock prices and has no customer accounts, intake, bookings, or payments. Optional saved plans remain unencrypted in your browser.

The demo is deployed separately from GitHub. Merging code does not automatically update the hosted version; see [demo maintenance](docs/HOSTED_DEMO.md).

**Explore this repository:** [Features](#features) · [Quick start](#quick-start) · [Pages](#pages) · [Project structure](#project-structure) · [Development](#development) · [Deployment](#deployment) · [Documentation](#documentation)

## Features

| Workspace | What you can do |
| --- | --- |
| Money plan | Model monthly cash flow, cash-reserve coverage, and a reserve target. |
| Savings goals | Compare three return assumptions after fees and inflation, with a chart, results table, and CSV export. |
| Debt explorer | Compare repayment time and interest with extra payments; identify payments that do not reduce principal. |
| Practice portfolio | Start with €5,000 in virtual cash, search and filter example companies, buy or sell virtual shares, and track holdings and concentration. |
| Learning centre | Use plain-language lessons, FAQs, a knowledge check, and growth, transaction-cost, and downside calculators. |
| Business lab | Explore contribution margin, break-even sales, cash runway, and a sales-reduction stress test. |
| Launch lab | Model a 48-hour experiment with delivery capacity, founder time, acquisition costs, and an action checklist. |
| Action worksheet | Turn a scenario into a next step and print or save it as a PDF through your browser. |

The frontend includes responsive layouts, keyboard focus states, screen-reader announcements, and optional device-local saving. The hosted demo includes a fictional operator dashboard; real pilot intake and operator workflows require a separately configured backend.

## Quick start

You need **Git and Python 3.11+**. Node.js 22+ is used for JavaScript tests; the application does not require a frontend build step.

```bash
git clone https://github.com/Sanjeevan-informatik/Moneliora.git
cd Moneliora
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export MONELIORA_PUBLIC_PREVIEW=true
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:MONELIORA_PUBLIC_PREVIEW = "true"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. These commands enable educational preview mode, which blocks customer and billing APIs. No payment or market-data credentials are needed.

Settings are read from the process environment. [.env.example](.env.example) is a reference; copying it alone does not load its values. For other modes, follow the [deployment guide](docs/DEPLOYMENT.md).

## Pages

| Local route | Purpose |
| --- | --- |
| `/` | Product overview, free tools, and educational-session concepts. |
| `/studio` | Planners, business lab, virtual portfolio, lessons, and calculators. |
| `/launch` | Launch economics, validation checklist, and experiment export. |
| `/static/workbook.html` | Editable action worksheet with browser print/PDF support. |
| `/operator` | Protected pilot request management; locked in backend preview mode. |
| `/api/health` | Application health endpoint. |

The static live demo uses trailing slashes for `/studio/`, `/launch/`, and `/operator/`. Its operator page contains only fictional sample inquiries.

## Project structure

| Path | Responsibility |
| --- | --- |
| [main.py](main.py) | Stable application entry point for Uvicorn. |
| [moneliora/application.py](moneliora/application.py) | FastAPI application and router assembly. |
| [moneliora/settings.py](moneliora/settings.py), [middleware.py](moneliora/middleware.py) | Configuration, security headers, request controls, and preview restrictions. |
| [moneliora/routes/](moneliora/routes/), [services/](moneliora/services/) | Pages, consultation requests, pilot APIs, and persistence. |
| [moneliora/accounts.py](moneliora/accounts.py), [integrations/](moneliora/integrations/) | Optional account, booking, market-data, and payment prototypes. |
| [static/](static/) | HTML, CSS, JavaScript, and browser-only calculation models. |
| [scripts/build_demo.py](scripts/build_demo.py) | Allowlisted static export for the hosted demo. |
| [tests/](tests/) | Python, JavaScript calculation, and browser regression checks. |
| [docs/](docs/) | Architecture, business experiment, operations, and hosting guides. |

See [architecture](docs/ARCHITECTURE.md) for module boundaries and remaining coupling.

## Development

Run the backend and calculation tests from the repository root:

```bash
python -m pytest -q
node --test tests/*.test.cjs
```

The [CI workflow](.github/workflows/security.yml) also checks JavaScript syntax and audits Python dependencies. Tests cover financial edge cases, request validation, authorization, preview restrictions, pilot retention, provider mocks, and the static export.

The [security review](docs/SECURITY_HARDENING.md) documents authentication throttling and audits, session revocation, integer-cent snapshot migration, pagination, and SQLite concurrency behaviour.

For optional browser checks, install Playwright and its Chromium browser, start the local application, then run:

```bash
node tests/browser_smoke.cjs
node tests/commercial_browser.cjs
```

For another local port, set `MONELIORA_TEST_URL` to the full studio URL for `browser_smoke.cjs` (for example, `http://127.0.0.1:8001/studio`) and `MONELIORA_TEST_ORIGIN` to the origin for `commercial_browser.cjs` (`http://127.0.0.1:8001`). The suites cover planners, virtual trades, saved state, exports, pilot/operator UI states, worksheet printing, and desktop/mobile layouts.

To create a static demo export, choose an **empty directory outside this repository**:

```bash
python scripts/build_demo.py /absolute/path/to/moneliora-demo
python -m pytest -q tests/test_demo_export.py
```

Exporting does not deploy the site. Follow [hosted demo maintenance](docs/HOSTED_DEMO.md) to publish an update.

## Deployment

| Mode | Scope | Guide |
| --- | --- | --- |
| Hosted static demo | Browser tools and fictional operator samples; no FastAPI backend or customer database. | [Hosted demo](docs/HOSTED_DEMO.md) |
| FastAPI educational preview | Free tools with customer and billing APIs blocked by `MONELIORA_PUBLIC_PREVIEW=true`. | [Deployment](docs/DEPLOYMENT.md) and [Render blueprint](render.yaml) |
| Configured pilot | Optional consented interest requests and protected operations; no checkout or verified revenue records. | [Pilot operations](docs/PILOT_OPERATIONS.md) |
| Optional integrations | Account, booking, Twelve Data, Stripe, and PayPal prototypes requiring separate setup and validation. | [Integrations](docs/INTEGRATIONS.md) |

Moneliora is an educational prototype. It does not accept deposits, execute securities trades, or provide personal investment advice. The practice portfolio uses fixed fictional EUR prices; optional provider quotes are separate and are not guaranteed to be real-time. Calculator results are assumptions, not forecasts.

The proposed €49 and €99 guided-session prices are research hypotheses. The [48-hour business experiment](docs/BUSINESS_MODEL.md) tests demand and costs; it does not promise revenue in two days.

Browser saves are unencrypted. Before accepting real customer data or payments, address the documented identity, storage, rate-limiting, provider, privacy, and operational gaps in the [deployment guide](docs/DEPLOYMENT.md).

## Documentation

| Guide | Read it for |
| --- | --- |
| [Hosted demo](docs/HOSTED_DEMO.md) | Live URL, access, export contents, and publishing updates. |
| [Architecture](docs/ARCHITECTURE.md) | Application entry points, module boundaries, and model/UI separation. |
| [Business model](docs/BUSINESS_MODEL.md) | Offer hypotheses, economics, and the 48-hour validation plan. |
| [Pilot operations](docs/PILOT_OPERATIONS.md) | Intake configuration, operator workflow, authorization, and retention. |
| [Deployment](docs/DEPLOYMENT.md) | Hosting modes, environment setup, security controls, and production gaps. |
| [Integrations](docs/INTEGRATIONS.md) | Optional accounts, bookings, market data, Stripe, and PayPal. |
| [Security review](docs/SECURITY_HARDENING.md) | Verified findings, implemented controls, schema changes, and remaining limits. |

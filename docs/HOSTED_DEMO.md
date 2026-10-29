# Hosted demo

URL: https://moneliora-live-demo.sanjeevanvive.chatgpt.site

Access is owner-private through the owner's signed-in ChatGPT account. The deployment contains browser-only static files, not the FastAPI application or a customer database.

| Route | Demo capability |
| --- | --- |
| `/` | Product overview and hypothetical pilot offers |
| `/studio/` | Money plan, savings scenarios, debt payoff, business modelling, virtual portfolio and lessons |
| `/launch/` | Launch economics, checklist and experiment export |
| `/static/workbook.html` | Printable action worksheet |
| `/operator/` | Two fictional inquiries with local stage changes and reset |

Accounts, customer intake, provider quotes, bookings and payments are excluded. No API credentials or customer records are copied. Planning inputs and virtual trades stay in the browser. Optional local storage is unencrypted and should not contain sensitive information. Operator sample changes last only for the current tab.

## Rebuild and publish

1. Check out the intended application commit and run its tests.
2. Run `python scripts/build_demo.py /absolute/path/to/empty-output` with an empty directory outside the repository. The exporter refuses to overwrite an existing export and copies only allowlisted assets.
3. Run `python -m pytest -q tests/test_demo_export.py`. Check JavaScript syntax and the overview, calculators, virtual purchase and sample dashboard in the browser.
4. Update the existing Site's static directory with the export. Preserve its existing hosting manifest and project ID `appgprj_6ae2e954f7c081918862d4070e5438a9`; do not create a new Site for an update.
5. Commit and push the exact Site source, package it with the Sites workflow, and deploy the saved version while preserving the current audience. Confirm a successful deployment before updating this link.

The initial deployment exports application commit `e24bd50a1654a3defb784ef029243d819e0a0e74`. Each export records its source commit and disabled integrations in `demo-info.json`. GitHub merges do not automatically publish a new Site version.

The exporter removes backend-dependent markup and scripts rather than leaving inactive forms on the page. The regression test checks internal links, duplicate IDs, excluded controls and the absence of API calls in exported JavaScript. This demo does not alter the backend's deployment or integration settings.

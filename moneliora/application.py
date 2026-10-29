"""Composition root: routes, integrations and shared policies are wired here."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from moneliora.settings import ROOT, Settings
from moneliora.middleware import SecurityMiddleware
from moneliora.routes import pages, consultations, pilot
from moneliora import accounts
from moneliora.integrations import market_data, market_snapshot, paypal


def create_app(settings: Settings | None = None):
    app = FastAPI(title='Moneliora', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings or Settings()
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    for router in (pages.router, consultations.router, pilot.router, accounts.router,
                   market_data.router, market_snapshot.router, paypal.router):
        app.include_router(router)
    app.add_middleware(SecurityMiddleware)
    return app

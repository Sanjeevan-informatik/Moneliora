"""Public acquisition pages are separate from the interactive learning studio."""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from moneliora.settings import ROOT

router = APIRouter()

@router.get('/')
def home():
    return FileResponse(ROOT / 'static/landing.html')

@router.get('/launch')
def launch():
    return FileResponse(ROOT / 'static/launch.html')

@router.get('/operator')
def operator():
    return FileResponse(ROOT / 'static/operator.html')

@router.get('/studio')
def studio(request: Request):
    if not (request.app.state.settings.public_preview or request.app.state.settings.pilot_only):
        return FileResponse(ROOT / 'static/index.html')
    page = (ROOT / 'static/index.html').read_text()
    for script in ('account.js', 'paypal.js', 'market.js'):
        page = page.replace(f'<script src="/static/{script}" defer></script>', '')
    page = page.replace('<body>', '<body class="public-preview"><div class="preview-banner" role="status">'
                        'PUBLIC EDUCATIONAL PREVIEW — virtual funds only. Accounts, contact forms and payments are disabled. '
                        'Provider quotes require a licensed feed.</div>', 1)
    if request.app.state.settings.pilot_only and not request.app.state.settings.public_preview:
        page = page.replace('PUBLIC EDUCATIONAL PREVIEW — virtual funds only. Accounts, contact forms and payments are disabled.',
                            'EDUCATIONAL STUDIO — virtual funds only. Accounts and payments are disabled. Pilot interest requests are available on the public website.')
    return HTMLResponse(page)

@router.get('/api/health')
def health(request: Request):
    preview = request.app.state.settings.public_preview
    return {'ok': True, 'mode': 'public-preview' if preview else ('pilot-only' if request.app.state.settings.pilot_only else 'education-only'),
            'live_trading': False, 'payments_enabled': False if preview or request.app.state.settings.pilot_only else None}

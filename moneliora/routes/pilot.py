"""Truthful product catalog and opt-in pilot inquiry; disabled until configured."""
from threading import Lock
import time
from typing import Literal
from fastapi import APIRouter, Header, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from moneliora.routes.consultations import require_admin
from moneliora.services import pilot as service
from moneliora.settings import safe_https_url

router = APIRouter()
LOCK = Lock()
HITS = {}

class PilotInput(BaseModel):
    model_config = {'extra': 'forbid', 'str_strip_whitespace': True}
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    offer: Literal['guided-planning', 'business-basics']
    objective: str = Field(min_length=10, max_length=800)
    consent: Literal[True]
    website: str = Field(default='', max_length=0)

    @field_validator('name', 'objective')
    @classmethod
    def plain_text(cls, value):
        if '<' in value or '>' in value or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Use plain text')
        return value

class StageInput(BaseModel):
    model_config = {'extra': 'forbid'}
    stage: Literal['new', 'contacted', 'qualified', 'completed', 'declined']

@router.get('/api/offers')
def offers(request: Request):
    settings = request.app.state.settings
    return {'accepting_requests': settings.pilot_available, 'payments_enabled': False,
            'seller': settings.seller_name if settings.pilot_available else None,
            'privacy_url': settings.privacy_url if safe_https_url(settings.privacy_url) else None,
            'terms_url': settings.terms_url if safe_https_url(settings.terms_url) else None,
            'legal_url': settings.legal_url if safe_https_url(settings.legal_url) else None,
            'offers': [
                {'id': 'guided-planning', 'name': 'Guided planning session', 'minutes': 45,
                 'pilot_price_hypothesis_eur': 49, 'price_status': 'research-hypothesis',
                 'deliverable': 'Guided use of the cash-flow and goal tools, with a personal action worksheet.'},
                {'id': 'business-basics', 'name': 'Business numbers session', 'minutes': 60,
                 'pilot_price_hypothesis_eur': 99, 'price_status': 'research-hypothesis',
                 'deliverable': 'A one-product break-even and cash-flow worksheet using your assumptions.'}
            ]}

@router.post('/api/pilot/requests', status_code=202)
def request_pilot(data: PilotInput, request: Request):
    settings = request.app.state.settings
    if not settings.pilot_available:
        raise HTTPException(503, 'Pilot requests are not open. The free studio remains available.')
    key = request.client.host if request.client else 'unknown'
    instant = time.monotonic()
    with LOCK:
        for client in list(HITS):
            HITS[client] = [t for t in HITS[client] if instant-t < 3600]
            if not HITS[client]:
                del HITS[client]
        if len(HITS) >= 10000 and key not in HITS:
            raise HTTPException(429, 'Please try again later.')
        entries = HITS.setdefault(key, [])
        if len(entries) >= 5:
            raise HTTPException(429, 'Too many requests. Please try again later.')
        entries.append(instant)
    service.create(settings.database, data)
    return {'status': 'received', 'message': 'Interest recorded. This is not a booking or payment. No response time or availability is guaranteed.'}

@router.get('/api/admin/pilot')
def admin_list(request: Request, x_admin_token: str | None = Header(default=None),
               limit:int=Query(100,ge=1,le=100), cursor:str | None=Query(None,max_length=256)):
    require_admin(request, x_admin_token)
    return service.listing(request.app.state.settings.database, limit, cursor)

@router.patch('/api/admin/pilot/{request_id}')
def update(request_id: str, data: StageInput, request: Request, x_admin_token: str | None = Header(default=None)):
    require_admin(request, x_admin_token)
    if not service.transition(request.app.state.settings.database, request_id, data.stage):
        raise HTTPException(404, 'Request not found')
    return {'updated': True}

@router.delete('/api/admin/pilot/{request_id}')
def delete(request_id: str, request: Request, x_admin_token: str | None = Header(default=None)):
    require_admin(request, x_admin_token)
    if not service.remove(request.app.state.settings.database, request_id):
        raise HTTPException(404, 'Request not found')
    return {'deleted': True}

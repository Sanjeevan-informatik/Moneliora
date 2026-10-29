from dataclasses import replace
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from main import app
from moneliora.services import pilot as service
from moneliora.settings import Settings

client = TestClient(app)
HEADERS = {'x-admin-token': 'a'*64}
DATA = {'name': 'Example Person', 'email': 'person@example.org', 'offer': 'guided-planning',
        'objective': 'I want to understand the goal calculator.', 'consent': True, 'website': ''}

@pytest.fixture
def enabled(monkeypatch):
    settings = replace(app.state.settings, pilot_enabled=True, origin='https://example.org',
                       seller_name='Test Operator', privacy_url='https://example.org/privacy',
                       terms_url='https://example.org/terms', legal_url='https://example.org/legal')
    monkeypatch.setitem(app.state._state, 'settings', settings)
    return settings


def test_pilot_closed_by_default():
    assert client.get('/api/offers').json()['accepting_requests'] is False
    assert client.post('/api/pilot/requests', json=DATA).status_code == 503


def test_no_partial_configuration_can_open_requests():
    settings = Settings(pilot_enabled=True, public_preview=False)
    assert not settings.pilot_available
    assert not replace(settings, seller_name='X', admin_token='x'*64, origin='https://example.org',
                       privacy_url='javascript:alert(1)', terms_url='https://example.org/t', legal_url='https://example.org/l').pilot_available


def test_requests_deduplicate_and_operator_can_manage(enabled):
    assert client.get('/api/offers').json()['accepting_requests'] is True
    for _ in range(2):
        response = client.post('/api/pilot/requests', json=DATA)
        assert response.status_code == 202
        assert 'id' not in response.json()
    assert client.get('/api/admin/pilot').status_code == 401
    listing = client.get('/api/admin/pilot', headers=HEADERS).json()
    assert listing['counts']['new'] == 1
    row = listing['requests'][0]
    assert row['consent_version'] == 'pilot-v1'
    url = '/api/admin/pilot/' + row['id']
    assert client.patch(url, json={'stage': 'qualified'}, headers=HEADERS).status_code == 200
    assert client.patch(url, json={'stage': 'paid'}, headers=HEADERS).status_code == 422
    assert client.delete(url, headers=HEADERS).status_code == 200
    assert client.delete(url, headers=HEADERS).status_code == 404


def test_consent_validation_origin_and_limit(enabled):
    assert client.post('/api/pilot/requests', json={**DATA, 'consent': False}).status_code == 422
    assert client.post('/api/pilot/requests', json={**DATA, 'website': 'spam'}).status_code == 422
    assert client.post('/api/pilot/requests', json={**DATA, 'name': '  '}).status_code == 422
    assert client.post('/api/pilot/requests', json=DATA, headers={'Origin': 'https://attacker.example'}).status_code == 403
    for _ in range(5):
        assert client.post('/api/pilot/requests', json=DATA).status_code == 202
    assert client.post('/api/pilot/requests', json=DATA).status_code == 429


def test_preview_stays_readonly_even_when_pilot_enabled(enabled, monkeypatch):
    monkeypatch.setitem(app.state._state, 'settings', replace(enabled, public_preview=True))
    assert client.get('/api/offers').json()['accepting_requests'] is False
    assert client.post('/api/pilot/requests', json=DATA).status_code == 403
    assert client.get('/api/admin/pilot', headers=HEADERS).status_code == 403


def test_expired_requests_are_removed(enabled):
    client.post('/api/pilot/requests', json=DATA)
    with service.connect(enabled.database) as db:
        db.execute('UPDATE pilot_requests SET created_at=?', ((service.now()-timedelta(days=31)).isoformat(),))
    assert client.get('/api/admin/pilot', headers=HEADERS).json()['requests'] == []


def test_chunked_request_size_is_enforced():
    def body():
        yield b'{"data":"'
        yield b'x' * 5000
        yield b'"}'
    response = client.post('/api/pilot/requests', content=body(), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
    assert response.headers['x-frame-options'] == 'DENY'


def test_page_routes_and_studio_links():
    assert 'Better questions.' in client.get('/').text
    assert 'Your money, with a plan.' in client.get('/studio').text
    assert '48-hour launch lab' in client.get('/launch').text
    assert 'My clarity worksheet' in client.get('/static/workbook.html').text


def test_pilot_only_mode_blocks_legacy_customer_and_billing_apis(enabled, monkeypatch):
    monkeypatch.setitem(app.state._state, 'settings', replace(enabled, pilot_only=True))
    assert client.post('/api/pilot/requests', json=DATA).status_code == 202
    assert client.get('/api/admin/pilot', headers=HEADERS).status_code == 200
    for path in ('/api/auth/me', '/api/paypal/status', '/api/billing/status', '/api/admin/consultations'):
        assert client.get(path, headers=HEADERS).status_code == 403
    assert client.post('/api/consultations', json={}).status_code == 403
    assert client.get('/api/health').json()['mode'] == 'pilot-only'
    assert client.get('/api/health').json()['payments_enabled'] is False
    assert 'src="/static/account.js"' not in client.get('/studio').text


def test_webhook_bodies_are_bounded_before_provider_processing():
    response = client.post('/api/paypal/webhook', content=b'x' * 262145,
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
    assert response.headers['x-content-type-options'] == 'nosniff'

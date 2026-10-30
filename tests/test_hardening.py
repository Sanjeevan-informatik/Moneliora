"""Security and integrity regressions using disposable databases and fake money."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
import json
import sqlite3
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pyotp
import pytest

from main import app
from moneliora import accounts, security
from moneliora.database import connect_database
from moneliora.services import pilot

PASSWORD = 'Synthetic-test-password-5678'
ADMIN = {'x-admin-token': 'a'*64}


def register(client, email='security@example.org'):
    result = client.post('/api/auth/register', json={'email':email, 'password':PASSWORD})
    assert result.status_code == 201, result.text
    return {'x-csrf-token':result.json()['csrf']}


def test_cookie_session_rotation_logout_and_expiry(monkeypatch):
    monkeypatch.setattr(accounts, 'COOKIE_SECURE', False)
    client = TestClient(app, base_url='https://testserver')
    headers = register(client)
    original = client.cookies.get('moneliora_session')
    assert len(original) == 64
    cookie = next(iter(client.cookies.jar))
    assert cookie.secure and cookie.has_nonstandard_attr('HttpOnly')
    assert cookie.get_nonstandard_attr('SameSite') == 'strict'
    with accounts.db_conn() as db:
        stored = db.execute('SELECT token_hash FROM sessions').fetchone()[0]
        assert stored == sha256(original.encode()).hexdigest() and stored != original
    response = client.post('/api/auth/login', json={'email':'security@example.org','password':PASSWORD})
    assert response.status_code == 200
    assert client.cookies.get('moneliora_session') != original
    replay = TestClient(app)
    replay.cookies.set('moneliora_session', original)
    assert replay.get('/api/auth/me').status_code == 401
    current = client.cookies.get('moneliora_session')
    assert client.post('/api/auth/logout', json={}, headers={'x-csrf-token':response.json()['csrf']}).status_code == 200
    replay.cookies.set('moneliora_session', current)
    assert replay.get('/api/auth/me').status_code == 401
    response = client.post('/api/auth/login', json={'email':'security@example.org','password':PASSWORD})
    assert response.status_code == 200
    with accounts.db_conn() as db:
        db.execute('UPDATE sessions SET expires_at=?', ('2000-01-01T00:00:00+00:00',))
    assert client.get('/api/auth/me').status_code == 401


def test_failed_login_audit_commits_and_never_contains_credentials():
    client = TestClient(app)
    register(client)
    for email in ('security@example.org','missing@example.org'):
        assert client.post('/api/auth/login',json={'email':email,'password':'Incorrect-password-4567'}).status_code == 401
    with accounts.db_conn() as db:
        events = [dict(row) for row in db.execute("SELECT * FROM security_events WHERE event='LOGIN_FAILED'")]
        assert len(events) == 2
        assert db.execute('SELECT failed_attempts FROM users').fetchone()[0] == 1
    serialized = json.dumps(events)
    for secret in (PASSWORD, 'Incorrect-password-4567', 'security@example.org', client.cookies.get('moneliora_session')):
        assert secret not in serialized
    assert TestClient(app).get('/api/admin/audit').status_code == 401
    assert client.get('/api/admin/audit').status_code == 403
    with accounts.db_conn() as db:
        db.execute("UPDATE users SET role='admin'")
    result = client.get('/api/admin/audit?limit=1').json()
    assert result['has_more'] and len(result['events']) == 1
    older = client.get('/api/admin/audit',params={'limit':1,'cursor':result['next_cursor']}).json()
    assert older['events'][0]['id'] < result['events'][0]['id']


def test_account_throttling_survives_new_clients_and_ip_rotation(monkeypatch):
    monkeypatch.setattr(accounts, 'PASSWORD', SimpleNamespace(verify=lambda *_: False))
    for index in range(8):
        client = TestClient(app, client=(f'192.0.2.{index+1}', 4000))
        assert client.post('/api/auth/login',json={'email':'unknown@example.org','password':PASSWORD}).status_code == 401
    client = TestClient(app, client=('192.0.2.99',4000))
    for _ in range(3):
        response = client.post('/api/auth/login',json={'email':'unknown@example.org','password':PASSWORD})
        assert response.status_code == 429
        assert 1 <= int(response.headers['retry-after']) <= 900
    with accounts.db_conn() as db:
        assert db.execute("SELECT COUNT(*) FROM security_events WHERE event='AUTH_THROTTLED'").fetchone()[0] == 1


def test_ip_throttle_cannot_be_bypassed_by_changing_email(monkeypatch):
    monkeypatch.setattr(accounts, 'PASSWORD', SimpleNamespace(verify=lambda *_: False))
    client = TestClient(app)
    for index in range(30):
        assert client.post('/api/auth/login',json={'email':f'person{index}@example.org','password':PASSWORD}).status_code == 401
    assert client.post('/api/auth/login',json={'email':'another@example.org','password':PASSWORD}).status_code == 429


def test_throttle_is_atomic_under_concurrent_connections():
    with accounts.db_conn():
        pass
    def attempt(index):
        try:
            security.throttle(accounts.DB, 'login', f'client-{index}', 'one@example.org')
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert results.count(200) == 8 and results.count(429) == 8


def test_mfa_change_rotates_cookie_and_csrf():
    client = TestClient(app)
    headers = register(client)
    old_cookie = client.cookies.get('moneliora_session')
    setup = client.post('/api/auth/mfa/setup',json={},headers=headers).json()
    code = pyotp.TOTP(setup['secret']).now()
    response = client.post('/api/auth/mfa/confirm',json={'code':code},headers=headers)
    assert response.status_code == 200
    assert response.json()['csrf'] != headers['x-csrf-token']
    stale = TestClient(app)
    stale.cookies.set('moneliora_session',old_cookie)
    assert stale.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/logout',json={},headers=headers).status_code == 403
    new_headers = {'x-csrf-token':response.json()['csrf']}
    old_cookie = client.cookies.get('moneliora_session')
    response = client.post('/api/auth/mfa/disable',json={'password':PASSWORD,'code':code},headers=new_headers)
    assert response.status_code == 200
    stale.cookies.set('moneliora_session',old_cookie)
    assert stale.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/logout',json={},headers={'x-csrf-token':response.json()['csrf']}).status_code == 200


def test_snapshots_store_integer_cents_and_reject_invalid_precision():
    client = TestClient(app)
    headers = register(client)
    state = {'cash':'0.29','positions':{},'trades':[{'symbol':'NVDA','qty':1,'amount':'12.34','side':'buy','date':'example'}]}
    assert client.put('/api/account/state',json=state,headers=headers).status_code == 200
    response = client.get('/api/account/state').json()['state']
    assert response['cash_cents'] == 29 and response['schema_version'] == 2
    assert response['trades'][0]['amount_cents'] == 1234
    with accounts.db_conn() as db:
        stored = json.loads(db.execute('SELECT data FROM account_states').fetchone()[0])
        assert type(stored['cash_cents']) is int and 'cash' not in stored
        assert 'amount' not in stored['trades'][0]
    for invalid in ({'cash':'0.001'}, {'cash':'NaN'}, {'cash':'1e-999999'}, {'cash':'1e999999'},
                    {'cash_cents':1.5}, {'cash_cents':True}, {'cash_cents':-1},
                    {'cash_cents':1, 'cash':'0.01'}, {'cash_cents':500001}):
        assert client.put('/api/account/state',json=invalid,headers=headers).status_code == 422, invalid
    assert client.get('/api/account/state').json()['state'] == response
    for raw in ('{"cash":0.010000000000000000001}', '{"cash":1,"cash":2}'):
        assert client.put('/api/account/state',content=raw,headers={**headers,'content-type':'application/json'}).status_code==422


def test_existing_snapshot_is_migrated_without_overwriting_invalid_data():
    client = TestClient(app)
    register(client)
    old = json.dumps({'cash':1234.56,'positions':{},'watched':[],'trades':[]})
    with accounts.db_conn() as db:
        uid = db.execute('SELECT id FROM users').fetchone()[0]
        db.execute('INSERT INTO account_states VALUES(?,?,?)',(uid,old,accounts.now_iso()))
    assert client.get('/api/account/state').json()['state']['cash_cents'] == 123456
    with accounts.db_conn() as db:
        assert json.loads(db.execute('SELECT data FROM account_states').fetchone()[0])['schema_version'] == 2
        db.execute('UPDATE account_states SET data=?', ('{"cash":"NaN"}',))
    assert client.get('/api/account/state').status_code == 409
    with accounts.db_conn() as db:
        assert db.execute('SELECT data FROM account_states').fetchone()[0] == '{"cash":"NaN"}'


def test_wal_allows_writer_during_read_snapshot_and_closes_connections(tmp_path):
    path = tmp_path / 'concurrency.db'
    with connect_database(path,'CREATE TABLE counter(value INTEGER); INSERT INTO counter VALUES(0);') as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')
    with connect_database(path) as reader:
        reader.execute('BEGIN')
        assert reader.execute('SELECT value FROM counter').fetchone()[0] == 0
        def write():
            with connect_database(path) as writer:
                writer.execute('BEGIN IMMEDIATE')
                writer.execute('UPDATE counter SET value=value+1')
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(write).result(timeout=3)
        assert reader.execute('SELECT value FROM counter').fetchone()[0] == 0
    with pytest.raises(RuntimeError), connect_database(path) as db:
        db.execute('UPDATE counter SET value=99')
        raise RuntimeError('rollback this write')
    with connect_database(path) as db:
        assert db.execute('SELECT value FROM counter').fetchone()[0] == 1


def test_pending_booking_cap_is_atomic():
    client = TestClient(app)
    headers = register(client)
    token = client.cookies.get('moneliora_session')
    payload={'topic':'Learning session','preferred_date':str(date.today()+timedelta(days=1)),
             'preferred_time':'12:00','question':'Synthetic request'}
    def submit(_):
        worker=TestClient(app)
        worker.cookies.set('moneliora_session',token)
        return worker.post('/api/bookings',json=payload,headers=headers).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(submit,range(6)))
    assert results.count(201)==3 and results.count(429)==3


def test_booking_pages_are_bounded_isolated_and_stable_after_insert():
    first, second = TestClient(app), TestClient(app)
    register(first,'first@example.org'); register(second,'second@example.org')
    with accounts.db_conn() as db:
        ids={r['email']:r['id'] for r in db.execute('SELECT id,email FROM users')}
        for owner in ids.values():
            for index in range(5):
                db.execute('''INSERT INTO booking_requests(user_id,topic,preferred_date,preferred_time,question,created_at,status)
                              VALUES(?,?,?,?,?,?,?)''',(owner,f'Sample {index}','2030-01-01','12:00','',accounts.now_iso(),'cancelled'))
    result=first.get('/api/bookings?limit=2').json()
    seen=[r['id'] for r in result['bookings']]
    with accounts.db_conn() as db:
        assert seen==[5,4]
        db.execute('DELETE FROM booking_requests WHERE id=4')
        db.execute('''INSERT INTO booking_requests(user_id,topic,preferred_date,preferred_time,question,created_at)
                      VALUES(?,?,?,?,?,?)''',(ids['first@example.org'],'New','2030-01-01','12:00','',accounts.now_iso()))
    while result['has_more']:
        result=first.get('/api/bookings',params={'limit':2,'cursor':result['next_cursor']}).json()
        seen += [row['id'] for row in result['bookings']]
    assert seen==[5,4,3,2,1]
    assert first.get('/api/bookings?limit=101').status_code==422
    assert first.get('/api/bookings?cursor=-1').status_code==422
    assert first.get('/api/admin/bookings').status_code==403
    with accounts.db_conn() as db:
        db.execute("UPDATE users SET role='admin' WHERE email='first@example.org'")
    assert len(first.get('/api/admin/bookings?limit=2').json()['bookings'])==2


def test_pilot_cursor_survives_deleted_boundary_with_equal_timestamps():
    client=TestClient(app)
    with pilot.connect(app.state.settings.database) as db:
        for index in range(5):
            db.execute('''INSERT INTO pilot_requests VALUES(?,?,?,?,?,?,?,?,?)''',
                       (f'{index:032x}',f'person{index}@example.org','Example','guided-planning',
                        'Synthetic objective','new','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','pilot-v1'))
        # Relative to execution date, so retention doesn't invalidate the fixtures.
        db.execute('UPDATE pilot_requests SET created_at=?,updated_at=?',(pilot.now().isoformat(),pilot.now().isoformat()))
    result=client.get('/api/admin/pilot?limit=2',headers=ADMIN).json()
    seen=[r['id'] for r in result['requests']]
    assert result['counts']['new']==5
    assert client.delete('/api/admin/pilot/'+seen[-1],headers=ADMIN).status_code==200
    while result['has_more']:
        result=client.get('/api/admin/pilot',params={'limit':2,'cursor':result['next_cursor']},headers=ADMIN).json()
        seen += [r['id'] for r in result['requests']]
    assert seen==[f'{i:032x}' for i in reversed(range(5))]
    assert client.get('/api/admin/pilot?cursor=not-valid',headers=ADMIN).status_code==422


def test_consultation_pagination_and_fail_closed_admin_configuration(monkeypatch):
    client=TestClient(app)
    for i in range(5):
        assert client.post('/api/consultations',json={'name':'Example','email':f'example{i}@example.org',
            'topic':'Learning','preferred_date':str(date.today()),'message':'','privacy_accepted':True}).status_code==201
    result=client.get('/api/admin/consultations?limit=2',headers=ADMIN).json()
    assert len(result['requests'])==2 and result['has_more']
    assert len(client.get('/api/admin/consultations',params={'cursor':result['next_cursor']},headers=ADMIN).json()['requests'])==3
    for token in ('', 'replace-with-a-random-64-character-secret'):
        monkeypatch.setitem(app.state._state,'settings',replace(app.state.settings,admin_token=token))
        assert client.get('/api/admin/consultations',headers={'x-admin-token':token}).status_code==503


def test_cross_site_writes_and_csp():
    client=TestClient(app)
    headers=register(client)
    response=client.post('/api/auth/logout',json={},headers={**headers,'sec-fetch-site':'cross-site'})
    assert response.status_code==403
    assert client.get('/api/auth/me').status_code==200
    csp=response.headers['content-security-policy']
    assert "script-src 'self'" in csp and "object-src 'none'" in csp
    assert 'unsafe-inline' not in csp and 'unsafe-eval' not in csp
    assert response.headers['cache-control']=='no-store'

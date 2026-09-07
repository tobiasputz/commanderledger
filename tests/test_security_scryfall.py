import re
import time
import sqlite3
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import security
from app.security import SecurityConfig
from app.services.scryfall import ScryfallClient,ScryfallError

@pytest.fixture
def secured(client,tmp_path,monkeypatch):
    encoded=security.hash_password('test-only-long-password')
    cfg=SecurityConfig(True,encoded,'https://ledger.example',tmp_path/'auth.sqlite3')
    monkeypatch.setattr(security,'config',lambda:cfg)
    import app.routes.auth as auth
    monkeypatch.setattr(auth,'config',lambda:cfg)
    monkeypatch.setenv('COMMANDER_DB',str(tmp_path/'games.db'))
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path/'backups'))
    monkeypatch.delenv('COMMANDER_REQUIRE_MOUNT',raising=False)
    client.base_url='https://ledger.example'
    return client,cfg

def sign_in(client):
    page=client.get('/login')
    csrf=re.search('name="csrf" value="([^"]+)"',page.text).group(1)
    return client.post('/login',data={'password':'test-only-long-password','csrf':csrf},follow_redirects=False)

def token(client):
    page=client.get('/')
    return re.search('name="csrf-token" content="([^"]+)"',page.text).group(1)

def test_password_hash_and_validation():
    hashed=security.hash_password('test-only-long-password')
    assert security.verify_password('test-only-long-password',hashed)
    assert not security.verify_password('wrong',hashed)
    assert not security.verify_password('x','invalid')
    with pytest.raises(ValueError): security.hash_password('short')

def test_hosted_configuration_fails_closed(client,monkeypatch):
    monkeypatch.setenv('COMMANDER_MODE','hosted')
    monkeypatch.delenv('COMMANDER_PASSWORD_HASH',raising=False)
    assert client.get('/').status_code==503
    assert client.get('/api/export/json').status_code==503

def test_routes_protected(secured):
    client,cfg=secured
    for route in ['/api/catalog','/api/export/json','/api/export/csv/players','/api/anonymous','/api/scryfall/autocomplete?q=Winter','/openapi.json']:
        assert client.get(route,follow_redirects=False).status_code in (401,303)
    assert client.get('/',follow_redirects=False).status_code==303
    assert client.get('/healthz').status_code==200
    assert client.get('/static/app.css').status_code==200

def test_login_csrf_cookies_write_logout(secured):
    client,cfg=secured
    assert client.post('/login',data={'password':'test-only-long-password','csrf':'bad'}).status_code==403
    response=sign_in(client)
    assert response.status_code==303
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    assert client.get('/api/catalog').status_code==200
    assert client.post('/api/players',json={'name':'New'}).status_code==403
    csrf=token(client)
    headers={'X-CSRF-Token':csrf,'Origin':'https://ledger.example'}
    assert client.post('/api/players',json={'name':'New'},headers=headers).status_code==200
    assert client.post('/api/players',json={'name':'Injected'},headers={**headers,'Origin':'https://evil.example'}).status_code==403
    assert client.get('/api/export/json').headers['cache-control']=='no-store'
    saved=client.cookies.get(security.COOKIE)
    assert client.post('/logout',headers=headers,follow_redirects=False).status_code==303
    client.cookies.set(security.COOKIE,saved,domain='ledger.example')
    assert client.get('/api/catalog').status_code==401

def test_forged_and_expired_sessions(secured):
    client,cfg=secured
    client.cookies.set(security.COOKIE,'forged',domain='ledger.example')
    assert client.get('/api/catalog').status_code==401
    sign_in(client)
    with security.connect(cfg) as con: con.execute('UPDATE sessions SET expires=?',(time.time()-1,))
    assert client.get('/api/catalog').status_code==401

def test_login_throttle(secured):
    client,cfg=secured
    for _ in range(10): assert security.login_attempt(cfg,'testclient')
    assert not security.login_attempt(cfg,'testclient')
    response=sign_in(client)
    assert response.status_code==429

def test_host_validation(secured):
    client,_=secured
    assert client.get('/',headers={'Host':'attacker.example'}).status_code==400

def test_cache_headers_and_multi_commander(tmp_path):
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.headers['User-Agent'].startswith('CommanderLedger/')
        assert request.headers['Accept']=='application/json'
        if request.url.path.endswith('autocomplete'): return httpx.Response(200,json={'data':['Winter, Cynical Opportunist']})
        return httpx.Response(200,json={'id':'card','name':request.url.params['fuzzy'],'color_identity':['B','G'],'type_line':'Legendary Creature','oracle_text':'Partner','legalities':{'commander':'legal'},'image_uris':{'normal':'https://cards.scryfall.io/normal/example.jpg'},'scryfall_uri':'https://scryfall.com/card/example'})
    client=ScryfallClient(tmp_path/'cache.sqlite3',httpx.MockTransport(handler))
    assert client.autocomplete('Win')['names']==['Winter, Cynical Opportunist']
    assert client.autocomplete('Win')['cached']
    with patch('app.services.scryfall.time.sleep'):
        data=client.lookup('First; Second')
    assert data['commanders']=='First; Second' and data['color_identity']=='BG'
    assert 'not validated' in data['pairing_note']
    assert len(requests)==3
    fresh=ScryfallClient(tmp_path/'cache.sqlite3',httpx.MockTransport(lambda r:pytest.fail('Expected disk cache')))
    assert fresh.autocomplete('Win')['cached']

def test_stale_cache_network_failure_and_disabled(tmp_path,monkeypatch):
    path=tmp_path/'cache.sqlite3'
    client=ScryfallClient(path,httpx.MockTransport(lambda r:httpx.Response(200,json={'data':['Winter']})))
    client.autocomplete('Wi')
    with client.connection() as con: con.execute('UPDATE cache SET fetched=0')
    client.transport=httpx.MockTransport(lambda r:httpx.Response(503))
    with patch('app.services.scryfall.time.sleep'):
        assert client.autocomplete('Wi')['stale']
    monkeypatch.setenv('COMMANDER_SCRYFALL','false')
    other=ScryfallClient(path,httpx.MockTransport(lambda r:pytest.fail('Disabled requests must not run')))
    assert other.autocomplete('Wi')['stale']
    with pytest.raises(ScryfallError): other.autocomplete('Other')

def test_rate_limit_no_retry_and_safe_urls(tmp_path):
    calls=[]
    def limited(request): calls.append(request);return httpx.Response(429,headers={'Retry-After':'120'})
    client=ScryfallClient(tmp_path/'limited.sqlite3',httpx.MockTransport(limited))
    with pytest.raises(ScryfallError): client.autocomplete('ab')
    with pytest.raises(ScryfallError): client.autocomplete('cd')
    assert len(calls)==1 and client.cooldown>time.monotonic()+100
    unsafe=ScryfallClient(tmp_path/'unsafe.sqlite3',httpx.MockTransport(lambda r:httpx.Response(200,json={'name':'Custom','image_uris':{'normal':'https://evil.example/image'},'scryfall_uri':'javascript:alert(1)'})))
    card=unsafe.lookup('Custom')['cards'][0]
    assert card['image']=='' and card['url']==''

def test_scryfall_outage_endpoint_allows_manual_games(client,records,monkeypatch,tmp_path):
    import app.routes.scryfall as route
    monkeypatch.setattr(route,'client',ScryfallClient(tmp_path/'outage.sqlite3',httpx.MockTransport(lambda r:httpx.Response(503))))
    assert client.get('/api/scryfall/autocomplete?q=Unknown').json()['available'] is False
    assert client.get('/api/scryfall/lookup?names=Unknown').status_code==503
    from conftest import payload
    assert client.post('/api/games',json=payload(records,anonymous=True)).status_code==200

def test_password_rotation_invalidates_sessions(secured,monkeypatch):
    client,cfg=secured
    sign_in(client)
    rotated=SecurityConfig(True,security.hash_password('new-test-only-password'),cfg.origin,cfg.auth_path)
    monkeypatch.setattr(security,'config',lambda:rotated)
    assert client.get('/api/catalog').status_code==401

def test_missing_volume_rejected(tmp_path,monkeypatch):
    cfg=SecurityConfig(True,security.hash_password('test-only-long-password'),'https://ledger.example',tmp_path/'auth.sqlite3')
    monkeypatch.setattr(security,'DB_PATH',tmp_path/'game.db')
    monkeypatch.setenv('COMMANDER_REQUIRE_MOUNT','true')
    monkeypatch.setenv('COMMANDER_DB',str(tmp_path/'game.db'))
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path/'backups'))
    with pytest.raises(RuntimeError,match='Persistent volume'): security.validate_configuration(cfg)

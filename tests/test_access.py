from fastapi import FastAPI
from fastapi.testclient import TestClient
from otomoto_parser.v2.access import install_access


def client(path):
    app = FastAPI()
    install_access(app, path)
    @app.get('/api/private')
    def private():
        return {'private': True}
    @app.post('/api/private')
    def mutate():
        return {'ok': True}
    return TestClient(app)


def test_full_lifecycle(tmp_path):
    c = client(tmp_path)
    assert c.get('/api/private').status_code == 200
    assert c.post('/api/access', json={'action':'save','newCode':'test-code-123'}).status_code == 200
    assert 'test-code-123' not in (tmp_path / 'access.json').read_text()
    assert c.get('/api/private').status_code == 200
    c.cookies.clear()
    assert c.get('/api/private').status_code == 401
    assert c.get('/docs').status_code == 401
    assert c.get('/', follow_redirects=False).status_code == 303
    assert c.post('/api/access', json={'action':'save','newCode':''}).status_code == 401
    assert c.post('/api/access', json={'action':'login','code':'wrong'}).status_code == 401
    assert c.post('/api/access', json={'action':'login','code':'test-code-123'}).status_code == 200
    old = c.cookies.get('otomoto_session')
    assert client(tmp_path).get('/api/private', cookies={'otomoto_session': old}).status_code == 200
    assert c.post('/api/access', json={'action':'save','code':'test-code-123','newCode':'replacement-code'}).status_code == 200
    assert c.get('/api/private', cookies={'otomoto_session':old}).status_code == 401
    assert c.post('/api/access', json={'action':'save','code':'replacement-code','newCode':''}).status_code == 200
    assert client(tmp_path).get('/api/private').status_code == 200


def test_csrf_validation_rate_and_cookie(tmp_path):
    c = client(tmp_path)
    assert c.post('/api/access', json={'action':'save','newCode':'long-enough'}, headers={'Origin':'https://evil.test'}).status_code == 403
    assert c.post('/api/access', data={'action':'save'}).status_code == 415
    assert c.post('/api/access', json=[]).status_code == 400
    assert c.post('/api/access', json={'action':'save','newCode':'1234'}).status_code == 400
    r = c.post('/api/access', json={'action':'save','newCode':'long-enough'})
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    assert 'Domain=' not in r.headers['set-cookie']
    for _ in range(10):
        r = c.post('/api/access', json={'action':'login','code':'wrong'})
    assert r.status_code == 429


def test_rolling_session_restart_logout_and_idle_expiry(tmp_path, monkeypatch):
    from otomoto_parser.v2 import access
    now = 2000000000
    monkeypatch.setattr(access.time, 'time', lambda: now)
    c = client(tmp_path)
    response = c.post('/api/access', json={'action': 'save', 'newCode': 'test-code-123'})
    token = c.cookies.get(access.COOKIE)
    assert 'Max-Age=31536000' in response.headers['set-cookie']
    c.cookies.clear()
    c.cookies.set(access.COOKIE, token, domain="testserver.local")
    assert 'set-cookie' not in c.get('/api/private').headers
    now += 340 * 86400
    response = c.get('/api/private')
    assert response.status_code == 200
    renewed = c.cookies.get(access.COOKIE)
    assert renewed != token
    c = client(tmp_path)
    c.cookies.set(access.COOKIE, renewed, domain="testserver.local")
    assert c.get('/api/private').status_code == 200
    assert c.post('/api/access', json={'action': 'logout'}).status_code == 200
    c.cookies.set(access.COOKIE, renewed, domain="testserver.local")
    assert c.get('/api/private').status_code == 401
    c.cookies.set(access.COOKIE, token, domain="testserver.local")
    assert c.get('/api/private').status_code == 401
    c.cookies.clear()
    c.post('/api/access', json={'action': 'login', 'code': 'test-code-123'})
    token = c.cookies.get(access.COOKIE)
    now += 366 * 86400
    c.cookies.set(access.COOKIE, token, domain="testserver.local")
    assert c.get('/api/private').status_code == 401


def test_legacy_session_renews_without_code(tmp_path, monkeypatch):
    import hashlib
    import hmac
    from otomoto_parser.v2 import access
    now = 2000000000
    monkeypatch.setattr(access.time, 'time', lambda: now)
    c = client(tmp_path)
    c.post('/api/access', json={'action': 'save', 'newCode': 'test-code-123'})
    state = c.app.state.access.state
    expiry = str(now + 20 * 86400)
    signature = hmac.new(bytes.fromhex(state['secret']), expiry.encode(), hashlib.sha256).hexdigest()
    legacy = expiry + '.' + signature
    c.cookies.clear()
    c.cookies.set(access.COOKIE, legacy, domain="testserver.local")
    assert c.get('/api/private').status_code == 200
    renewed = c.cookies.get(access.COOKIE)
    assert len(renewed.split('.')) == 3
    c.post('/api/access', json={'action': 'logout'})
    c.cookies.set(access.COOKIE, legacy, domain="testserver.local")
    assert c.get('/api/private').status_code == 401


def test_checked_in_frontend_serves_native_access_route(tmp_path):
    import re
    from otomoto_parser.v2.app import create_app
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as c:
        c.post('/api/access', json={'action': 'save', 'newCode': 'test-code-123'})
        c.cookies.clear()
        page = c.get('/access')
        assert page.status_code == 200
        asset = re.search(r'src="([^"]+\.js)"', page.text).group(1)
        bundle = c.get(asset)
        assert bundle.status_code == 200
        assert 'Repeat new code' in bundle.text
        assert 'Current code' in bundle.text
        assert c.get('/api/settings').status_code == 401

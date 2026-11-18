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

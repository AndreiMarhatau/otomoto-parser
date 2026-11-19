"""Single-household access gate; configuration lives alongside application data."""
import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE = 'otomoto_session'
TTL = 365 * 86400


class Access:
    def __init__(self, directory: Path):
        self.path = directory / 'access.json'
        self.lock = threading.Lock()
        self.attempts = []
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {}

    def identity(self, token):
        parts = (token or '').split('.')
        if len(parts) == 2:
            return hashlib.sha256(token.encode()).hexdigest()
        return parts[1] if len(parts) == 3 else ''

    def valid(self, token):
        try:
            payload, signature = (token or '').rsplit('.', 1)
            expiry = payload.split('.')[0]
            expected = hmac.new(bytes.fromhex(self.state['secret']), payload.encode(), hashlib.sha256).hexdigest()
            revoked = self.state.get('revoked', {})
            return (int(expiry) > time.time() and hmac.compare_digest(signature, expected)
                    and self.identity(token) not in revoked)
        except (ValueError, KeyError):
            return False

    def persist(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w') as output:
            temporary.chmod(0o600)
            json.dump(state, output)
        temporary.replace(self.path)
        self.state = state

    def revoke(self, token):
        if self.valid(token):
            now = time.time()
            revoked = {key: expiry for key, expiry in self.state.get('revoked', {}).items() if expiry > now}
            revoked[self.identity(token)] = now + TTL
            self.persist({**self.state, 'revoked': revoked})

    def verify(self, code):
        if not isinstance(code, str) or len(code) > 256:
            return False
        digest = hashlib.scrypt(code.encode(), salt=bytes.fromhex(self.state['salt']), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(digest, self.state['hash'])

    def save(self, code):
        state = {}
        if code:
            salt = secrets.token_bytes(16)
            state = {'salt': salt.hex(), 'hash': hashlib.scrypt(code.encode(), salt=salt, n=16384, r=8, p=1).hex(), 'secret': secrets.token_hex(32)}
        self.persist(state)

    def cookie(self, response, request, token=None):
        expiry = str(int(time.time()) + TTL)
        identity = self.identity(token) if token else secrets.token_hex(32)
        payload = f'{expiry}.{identity}'
        signature = hmac.new(bytes.fromhex(self.state['secret']), payload.encode(), hashlib.sha256).hexdigest()
        response.set_cookie(COOKIE, f'{payload}.{signature}', max_age=TTL, httponly=True, samesite='strict', secure=request.url.scheme == 'https')


def install_access(app, directory):
    access = Access(directory)
    app.state.access = access

    @app.middleware('http')
    async def gate(request: Request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
                return JSONResponse({'detail': 'Cross-origin request rejected'}, status_code=403)
        public = request.url.path in ('/access', '/api/access') or request.url.path.startswith('/assets/')
        if access.state and not public and not access.valid(request.cookies.get(COOKIE)):
            if request.url.path.startswith('/api/') or request.url.path in ('/docs', '/redoc', '/openapi.json'):
                return JSONResponse({'detail': 'Sign in at /access'}, status_code=401)
            return RedirectResponse('/access', status_code=303)
        token = request.cookies.get(COOKIE)
        response = await call_next(request)
        # Do not overwrite cookies issued by login, rotation, or logout.
        if ('set-cookie' not in response.headers and access.valid(token)
                and int(token.split('.')[0]) < time.time() + 30 * 86400):
            access.cookie(response, request, token)
        return response

    @app.get('/api/access')
    def status(request: Request):
        return {'enabled': bool(access.state), 'authenticated': not access.state or access.valid(request.cookies.get(COOKIE))}

    app.add_api_route('/api/access', update_access, methods=['POST'])


async def update_access(request: Request):
    access = request.app.state.access
    payload = await read_payload(request)
    if isinstance(payload, JSONResponse):
        return payload
    action = payload.get('action')
    with access.lock:
        now = time.monotonic()
        access.attempts = [t for t in access.attempts if now - t < 60]
        if len(access.attempts) >= 10:
            return JSONResponse({'detail': 'Too many attempts; wait a minute'}, status_code=429)
        access.attempts.append(now)
        if action == 'logout':
            access.revoke(request.cookies.get(COOKIE))
            response = JSONResponse({'ok': True})
            response.delete_cookie(COOKIE)
            return response
        if action not in ('login', 'save'):
            return JSONResponse({'detail': 'Unknown action'}, status_code=400)
        if access.state and not access.verify(payload.get('code')):
            return JSONResponse({'detail': 'Incorrect current code'}, status_code=401)
        if action == 'save':
            code = payload.get('newCode')
            if not isinstance(code, str) or (code and not 8 <= len(code) <= 128):
                return JSONResponse({'detail': 'Use 8–128 characters, or empty to disable'}, status_code=400)
            access.save(code)
        response = JSONResponse({'ok': True})
        if access.state:
            access.cookie(response, request)
        else:
            response.delete_cookie(COOKIE)
        return response

async def read_payload(request):
    if request.headers.get('content-type', '').split(';')[0] != 'application/json':
        return JSONResponse({'detail': 'JSON required'}, status_code=415)
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2048:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
    except (ValueError, TypeError):
        return JSONResponse({"detail": "Invalid JSON object"}, status_code=400)
    return payload

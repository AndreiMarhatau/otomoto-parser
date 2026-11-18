"""Single-household access gate; configuration lives alongside application data."""
import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = 'otomoto_session'
TTL = 30 * 86400


class Access:
    def __init__(self, directory: Path):
        self.path = directory / 'access.json'
        self.lock = threading.Lock()
        self.attempts = []
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {}

    def valid(self, token):
        try:
            expiry, signature = (token or '').split('.')
            expected = hmac.new(bytes.fromhex(self.state['secret']), expiry.encode(), hashlib.sha256).hexdigest()
            return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
        except (ValueError, KeyError):
            return False

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state))
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.state = state

    def cookie(self, response, request):
        expiry = str(int(time.time()) + TTL)
        signature = hmac.new(bytes.fromhex(self.state['secret']), expiry.encode(), hashlib.sha256).hexdigest()
        response.set_cookie(COOKIE, f'{expiry}.{signature}', max_age=TTL, httponly=True, samesite='strict', secure=request.url.scheme == 'https')


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
        return await call_next(request)

    @app.get('/access', response_class=HTMLResponse)
    def page():
        return PAGE

    @app.get('/api/access')
    def status(request: Request):
        return {'enabled': bool(access.state), 'authenticated': access.valid(request.cookies.get(COOKIE))}

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


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Access settings</title>
<style>body{font:18px system-ui;max-width:500px;margin:8vh auto;padding:20px}input,button{font:inherit;padding:10px;margin:8px 0;box-sizing:border-box;width:100%}label{display:block}p{line-height:1.5}</style>
<h1>Access code</h1><p id="status">Loading…</p><form id="form"><label>Current code<input id="code" type="password" autocomplete="current-password" maxlength="128"></label><button id="login">Sign in</button><section id="settings" hidden><label>New code (8–128 characters; empty disables protection)<input id="newCode" type="password" autocomplete="new-password" maxlength="128"></label><button id="save" type="button">Save access settings</button><button id="logout" type="button">Sign out</button></section></form><p id="error" role="alert"></p><a href="/">Back to application</a>
<script>
const $=id=>document.getElementById(id);
async function refresh(){const r=await fetch('/api/access');const s=await r.json();$('status').textContent=s.enabled?'Protection enabled. Enter your code to sign in or change it.':'Protection disabled. Set a code here BEFORE exposing this app to the internet.';$('settings').hidden=s.enabled&&!s.authenticated;$('login').hidden=!s.enabled||s.authenticated;}
async function send(action){$('error').textContent='';try{const r=await fetch('/api/access',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,code:$('code').value,newCode:$('newCode').value})});const data=await r.json();if(!r.ok)throw Error(data.detail);$('code').value='';$('newCode').value='';if(action==='login')location.href='/';else await refresh();}catch(e){$('error').textContent=e.message;}}
$('form').onsubmit=e=>{e.preventDefault();send('login')};$('save').onclick=()=>send('save');$('logout').onclick=()=>send('logout');refresh().catch(e=>$('error').textContent=e.message);
</script></html>'''

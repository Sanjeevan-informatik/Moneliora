"""Shared security boundary with actual streamed-body size enforcement."""
from starlette.responses import JSONResponse

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
SECURITY_HEADERS = {'Content-Security-Policy': CSP, 'X-Content-Type-Options': 'nosniff',
                    'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
                    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
                    'Cache-Control': 'no-store'}
PREVIEW_READS = frozenset(('/api/health', '/api/quotes/status', '/api/quotes/snapshot', '/api/offers'))
WEBHOOKS = frozenset(('/api/billing/webhook', '/api/paypal/webhook'))

class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        settings = scope['app'].state.settings
        headers = {k.decode().lower(): v.decode() for k, v in scope.get('headers', [])}
        path, method = scope['path'], scope['method']
        async def secured_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
                if scope.get('scheme') == 'https':
                    message['headers'].append((b'strict-transport-security', b'max-age=31536000; includeSubDomains'))
            await send(message)
        async def reject(code, detail):
            return await JSONResponse({'detail': detail}, status_code=code)(scope, receive, secured_send)
        if settings.public_preview and path.startswith('/api/') and (path not in PREVIEW_READS or method not in ('GET', 'HEAD')):
            return await reject(403, 'Accounts, customer requests and payments are disabled in this preview.')
        if settings.pilot_only and path.startswith('/api/'):
            allowed = ((method in ('GET', 'HEAD') and path in PREVIEW_READS)
                       or (method == 'POST' and path == '/api/pilot/requests')
                       or (method == 'GET' and path == '/api/admin/pilot')
                       or (method in ('PATCH', 'DELETE') and path.startswith('/api/admin/pilot/')))
            if not allowed:
                return await reject(403, 'Accounts, billing and other customer APIs are disabled in pilot-only mode.')
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):

            webhook = path in WEBHOOKS
            if not webhook and headers.get('origin', settings.origin).rstrip('/') != settings.origin:
                return await reject(403, 'Origin not allowed')
            if not webhook and method != 'DELETE' and headers.get('content-type', '').split(';')[0].strip() != 'application/json':
                return await reject(415, 'JSON required')
            limit = 262144 if webhook else 4096
            try:
                length = int(headers.get('content-length', '0'))
                if length < 0 or length > limit:
                    return await reject(413, 'Request too large')
            except ValueError:
                return await reject(413, 'Invalid content length')
            # Bounded buffering also protects chunked requests without Content-Length.
            chunks, size = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                size += len(chunk)
                if size > limit:
                    return await reject(413, 'Request too large')
                chunks.append(chunk)
                if not message.get('more_body', False):
                    break
            delivered = False
            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return await receive()
            return await self.app(scope, buffered_receive, secured_send)
        return await self.app(scope, receive, secured_send)

"""Opt-in loopback JSON adapter; never a replacement for historical login HTTP."""
from contextlib import contextmanager
import asyncio
import json
from threading import BoundedSemaphore, Lock
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response

from kbht_server.auth import AccountService
from kbht_server.bootstrap import BootstrapService, DEFAULT_INVENTORY_URL
from kbht_server.contracts import DomainFailure

ERRORS = {
    'VALIDATION_ERROR': (422, 'Invalid request'),
    'UNAUTHENTICATED': (401, 'Authentication required'),
    'FORBIDDEN': (403, 'Request forbidden'),
    'NOT_FOUND': (404, 'Resource not found'),
    'CONFLICT': (409, 'Account unavailable'),
    'CONTENT_UNAVAILABLE': (409, 'Content unavailable'),
    'NOT_IMPLEMENTED': (422, 'Capability unavailable'),
    'RATE_LIMITED': (429, 'Too many requests'),
    'PAYLOAD_TOO_LARGE': (413, 'Request too large'),
    'UNSUPPORTED_MEDIA_TYPE': (415, 'JSON required'),
    'INTERNAL_ERROR': (500, 'Request failed'),
    'METHOD_NOT_ALLOWED': (405, 'Method not allowed'),
    'REQUEST_TIMEOUT': (408, 'Request timed out'),
}
BODY_READ_SECONDS = 5.0


def error_response(code, request_id):
    status, message = ERRORS.get(code, ERRORS['INTERNAL_ERROR'])
    if code not in ERRORS:
        code = 'INTERNAL_ERROR'
    return JSONResponse({'error': {'code': code, 'message': message, 'details': {}},
                         'requestId': request_id}, status_code=status,
                        headers={'Cache-Control': 'no-store'})


class AuthLimiter:
    """Process-local global bucket, constant space; no attacker identity cache."""
    def __init__(self, attempts=120, window_seconds=60, concurrent_hashes=2):
        if type(attempts) is not int or attempts < 1 or window_seconds <= 0 or type(concurrent_hashes) is not int or concurrent_hashes < 1:
            raise ValueError('Invalid auth limits')
        self.attempts = attempts
        self.window = window_seconds
        self._lock = Lock()
        self._start = monotonic()
        self._used = 0
        self._hashes = BoundedSemaphore(concurrent_hashes)

    @contextmanager
    def acquire(self):
        with self._lock:
            now = monotonic()
            if now - self._start >= self.window:
                self._used = 0
                self._start = now
            if self._used >= self.attempts:
                raise DomainFailure('RATE_LIMITED', 'Too many requests')
            self._used += 1
        if not self._hashes.acquire(blocking=False):
            raise DomainFailure('RATE_LIMITED', 'Too many requests')
        try:
            yield
        finally:
            self._hashes.release()


_AUTH_LIMITER = AuthLimiter()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Nonfinite JSON number')


class _Boundary:
    """Buffer at most4096 bytes before JSON parsing, including chunked bodies.

    Catch below Starlette's outer error middleware so exceptions containing SQL
    or credentials are not re-raised into the server's exception logger.
    """
    def __init__(self, app, *, media_type=b'application/json', body_validator=None,
                 respond=error_response, allow_players_query=True):
        self.app = app
        self.media_type = media_type
        self.body_validator = body_validator
        self.respond = respond
        self.allow_players_query = allow_players_query

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault('state', {})['request_id'] = request_id
        headers = scope.get('headers', [])
        async def safe_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'cache-control'] + [(b'cache-control', b'no-store')]
            await send(message)
        async def reject(code):
            await self.respond(code, request_id)(scope, receive, safe_send)
        denied = None
        if any(key.lower() == b'origin' for key, _ in headers):
            denied = 'FORBIDDEN'
        if scope.get('query_string') and not (self.allow_players_query and scope['path'] == '/v1/players' and scope['method'] == 'GET'):
            denied = denied or 'VALIDATION_ERROR'
        if scope['method'] == 'POST':
            types = [v for k, v in headers if k.lower() == b'content-type']
            if len(types) != 1 or types[0].split(b';', 1)[0].strip().lower() != self.media_type:
                denied = denied or 'UNSUPPORTED_MEDIA_TYPE'
        body = bytearray()
        try:
            deadline = monotonic() + BODY_READ_SECONDS
            while True:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - monotonic()))
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                if len(body) + len(chunk) > 4096:
                    return await reject('PAYLOAD_TOO_LARGE')
                body.extend(chunk)
                if not message.get('more_body', False):
                    break
            # Read bounded small bodies before rejecting headers to avoid an
            # unread-body connection reset on Windows. Never drain unboundedly.
            if denied:
                return await reject(denied)
            if scope['method'] == 'POST':
                try:
                    if self.body_validator is None:
                        json.loads(body, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                    else:
                        self.body_validator(bytes(body))
                except (ValueError, UnicodeError, RecursionError):
                    return await reject('VALIDATION_ERROR')
            sent = False
            async def buffered_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()
            await self.app(scope, buffered_receive, safe_send)
        except TimeoutError:
            await reject('REQUEST_TIMEOUT')
        except Exception:
            # No repr, stack trace, request body or exception text is logged.
            await reject('INTERNAL_ERROR')


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    login: StrictStr = Field(min_length=3, max_length=128)
    password: StrictStr = Field(min_length=8, max_length=128)


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    playerId: StrictInt = Field(gt=0, le=9007199254740991)
    serverId: StrictInt = Field(gt=0, le=2147483647)


def _token(request):
    values = request.headers.getlist('authorization')
    if len(values) != 1 or not values[0].startswith('Bearer '):
        raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
    token = values[0][7:]
    if not 20 <= len(token) <= 256 or any(ch.isspace() for ch in token):
        raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
    return token


def _page(request):
    query = request.query_params
    if set(query) - {'limit', 'after'} or len(query.multi_items()) != len(query):
        raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
    values = []
    for key, default in [('limit', '25'), ('after', '0')]:
        value = query.get(key, default)
        if not value.isascii() or not value.isdecimal() or len(value) > 16:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        values.append(int(value))
    return values


def create_bootstrap_app(engine, *, inventory_url=DEFAULT_INVENTORY_URL, auth_limiter=None):
    service = BootstrapService(engine, inventory_url)
    accounts = AccountService(engine)
    limiter = auth_limiter if auth_limiter is not None else _AUTH_LIMITER
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_Boundary)

    @app.exception_handler(DomainFailure)
    async def domain_error(request, error):
        return error_response(error.code, request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response('VALIDATION_ERROR', request.state.request_id)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response({404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED'}.get(error.status_code, 'VALIDATION_ERROR'), request.state.request_id)

    @app.post('/v1/accounts', status_code=201)
    def register(body: Credentials):
        with limiter.acquire():
            try:
                account = accounts.register(body.login, body.password)
            except ValueError as error:
                code = 'CONFLICT' if str(error) == 'login already exists' else 'VALIDATION_ERROR'
                raise DomainFailure(code, 'Request rejected') from None
        return {'accountId': str(account)}

    @app.post('/v1/sessions')
    def login(body: Credentials):
        with limiter.acquire():
            account = accounts.authenticate(body.login, body.password)
            if account is None:
                raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
            try:
                token = service.sessions.issue(account)
            except ValueError:
                raise DomainFailure('UNAUTHENTICATED', 'Authentication required') from None
        return {'token': token, 'tokenType': 'Bearer', 'expiresIn': int(service.sessions.ttl.total_seconds())}

    @app.delete('/v1/sessions/current', status_code=204)
    def revoke(request: Request):
        token = _token(request)
        service.account(token)
        service.sessions.revoke(token)
        return Response(status_code=204)

    @app.get('/v1/players')
    def players(request: Request):
        limit, after = _page(request)
        return service.list_players(_token(request), limit=limit, after=after)

    @app.post('/v1/inventory/bootstrap')
    def bootstrap(request: Request, body: Selection):
        return service.select(_token(request), body.playerId, body.serverId)

    return app

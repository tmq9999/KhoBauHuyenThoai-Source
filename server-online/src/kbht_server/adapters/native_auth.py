"""Recovered serverMain form contract; no provider or gameplay emulation."""
from urllib.parse import parse_qsl
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from kbht_server.auth import AccountService, SessionService
from kbht_server.contracts import DomainFailure
from .bootstrap import _Boundary, AuthLimiter

_MESSAGES = {
    'VALIDATION_ERROR': 'Invalid request',
    'UNAUTHENTICATED': 'Authentication required',
    'FORBIDDEN': 'Request forbidden',
    'CONFLICT': 'Account unavailable',
    'CONTENT_UNAVAILABLE': 'Server maintenance',
    'NOT_IMPLEMENTED': 'Native player snapshot unavailable',
    'RATE_LIMITED': 'Too many requests',
    'PAYLOAD_TOO_LARGE': 'Request too large',
    'UNSUPPORTED_MEDIA_TYPE': 'Form data required',
    'REQUEST_TIMEOUT': 'Request timed out',
    'NOT_FOUND': 'Resource not found',
    'METHOD_NOT_ALLOWED': 'Method not allowed',
}
_LIMITER = AuthLimiter()


def native_failure(code):
    return {'code': 500, 'msg': _MESSAGES.get(code, 'Request failed')}


def native_error_response(code, request_id=None):
    # Native callbacks inspect body.code, not the modern error wrapper.
    return JSONResponse(native_failure(code), headers={'Cache-Control': 'no-store'})


def decode_form(body):
    value = body.decode('utf-8', errors='strict')
    if re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ValueError('Invalid form encoding')
    pairs = parse_qsl(value, keep_blank_values=True, strict_parsing=True,
                     encoding='utf-8', errors='strict', max_num_fields=5)
    result = {}
    for key, item in pairs:
        if key in result or not key or len(key) > 32 or len(item) > 128:
            raise ValueError('Invalid form field')
        result[key] = item
    return result


def _fields(body, required, optional=()):
    if set(body) - set(required) - set(optional) or not set(required) <= set(body):
        raise DomainFailure('VALIDATION_ERROR', 'Invalid request')


def public_servers(engine):
    """No account lookup: the recovered serverInfo request has no token."""
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT s.id,s.name FROM game_servers s JOIN content_versions c "
            "ON c.id=s.active_content_version_id WHERE s.status='OPEN' "
            "AND c.status='PUBLISHED' ORDER BY s.id LIMIT 1001"
        )).mappings().all()
    if len(rows) > 1000 or any(not 0 < row['id'] <= 2147483647 for row in rows):
        raise DomainFailure('CONTENT_UNAVAILABLE', 'Server maintenance')
    # There is no legacy merge mapping in the online schema. Identity mapping
    # is explicit; connector rejects a different oldServerId.
    servers = [{'serverId': row['id'], 'oldServerId': row['id'], 'name': row['name']}
               for row in rows]
    if not servers:
        return {**native_failure('CONTENT_UNAVAILABLE'), 'serverList': [], 'players': []}
    return {'serverList': servers, 'players': []}


def create_native_auth_app(engine, *, auth_limiter=None):
    accounts, sessions = AccountService(engine), SessionService(engine)
    limiter = auth_limiter if auth_limiter is not None else _LIMITER
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(_Boundary, media_type=b'application/x-www-form-urlencoded',
                       body_validator=decode_form, respond=native_error_response,
                       allow_players_query=False)

    @app.exception_handler(DomainFailure)
    async def domain_error(request, error):
        return native_error_response(error.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return native_error_response('VALIDATION_ERROR')

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return native_error_response({404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED'}.get(
            error.status_code, 'VALIDATION_ERROR'))

    def register_form(body):
        _fields(body, ('name', 'password'), ('from', 'channel', 'accountId'))
        with limiter.acquire():
            try:
                accounts.register(body['name'], body['password'])
            except ValueError as error:
                code = 'CONFLICT' if str(error) == 'login already exists' else 'VALIDATION_ERROR'
                raise DomainFailure(code, 'Request rejected') from None
        return {'code': 200}

    def login_form(body):
        _fields(body, ('name', 'password'))
        with limiter.acquire():
            account = accounts.authenticate(body['name'], body['password'])
            if account is None:
                raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
            try:
                token = sessions.issue(account)
            except ValueError:
                raise DomainFailure('UNAUTHENTICATED', 'Authentication required') from None
        return {'uid': str(account), 'token': token}

    def server_info_form(body):
        _fields(body, ('userName',))
        try:
            AccountService._normalize(body['userName'])
        except ValueError:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request') from None
        return public_servers(engine)

    @app.post('/user/register')
    async def register(request: Request):
        return await run_in_threadpool(register_form, decode_form(await request.body()))

    @app.post('/user/login')
    async def login(request: Request):
        return await run_in_threadpool(login_form, decode_form(await request.body()))

    @app.post('/user/serverInfo')
    async def server_info(request: Request):
        return await run_in_threadpool(server_info_form, decode_form(await request.body()))

    return app

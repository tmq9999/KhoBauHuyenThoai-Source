from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException

from kbht_server.contracts import DomainFailure
from .commands import CommandAdapter


def create_app(adapter: CommandAdapter, *, authenticate: Callable[[str], UUID | None] | None = None) -> FastAPI:
    app = FastAPI(title="KBHT Online Command Transport")

    @app.get("/health")
    def health():
        return {"status": "alive", "gameplay_ready": False}

    @app.post("/v1/command")
    def command(envelope: dict, authorization: str | None = Header(default=None)):
        account_id = None
        if authenticate is not None and authorization is not None:
            scheme, separator, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and separator and token and len(token) <= 512:
                account_id = authenticate(token)
        if not isinstance(account_id, UUID):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED"},
                                headers={"WWW-Authenticate": "Bearer"})
        try:
            return adapter.execute(account_id, envelope)
        except DomainFailure as error:
            status = {"FORBIDDEN": 403, "CONFLICT": 409, "VALIDATION_ERROR": 422,
                      "NOT_IMPLEMENTED": 501, "NOT_FOUND": 404,
                      "CONTENT_UNAVAILABLE": 503}.get(error.code, 400)
            raise HTTPException(status_code=status, detail={"code": error.code}) from None

    return app

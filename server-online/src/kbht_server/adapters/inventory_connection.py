"""Per-connection negotiation for the bounded inventory protocol.

This is not a listener or full player bootstrap. Transports allocate one object
per connection and call close on disconnect; reconnect negotiates anew.
"""
from threading import RLock
from uuid import UUID

from kbht_server.auth import SessionService
from kbht_server.contracts import DomainFailure


class InventoryConnection:
    def __init__(self,engine):
        from .native_inventory import NativeInventoryAdapter
        self._adapter=NativeInventoryAdapter(engine)
        self._sessions=SessionService(engine)
        self._lock=RLock()
        self._binding=None

    def close(self):
        with self._lock:
            self._binding=None

    def _account(self):
        if self._binding is None:
            raise DomainFailure('UNAUTHENTICATED','Inventory connection is not authenticated')
        token,account,_,_,_=self._binding
        if self._sessions.resolve(token)!=account:
            self._binding=None
            raise DomainFailure('UNAUTHENTICATED','Session is unavailable')
        return account

    def negotiate(self,token,hello):
        from .native_inventory import CAPABILITY,ROUTE,MAX_SAFE

        with self._lock:
            # Failed re-authentication must not leave the former player selected.
            self._binding=None
            account=self._sessions.resolve(token)
            if account is None:
                raise DomainFailure('UNAUTHENTICATED','Session is unavailable')
            if type(hello) is not dict or set(hello)!={
                'protocolVersion','capabilities','playerId','serverId','contentVersionId'
            }:
                raise DomainFailure('VALIDATION_ERROR','Invalid inventory negotiation')
            if type(hello['protocolVersion']) is not int or hello['protocolVersion']!=1:
                raise DomainFailure('NOT_IMPLEMENTED','Unsupported inventory protocol')
            capabilities=hello['capabilities']
            if (type(capabilities) is not list or not 1<=len(capabilities)<=16 or
                    any(type(value) is not str or not 1<=len(value)<=64 for value in capabilities) or
                    len(set(capabilities))!=len(capabilities)):
                raise DomainFailure('VALIDATION_ERROR','Invalid capability list')
            if CAPABILITY not in capabilities:
                raise DomainFailure('NOT_IMPLEMENTED','Inventory capability unavailable')
            player,server=hello['playerId'],hello['serverId']
            if (type(player) is not int or not 0<player<=MAX_SAFE or
                    type(server) is not int or not 0<server<=2147483647):
                raise DomainFailure('VALIDATION_ERROR','Invalid selection')
            try:
                if type(hello['contentVersionId']) is not str:
                    raise ValueError
                content=UUID(hello['contentVersionId'])
            except (ValueError,TypeError,AttributeError):
                raise DomainFailure('VALIDATION_ERROR','Invalid content version') from None
            snapshot=self._adapter.snapshot(account,player,server,content,capability=CAPABILITY)
            # Snapshot work may have waited for another command. Do not bind an
            # already-invalid token after waiting; subsequent operations recheck.
            if self._sessions.resolve(token)!=account:
                raise DomainFailure('UNAUTHENTICATED','Session is unavailable')
            self._binding=(token,account,player,server,content)
            return {'protocolVersion':1,'capability':CAPABILITY,'playerId':player,'serverId':server,
                    'contentVersionId':str(content),'allowedRoutes':[ROUTE],
                    'fullPlayerSnapshot':False,'snapshotMode':'replace-bag','snapshot':snapshot}

    def execute(self,envelope):
        from .native_inventory import CAPABILITY

        with self._lock:
            account=self._account()
            _,_,player,server,content=self._binding
            if type(envelope) is not dict:
                raise DomainFailure('VALIDATION_ERROR','Invalid command envelope')
            if (type(envelope.get('player_id')) is not int or type(envelope.get('server_id')) is not int):
                raise DomainFailure('VALIDATION_ERROR','Invalid command scope')
            if envelope['player_id']!=player or envelope['server_id']!=server:
                raise DomainFailure('FORBIDDEN','Command differs from selected player/server')
            try:
                if type(envelope.get('content_version_id')) is not str:
                    raise ValueError
                requested=UUID(envelope['content_version_id'])
            except (TypeError,ValueError,AttributeError):
                raise DomainFailure('VALIDATION_ERROR','Invalid command content') from None
            if requested!=content:
                raise DomainFailure('CONTENT_UNAVAILABLE','Content renegotiation required')
            # Do not rewrite expected_version or command_id after reconnect:
            # exact old requests must reach durable receipt replay unchanged.
            return self._adapter.execute(account,envelope,capability=CAPABILITY)

    def resync(self):
        from .native_inventory import CAPABILITY

        with self._lock:
            account=self._account()
            _,_,player,server,content=self._binding
            snapshot=self._adapter.snapshot(account,player,server,content,capability=CAPABILITY)
            self._account()
            return {'snapshotMode':'replace-bag','fullPlayerSnapshot':False,'snapshot':snapshot}

"""Native Pomelo gate/connector authentication, not a fabricated game server."""
from sqlalchemy import text

from kbht_server.auth import SessionService
from kbht_server.contracts import DomainFailure
from kbht_server.players.creation import create_player, rename_player
from kbht_server.players.recruitment import claim_tutorial
from kbht_server.players.snapshots import player_snapshot, encode_player
from kbht_server.battles.maps import begin_smap, BEGIN_ROUTE, END_ROUTE
from kbht_server.battles.settlement import end_smap
from .native_auth import native_failure
from .pomelo_codec import HEARTBEAT
from .pomelo_transport import PomeloInventoryServer, _ProtocolError, _json_bytes, _json_loads

MAX_SAFE_ID = 9007199254740991


class NativeConnection:
    def __init__(self, engine, battle_engine=None):
        self.engine = engine
        self.battle_engine = battle_engine
        self.sessions = SessionService(engine)
        self.close()

    def close(self):
        self.token = self.account_id = self.server_id = self.content_id = self.player_id = None

    def _content(self, server_id):
        with self.engine.connect() as connection:
            return connection.execute(text(
                "SELECT c.id FROM game_servers s JOIN content_versions c "
                "ON c.id=s.active_content_version_id WHERE s.id=:server "
                "AND s.status='OPEN' AND c.status='PUBLISHED'"
            ), {'server': server_id}).scalar_one_or_none()

    def revalidate(self):
        if self.token is None:
            raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
        try:
            if self._content(self.server_id) != self.content_id:
                raise DomainFailure('CONTENT_UNAVAILABLE', 'Server maintenance')
            # Content/pool waits must finish before the last auth read. A token
            # revoked, expired or account-locked during that wait is not valid.
            if self.sessions.resolve(self.token) != self.account_id:
                raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
        except Exception:
            self.close()
            raise

    def bind(self, body):
        self.close()  # A failed reauthentication never retains prior authority.
        if set(body) != {'token', 'serverId', 'oldServerId'}:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        server, old_server, token = body['serverId'], body['oldServerId'], body['token']
        if (type(server) is not int or not 0 < server <= 2147483647 or
                type(old_server) is not int or old_server != server or
                not isinstance(token, str) or not 20 <= len(token) <= 256 or
                any(ch.isspace() for ch in token)):
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        account = self.sessions.resolve(token)
        if account is None:
            raise DomainFailure('UNAUTHENTICATED', 'Authentication required')
        content = self._content(server)
        if content is None:
            raise DomainFailure('CONTENT_UNAVAILABLE', 'Server maintenance')
        self.token, self.account_id = token, account
        self.server_id, self.content_id = server, content
        self.revalidate()
        return {'code': 200}

    def request(self, route, body):
        if route == 'connector.entryHandler.entry':
            return self.bind(body)
        self.revalidate()
        if route in (BEGIN_ROUTE,END_ROUTE):
            if self.player_id is None:
                raise DomainFailure('VALIDATION_ERROR','Invalid request')
            handler = begin_smap if route==BEGIN_ROUTE else end_smap
            result = handler(self.engine,self.account_id,self.server_id,self.player_id,
                             self.content_id,self.token,body,self.battle_engine)
            self.revalidate()
            return result
        if route == 'connector.playerHandler.createPlayer':
            if set(body) != {'name'}:
                raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
            snapshot = create_player(self.engine, self.account_id, self.server_id, body['name'], self.content_id, self.token)
            self.revalidate()
            self.player_id = snapshot['id']
            return {'player': encode_player(snapshot)}
        if route == 'connector.playerHandler.entry':
            if (set(body) != {'playerId', 'isReconnect'} or type(body['playerId']) is not int or
                    not 10000 < body['playerId'] <= MAX_SAFE_ID or type(body['isReconnect']) is not bool):
                raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
            self.player_id = None
            snapshot = player_snapshot(self.engine, self.account_id, self.server_id, body['playerId'], self.content_id, self.token)
            self.revalidate()
            self.player_id = snapshot['id']
            return {'player': encode_player(snapshot)}
        if route == 'logic.playerHandler.rename':
            if set(body) != {'name'} or self.player_id is None:
                raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
            result = rename_player(self.engine, self.account_id, self.server_id, self.player_id, body['name'], self.content_id, self.token)
            self.revalidate()
            return result
        if route in ('logic.pointHandler.coin','logic.pointHandler.gem'):
            if body != {} or self.player_id is None:
                raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
            result = claim_tutorial(self.engine,self.account_id,self.server_id,self.player_id,
                                    route.rsplit('.',1)[1],self.content_id,self.token)
            self.revalidate()
            return result
        if route != 'connector.playerHandler.getPlayers':
            raise DomainFailure('NOT_IMPLEMENTED', 'Native route unavailable')
        if body != {}:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        with self.engine.connect() as connection:
            rows = connection.execute(text(
                'SELECT id,name FROM players WHERE account_id=:account '
                'AND server_id=:server ORDER BY id LIMIT 2'
            ), {'account': self.account_id, 'server': self.server_id}).mappings().all()
        # Current DB uniqueness is one player/account/server. Never truncate a
        # divergent schema or emit an unsafe JS integer.
        if len(rows) > 1 or any(not 0 < row['id'] <= MAX_SAFE_ID for row in rows):
            raise DomainFailure('CONTENT_UNAVAILABLE', 'Player unavailable')
        self.revalidate()
        return {'players': [{'id': row['id'], 'name': row['name']} for row in rows]}


class NativePomeloServer(PomeloInventoryServer):
    """Reuse the bounded upgrade, framing, ACK, worker and shutdown lifecycle."""
    websocket_path = '/'

    def __init__(self, engine, *, role, host='127.0.0.1', port=0,
                 connector_host='127.0.0.1', connector_port=20101, battle_engine=None):
        super().__init__(engine, host=host, port=port)
        self.battle_engine = battle_engine
        if role not in ('gate', 'connector'):
            raise ValueError('Invalid native endpoint role')
        if connector_host not in ('127.0.0.1', '::1') or type(connector_port) is not int or not 1 <= connector_port <= 65535:
            raise ValueError('Invalid loopback connector address')
        self.role = role
        # Client assembles ws:// + host + :port, so IPv6 needs brackets.
        self.connector_host = '[::1]' if connector_host == '::1' else connector_host
        self.connector_port = connector_port

    def _connection(self):
        return NativeConnection(self.engine,self.battle_engine)

    async def _ready(self, writer):
        # Recovered client schedules its timer only after the first server
        # heartbeat. Three seconds is an explicit new loopback server policy,
        # below the shared 10-second read bound, not a historical recovered value.
        await self._send_package(writer, HEARTBEAT, b'')

    @staticmethod
    def _handshake(connection, body):
        obj = _json_loads(body)
        if not isinstance(obj, dict) or set(obj) - {'sys', 'user'} or 'sys' not in obj:
            raise _ProtocolError('Invalid handshake')
        sys = obj['sys']
        if (not isinstance(sys, dict) or set(sys) - {'type', 'version', 'rsa', 'protoVersion'} or
                sys.get('type') != 'js-websocket' or sys.get('version') != '0.0.1' or
                sys.get('rsa', {}) != {} or
                type(sys.get('protoVersion', 0)) is not int or
                not 0 <= sys.get('protoVersion', 0) <= 2147483647 or
                obj.get('user', {}) != {}):
            raise _ProtocolError('Invalid handshake')
        return _json_bytes({'code': 200, 'sys': {'heartbeat': 3, 'dict': {},
            'protos': {'version': 0, 'server': {}, 'client': {}}}, 'user': {}})

    def _request(self, connection, route, body):
        if self.role == 'connector':
            return connection.request(route, body)
        # uid is a bounded routing hint only; it is not an authenticated account.
        if route != 'gate.gateHandler.queryEntry':
            raise DomainFailure('NOT_IMPLEMENTED', 'Native route unavailable')
        if set(body) != {'uid'} or not isinstance(body['uid'], str) or not 1 <= len(body['uid']) <= 128:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        return {'code': 200, 'host': self.connector_host, 'port': self.connector_port}

    async def _dispatch(self, writer, connection, message):
        try:
            body = _json_loads(message.payload_bytes)
            if not isinstance(body, dict):
                raise ValueError('Invalid request')
            payload = await self._blocking(self._request, connection, message.route, body)
        except (ValueError, UnicodeError):
            if message.route == 'connector.entryHandler.entry':
                connection.close()
            payload = native_failure('VALIDATION_ERROR')
        except DomainFailure as error:
            payload = native_failure(error.code)
        except Exception:
            connection.close()
            payload = native_failure('INTERNAL_ERROR')
        await self._send_response(writer, message.request_id, payload)

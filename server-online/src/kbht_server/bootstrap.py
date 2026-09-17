"""Auth-owned selection for the bounded inventory capability, no player creation."""
from urllib.parse import urlsplit

from sqlalchemy import text

from kbht_server.auth import SessionService
from kbht_server.contracts import DomainFailure
from kbht_server.adapters.native_inventory import NativeInventoryAdapter, CAPABILITY, MAX_SAFE

DEFAULT_INVENTORY_URL = 'ws://127.0.0.1:21002/inventory'


def validate_inventory_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'ws' or parsed.hostname not in ('127.0.0.1', '::1') or
                parsed.username is not None or parsed.password is not None or
                parsed.path != '/inventory' or parsed.query or parsed.fragment or
                parsed.port is None or not 1 <= parsed.port <= 65535 or
                value != f"ws://{'[' + parsed.hostname + ']' if ':' in parsed.hostname else parsed.hostname}:{parsed.port}/inventory"):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid loopback inventory URL') from None
    return value


class BootstrapService:
    def __init__(self, engine, inventory_url=DEFAULT_INVENTORY_URL):
        self.engine = engine
        self.inventory_url = validate_inventory_url(inventory_url)
        self.sessions = SessionService(engine)
        self.inventory = NativeInventoryAdapter(engine)

    def account(self, token):
        account = self.sessions.resolve(token)
        if account is None:
            raise DomainFailure('UNAUTHENTICATED', 'Session unavailable')
        return account

    def list_players(self, token, *, limit=25, after=0):
        account = self.account(token)
        if type(limit) is not int or not 1 <= limit <= 100 or type(after) is not int or not 0 <= after <= MAX_SAFE:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        with self.engine.connect() as connection:
            rows = connection.execute(text('SELECT id,server_id,name FROM players WHERE account_id=:account AND id>:after ORDER BY id LIMIT :limit'), {'account': account, 'after': after, 'limit': limit + 1}).mappings().all()
        self.account(token)
        return {'players': [{'playerId': row['id'], 'serverId': row['server_id'], 'name': row['name']} for row in rows[:limit]],
                'nextAfter': rows[limit-1]['id'] if len(rows) > limit else None}

    def select(self, token, player_id, server_id):
        account = self.account(token)
        if type(player_id) is not int or not 0 < player_id <= MAX_SAFE or type(server_id) is not int or not 0 < server_id <= 2147483647:
            raise DomainFailure('VALIDATION_ERROR', 'Invalid request')
        with self.engine.connect() as connection:
            owned = connection.execute(text('SELECT id FROM players WHERE id=:player AND server_id=:server AND account_id=:account'), {'player': player_id, 'server': server_id, 'account': account}).first()
            if owned is None:
                raise DomainFailure('FORBIDDEN', 'Player unavailable')
            content = connection.execute(text("SELECT c.id FROM game_servers s JOIN content_versions c ON c.id=s.active_content_version_id WHERE s.id=:server AND s.status='OPEN' AND c.status='PUBLISHED'"), {'server': server_id}).scalar_one_or_none()
            if content is None:
                raise DomainFailure('CONTENT_UNAVAILABLE', 'Content unavailable')
        snapshot = self.inventory.snapshot(account, player_id, server_id, content, capability=CAPABILITY)
        if self.sessions.resolve(token) != account:
            raise DomainFailure('UNAUTHENTICATED', 'Session unavailable')
        return {'hello': {'protocolVersion': 1, 'capabilities': [CAPABILITY], 'playerId': player_id, 'serverId': server_id, 'contentVersionId': str(content)},
                'inventoryUrl': self.inventory_url, 'inventoryIdentity': 'postgres-v1',
                'fullPlayerSnapshot': False, 'snapshot': snapshot}

"""Opt-in native fragment/box DTOs, not a legacy gateway or full player snapshot."""
import re
from uuid import UUID

from sqlalchemy import select

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import players,game_servers,content_versions,inventory_items
from kbht_server.db.uow import CommandExecutor
from kbht_server.economy.boxes import use_fixed_box
from .inventory_connection import InventoryConnection

CAPABILITY='native-inventory-v1'
ROUTE='logic.playerHandler.useItem'
MAX_SAFE=9007199254740991


def _require_capability(value):
    if value!=CAPABILITY:
        raise DomainFailure('NOT_IMPLEMENTED','Native inventory capability is required')


def _bag_id(value):
    # Fresh PostgreSQL clients use the immutable inventory primary key as the
    # canonical decimal bag key. No SQLite/legacy ID equivalence is implied.
    if type(value) is not str or re.fullmatch(r'[1-9][0-9]{0,15}',value) is None or int(value)>MAX_SAFE:
        raise DomainFailure('VALIDATION_ERROR','Invalid native bagIndex')
    return int(value)


def _use_item(work,payload):
    if type(payload) is not dict or set(payload)!={'bagIndex','itemCount'}:
        raise DomainFailure('VALIDATION_ERROR','Invalid native useItem payload')
    result=use_fixed_box(work,{'inventory_id':_bag_id(payload['bagIndex']),'quantity':payload['itemCount']})
    items={key:None if row is None else {'kindId':row['kind_id'],'count':row['quantity']}
           for key,row in result['inventory'].items()}
    rewards={str(row['kind_id']):row['quantity'] for row in result['reward']['items']}
    # Saved by CommandExecutor in the same TX. Never rebuild replay from new DB
    # state after committing (it would change the original response on retry).
    return {'bag':{'items':items},'_temp':{'route':ROUTE,'entityCountMap':rewards}}


class NativeInventoryAdapter:
    """Caller supplies authenticated identity and negotiated capability.

    Stable string IDs reuse immutable PostgreSQL IDs. No extra mapping state is
    necessary for new online inventories; importing a legacy bag is separate.
    """
    def __init__(self,engine):
        from .commands import CommandAdapter
        self.engine=engine
        self.commands=CommandAdapter(CommandExecutor(engine,{ROUTE:_use_item}),{ROUTE})

    def execute(self,account_id,envelope,*,capability=None):
        _require_capability(capability)
        return self.commands.execute(account_id,envelope)

    def snapshot(self,account_id,player_id,server_id,content_version_id,*,capability=None):
        from sqlalchemy import text

        _require_capability(capability)
        if (type(account_id) is not UUID or type(content_version_id) is not UUID or
                any(type(value) is not int or not 0<value<=MAX_SAFE for value in (player_id,server_id))):
            raise DomainFailure('VALIDATION_ERROR','Invalid snapshot identity')
        with self.engine.begin() as connection:
            # Same aggregate lock order as CommandExecutor. Shared lock retains
            # version and inventory consistency until all rows have been read.
            player=connection.execute(select(players).where(players.c.id==player_id).with_for_update(read=True)).mappings().one_or_none()
            if player is None or player['account_id']!=account_id or player['server_id']!=server_id:
                raise DomainFailure('FORBIDDEN','Player is not owned in this server')
            content=connection.execute(select(content_versions.c.id).join(
                game_servers,game_servers.c.active_content_version_id==content_versions.c.id).where(
                game_servers.c.id==server_id,game_servers.c.status=='OPEN',
                content_versions.c.id==content_version_id,content_versions.c.status=='PUBLISHED'
            ).with_for_update(read=True)).first()
            if content is None:
                raise DomainFailure('CONTENT_UNAVAILABLE','Active published content is unavailable')
            supported=set(connection.execute(text(
                'SELECT kind_id FROM fixed_box_definitions WHERE content_version_id=:version '
                'UNION SELECT reward_kind_id FROM fixed_box_rewards WHERE content_version_id=:version'
            ),{'version':content_version_id}).scalars())
            rows=connection.execute(select(inventory_items).where(
                inventory_items.c.player_id==player_id,inventory_items.c.quantity>0
            ).order_by(inventory_items.c.id)).mappings().all()
            items={}
            for row in rows:
                if row['content_version_id']!=content_version_id:
                    raise DomainFailure('CONTENT_UNAVAILABLE','Inventory requires content migration')
                if row['kind_id'] not in supported:
                    raise DomainFailure('NOT_IMPLEMENTED','Native item metadata is not supported')
                items[str(row['id'])]={'kindId':row['kind_id'],'count':row['quantity']}
            return {'version':player['version'],'contentVersionId':str(content_version_id),'bag':{'items':items}}

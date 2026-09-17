"""Fixed fragment box use inside an already authorized CommandExecutor TX."""
from sqlalchemy import select,text

from kbht_server.contracts import DomainFailure
from kbht_server.db.repositories import positive_int,MAX_QUANTITY
from kbht_server.db.schema import inventory_items

MAX_BOXES_PER_COMMAND=100


def use_fixed_box(work,payload):
    if type(payload) is not dict or set(payload)!={'inventory_id','quantity'}:
        raise DomainFailure('VALIDATION_ERROR','Invalid box payload')
    inventory_id,quantity=payload['inventory_id'],payload['quantity']
    positive_int(inventory_id)
    positive_int(quantity)
    if quantity>MAX_BOXES_PER_COMMAND:
        raise DomainFailure('LIMIT_REACHED','Box batch limit exceeded')
    owned=work.connection.execute(select(inventory_items).where(
        inventory_items.c.id==inventory_id,
        inventory_items.c.player_id==work.command.player_id,
    ).with_for_update()).mappings().one_or_none()
    if owned is None:
        raise DomainFailure('NOT_FOUND','Owned box not found')
    if owned['content_version_id']!=work.command.content_version_id:
        raise DomainFailure('CONTENT_UNAVAILABLE','Box requires content migration')
    kind=owned['kind_id']
    params={'version':work.command.content_version_id,'kind':kind}
    # Executor holds the published content row. Definitions are immutable then;
    # runtime needs SELECT only, not permissions to edit box recipes.
    defined=work.connection.execute(text('SELECT kind_id FROM fixed_box_definitions WHERE content_version_id=:version AND kind_id=:kind'),params).scalar_one_or_none()
    if defined is None:
        raise DomainFailure('NOT_IMPLEMENTED','Fixed box is not supported in this release')
    lines=work.connection.execute(text('SELECT reward_kind_id,quantity FROM fixed_box_rewards WHERE content_version_id=:version AND kind_id=:kind ORDER BY reward_kind_id'),params).all()
    if not lines or len(lines)>100:
        raise DomainFailure('CONTENT_UNAVAILABLE','Invalid fixed box rewards')
    items={row[0]:row[1]*quantity for row in lines}
    if kind in items or any(total>MAX_QUANTITY for total in items.values()):
        raise DomainFailure('LIMIT_REACHED','Invalid fixed box reward capacity')
    for reward_kind in items:
        work.inventory.definition(reward_kind)
    before_ids=set(work.connection.execute(select(inventory_items.c.id).where(
        inventory_items.c.player_id==work.command.player_id,
        inventory_items.c.kind_id.in_([kind,*items]),
    )).scalars())
    consumed=work.inventory.consume(kind,quantity,reason='fixed-box.use',inventory_id=inventory_id)
    reward=work.rewards.grant(source_type='fixed-box',source_id=work.command.command_id,items=items)
    after=work.connection.execute(select(inventory_items).where(
        inventory_items.c.player_id==work.command.player_id,
        inventory_items.c.kind_id.in_([kind,*items]),
    ).order_by(inventory_items.c.id)).mappings().all()
    snapshot={str(row['id']):({'kind_id':row['kind_id'],'quantity':row['quantity'],'version':row['version']}
                            if row['quantity'] else None) for row in after}
    for removed in before_ids-{row['id'] for row in after}:
        snapshot[str(removed)]=None
    work.emit('inventory.box_used',{'inventory_id':inventory_id,'kind_id':kind,'quantity':quantity,'grant_id':reward['grant_id']})
    return {'consumed':{'inventory_id':inventory_id,'kind_id':kind,'quantity':quantity},
            'remaining':consumed['remaining'],'reward':reward,'inventory':snapshot}

"""Only the original guide's two free deterministic once-only recruitment claims.

Native payload is {} with no durable action ID. Subsequent calls fail closed,
including uncertain-response retries: relog to resync, never mint another role.
"""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from kbht_server.content.native_tutorial import tutorial_content
from kbht_server.contracts import DomainFailure, GameCommand
from kbht_server.db.uow import UnitOfWork
from .creation import _receipt
from .snapshots import locked_player, release_content, validate_session, project_snapshot, fail


def claim_tutorial(engine, account_id, server_id, player_id, draw_kind, content_id, token):
    if draw_kind not in ('coin','gem'):
        fail('NOT_IMPLEMENTED')
    with engine.begin() as connection:
        player = locked_player(connection,account_id,server_id,player_id)
        release = release_content(connection,server_id,content_id)
        validate_session(connection,account_id,token)
        tutorial = tutorial_content(connection,release)
        if tutorial is None:
            fail()
        profile = connection.execute(text('SELECT * FROM native_player_profiles WHERE player_id=:id'),{'id':player_id}).mappings().one_or_none()
        if (profile is None or profile['content_version_id']!=release['content_version_id'] or
                profile['rules_id']!=release['rules_id'] or not profile['first_rename_completed']):
            fail()
        claims = set(connection.execute(text('SELECT draw_kind FROM native_tutorial_claims WHERE player_id=:id'),{'id':player_id}).scalars())
        if draw_kind in claims:
            raise DomainFailure('NOT_IMPLEMENTED','Tutorial already claimed; reconnect to resync')
        if draw_kind=='gem' and 'coin' not in claims:
            fail('CONFLICT')
        draw = tutorial['draws'][draw_kind]
        kind,slot,star = draw['drop']['entityId'],draw['slot'],draw['drop']['extra']['star']
        # Ownership is a consistency precondition, NEVER the once-only marker.
        existing = connection.execute(text('SELECT slot,kind_id FROM native_owned_roles WHERE player_id=:id ORDER BY slot'),{'id':player_id}).all()
        expected = [(1,100101)] if draw_kind=='coin' else [(1,100101),(2,100201)]
        if existing!=expected:
            fail()
        definition = tutorial['roles'][str(kind)]
        command = GameCommand(uuid5(NAMESPACE_URL,f'kbht:native:tutorial:{player_id}:{draw_kind}'),
            account_id,player_id,server_id,'logic.pointHandler.'+draw_kind,player['version'],
            release['content_version_id'],{'tutorial_claim':draw_kind,'source_drop_id':draw['source_drop_id']})
        work = UnitOfWork(connection,command)
        connection.execute(text('INSERT INTO native_owned_roles(player_id,slot,content_version_id,kind_id,star,level,experience,awake_level,awake_rate_increase_times) VALUES (:id,:slot,:content,:kind,:star,1,0,0,0)'),
            {'id':player_id,'slot':slot,'content':release['content_version_id'],'kind':kind,'star':star})
        connection.execute(text('INSERT INTO native_role_equipment(player_id,role_slot,equipment_slot,kind_id,level) VALUES (:id,:role,:slot,:kind,1)'),
            [{'id':player_id,'role':slot,'slot':number,'kind':eq} for number,eq in enumerate(definition['role']['initEvlItemIds'],1)])
        connection.execute(text("INSERT INTO native_role_skills(player_id,role_slot,kind_id,skill_group,level) VALUES (:id,:slot,:kind,'skills',1)"),
            {'id':player_id,'slot':slot,'kind':definition['role']['skillIds'][0]})
        now_ms = int(datetime.now(timezone.utc).timestamp()*1000)
        # Dedicated append-only role issuance ledger. No item masquerading as a
        # role and no fabricated wallet posting for a free, currency-less grant.
        connection.execute(text('INSERT INTO native_tutorial_claims(player_id,draw_kind,content_version_id,command_id,role_slot,role_kind_id,source_drop_id,claimed_at_ms) VALUES (:id,:draw,:content,:command,:slot,:kind,:drop,:time)'),
            {'id':player_id,'draw':draw_kind,'content':release['content_version_id'],'command':command.command_id,
             'slot':slot,'kind':kind,'drop':draw['source_drop_id'],'time':now_ms})
        updated = connection.execute(text('UPDATE players SET version=version+1,updated_at=now() WHERE id=:id RETURNING *'),{'id':player_id}).mappings().one()
        login = connection.execute(text('SELECT normalized_login FROM accounts WHERE id=:id'),{'id':account_id}).scalar_one()
        snapshot = project_snapshot(connection,updated,release,login)
        result = {'team':snapshot['team'],'point':snapshot['point'],'power':snapshot['power'],
                  '_temp':{'route':command.route,'dropList':[draw['drop']]}}
        work.emit('native.tutorial.claimed',{'draw_kind':draw_kind,'role_slot':slot,
            'role_kind_id':kind,'source_drop_id':draw['source_drop_id'],'star':star})
        _receipt(connection,work,result,updated['version'])
        validate_session(connection,account_id,token)
        return result

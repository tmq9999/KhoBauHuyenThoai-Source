"""Consistent native DTOs projected from normalized owned records."""
import base64
import gzip
import hashlib
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from kbht_server.contracts import DomainFailure
from kbht_server.content.native_players import SOURCE_SHA, canonical, validate_policy
from kbht_server.content.native_tutorial import tutorial_content
from kbht_server.content.native_battles import battle_content
from .progression import role_cap
from .stats import ATTRS, initial_attributes, equipment_attributes, power_milli


def fail(code='CONTENT_UNAVAILABLE'):
    raise DomainFailure(code, 'Native player unavailable')


def release_content(connection, server_id, content_id):
    release = connection.execute(text(
        "SELECT n.* FROM game_servers s JOIN content_versions c ON c.id=s.active_content_version_id "
        "JOIN native_player_content n ON n.content_version_id=c.id WHERE s.id=:server "
        "AND s.status='OPEN' AND c.status='PUBLISHED' AND c.id=:content FOR SHARE OF s,c,n"
    ),{'server':server_id,'content':content_id}).mappings().one_or_none()
    if release is None or release['source_sha256']!=SOURCE_SHA:
        fail()
    try:
        validate_policy(release['policy'])
        digest = hashlib.sha256(canonical({'definitions':release['definitions'],'policy':release['policy']}).encode()).hexdigest()
        if digest!=release['definition_sha256'] or release['rules_id']!=release['policy']['rules_id']:
            fail()
    except ValueError:
        fail()
    return release


def validate_session(connection, account_id, token):
    if not isinstance(token,str):
        fail('UNAUTHENTICATED')
    session = connection.execute(text(
        "SELECT s.id FROM sessions s JOIN accounts a ON a.id=s.account_id "
        "WHERE s.account_id=:account AND s.token_hash=:hash AND s.revoked_at IS NULL "
        "AND s.expires_at>clock_timestamp() AND a.status='ACTIVE' FOR SHARE OF s,a"
    ),{'account':account_id,'hash':hashlib.sha256(token.encode()).hexdigest()}).scalar_one_or_none()
    if session is None:
        fail('UNAUTHENTICATED')


def locked_player(connection, account_id, server_id, player_id):
    # Consistent account -> player -> content -> session lock order, also used
    # by absent-player creation and SessionService.issue.
    if connection.execute(text("SELECT id FROM accounts WHERE id=:id AND status='ACTIVE' FOR SHARE"),{'id':account_id}).scalar_one_or_none() is None:
        fail('UNAUTHENTICATED')
    player = connection.execute(text('SELECT * FROM players WHERE id=:id FOR UPDATE'),{'id':player_id}).mappings().one_or_none()
    if player is None or player['account_id']!=account_id or player['server_id']!=server_id:
        fail('FORBIDDEN')
    return player


def project_snapshot(connection, player, release, user_name):
    pid = player['id']
    profile = connection.execute(text('SELECT * FROM native_player_profiles WHERE player_id=:id'),{'id':pid}).mappings().one_or_none()
    if profile is None or profile['content_version_id']!=release['content_version_id'] or profile['rules_id']!=release['rules_id']:
        fail()
    definitions, policy = release['definitions'], release['policy']
    tutorial = tutorial_content(connection,release)
    battle = battle_content(connection,release,required=False)
    xp_table = battle['experience'] if battle else {'1':definitions['experience']}
    role_definitions = {str(definitions['role']['kindId']):definitions}
    if tutorial:
        role_definitions.update(tutorial['roles'])
    # This slice explicitly has no progression handlers; fail rather than project
    # a stale first-level XP table for records written by an incompatible service.
    if str(profile['level']) not in xp_table:
        fail()
    roles, powers = {}, []
    for owned in connection.execute(text('SELECT * FROM native_owned_roles WHERE player_id=:id ORDER BY slot'),{'id':pid}).mappings():
        role_definition = role_definitions.get(str(owned['kind_id']))
        if (role_definition is None or owned['content_version_id']!=release['content_version_id'] or
                str(owned['level']) not in xp_table or owned['level']>role_cap(profile['level']) or owned['awake_level']!=0):
            fail()
        initial,growth = initial_attributes(role_definition['role'],owned['level'],owned['star'])
        equipment, equipment_total = {},dict.fromkeys(ATTRS,0)
        for eq in connection.execute(text('SELECT * FROM native_role_equipment WHERE player_id=:id AND role_slot=:slot ORDER BY equipment_slot'),{'id':pid,'slot':owned['slot']}).mappings():
            definition = role_definition['equipment'].get(str(eq['kind_id']))
            if definition is None:
                fail()
            attrs = equipment_attributes(definition['effect'],eq['level'])
            equipment['evlItem_'+str(eq['equipment_slot'])] = {'kindId':eq['kind_id'],'level':eq['level'],'attrs':attrs}
            for key,value in attrs.items():
                equipment_total[key] += value
        if len(equipment)!=6:
            fail()
        skills = {'skills':{},'awakeSkills':{}}
        attr = {key:initial[key]+equipment_total[key] for key in ATTRS}
        attr.update(growth)
        for skill in connection.execute(text('SELECT * FROM native_role_skills WHERE player_id=:id AND role_slot=:slot ORDER BY kind_id'),{'id':pid,'slot':owned['slot']}).mappings():
            kind = str(skill['kind_id'])
            if owned['kind_id']!=definitions['role']['kindId'] and (skill['kind_id']!=role_definition['role']['skillIds'][0] or skill['level']!=1):
                fail()
            definition = role_definition['skills'].get(kind)
            if definition is None or skill['skill_group']!='skills':
                fail()
            skills[skill['skill_group']][kind] = {'kindId':skill['kind_id'],'level':skill['level']}
            if definition['type']==3:
                for buff_id in definition['buffIds']:
                    extra = role_definition['buffs'][str(buff_id)]['extra']
                    for key in ATTRS:
                        if key in extra:
                            attr[key] += extra[key]+extra.get('growth',0)*skill['level']
        power = power_milli(attr,owned['level'] if battle else policy['power_second_argument'])
        powers.append(power)
        roles[str(owned['slot'])] = {'kindId':owned['kind_id'],'star':owned['star'],'level':owned['level'],
            'experience':owned['experience'],'nextLevelExp':xp_table[str(owned['level'])]['roleExp'],
            'awakeLevel':owned['awake_level'],'awakeRateIncreaseTimes':owned['awake_rate_increase_times'],
            'initAttr':initial,'equipmentsAttr':equipment_total,'attr':attr,'equipments':equipment,
            'power':power//1000,**skills}
    if '1' not in roles:
        fail()
    balances = dict(connection.execute(text('SELECT currency,balance FROM wallets WHERE player_id=:id'),{'id':pid}).all())
    if any(key not in balances for key in ('coin','gem','actionPoint','skillPoint')):
        fail()
    items = {}
    supported_items = set(connection.execute(text(
        'SELECT kind_id FROM fixed_box_definitions WHERE content_version_id=:content '
        'UNION SELECT reward_kind_id FROM fixed_box_rewards WHERE content_version_id=:content'
    ),{'content':release['content_version_id']}).scalars())
    for item in connection.execute(text('SELECT id,content_version_id,kind_id,quantity FROM inventory_items WHERE player_id=:id AND quantity>0'),{'id':pid}).mappings():
        if (item['content_version_id']!=release['content_version_id'] or
            item['kind_id'] not in supported_items or not 10000<item['id']<=9007199254740991):
            fail()
        items[str(item['id'])] = {'kindId':item['kind_id'],'count':item['quantity']}
    stars,times = {'1':{'101':{}}},{}
    for row in connection.execute(text('SELECT * FROM native_map_progress WHERE player_id=:id'),{'id':pid}).mappings():
        stars.setdefault(str(row['map_type']),{}).setdefault(str(row['chapter_id']),{})[str(row['map_id'])]=row['star']
        times.setdefault(str(row['map_type']),{}).setdefault(str(row['chapter_id']),{})[str(row['map_id'])]=row['attempts']
    if battle:
        times = {}
        for row in connection.execute(text("SELECT smap_id,attempts FROM native_battle_attempts WHERE player_id=:id AND reset_day=((clock_timestamp() AT TIME ZONE 'Asia/Ho_Chi_Minh')-interval '5 hours')::date"),{'id':pid}).mappings():
            stage = battle['graph'][str(row['smap_id'])]
            times.setdefault('1',{}).setdefault(str(stage['chapter_id']),{})[str(row['smap_id'])]=row['attempts']
    now_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    vietnam = datetime.fromtimestamp(now_ms/1000,timezone(timedelta(hours=7)))
    claims = {row['draw_kind']:row for row in connection.execute(text(
        'SELECT draw_kind,claimed_at_ms FROM native_tutorial_claims WHERE player_id=:id'
    ),{'id':pid}).mappings()}
    coin,gem = claims.get('coin'),claims.get('gem')
    point = {'freeCoinTimes':1 if coin else 0,'coinTimes':1 if coin else 0,
             'gemTimes':1 if gem else 0,'isPayGemFirst':False,
             'nextCoinFreeTime':coin['claimed_at_ms']+300000 if coin else 0,
             'nextGemFreeTime':gem['claimed_at_ms']+172800000 if gem else 0}
    # Explicit unavailable-zero-v1 policy. These are not seeded rewards, offers,
    # progress or writable JSON state; features cannot mutate them in this slice.
    return {'id':pid,'serverId':player['server_id'],'userName':user_name,'name':player['name'],
        'level':profile['level'],'experience':profile['experience'],
        'nextLevelExp':xp_table[str(profile['level'])]['playerExp'],'power':sum(powers)//1000,
        **{key:balances[key] for key in ('coin','gem','actionPoint','skillPoint')},
        'timesMaxMap':{'actionPoint':60+profile['level'],'skillPoint':profile['skill_point_cap']},
        'nextRecoverTimeMap':{'actionPoint':profile['next_action_recover_ms'],'skillPoint':profile['next_skill_recover_ms']},
        'photoInfo':{'photoImgId':profile['photo_img_id'],'shipImgId':profile['ship_img_id']},
        'vip':{'level':profile['vip_level'],'topUpGem':profile['vip_top_up_gem'],'giftGem':profile['vip_gift_gem'],
               'buyActionPointTimes':profile['buy_action_point_times'],'buySkillPointTimes':profile['buy_skill_point_times']},
        'bag':{'items':items},'team':{'roles':roles,'friendshipAttr':dict.fromkeys(ATTRS[:4],0)},
        'point':point,
        'arena':{'challengeCD':0,'remainingChallengeTimes':0},'arena3v3':{'challengeCD':0,'remainingChallengeTimes':0},
        'shop':{'hideRoleClassIds':policy['hide_role_class_ids'],'refreshTimesMap':{},'goodsMap':{}},
        'task':{'main':{'1':{'taskId':0}},'daily':{},'achievement':{},'dailyActivePoint':0,'weeklyActivePoint':0,'receivedPointMap':{'daily':{},'weekly':{}}},
        'activity':{'map':{}},'signInDays':0,'signInTime':0,'monthCardExpire':0,'bigMonthCardExpire':0,'yearCardExpire':0,'weekCardExpire':0,
        'friend':{'count':0,'actionPointReceiveTimes':0,'infoMap':{}},'smapStarMap':stars,'smapTimesMap':times,'guildId':0,
        'extra':{'serverTime':now_ms,'serverTimeStr':vietnam.strftime('%Y-%m-%d %H:%M:%S.')+f'{now_ms%1000:03d}',
                 'openDays':policy['open_days'],'mails':[],'goodsList':[],
                 'chat':{'worldList':[],'guildList':[],'allServerList':[]},
                 'nativeAvailability':dict.fromkeys(('shop','paidCatalog','tasks','recruitment','arena','friends','activity','chat','battle'),False)}}


def encode_player(snapshot):
    raw = json.dumps(snapshot,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode('utf-8')
    return base64.b64encode(gzip.compress(raw,mtime=0)).decode('ascii')


def player_snapshot(engine, account_id, server_id, player_id, content_id, token):
    with engine.begin() as connection:
        player = locked_player(connection,account_id,server_id,player_id)
        release = release_content(connection,server_id,content_id)
        validate_session(connection,account_id,token)
        login = connection.execute(text('SELECT normalized_login FROM accounts WHERE id=:id'),{'id':account_id}).scalar_one()
        from .creation import recover_resources
        player = recover_resources(connection,player,release)
        result = project_snapshot(connection,player,release,login)
        validate_session(connection,account_id,token)
        return result

# Native first-login player contract

Status: STATIC_CONTRACT. This is derived from client constructors/consumers,
not a saved SQLite candidate or proof of server initialization semantics.
Source project.js SHA256:
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.

## Entry/rename wire

getPlayers consumes `players[].id` (31421ff). Create/entry need complete
`{player:...}` with existing native compression/decoder (53938ff). Rename returns
root `{name,...changed fields}`, not another nested player; socket merges before
calling success (53993ff,40114ff). `userName==name` triggers first-name guide
(26015/22219). Persist first-rename completion explicitly; later rename costs
100gem (49514), not repeatedly free when names happen to match.

## Mandatory first-home projection

| Group | Required fields | Client consumers |
| --- | --- | --- |
| Identity | id,serverId,userName,name,level,power,experience,nextLevelExp | 26155ff,22364,49464ff |
| Balances/time | coin,gem,actionPoint,skillPoint,timesMaxMap,nextRecoverTimeMap (actionPoint/skillPoint keys) | 17110ff,45733,53430 |
| Avatar/VIP | photoInfo(photoImgId,shipImgId),vip(level,topUpGem,giftGem,buyActionPointTimes,buySkillPointTimes) | 40097,26155,17127 |
| Owned bag/team | bag.items; team.roles with starter key1; team.friendshipAttr hp/atk/def/mdef | 5837ff,55994ff,22364 |
| Recruitment | point freeCoinTimes/isPayGemFirst/nextCoinFreeTime/nextGemFreeTime | 40483ff,26155ff |
| Arena badges | arena/arena3v3 challengeCD/remainingChallengeTimes | 26155ff |
| Shop | hideRoleClassIds,refreshTimesMap,goodsMap; eager goods dereference needs guard or real offers | 52688ff,26158 |
| Task | main['1'],daily,achievement,dailyActivePoint,weeklyActivePoint,receivedPointMap.daily/weekly | 31908ff,42504,18354ff,1310ff |
| Activity/cards | activity.map,signInDays,signInTime,four card expiry fields; paid-catalog eager reads | 2074ff,2101ff |
| Friends/map | friend count/actionPointReceiveTimes/infoMap; smapStarMap['1']['101'],smapTimesMap | 22017ff,22582,53719ff |
| Misc | guildId; extra serverTimeStr/serverTime/openDays/mails/goodsList; chat lists if chat enabled | 40099ff,31786,16572,16977ff |

Empty collections may be shape-compatible but are not proof of historical
server defaults. Explicit source fallbacks handle optional rank leaders and
extra battle containers; do not fabricate progress. Time is milliseconds and
matching formatted local time: constructor replaces '-' with '/' before parsing
serverTimeStr and calculates an offset from serverTime (40106ff).

## Mandatory starter role

Entry calls genTeamData before opening home (31411ff); it builds role-screen
cache for every owned role (47589ff). Each role requires kindId,star,level,XP,
nextLevelExp,power,awakeLevel,awakeRateIncreaseTimes; skill/awakeSkill maps of
`{kindId,level}`; six evlItem slots `{kindId,level}`; initAttr/equipmentsAttr maps
for hp/atk/def/mdef/hit/dodge/crit and complete derived attr/growth. Wire idx comes
from stable team map key. Missing stone/artifact slots do not imply ownership.
References:56003ff,19727ff,46404ff,53476ff.

CREATE_PLAYER49500ff defines coin0,gem50,AP60,skill10,role100101. RoleData45463
lists basic attack100100,skills100101..100104,equipment30101..30601. SoulData54057
gives star1. Level1/XP0 matches preview46414ff and guide22364; experienceData20543
gives next XP25. Avatar fallback40054ff is1001/901, but home needs the object.

## Known unresolved policies and honest unavailable state

1. Home26158 reads shopItems[0/1] before level gating. Empty catalog throws.
   Normal goods require entityId,count,moneyId,price,isSaleOut,requireVip,shopType
   (52689ff). ShopData alone doesn't prove initial stock selection. Use real
   persisted offers or pinned unavailable-state guard, not fake goods.
2. Activity2101-2122 needs four card products by isMonthCard/isBigMonthCard/
   isYearCard/isWeekCard and reads show/price/gem/dailyGem even with no events.
   No dummy zero-price products. Guard absent paid catalogs explicitly.
3. Guide22243-22359 enters two-role recruitment after rename. Implement actual
   single-draw/once-only behavior; do not pregrant roles to skip it.
4. Owned-role skill initialization is not present as a constructor in recovered
   client. Unlock-color rules49768ff alone do not prove initial owned levels.
   RoleScene46465-46473 assumes owned skill IDs form a source-list prefix; a
   non-prefix subset duplicates/omits UI skills and must fail content validation.
5. Power formula49701ff exists; its second argument semantics remain unresolved.
   Starter preview grows floor-before-multiply (46420ff). Equipment preview
   level1 totals are hp661/atk100/def62/mdef62/crit48/dodge33. Do not reuse the
   differing historical compatibility candidate as source authority.
6. AP60 opening is not cap: source49554 yields level1 cap61. VIP0 adds5 to skill
   point max (59161); creation constant10 is not proof of final cap semantics.
7. Free draw/counter/task/open-day/guild/card-zero initialization requires a
   versioned new-service opening policy when source cannot establish it.
8. First-entry genTeamData47590 calls genFriendshipData55926. Friendship row7
   references classes55/63, but roleData lacks63. Every visible friendship must
   resolve role+entity metadata; an explicit hide policy can exclude the broken
   row through a referenced class. Do not auto-add an undocumented hidden class.

Keep these decisions visible; an unavailable feature guard is not completion
of that feature. Combat duplicates and drop125 semantics remain separate gates.

## PostgreSQL implementation boundary

Existing players currently stores identity/ownership/version only. Add typed
progression, first rename, avatar, content/rules pin, resource/recovery fields;
normalized owned role/skill/equipment and slot relations; map progress/attempts.
Use wallet/inventory ledger and creation receipt in the same transaction as
starter ownership. Project DTOs from those records. Server time, empty unavailable
collections and optional leaders are computed projections, not mutable assets.
Every initialization value must name a source reference or approved versioned
new rule before native createPlayer/entry is enabled.

## Implemented persistence boundary (2026-09-17)

Migration0014 and players/{creation,snapshots,stats}.py now implement these
normalized records and native compression. Creation binds account/server/release,
serializes absent-player creation and writes starter ownership and shared
currency reward/ledger/receipt/outbox in one transaction. Repeated create selects
existing state. Entry uses a consistent projection with fresh time; first rename
is persisted once, while later paid rename fails until durable action IDs exist.

Recovery source interval300000ms is applied on entry/reconnect under the player
lock. Capped credits and deadline changes are ledgered; no live push scheduler
is asserted. Snapshot now supplies nested map state and extra.chat with original
field names. Unavailable catalogs remain empty; staged NativeAvailability guards
are necessary for the original eager home consumers.

Activation still requires a published version containing native_player_content.
Preparation accepts only matching DRAFT and explicit policy keys:
`rules_id,origin,provenance,power_second_argument,skills,awake_skills,
skill_point_cap,hide_role_class_ids,opening_state,owned_attribute_rule,
recovery_policy,open_days`. Origin must explicitly identify owner-approved new
rules; a nonempty provenance string is a recorded assertion, not automatic
approval. No production policy values were supplied or published in this work.

Known policy variants implemented are unavailable-zero-v1 (honest unsupported
feature projections), source-preview-floor-growth-v1 (owned initial stats) and
source-300000ms-v1 (lazy recovery). The unresolved power argument, owned skill
levels, cap and visibility choices must be approved before real account creation
is enabled. TEST-only probe policy is not a source claim or deployable release.

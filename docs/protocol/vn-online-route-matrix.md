# VN online route and defect matrix

Evidence date: 2026-09-16. Scope: current worktree, not only HEAD `e1a2045`.
Review inputs: four owner screenshots, recovered request builders/consumers,
`server-compatible/src/game_server.py`, `game_state.py`, `game_rules.py`.

Static count at review: 225 unique `logic.*` request literals in the recovered
client versus 11 gameplay route literals handled by the runner. This is a
surface inventory, not a percentage of working gameplay: even implemented
routes are partial, and dynamic handshake/bootstrap calls need separate tracing.

## Findings, ordered by release risk

| ID | Severity | Evidence / cause | Required correction / proof |
| --- | --- | --- | --- |
| F01 | Release blocker | `game_state.py:73` has accounts, JSON player payloads and pending battles only. There is no normalized economy/claim/content/audit schema. | PostgreSQL migrations, import reconciliation, immutable ledgers, concurrent debit/claim tests; spec DB gate. |
| F02 | Release blocker | `end_smap` takes client `star` as settlement input, with no authoritative combat verification. | Versioned battle engine and server-verified result. Forged win must not issue rewards. |
| F03 | P1 | Screenshot shows `3873.0999999999999`. `game_rules.py:68` rounds each power but client `project.js:48975` exposes sums and `47952` renders them directly. Rounding the Python response alone cannot prevent JS sum artifacts. | Fixed-point calculation and one client display function for home/roster/team/rank; screenshot and fractional-sum regression. Exact server second-argument semantics remain a documented local policy until resolved. |
| F04 | P1 | `game_rules.py:24` allows only 10101-10106; `game_state.py:746` rejects other IDs. Owner sees invalid request on map continuation. | Full normal-map graph, attempts/reset/level/AP checks, deterministic content-backed rewards; play 10106 -> 10107 -> next chapter. The screenshot alone does not prove which guard rejected that request. |
| F05 | P1 | `award_recruit` returns only deterministic first Zoro/Nami; `coinTen`, `gemTen` absent from dispatch. | Free/paid single/ten draws, first-draw markers, counters, cooldown, guaranteed-draw rule resolution, duplicate conversion, persisted RNG outcome and replay. |
| F06 | P1 | Owner screenshot fails equipment LV1 -> LV2. `upgradeEquipment`, `upgradeEquipmentMax`, `upgradeAllEquipmentMax` builders exist (`55436`) but server dispatch omits them. | Debit exact cost + upgrade + stats + daily task progress + response delta in one transaction. |
| F07 | P1 | `friendHandler` routes (`21669`) all missing; only empty bootstrap friend fields exist. | Two real lab accounts, request/accept/reject/remove/gifts, cross-player locks, privacy, restart. |
| F08 | P1 | Daily task/achievement maps are empty; `receiveTaskAward`, `receiveTaskActiveAward` absent. | Import task requirements; progress from committed domain events; once-only rewards and daily/weekly reset. |
| F09 | P1 | Screenshot Beli purchase shows `undefined/1`. `buyCoinPanel` (`16133`) reads absent `vip.buyCoinTimes`; undefined+1 falls into max price fallback. `buyCoin` route also absent. | Always initialize counters and return server quote with version; spend gems, credit coin, increment counter atomically. Test first VIP0 purchase, insufficient gems, limit, midnight, retry. |
| F10 | P1 | `SUPPORTED_ROLE_IDS` contains four classes and white/green tiers. Green evolution additionally needs 49902, not obtainable in mapped normal stages. | Supported content manifest must have a reachable acquisition path for every required material and all visible role tiers/skills; no test-DB grant as gameplay proof. |
| F11 | P1 | `activity.map` empty; receive/update activity routes missing. Sign-in alone is not an event system. | Validated event definitions, schedule, qualification, claim history, admin preview/publish/rollback. |
| F12 | P1 | Session tokens are RAM-only (`game_state.py:69`); password digest is single salted SHA256 (`99`). No admin identity, rate limits, durable replay keys. | New auth/session/RBAC model; legacy hash upgraded on successful login; session revocation; internet release blocked until security gate. |
| F13 | P1 | Native bundle, manifest, backend rules and imported content have no enforced compatibility release ID. Tests previously accepted empty rewards and zero-power fixtures. | Release manifest and native smoke gates, request/content version trace, fresh tests proving user-visible behavior. |
| F14 | Process | README identifies older installed APK and focuses on tutorial; CHANGELOG did not exist before this handoff. | README+CHANGELOG change in every deliverable commit, post-commit audit; current runbook linked from AGENTS.md. |

No new APK interactions or live account mutations are performed for this review.
HTTP 200 bootstrap logs are not evidence that a gameplay route succeeds.

## Route groups

All rows below are **static-observed** unless explicit new native evidence is
attached. `lab-partial` is not a production coverage claim. Field names retain
the APK spelling (`teamIndexs`, `bagIndexs`). `_temp` values are transient UI data;
the matching bag/team/wallet changes must also persist.

| Client routes | Request fields | Response consumer / state | Current state | Target milestone |
| --- | --- | --- | --- | --- |
| `gate.gateHandler.queryEntry`; `connector.entryHandler.entry` | uid; token/serverId/oldServerId | host/port; session owner | lab-partial | M2 |
| `connector.playerHandler.getPlayers/createPlayer/entry` | empty; name; playerId/isReconnect | compressed player snapshot, stable IDs | lab-partial | M2 |
| `logic.playerHandler.rename/setPhotoImg/setShipImg/setTitleImg` | name; imgId | profile + currency/cost if any | first rename only | M2/M3 |
| `logic.playerHandler.buyCoin/buyActionPoint/buySkillPoint` | empty | wallet, AP/skill point, vip counters; buyCoin `_temp.costGem/getCoin/ratio` (`16118`) | missing | M3 |
| `logic.teamHandler.upgradeEquipment/upgradeEquipmentMax` | teamIndex/equipmentType | complete role, coin, item attrs; `eqptScene:19678` | missing | M4 |
| `logic.teamHandler.upgradeAllEquipmentMax` | teamIndex | all six slots, coin, complete role | missing | M4 |
| `logic.teamHandler.evolveEquipment/evolveRole` | teamIndex/equipmentType; teamIndex | equipment attrs; `_temp.preRole`, full updated role | green only | M4 |
| `logic.teamHandler.upgradeRoleSkill/upgradeRoleStar/roleBreak` | teamIndex/skillKindId; teamIndex; teamIndex/bagIndexs | skill levels, consumed points/materials, stats | missing | M4 |
| `logic.teamHandler.useExpItem/useExpItemMax` | teamIndex/bagIndex/itemCount; teamIndex | bag tombstones + role/XP/power | explicit EXP item partial, max missing | M4 |
| `logic.teamHandler.equipStone/unEquipStone/equipArtifact/unEquipArtifact` and All variants | inspect complete builder per variant (`55506`) | slots, inventory ownership, stats | missing | M4 extension gate |
| `logic.bagHandler.sell/composeItem/composeRole` | bagIndexs/itemCounts; kindId/isAll; classId | inventory, coin, new role, rewards | sell partial | M3/M4/M5 |
| `logic.playerHandler.useItem` | bagIndex/itemCount | `_temp.entityCountMap`, bag deltas/AP | AP + fixed material boxes only | M3 |
| `logic.pointHandler.coin/coinTen/gem/gemTen` | empty | `_temp.dropList`, team/bag, point counters, wallet | two tutorial recruits only | M5 |
| `logic.smapHandler.beginSmap/endSmap` | smapId/teamIndexs; star/teamIndexs | AP, preview, report, role XP, star/times map, bag reward | six stages; client-reported win | M6 |
| `logic.smapHandler.skip/resetSmapTimes/receiveBmapAward` | smapId/times; smapId; mapId/star | rewards list, counters, gem/tickets, chapter claims | missing | M6 |
| `logic.playerHandler.signIn` | empty | signInDays/time, bag/team, `_temp.entityCountMap` | lab-partial | M7 |
| `logic.playerHandler.receiveTaskAward/receiveTaskActiveAward` | taskId; type/point | task subtree, activity points, rewards | missing | M7 |
| `logic.playerHandler.receiveActivityAward/updateFreeActivity/activitySaveGem` | activityName/rewardIdx; activityName | activity map/reach/status, wallet, rewards | missing | M8 |
| `logic.friendHandler.myFriendList/recommendList/requestAddFriendList` | empty | `_temp` list shapes must be mapped from callbacks | missing | M7 |
| `logic.friendHandler.findTarget` | content | search result; no account secrets | missing | M7 |
| `logic.friendHandler.requestAddFriend/acceptAddFriend/refuseAddFriend/removeFriend/giveGift/receiveGift` | targetId | shared relationship/gift state | missing | M7 |
| `logic.friendHandler.giveGiftAll/receiveGiftAll` | empty | bounded batch results, AP/counters | missing | M7 |
| `logic.mailHandler.list/read/receive/removeAllRead/unReadCount` | builder-specific mail id/list (map before implementation) | mail list/count/status, rewards | missing | M7/M8 |
| `logic.playerHandler.topUpGoodsList/useGiftCode`; `logic.mailHandler.useGiftCode` | empty; giftCode | catalog/order state, claim result | missing | M9 |
| `logic.shopHandler.buy/refresh` | inspect builder (`52511`, `52504`) | wallet/bag, goodsMap and refresh counter | bootstrap goods only | M3 |
| `logic.gmHandler.addItem/addRole/removeRole` | visible builder arguments | never enabled on player gateway | denied | M2 security |

### Full inventory rule

M0 extracts every `a.request("logic...` / `connector...` / `gate...` builder,
groups by route, and records source hash/line, request keys, complete response
read-set, auth, side effects, error states and tests. The table above is a
prioritized review, not a claim that all discovered routes were specified.

Every route receives a tier: `CORE`, `EXPANSION`, `DENIED_ADMIN_ONLY`, or
`BLOCKED_EVIDENCE`. Missing gameplay evidence is a bounded recovery task with
an owner, exact symbol and capture/test needed; it is not a reason to invent
loot or mark the entire project blocked.

### Source of truth rule

For each numeric rule record `apk-static`, `native-observed`, or
`owner-approved-new-rule`. In particular, `specifyDropValues=125` cannot be
silently interpreted as 125 items; the gem guarantee counter (`gemTimes % 10`
in UI versus named constant EVERY_7) requires explicit conflict resolution.
Game-specific rules absent from the APK may be designed as new server rules,
versioned and approved, rather than pretending to recover the original backend.

### Acceptance fixture for the reported bugs

Use an isolated copy of the owner state and a fresh player. Preserve actual
values in a private fixture, strip login/session identifiers, and attach a
sanitized counterpart for CI. The visible checks are:

```text
home_power: "3873" (integer UI, no fractional tail or NaN)
team_power: same formatting policy on sum, not only role rows
map: 10106 win -> 10107 selectable -> next chapter unlocked by content
equipment: level1 -> level2; all six level1 -> level4 costs 2160
equipment_single_max: level1 -> level4 costs 360 (110 + 120 + 130)
buy_beli: counter "0/1" at VIP0, first cost 10 (not undefined -> 200)
recruit: second legitimate request is a new draw, retry is same draw
friends: account A requests B; B accepts; both lists agree after restart
daily_task: equipment upgrade increments progress once; reward claim once
```

Numbers above are screenshot/static fixture expectations, not completed tests.
For Beli RNG/amount assert the server quote/outcome and ledger, not a guessed
literal amount; the screenshot's 86509 is the invalid-price preview.

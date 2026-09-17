# Native-client-first online slice

Status: owner-directed execution spec, 2026-09-17.

The owner's request to write this set and immediately implement approves this
direction; do not introduce a second approval loop for the same local work.
This is the active native delivery spec. Existing 2026-09-16 normalized database,
ledger, admin, finance and security requirements remain binding for later slices.

## Goal

Run the recovered APK against PostgreSQL through the exact native contracts in
`project.js`, then make one real first-chapter continuation (`10106 -> 10107`)
work in the APK. Compatibility SQLite runner output, synthetic `/v1` clients and
unit-only success are not acceptance.

## Source contract

The immutable recovered client is the authority for wire shape:

- `project.js:51711-51734`: form `/user/register`, `/user/login`, `/user/serverInfo`.
- `project.js:53945-54006`: Pomelo gate `gate.gateHandler.queryEntry`, then
  connector `connector.entryHandler.entry`; handshake sys is
  `{type:"js-websocket",version:"0.0.1",rsa:{},protoVersion:0}`.
- `project.js:39869-39896`: `getPlayers`, `createPlayer`, `entry` consumer.
- `project.js:53521-53535`: `smapHandler.beginSmap/endSmap` payloads.
- `project.js:48285-48345` and `12275-12325`: battle scene builds the local
  presentation team, sends only stage/team and later reports client star. The
  server must verify the battle, not trust that star.

No source bundle execution on the server, no rewritten `project.js`, and no
history/provider endpoint contact.

Pinned APK SHA256 `d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4`;
pinned project SHA256 `9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.

## Native auth and player-entry details

Register sends `name,password,from,channel,accountId`; the last three are client
metadata, never authorization. Login sends `name,password`, consumes `uid,token`,
and branches on code500/503/504. ServerInfo sends only `userName`, so public
server list can be returned but player details must not leak through that name.
Use real OPEN/PUBLISHED server rows and an explicit empty/maintenance state.
The original server-info callback lacks an empty-list guard; stage a narrow
guard if needed rather than inventing an available server.

Gate uid is a routing hint. Connector token authenticates; `serverId` and
`oldServerId` must map to an authorized real server. The current schema has no
merged server mapping, so require equality. Revalidate account/session and pinned
release after waits and reconnects. Reject every GM route.

Native heartbeat policy is server-authored: negotiate3seconds and send the first
HEARTBEAT after HANDSHAKE_ACK; the recovered client40721ff starts its heartbeat
timer only on receiving that first package. Reuse bounded10-second reads;
heartbeat0 with idle timeout would disconnect normal users reading a screen.
Inventory-only listener semantics remain separate and unchanged.

GetPlayers reads one owned player per server (database uniqueness already exists).
Create/entry return `{player:<compressed native JSON>}` through the existing
socket decoder. `Player` immediately constructs bag/team, reads vip.level and
extra.serverTimeStr/serverTime (source40090ff); every further first-home consumer
must have a source-cited field contract before enabling entry.

Starter state is source-backed: CREATE_PLAYER49498ff declares coin0, gem50,
AP60, skill points10 and role100101. Store actual owned role/equipment/skills,
wallet postings and creation receipt atomically; these are account-start rules,
not disposable test grants. IDs exceed10000 and stay JS-safe. A repeated create
for the same authenticated account/server returns the same owned player without
duplicating starter assets. Name/rename, level/XP, power and per-day state are
typed fields/projections, not an unrestricted JSON blob copied from SQLite.

## Battle authority and content decisions

The real client seeds SMAP with Date.now (battleMain11615ff), simulates waves and
sends only `{star,teamIndexs}` on endSmap. Server authority therefore requires a
reviewed staged patch carrying a server-issued battle ID/seed and ordered manual
skill inputs. Reusing that unmodified client star as truth is not acceptable.
Keep visual/action modules; port or isolate only reviewed deterministic battle
logic, never run the full recovered application or replace combat with auto-win.

DataApi18445ff overwrites duplicate rows on the client. This establishes client
lookup behavior, not historical backend intent. Preserve both rows and record a
versioned explicit decision before normalizing duplicates for a server battle.
Raw specifyDropValues125 is not an item quantity. Until its selection semantics
are established or a new rule is explicitly approved, no invented drop grants.

## First-slice milestones and whole-game continuation

1. Native form/handshake/owned getPlayers with real PostgreSQL authentication.
2. Complete persisted starter/create/entry/home/rename through original scenes.
3. Source-backed tutorial single recruitment required by the original guide,
   then content release, battle/action bridge, 10106->10107->chapter2.
4. Equipment/role upgrades and organically reachable resources, Beli/AP/skills.
5. Remaining single/ten recruitment, social/task/sign-in/mail and event flows.
6. Admin operations, sandbox finance, all remaining visible modes, then online
   operational/load/restore acceptance from the retained broader design.

Each item needs independent native evidence. Completing item1 does not imply
item2; getting to home does not imply item3. No date/percentage is inferred from
route inventory or automated test counts.

## Architecture

`server-online` owns a native adapter: form auth -> durable PostgreSQL session ->
gate lookup -> connector binding -> typed player snapshot. The connector owns
only authenticated player scope; unsupported mutations return native `code:500`
with fixed messages until their authoritative service exists. The battle slice
uses imported published normal-map content and a versioned server report; its
reward uses the existing ledger/receipt/outbox path.

The compatibility runner is retired from this slice. `/v1` bootstrap and
inventory-only handshake remain diagnostics for server development, not native
client acceptance or fallback.

## Safety and acceptance

- PostgreSQL is the only mutable game source. No SQLite dual-write or test grants.
- Native listeners bind loopback in the isolated lab; no public deployment.
- Auth/session errors are fixed and sanitized; GM routes are denied.
- Native acceptance requires a real APK: register/login, server selection,
  player list/create/entry, map 10106 continuation to 10107, authoritative win,
  reward visible, relog persistence. Each step records wire trace plus screenshot.
- A route is not marked delivered if the APK falls back, displays `undefined`,
  or only a seeded service test passes.
- Combat duplicate definitions `skill1105010` and `buff10006` stay blocked until
  an explicit versioned resolution is recorded; no silent last-wins server rule.

Recorded2026-09-17 resolution: optional `vn-data-api-observed-lookup-v1` reproduces
the exact native dataApi18445ff row-order overwrite for only the two fingerprinted
pairs. Defaults still reject ambiguity, both source rows remain archived, new
conflicts fail. See vn-native-battle-authority.md. This is explicit client-parity
semantics, not a claim to historical backend intent or item-drop approval.

## Non-goals for this slice

Friends, equipment, shop, tasks, recruitment ten-draw, admin/payment and later
chapters are not declared complete by 10107. They follow separate native slices.

## First-home consumer prerequisites

Guide22364 directly reads team.roles['1']; guide22582 reads
smapStarMap['1']['101']; mainTask31909 reads task.main['1']. QuickNode42504
eagerly calls dailyTask/achievement builders, so required task containers and
claim counters must exist even before rewards are implemented.

Home26158 eagerly dereferences two normal-shop items. Activity2101-2122 eagerly
reads four paid-card catalog rows. Provide real validated catalog entries, or
explicit unavailable-UI guards for unsupported catalogs; never invent sale
prices/rewards. The first rename triggers guide point2Role22243-22359; tutorial
single recruitment is a predecessor to the native battle path, not a milestone
that can be postponed until after10107. No extra roles are pregranted to skip it.

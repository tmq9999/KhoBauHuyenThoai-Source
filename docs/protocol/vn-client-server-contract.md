# VN client/server contract (static-inferred)

This contract records only fields and routes observed in the recovered APK.
`runtime_confirmed` is false for every item: no APK runtime, endpoint, or
network trace was used. Values not present in static evidence remain UNKNOWN.

## HTTP bootstrap

The static client posts `application/x-www-form-urlencoded` and JSON-parses a
non-empty HTTP 200 response. The probe returns HTTP 200 with application
`{"code":500,"msg":"Chưa hỗ trợ route trong probe local","probeStatus":"UNKNOWN"}`
for known paths because response schemas are not known. Submitted values are
never reflected.

| Route | Request fields | Response/runtime value |
| --- | --- | --- |
| `POST /user/register` | `name`, `password`, `from`, `channel`, `accountId` | UNKNOWN; probe HTTP 200/application 500 |
| `POST /user/login` | `name`, `password` | UNKNOWN; probe HTTP 200/application 500 |
| `POST /user/serverInfo` | `userName` | UNKNOWN; probe HTTP 200/application 500 |
| `POST /sdk/verifyToken` | `sdkName`, caller-supplied token fields | UNKNOWN; probe HTTP 200/application 500 |

## Pomelo transport

WebSocket URL is `ws://<host>[:<port>]`, binary type `arraybuffer`. Every
package is `type:1 byte`, `length:uint24 big-endian`, then `body:length`.

Package types: `HANDSHAKE=1`, `HANDSHAKE_ACK=2`, `HEARTBEAT=3`, `DATA=4`,
`KICK=5`. DATA message types are `REQUEST=0`, `NOTIFY=1`, `RESPONSE=2`,
`PUSH=3`; the message flag is followed by a varint request/response ID where
applicable, then a one-byte-length UTF-8 route (or compressed uint16 route),
then payload bytes. Payloads fall back to JSON UTF-8 when no protobuf schema is
available.

## Handshake and bootstrap routes

Client handshake statically includes `sys.type=js-websocket`, `sys.version=0.0.1`,
`sys.protoVersion`, optional RSA metadata, and configured `user`. A server code
200 causes a HANDSHAKE_ACK; code 501 is a client-version error. The client
consumes `sys.heartbeat`, `sys.dict`, `sys.protos`, and `user`; exact values are
UNKNOWN in the APK report.

After gate login, the observed sequence is:

1. `gate.gateHandler.queryEntry` with `{uid}`
2. `connector.entryHandler.entry` with `{token,serverId,oldServerId}`
3. `connector.playerHandler.getPlayers` with `{}`
4. If empty, `connector.playerHandler.createPlayer` with `{name}`
5. Otherwise `connector.playerHandler.entry` with `{playerId,isReconnect}`

Route response schemas, user/token values, connector addresses, heartbeat
number, dictionary, protobuf tables, and encoded player payloads are UNKNOWN.
The local probe advertises heartbeat `0` (disabled policy), never fabricates a
positive interval, and never fabricates success or player data.

## Local game-entry compatibility slice

The loopback `game_server.py` implements a bounded lab slice used by the
recovered client. These routes are statically observed in `project.js`; the
state changes below are local compatibility policy, not a claim about the
historical provider backend.

| Route | Request | Local state change |
| --- | --- | --- |
| `logic.pointHandler.coin` / `gem` | `{}` | deterministic tutorial recruit, idempotent |
| `logic.smapHandler.beginSmap` | `smapId`, `teamIndexs` | debits AP and opens a pending battle |
| `logic.smapHandler.endSmap` | `star`, `teamIndexs` | settles attempt, AP/coin/EXP/role-EXP and material drop |
| `logic.playerHandler.signIn` | `{}` | one sign-in per Vietnam calendar day, APK `signInData` rows |
| `logic.playerHandler.useItem` | `bagIndex`, `itemCount` | consumes AP/box item and returns bag delta/rewards |
| `logic.bagHandler.sell` | `bagIndexs`, `itemCounts` | consumes sellable stacks and credits coin |
| `logic.teamHandler.useExpItem` | `teamIndex`, `bagIndex`, `itemCount` | consumes role-EXP item and updates teammate stats |
| `logic.teamHandler.evolveEquipment` | `teamIndex`, `equipmentType` | consumes first green-tier materials and updates equipment |
| `logic.teamHandler.evolveRole` | `teamIndex` | requires six green-tier equipment items, returns `preRole` |

All local mutations are SQLite transactions scoped to the authenticated,
selected player. Unmapped activity, shop, task, multiplayer and later-tier
routes remain `500` until their APK consumer fields and reward rules are
recovered. Repack/sign success and this compatibility slice do not prove
historical server compatibility or full-game parity.

See [feature slice evidence and limits](../release/2026-09-15-server-feature-slice.md)
for source-line references, local policy choices, missing material sources,
and the distinction between loopback tests and native-client verification.

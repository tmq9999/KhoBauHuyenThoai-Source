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

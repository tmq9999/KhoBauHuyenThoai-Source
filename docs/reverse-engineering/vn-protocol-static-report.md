# VN protocol static extraction (recovered JS)

Source: `work/apk-vn/20260914T140500Z-efc5da6a/recovered-js/project.js` (SHA-256 `9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`, 5,586,139 chars). All findings below are static-inferred; no runtime/network confirmation was performed. Hostnames, credentials, tokens, and key material are intentionally omitted.

## Bootstrap and login

`serverMain` (line 51648) exposes HTTP POST form requests for `/user/register` (`name,password,from,channel,accountId`), `/user/login` (`name,password`) and `/user/serverInfo` (`userName`). `sdkApi.verifyToken` (line 47696) calls `/sdk/verifyToken` with `sdkName` plus caller-supplied token fields. The generic `http.request` helper (line 26230) uses POST `application/x-www-form-urlencoded`, GET for config, JSON-parses non-empty 200 responses, and has a 50-second timeout.

`clientConfig` (line 17034) contains client-side constants; runtime `client_config.json` is fetched by `logoScene` and can override URL/static/gate settings through `aliasUrl` (line 31517). The VN `buildExt.init` block (line 16020) selects the VN deployment at startup. `serverConfig` (line 49298) is gameplay/schema-side constants and helper logic; no wire endpoint is defined there.

After login, `socket.connect` (line 53911) first opens the gate and requests `gate.gateHandler.queryEntry` with `{uid}` (line 53958). It disconnects the gate, then opens the returned connector and requests `connector.entryHandler.entry` with `{token,serverId,oldServerId}` (line 53980). The login scene then calls `connector.playerHandler.getPlayers` (line 39872); if empty, `createPlayer({name})` (line 39877), otherwise `entry({playerId,isReconnect})` (line 39884).

## WebSocket/Pomelo framing

`pomeloClient` (line 40547) constructs `ws://<host>[:<port>]`, sets `binaryType=arraybuffer`, and sends a 4-byte package frame: one type byte followed by a 24-bit big-endian body length and body. Package types are HANDSHAKE=1, HANDSHAKE_ACK=2, HEARTBEAT=3, DATA=4, KICK=5 (protocol line 42151).

DATA messages use Pomelo message types REQUEST=0, NOTIFY=1, RESPONSE=2, PUSH=3. The message header carries a flag, request/response id as a varint, and either a numeric uint16 route (compressed) or a one-byte-length UTF-8 route; the remaining bytes are payload. Request IDs increment from 1; responses dispatch the stored callback, while notify/push dispatch by route. `socket` serializes requests in a queue and invokes callbacks only for non-FAIL responses.

## Handshake, heartbeat, schema compression

The client handshake JSON includes `sys.type=js-websocket`, `sys.version=0.0.1`, `sys.protoVersion`, optional RSA metadata when encryption is enabled, and configured `user`. A server handshake code 200 triggers schema setup and HANDSHAKE_ACK; 501 is a client-version error. Server `sys.heartbeat` is converted to a millisecond interval; timeout is two intervals, after which the client emits `heartbeat timeout` and disconnects.

Server `sys.dict` supplies route-string to numeric-id compression (with a reverse map for decoding). `sys.protos.server` and `.client` are cached under local-storage key `protos` and initialize protobuf decoder/encoder tables. Payloads fall back to JSON UTF-8 when no schema is available. Selected player fields (`player` on connector entry/createPlayer, and `_temp._decodeKeys` values) are base64+zip decoded by `socket.decodeData`; `onSyncZip` and selected push events receive the same treatment.

## Response consumers and next-server-step contract

`connector.playerHandler.entry` and `createPlayer` responses feed login/player initialization; `serverMain.sync` consumes `onSync`/`onSyncZip` updates to mutate player state. Generic response handling exposes `code`, `msg`, `_temp`, and route-specific fields to callbacks. This is sufficient to implement a protocol probe for gate → connector → player bootstrap, but route schemas and heartbeat values must be obtained from a live or captured handshake; this report provides no runtime-confirmed values.

See [`protocol-markers.json`](../../work/apk-vn/20260914T140500Z-efc5da6a/protocol-markers.json) for machine-readable offsets and route/field markers.

# Pomelo protocol probe (VN native-recovery milestone)

This is a deterministic, standard-library-only protocol probe derived from
static APK evidence. It is not a production game server and has no endpoint,
credential, schema, or runtime compatibility claim.

## Run

```powershell
python server-compatible/src/probe_server.py --host 127.0.0.1 --port 3010
```

The WebSocket listener accepts an unfragmented RFC6455 subset of binary frames
carrying Pomelo package frames. It responds to `HANDSHAKE` with code `200`,
advertises an empty route dictionary/protobuf schema and `sys.heartbeat: 0`
(heartbeat disabled by local probe policy), echoes heartbeat package frames,
and returns an application `code: 500` (`probeStatus: UNKNOWN`) response for
every REQUEST route.

The optional HTTP probe can be started from Python after adding
`server-compatible/src` to `sys.path`:

```python
from probe_server import ProbeHTTPServer
server = ProbeHTTPServer.start_in_thread()
```

`/user/register`, `/user/login`, `/user/serverInfo`, and `/sdk/verifyToken`
return HTTP 200 with application `code: 500`, Vietnamese unsupported-route
message, and redacted parsed form-field names. Unknown paths return `404`.
Request bodies are limited to 64 KiB and form content type; the server binds
loopback only.

## Tests

```powershell
python -m pytest server-compatible/tests/protocol
```

No dependencies beyond Python 3.11+ standard library are required at runtime.

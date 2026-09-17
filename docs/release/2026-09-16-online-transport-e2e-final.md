# Transport + client bridge final scoped checkpoint

Task1/Task2 verified:
`Node ES5 bridge -> WebSocket/Pomelo -> negotiated InventoryConnection -> PostgreSQL receipts/ledger/rewards`.

- Node bridge unit: 11 passed.
- Transport + real Node/PostgreSQL E2E: 10 passed in 4.34s.
- Task1 fix suite: 9 passed in 4.63s.
- Full backend before final bridge-only changes: 344 passed; recovery/protocol
  378 passed, 4 Windows symlink skips. Compileall, pip check and diff checks pass.

E2E proves dropped-response replay, conflict/resync, two-account rejection,
receipts/rewards/events, ledger invariants and final JS bag state. Credentials
enter Node via stdin only and are redacted. Test boxes/content are explicit
fixtures. Review fixes addressed handshake exception leakage, canonical WS
lengths and unreachable version-gap resync; final scoped reviews PASS.

Minor caveats: fail-closed invalid/foreign handshakes may close before an exact
application error envelope; Host is presence-checked but listener is loopback
bound. These do not claim historical Pomelo or native compatibility.

Remaining: full player bootstrap/account creation, native APK runtime, legacy
bag migration, project.js bridge wiring, organic box acquisition, combined
release publication and production security. No APK action, live state mutation,
commit or push.

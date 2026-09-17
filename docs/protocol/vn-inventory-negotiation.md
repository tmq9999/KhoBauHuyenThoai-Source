# Inventory negotiation contract — 2026-09-16

This is an explicitly new bounded online protocol, not a recovered historical
Pomelo handshake. It wraps the source-backed native inventory DTO adapter.

One `InventoryConnection` belongs to one transport connection. It starts unbound.
`negotiate(token, hello)` clears previous identity first, validates the session,
parses the strict hello, obtains an owned/current-release bag snapshot, rechecks
the session, then binds identity/player/server/content. Failure remains unbound.
`close()` clears token and selection; reconnect creates a new binding.

Hello has exactly protocolVersion1, a bounded unique string capability list
containing native-inventory-v1, playerId, serverId and UUID contentVersionId.
No account identity or grants are accepted from the body. Unknown offered
capabilities are not granted; only logic.playerHandler.useItem is advertised.
Response explicitly says fullPlayerSnapshot=false and snapshotMode=replace-bag.

Execute revalidates session and requires the durable command envelope's scope
to match the selected player/server/release. Its command_id, expected_version
and payload are forwarded unchanged. An old committed request can replay even
after resync reports a newer aggregate version. A new stale request conflicts.
The client must not generate a fresh action merely because a response was lost.

Resync gets a consistent bag-only snapshot and rechecks session afterward. It
must replace prior bag state, not merge the whole snapshot. Delta responses from
commands still use bag tombstones. Full player fields, server/client response
ordering and negotiation over actual Pomelo sockets remain unimplemented.

Methods on one object serialize through a lock. Close waits for an operation
already admitted on that connection; it does not tear a database transaction
in half. Session revoke/expiry/rotation blocks subsequent admissions and snapshot
release after invalidation. It is not atomic cancellation of an already admitted
command: concurrent revoke after its check may allow that in-flight command to
finish. Public deployment requires the remaining auth/account-ban/security gates.

Tests use real session rows, isolated PostgreSQL content and test opening boxes.
They cover failed renegotiation, cross-account selection, scope switching,
revocation/rotation/expiry, snapshot-time revocation, reconnect replay, stale
commands and concurrent close. No token is in response/repr or subprocess args.
Private in-memory binding retains token only until close; transports must close
objects on disconnect and must not log request credentials/object internals.

No listener/default route/port/DB schema/APK patch was added. This contract
supports later gateway implementation without fabricating player bootstrap.

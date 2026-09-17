# Negotiated inventory connection checkpoint

Added per-connection negotiation, authenticated selection/scope pinning,
session revalidation, reconnect receipt replay and replacement-bag resync.
This is a bounded server-side state machine, not a network listener/Pomelo
handshake or full native player bootstrap. No default route was enabled.

Tests:22 RED before implementation then22 GREEN; expanded28 scoped tests passed
17.29s. Full backend344 passed179.53s before the last two test-only cases were
included; final scoped run covers them. Recovery/protocol378 passed,4 symlink
skips113.94s. compileall/pip/diff checks passed; source unchanged.

Coverage includes expired/revoked/rotated tokens, failed renegotiation clearing
old identity, foreign selection/scope switching, stale commands, reconnect replay,
revocation during negotiate/resync and close serialization. Independent review
reported no Critical/Important issues; its suggested coverage was added.

No token in output/repr; private token memory cleared by close. Already admitted
commands may finish across a concurrent external revoke; no atomic cancellation
claim. Transport must own/close one instance per connection. Tests use disposable
kbht_test schemas and explicit opening-box fixtures, not gameplay acquisition.

Work uncommitted, no push/migration/native action/live state mutation. Next:
actual transport/client version-order queue, full player snapshot and release
integration. [Contract](../protocol/vn-inventory-negotiation.md).

# Fixed material-box transaction checkpoint

Status: SERVICE_TESTED and authenticated HTTP transport-tested core command;
not Pomelo/native accepted or a complete M3 acquisition loop.

Delivered:
- Migration0012 fixed_box_definitions/rewards with published immutability/FKs.
- Source-hash-checked fragment-only fixed recipe staging into existing DRAFT.
- Owned stack consumption plus reward grant/ledger/receipt/outbox in one TX.
- Versioned core response with inventory tombstones, bounded quantities and
  explicit rejection of random/unsupported boxes and client-supplied rewards.
- Least-privilege runtime SELECT-only recipe access; no public default route.

Box321 yields twelve fragments x1 and49902 x6 per box. Source recipe, owner,
count, version and content validation precede mutation. A consumed stack cannot
be retried as a second grant with the same command ID; changed/stale input fails.
Failure at a reward insert or capacity check rolls back prior box/reward writes.

Verification:
- Staging tests failed before staging code;13 handler tests failed after staging
  and before command implementation;19 then22 passed with ACL/HTTP additions.
- Runtime test observed permission denial before adding SELECT grants.
- Full backend295 passed166.55s, including28 fixed-box tests.
- Recovery/protocol378 passed,4 Windows symlink skips95.68s.
- Extra event assertions after full run: targeted crash/capacity3 passed4.15s.
- compileall/pip/diff checks pass; APK and source hashes unchanged.
- Scoped implementation and crash-test reviews: no Critical/Important findings.

Tests use controlled test content/publication and ledger-backed opening boxes,
not live grants. Child probes enforce generated schema and kbht_test, terminate
only themselves before/after commit, then retry the same command. No actual
server was killed; no production crash/recovery claim.

Default serve does not register inventory.useFixedBox. Native bagIndex mapping,
_temp response serialization, release policy/stack caps and obtaining the box
remain pending. No APK action, live/player/SQLite change, development migration,
commit or push. See [protocol boundary](../protocol/vn-fixed-box-service.md).

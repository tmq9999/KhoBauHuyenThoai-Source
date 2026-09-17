# Transport + client bridge E2E checkpoint

Task1 transport and Task2 bridge now run through a real loopback socket and
isolated PostgreSQL schema. The bounded slice is not a full online game or
native APK acceptance.

Task1 `serve-inventory` is opt-in, loopback-only, port21002 default, no migration
or seed. It copies the recovered Pomelo framing codec locally and rejects
noncanonical RFC WebSocket lengths, malformed strict JSON, unsafe frames,
non-loopback origins and unsupported routes. DB work is bounded and drains on
disconnect; unexpected lifecycle errors are sanitized.

Task2 `inventory-bridge.js` is standalone ES5-safe. Node tests:11 passed. It
handles handshake/ACK, credentials only in handshake body, bounded queue,
one in-flight mutation, exact action envelope retry, stale/conflict resync,
replacement snapshots, tombstones, callbacks and cleanup. It is not staged into
the recovered APK.

Real E2E: `test_inventory_bridge_e2e.py` launches Node with stdin-only token and
the real Task1 listener on port0. Final fresh evidence: Pomelo transport + E2E
10 passed in5.09s. It covers dropped response/reconnect replay, two live clients,
CONFLICT/resync, invalid/foreign auth, 4 receipts/rewards/events, inventory
ledger and `check_invariants()`, with no fifth stale receipt. Child timeout kills
only Node; diagnostics redact token. Test boxes are explicit opening fixtures.

Task1 re-review addressed both Important findings (handshake exception leakage,
nonminimal frame lengths); fresh transport suite9 passed4.63s. Native device
inventory was empty; no APK install/launch. Firewall outbound block rules were
enabled. Full player bootstrap, Pomelo gate/connector, organic acquisition,
legacy bag migration and native smoke remain required.

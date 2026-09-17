# Native inventory adapter checkpoint

Status: PostgreSQL/service and authenticated HTTP tests passed; no native APK
runtime or complete Pomelo/session/bootstrap acceptance.

Added opt-in NativeInventoryAdapter with capability/native route validation,
canonical string bag IDs for new PostgreSQL inventories, owned fixed-box command
translation and receipt-saved `{bag.items, _temp.entityCountMap, _temp.route}`.
Bag snapshot has owner/server/active content checks and consistent versioning.
Zero stacks omitted from snapshots, tombstones retained in deltas. Unsupported
metadata is rejected rather than silently flattened.

Verification:
- Initial19 tests RED before adapter, then19/22 GREEN as coverage expanded.
- Full backend317 passed155.28s and recovery378 passed,4 symlink skips107.30s.
- Full runs preceded final _temp.route fix and concurrency test; final native
  inventory integration23 passed12.40s covers these changes.
- _temp.route regression failed with KeyError before the field was added.
- compileall/pip check/diff check pass. Pinned project.js unchanged.
- Independent scoped review found no must-fix findings; its _temp.route note
  addressed. No reviewer native runtime claim.

No new schema migration, default listener route, APK patch/action, legacy bag
conversion or organic acquisition path. Work uncommitted; no push or live state
changes. Tests only touch generated kbht_test schemas. The test maximum-ID and
mixed-content records are explicit boundary fixtures, not acquisition evidence.

Next: connection negotiation, client version-order/reconnect queue and complete
player snapshots. Full bag snapshots must replace prior bag state; deltas merge.
See [contract/evidence](../protocol/vn-native-inventory-adapter.md).

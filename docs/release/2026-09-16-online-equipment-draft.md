# Equipment-only DRAFT checkpoint

Status: content service-tested; M1.2/M4 and native acceptance still incomplete.

Delivered `content/equipment.py`, `equipment_store.py`, additive migration
`0011_equipment_content`, `prepare-equipment` CLI and two test files. The draft
has120 definitions,342 ingredient rows, raw source snapshot and linked entity
metadata. Costs come from the target tier. Six terminal zero IDs remain in raw
source and become null only in relational next-tier pointers.

Validation rejects bad IDs/types/counts/effects, duplicate ingredients, missing
references and cycles. Persistence tests cover exact replay after reconnect,
concurrency, rollback, altered/missing projections and published-row guards.
No game-server activation, inventory grant or upgrade handler is supplied.

Verification:
- Pure equipment tests:21 passed after RED.
- PostgreSQL equipment tests:10 passed after RED.
- Full server:262 passed in112.08s.
- Full recovery/protocol:347 passed,4 Windows symlink skips in96.48s.
- compileall, pip check, CLI help and git diff --check passed.
- Independent scoped review: no Critical/Important findings.

Comparator ZIP/hash inspection found a different bundle layout; combat duplicate
policy remains unresolved. See [source evidence](../protocol/vn-equipment-content.md).
No native runtime evidence was created. Pinned source hash remains unchanged.
No commit/push, development/production migration, SQLite change or APK action.

Next: material acquisition/drop semantics and combined release validation,
alongside comparator loader evidence for ambiguous combat definitions.

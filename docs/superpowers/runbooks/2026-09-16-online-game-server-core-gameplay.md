# Codex Runbook — Online Server Core Gameplay Recovery

Date: 2026-09-16
Status: IN_PROGRESS

## Objective

Replace the compatibility-only SQLite runner with the authoritative PostgreSQL
server path while closing the native-client defects: integer power display,
recruitment, friends, equipment/role progression, and normal maps 10107+.

## Rules

- `server-online/` is the production-source target; `server-compatible/` remains
  a lab evidence runner and is not extended as the online server.
- APK `D61D4AE1994EC5BCAFDCFAF2406CC88ED9611CBB65DA853027799D50D6687EB4` and
  recovered `project.js` remain immutable evidence.
- No client-reported battle result is authoritative. Every reward is an atomic
  PostgreSQL command with wallet/inventory ledger, receipt and outbox event.
- Every route needs RED tests, implementation, protocol translation and native
  smoke evidence. Unit tests alone never mark a route complete.
- Update `README.md` and `CHANGELOG.md` for every deliverable.

## Current evidence

- Native client boots on `emulator-5554` but prior APK showed provider hostname
  failures when not built with lab bootstrap.
- Compatibility runner supports only SMAP `10101` through `10106`.
- `docs/protocol/vn-online-route-matrix.md` records F04 and missing M3/M4/M7
  routes; these are requirements, not completed functionality.
- Existing online foundation has PostgreSQL migrations, command receipts,
  ledger, inventory/rewards and outbox worker tests. It is not yet a native
  game server.

## Execution order

1. **M0.2 evidence/content importer**
   - Parse pinned APK literals without executing JavaScript.
   - Verify source hash, table shape, unique IDs, numeric bounds and references.
   - Import `smapData`, role/equipment/item/experience rows into immutable
     published content tables with source hash and content version.
   - Preserve unknown fields in an anomaly archive; reject unsafe expressions.

2. **M1/M2 authoritative command boundary**
   - Add account/session/player snapshot and Pomelo adapter over PostgreSQL.
   - Require `command_id`, player ownership, expected version and content version.
   - Return deterministic errors for stale/replayed/unsupported commands.

3. **M3/M4 economy and progression**
   - Implement recruitment, wallets, inventory, equip/unequip, equipment level,
     role level/skill/star/evolution and material acquisition.
   - All mutations use the same transaction as ledger, receipt and outbox.

4. **M6 normal-map graph**
   - Load all normal-map rows from pinned content, including 10107+.
   - Enforce unlock, attempts, AP and team validation server-side.
   - Simulate battle from published content; accept only a battle command/result
     proof, never a client star value as reward authority.
   - Add deterministic rewards and idempotent settlement.

5. **M7 social features**
   - Friend search/request/accept/refuse/remove, gifts and bounded batch actions.
   - Enforce ownership, duplicate requests, daily limits and ledger effects.

6. **Native acceptance**
   - Build lab APK with local bootstrap, install only on `emulator-5554`, run
     each flow, capture sanitized server and logcat evidence.
   - Power labels must render integer strings; no decimal suffix or sentinel
     placeholder may be accepted.

## Acceptance gates

- Content importer tests pass with wrong-hash/malformed/executable fixtures.
- PostgreSQL integration tests prove rollback, replay idempotency and ledger
  conservation under concurrency.
- Route matrix changes from `missing` to `service-tested`, then `wire-tested`,
  then `native-confirmed`; no broad “implemented” label.
- Native smoke covers recruit, friend, role/equipment progression and 10107.
- README/CHANGELOG and a timestamped release evidence report are updated.

## Immediate next task

Checkpoint: `server-online/src/kbht_server/content/` now parses verified stage
and chapter literals, classifies normal maps through chapter type and validates
their ordered graph. Migration `0009_normal_maps` materializes 376 map rows and
3,722 ordered wave references in a replay-checked DRAFT transaction. Chapter
provenance and raw stage fields are retained. See
`docs/protocol/vn-normal-map-content.md` for literal evidence and limitations.

Dependency continuation: migration `0010_dependency_archives` and CLI
`import-dependencies` retain seven ordered raw tables and a transitive normal-map
reference audit. Both definitions of duplicate skill1105010/buff10006 are
preserved; report is BLOCKED because skill1105010 is reachable from normal maps.
See `docs/protocol/vn-combat-content-dependencies.md`.

Next: resolve these duplicate semantics from comparator/native evidence and
record explicit versioned resolution before creating unambiguous combat rules.
Equipment continuation: `prepare-equipment` and migration0011 materialize
120 definitions/342 ingredient rows in a separate equipment-only DRAFT. Source
types, quantities, effects and separate evolution/material cycles are checked.
See `docs/protocol/vn-equipment-content.md`. No actual upgrade route is enabled.

Then validate effect/numeric/drop semantics and material acquisition
and remaining mode-specific references. Archives are not published definitions.

Acquisition checkpoint: `audit-acquisition` now preserves379 drop rows, checks
class/box references/cycles and lists78 required-material candidates. It does
not resolve177 count0 rows or execute RNG. Next concrete path is verifying
class102 coin-recruitment invocation and box321 acquisition before wiring a
ledger-backed material source; see `docs/protocol/vn-material-acquisition.md`.

Fixed-box service checkpoint: migration0012 and `use_fixed_box` now stage and
consume verified fixed material recipes through shared ledger/rewards, with
ownership/replay/rollback/runtime-ACL and authenticated HTTP test evidence.
Default listener remains closed to gameplay; test opening inventory does not
establish box acquisition. Next: durable native bag-ID mapping/snapshot and
real acquisition eligibility before exposing native useItem.

Inventory adapter checkpoint: opt-in native-inventory-v1 accepts the durable
envelope and native useItem payload, saves translated bag/reward results and
provides a consistent bag-only snapshot. New online inventories use decimal
string PG IDs; legacy mapping remains separate. Next gateway integration must
implement negotiation and version-order/reconnect handling plus full snapshots;
default serve and recovered APK remain unchanged.

Connection-state checkpoint: InventoryConnection now negotiates the bounded
inventory capability, pins authenticated selection, rechecks token state and
resyncs with replace-bag snapshots. Reconnect reuses original receipt envelopes.
No listener/transport wiring or complete bootstrap is implied. Next gateway work
must carry this contract over Pomelo and implement client version-order/queue
handling while retaining acquisition/release/native acceptance gates.
Map draft preparation does not prove valid combat or reward rules. Publication,
release activation and legacy SQLite reconciliation remain unimplemented gates.
Do not add more hard-coded map IDs to the compatibility runner.

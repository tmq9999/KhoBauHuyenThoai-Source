# Online Game Server Implementation Plan

Execution queue superseded by
[2026-09-17 native-client-first plan](2026-09-17-native-client-first-online-slice.md)
at the owner's request. Preserve this file for previous task evidence and the
remaining whole-game scope; do not restart M0 or report lab-only slices as delivery.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for inline Codex execution; use superpowers:subagent-driven-development only
> when its tools work and tasks are isolated. Steps use checkbox syntax. The
> owner selected Codex, not Antigravity.

**Goal:** Deliver a database-authoritative native online game with an audited
admin system and fix the reported core gameplay flows end-to-end.

**Architecture:** Modular Python backend, PostgreSQL authoritative state, Redis
ephemeral state, retained Pomelo/native adapter, separate admin UI/API and worker.
Preserve the compatibility runner as evidence during an explicit migration.

**Tech Stack:** Python 3.12, PostgreSQL, Redis, FastAPI, SQLAlchemy/Alembic,
psycopg, React/TypeScript/Vite for admin; recovered Cocos 1.10.3 native client.
Dependency patches/images are pinned after official-doc/version checks in M1/M8.

**Spec:** [Online design](../specs/2026-09-16-online-game-server-design.md)

**Runbook:** [Codex execution](../runbooks/2026-09-16-codex-online-game-server.md)

## Global Constraints

- Preserve original APK SHA256 `d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4`.
- Preserve recovered `project.js` SHA256 `9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.
- Reuse native scenes/resources/engine; proposed production code is not recovered historical server source.
- No provider/payment/analytics traffic, live money, public exposure or unknown-device install without scoped authorization.
- Existing SQLite is a read-only migration source, never a destructive test target.
- All deliverable commits include README.md and CHANGELOG.md; verification precedes commit/push.
- Evidence states distinguish static, service-tested, wire-tested and native-confirmed.
- Tests use real PostgreSQL transactions for persistence; mocks do not prove ledger correctness.
- A route is not complete until its item acquisition/spend/progression loop is usable through the APK.

## File ownership and interfaces

Paths marked Create are deliverables, not files claimed to exist now.

| Path | Responsibility |
| --- | --- |
| `server-online/src/kbht_server/contracts.py` | command/result/error DTOs; only public service types |
| `server-online/src/kbht_server/content/` | safe import/validation, immutable published rules |
| `server-online/src/kbht_server/db/` | connection/unit-of-work/repositories/migrations; never UI rules |
| `server-online/src/kbht_server/economy/` | wallets, inventory, ledger, rewards and purchases |
| `server-online/src/kbht_server/players/` | identity/projections/roles/equipment/skills/team |
| `server-online/src/kbht_server/battles/` | deterministic engine, map/sweep/settlement |
| `server-online/src/kbht_server/social/` | friends/gifts/mail |
| `server-online/src/kbht_server/liveops/` | tasks/sign-in/events/notices |
| `server-online/src/kbht_server/payments/` | sandbox provider adapters, orders/refunds/withdrawals |
| `server-online/src/kbht_server/admin/` | RBAC/approval/admin DTOs; commands call shared services |
| `server-online/src/kbht_server/adapters/` | bootstrap/Pomelo/native DTO translation and error mapping |
| `server-online/src/kbht_server/workers/` | outbox consumption, scheduling, reconciliation |
| `server-online/tests/{unit,integration,protocol,security,load}/` | exact assertions and real DB/transport coverage |
| `admin-panel/src/features/` | users/economy/liveops/finance/audit pages with typed API clients |
| `client-recovered/patches/` | reviewed native transport/display patches; pinned source untouched |
| `tools/ops/` | migration verification, backup/restore, release and run scripts |
| `docs/agent-runs/online-server-progress.md` | evidence/decision/commit checkpoints; task IDs come from this plan |

Public command contract (M1 implements, later tasks consume):

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class GameCommand:
    command_id: UUID
    account_id: UUID
    player_id: int
    server_id: int
    route: str
    expected_version: int
    content_version_id: UUID
    payload: dict[str, Any]

@dataclass(frozen=True)
class CommandResult:
    command_id: UUID
    aggregate_version: int
    content_version_id: UUID
    result: dict[str, Any]
    event_ids: tuple[UUID, ...]

@dataclass(frozen=True)
class DomainFailure(Exception):
    code: str
    message: str
```

Errors: `VALIDATION_ERROR`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`,
`CONFLICT`, `INSUFFICIENT_FUNDS`, `LIMIT_REACHED`, `CONTENT_UNAVAILABLE`,
`BATTLE_NOT_SETTLED`, `NOT_IMPLEMENTED`, `RATE_LIMITED`.
DTO parser rejects bool-as-int, non-finite values, extra authority fields and
unsafe numeric wire IDs. `execute(command: GameCommand) -> CommandResult` owns
the full transactional state transition through a route registry. RNG/time are
injectable only in test/services, never caller-supplied gameplay payloads.

### Test fixture interfaces used by the work packages

These are test-only adapters to real commands/DB; implement in conftest as their
milestone lands. They do not fabricate game successes. `key` labels in examples
map to a stable UUID inside the test fixture, with the same label always mapping
to the same command UUID. Setup operations run before the test and create
opening-ledger entries; they are never public admin or game endpoints.

| Fixture / task | Methods and return contract |
| --- | --- |
| pg_lab M1.1 | purchase_command(player_id,cost_gem,reward_coin,command_id)->GameCommand; execute(command)->CommandResult; wallet(player_id,currency)->int; ledger_deltas(player_id,currency)->list[int]; receipt_count(UUID)->int; items(player_id)->persisted inventory; events(command_id)->outbox rows |
| pg_lab M2 | call(player_id,route,payload,key)->decoded actual adapter response; snapshot(player_id)->actual serialized snapshot |
| pg_lab M4 | setup_role_level(player_id,role_slot,level,coin)->None in isolated setup; fund(player_id,currency,amount,reason)->opening ledger tx |
| pg_lab M5 | draw_count(key)->int from persisted draw rows; currency_spent(key,currency)->sum of actual player debit postings |
| pg_lab M6 | begin_verified_fixture(player_id,map_id,fixture)->BattleSession with id; finish_battle(session)->BattleReport with winner; settle(session)->saved response; reward_grants(source_id)->int; map_unlocked(player_id,map_id)->bool from progression service |
| pg_lab M7 | equipment_upgrade_event(player_id)->real committed upgrade event; consume_progress_event(event)->consumer result; task_progress(player_id,requirement)->int; claim_completed_daily_task(player_id)->claim with id; replay_claim(claim)->same persisted claim |
| admin_lab M8 | create_adjustment(actor,player_id,gem_delta,reason)->request with id; approve(request_id,actor)->real HTTP response; gem_delta(request_id)->ledger delta; audit_count(request_id)->int |
| payment_lab M9 | order(player_id,amount_minor,gem_amount)->test SKU/order; signed_paid_event(order)->sandbox signed callback; deliver(event)->HTTP response; order_status(order_id)->str; credited_gems(order_id)->ledger sum; gift_qualifications(order_id)->int |

The battle fixture `first-chapter-win` is recorded from a real headless engine
input/action log; it must not set winner directly. The payment fixture signs
using a test-only key unrelated to historical providers. If a helper bypasses
the behavior being tested, reject the test during review.

## M0: evidence, numeric contract and delivery gates

### Task M0.1: route inventory with source provenance

Execution status: extractor/CLI/generated manifest verified locally; consumer
profiles cover 77 CORE routes but four direct consumers and optional nested
schemas remain `BLOCKED_EVIDENCE`. See `docs/agent-runs/online-server-progress.md`.

**Create:** `tools/protocol/route_inventory.py`,
`tests/protocol/test_route_inventory.py`,
`docs/protocol/vn-route-inventory.json`,
`docs/agent-runs/online-server-progress.md`.
**Modify:** `docs/protocol/vn-online-route-matrix.md`, README.md, CHANGELOG.md.
**Interfaces:** `inventory(source: str) -> list[dict]`; each record has `route`,
`sourceLine`, `status`. Request/response schemas are recovered separately; a
regex occurrence is not a schema.

- [x] Write literal tests, then run RED:

```python
from tools.protocol.route_inventory import inventory

def test_request_inventory_keeps_source_line_and_route():
    source = 'x = 1;\na.request("logic.playerHandler.buyCoin", {}, cb);\n'
    assert inventory(source) == [{
        "route": "logic.playerHandler.buyCoin", "sourceLine": 2,
        "status": "STATIC_OBSERVED",
    }]

def test_unrelated_string_is_not_a_request():
    assert inventory('var text = "logic.playerHandler.buyCoin";') == []
```

Run `python -m pytest -q tests/protocol/test_route_inventory.py` and observe
the missing behavior. Implement the syntax-specific inventory without execution:

```python
import re

REQUEST = re.compile(r'\ba\.request\("((?:logic|connector|gate)\.[A-Za-z0-9_.]+)"\s*,')

def inventory(source: str) -> list[dict]:
    return [
        {"route": match.group(1),
         "sourceLine": source.count("\n", 0, match.start()) + 1,
         "status": "STATIC_OBSERVED"}
        for match in REQUEST.finditer(source)
    ]
```

- [x] Add CLI `--source`, `--output`, `--check`. Resolve paths, hash input, emit
  sorted JSON with duplicate call sites retained; refuse output overwrite unless
  identical or explicitly updating that generated manifest. Check mode compares
  without writing. Generated artifact includes source SHA and extraction format.
- [ ] Run against pinned project.js; compare request sites with `rg` output and
  record CORE/EXPANSION/DENIED_ADMIN_ONLY classifications. Fill complete callback
  read-sets for all CORE groups from the route matrix, citing line/hash.
  Inventory/classification and reviewed direct-read profiles are present;
  full schema promotion remains pending for the four explicit unresolved routes.
- [ ] Verify using both sample tests and `--check`; every generated route has
  at least one source line. Update README/CHANGELOG and commit explicit paths.

### Task M0.2: regressions for power/defaults and docs policy

Execution status: `IMPLEMENTED_NOT_VERIFIED` for native display. Authored
formatter, exact staged pins, real snapshot default migration and docs checker
have local tests; signed APK build succeeded without install/launch. CI definition
is present but no hosted Actions run is claimed.

**Create:** `client-recovered/patches/power-display.js`,
`tests/client/test_power_display.mjs`,
`tools/ci/check_delivery_docs.py`, `tests/tooling/test_delivery_docs.py`,
`.github/workflows/verify.yml`.
**Modify:** staged client patch pipeline in
`tools/apk-recovery/prepare-lab-bootstrap.py`, snapshot contract fixtures,
README.md, CHANGELOG.md. Do not change immutable project.js.
**Interfaces:** pure `formatPower(value) -> string`; CI `--base <sha> --head <sha>`
checks both docs for each non-merge deliverable commit after the new baseline.

- [x] Write and observe RED for fractional sums, all four label call sites and
  missing snapshot counters. Native reference screenshot belongs in a private
  evidence run; store only a redacted fixture in Git.

```javascript
import assert from 'node:assert/strict';
import {formatPower} from '../../client-recovered/patches/power-display.js';
assert.equal(formatPower(3873.0999999999999), '3873');
assert.equal(formatPower(980.2 + 980.2 + 978.2), '2938');
assert.equal(formatPower(0), '0');
assert.throws(() => formatPower(Number.NaN));
```

Pure formatter reference (adapt export to the reviewed staging module loader):

```javascript
export function formatPower(value) {
  if (!Number.isFinite(value) || value < 0) throw new Error('invalid power');
  return String(Math.floor(value));
}
```

- [x] Test docs checker in temporary Git repos: code+README+CHANGELOG passes;
  either doc absent fails; initial historical base excluded; merge commit handled;
  empty range passes; invalid SHA fails. Never inspect only working-tree docs.
- [x] Implement per-commit name set check from Git diff-tree; reject missing
  `{"README.md", "CHANGELOG.md"}`. Test the script with no network and no live repo
  mutations. CI runs scoped pytest/node checks and this script with full history.
- [ ] Verify patch counts/hashes, `node --check`, fixture tests and native labels
  when authorized. Missing native proof remains pending. Both docs in commit.

## M1: database and shared transaction foundation

### Task M1.1: installable core, content schema and command ledger

Current execution status: PostgreSQL 18.6 portable cluster, isolated Python
environment, hash lock, frozen Alembic core revision, command receipts, ledger,
outbox writes and migration CLI have local PostgreSQL test evidence. M1.1 remains
IN_PROGRESS: runtime operational provisioning, Compose/Redis engine smoke and
delivery review remain. A least-privilege runtime grant
function, process-loss-before/after-commit tests and a schema dump/restore drill
have local evidence. Inventory/rewards and two-player wallet/command fixtures
have real-PostgreSQL test evidence, including source dedup across command IDs,
stack ownership, concurrency and rollback. Explicit-delivery outbox
consumption/dedup and bounded polling/backoff have PostgreSQL evidence; engine
smoke and real task rules are separate remaining work.
Content import, auth, native adapter and gameplay routes also remain open.

Environment preparation: local Python 3.12.9 venv created and isolation checked.
PostgreSQL and dependency downloads completed after the initial approval block;
the checklist below remains open for content import and the rest of M1. See the
progress log for exact setup evidence.

**Create:** `server-online/pyproject.toml`, lockfile,
`server-online/src/kbht_server/{__init__,contracts,cli}.py`,
`server-online/src/kbht_server/db/{session,uow,repositories}.py`,
`server-online/src/kbht_server/db/alembic/versions/0001_core.py`, `compose.yaml`, `.env.example`,
`server-online/tests/conftest.py`, `server-online/tests/integration/test_ledger.py`.
**Interfaces:** GameCommand/CommandResult/DomainFailure above;
`execute(command)`; `UnitOfWork` context with receipts/wallets/items/events.

- [x] Verify current official dependency docs, pin versions and install with
  approval. Create development/test DSNs with no production default. Tests refuse
  destructive DB setup unless the database name is `kbht_test`.
- [x] Implement real `pg_lab` fixture: isolated schema per test, creates two
  accounts/players and published minimal content, rolls back/drops only that
  schema, returns `execute`, `wallet`, `items`, `receipt`, `events` helpers.
  Fixture player IDs 10001/10002, not production users. Seed initial balances
  via opening ledger transactions, never SQL wallet-only updates.
  Two-account setup and execute/wallet/items/ledger/receipt/events helpers are
  implemented; the fixture imports synthetic definitions only, not gameplay loot.
- [x] Write failing balance/retry tests before mutation services. This first
  route is an internal test command, not an exposed GM player endpoint:

```python
def test_receipt_replay_cannot_debit_twice(pg_lab):
    command = pg_lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300,
                                     command_id="00000000-0000-4000-8000-000000000001")
    first = pg_lab.execute(command)
    assert pg_lab.execute(command) == first
    assert pg_lab.wallet(10001, "gem") == 40
    assert pg_lab.wallet(10001, "coin") == 300
    assert pg_lab.ledger_deltas(10001, "gem") == [50, -10]
    assert pg_lab.receipt_count(command.command_id) == 1
```

- [ ] Implement spec physical keys/checks/FKs/indexes in 0001_core, fixed-point
  balances, append-only ledger role, transaction receipts and outbox. Use player
  row lock/version plus unique command key, no Redis-only money lock.
  Shared wallet/inventory/reward/receipt constraints and runtime column grants
  exist in additive revisions through 0005. Full content/gameplay fields and
  operational role provisioning remain; do not rewrite applied 0001.

Atomic debit reference, parameterized in repository code:

```sql
UPDATE wallets SET balance = balance - :amount, version = version + 1
WHERE player_id = :player_id AND currency = :currency
  AND balance >= :amount AND version = :expected_version
RETURNING balance, version;
```

Zero rows maps to insufficient funds or stale version after an owned row lookup;
rollback the whole command. Ledger/receipt/outbox insert before commit. Never
commit this statement independently of the grant.

- [ ] Run real DB tests: 20 concurrent spends cannot exceed balance; same key
  different payload conflicts; disconnect before/after commit; ledger failure
  rolls back all rows; worker duplicate does not duplicate task progress.
  Wallet contention and worker receipt/projection dedup are service-tested;
  abrupt process loss and isolated schema restore are also tested. Actual task
  projection belongs to M7; these counters do not complete daily gameplay.
- [ ] Add CLI `migrate`, `check-invariants` with explicit environment; verify
  fresh install and restore. Run `python -m pytest -q server-online/tests/integration/test_ledger.py`.
  Update README/CHANGELOG and commit the independently usable foundation.
  CLI, fresh schema, source upgrade and synthetic restore have evidence; release
  integration/review/commit remains open.

### Task M1.2: content import and legacy migration rehearsal

Continuation: hash-verified stage/chapter staging, chapter-based normal-map
validation and relational draft map/wave materialization have targeted
PostgreSQL test evidence (migration `0009_normal_maps`); see
`docs/protocol/vn-normal-map-content.md` for APK evidence. Publication, full
mob/skill/item validation and legacy SQLite reconciliation remain separate open
gates. Existing M2 auth/HTTP work is preserved, not treated as native acceptance.

Dependency audit continuation: seven raw ordered combat/item tables now archive
through `0010_dependency_archives`, preserving sparse/sentinel/duplicate rows.
Transitive normal-map references and equipment recipe entity references have
tests; conflicting skill1105010 and buff10006 remain reported blockers, not
silently resolved rules. See `docs/protocol/vn-combat-content-dependencies.md`.

Independent equipment slice: `prepare-equipment`/migration0011 validates
evolution and material cycles and materializes equipment-only DRAFT costs with
raw snapshots. Does not resolve combat duplicates, activate content or implement
an upgrade route. See `docs/protocol/vn-equipment-content.md`.

Acquisition continuation: strict descriptor/drop-class/box validation and
`audit-acquisition` archive now report candidates for78 materials.177 zero-count
rows remain unresolved; class invocation, actual probabilities and box
acquisition still block gameplay acceptance. See `docs/protocol/vn-material-acquisition.md`.

**Create:** `server-online/src/kbht_server/content/{importer,validation}.py`,
`server-online/src/kbht_server/db/legacy_import.py`,
`server-online/alembic/versions/0002_gameplay.py`,
`server-online/tests/integration/test_imports.py`,
`tools/ops/reconcile_import.py`.
**Interfaces:** `import_content(source, source_hash) -> content_version_id`;
`import_legacy(backup, import_id, target) -> report`; `verify_import(report)`.

- [ ] RED: wrong source hash rejected, duplicate import unchanged, missing skill
  or item FK rejected, unknown payload retained in anomaly archive, mismatched
  balances stop cutover. Assert literal known APK rows from the defect matrix.
- [ ] Import tables without executing JS, validate type/range/reference/recipe
  cycle, pin formula version; import role/equipment/inventory/progression/social
  JSON into normalized tables with opening ledger and stable legacy ID map.
- [ ] Reconcile row counts, total items, currency per player, ownership and claims.
  Hash/report every anomaly; no zeroing unsupported fields. Keep source backup
  immutable and never print password hashes/token data.
- [ ] Restore new DB in isolation, re-run import and invariant checker, test
  legacy auth scheme migration path. A failed rehearsal blocks cutover, not M2
  development against fresh test data. Update docs and commit.

## M2: durable sessions, complete snapshots and adapter synchronization

### Task 1: M2 negotiated Pomelo inventory transport

Continue existing online package, not SQLite runner. Create
`server-online/src/kbht_server/adapters/{pomelo_codec,pomelo_transport}.py`,
`server-online/tests/integration/test_pomelo_inventory.py`, test-only raw WebSocket
helpers as needed. Add explicit `serve-inventory` CLI (loopback only, separate
port21002, no automatic DB migration or seed). Do not change existing serve.

- Reuse recovered codec from server-compatible/src/pomelo_codec.py by a
  provenance-documented package-local copy (do not import the SQLite runner).
  Preserve original; strict JSON validation belongs to transport boundary.
- Implement bounded stdlib asyncio WebSocket transport with explicit listen/start/
  close lifecycle, port0 tests and loopback bind. No new package installation.
  HTTP upgrade validates GET, path `/inventory`, upgrade headers/version/key;
  reject non-loopback Origin, oversized headers, fragmented/unmasked/oversize
  frames, malformed/truncated data and unsupported message types. No auth in URL.
  Bound frame size64KiB, clients32, read timeout10s, response size1MiB, pending
  work32; close cancels idle clients without leaking auth or engine objects.
- Pomelo HANDSHAKE body `{sys:{type:"kbht-inventory",version:"1"},user:{token,
  hello}}`, where hello is InventoryConnection's existing strict contract.
  Successful response `{code:200,sys:{heartbeat:0,dict:{},protos:{}},user:<negotiation>}`.
  HANDSHAKE_ACK empty is required before DATA. No route compression/protobuf.
  Heartbeat after ACK returns heartbeat. Malformed/preauth input fails closed.
- DATA REQUEST has nonzero transport request ID, route matching body envelope's
  route. Allowed useItem passes full durable envelope unchanged to connection.
  New explicit resync route `connector.inventoryHandler.resync`, payload `{}`,
  returns `{code:200,result:<resync>}`. useItem returns `{code:200,...adapterResult}`.
  Typed domain errors -> `{code:500,error:{code:<allowlisted domain code>}}` without
  SQL/trace/token. Unexpected faults return sanitized INTERNAL_ERROR then close.
- Run blocking DB operations off event loop with bounded concurrency and close
  semantics: admitted command may finish; disconnect does not rerun/mint. Don't
  generate idempotency IDs from transport request numbers.
- TDD real socket+PostgreSQL tests: handshake/ACK, unauth/GM/malformed/oversize,
  request ID echo, owned use/replay/tombstone, disconnect/reconnect same envelope,
  revoked token, two accounts, clean shutdown and CLI argument safety. Tests use
  existing explicit box fixtures, no live seeds. No APK acceptance claim.

### Task 2: M2 client bridge and network-to-database E2E

Create standalone ES5-compatible `client-recovered/patches/inventory-bridge.js`
and Node tests under `tests/client/`; never change pinned project.js or stage
the bridge into an APK yet. Implement the explicit Task1 wire contract using
WebSocket and recovered Pomelo framing, no execution of full recovered bundle.

- Connection-local protocol handshake/ACK; credentials only in handshake body,
  never URL/log/storage. Callback API for snapshot replacement and ordered deltas.
- Caller supplies action UUID once; queue captures exact immutable envelope
  at first send (account identity excluded), expected aggregate/content version,
  canonical bag index. Enqueue freezes action ID/payload; first-send version uses
  latest synchronized version so later queued actions do not start stale.
  One inflight mutation, bounded pending queue, retry on reconnect preserves
  full original envelope even if resync version advanced. No new UUID on timeout.
- Public callback interface: `createBridge({WebSocket,setTimeout,clearTimeout,
  onSnapshot,onDelta,onReward,onError})`; `connect({url,token,hello},cb)`,
  `useItem(actionId,bagIndex,itemCount,cb)`, `reconnect(token,cb)`, `resync(cb)`,
  `close()`, `getState()` returning copied nonsecret bag/version/status. Never
  expose token or mutable internal queues. Unexpected socket close keeps a
  bounded pending action for explicit reconnect; explicit close cancels it.
- Apply deltas only at version+1. Ignore stale/replayed deltas without rolling
  state backward or showing reward twice; gaps request replacement snapshot.
  Negotiated snapshots replace bag, never merge stale stacks. Schema errors,
  expired auth, mismatch/unknown reply and excessive frames fail safely.
- Graceful close clears credentials/timers and rejects pending promises/callbacks;
  bounded reconnect initiated by caller, not infinite silent auto-loop. No DOM
  or UI replacement. Module must run with injected WebSocket/timer primitives in
  tests and on Cocos JSB later; no Node-specific imports in production JS.
- Integration: a Python pytest launches Node bridge against the real loopback
  Task1 listener and isolated PostgreSQL fixture. Exercise open box, response
  loss/reconnect retry, newer snapshot then old replay, version gap/resync,
  invalid token/ownership. Assert DB balances/ledger/receipt/events and actual
  JS bag contents/popup behavior. Test seeded inventory clearly labelled.

### Task 3: M2 release integration and native gate

- Review Task1/2 jointly, run package regression, original codec/protocol tests,
  Node tests and true socket/JS/DB E2E. Verify pinned APK/source hashes unchanged.
- Update README/CHANGELOG/progress with runnable listener/bridge interfaces and
  exact distinction between network E2E and native APK acceptance.
- Inspect matching lab identity/egress and available native bridge integration
  evidence read-only. Do not install/restart/overwrite existing player state.
  Actual native cutover needs matching full bootstrap/session, content release,
  client queue wiring and lab authority. Report precise remaining gate if those
  cannot be met safely; do not mislabel seeded Node E2E as a playable online game.

### Existing M2 work package

### Task 4: Opt-in recovered-client inventory integration

2026-09-17 continuation: implementation exists; scoped review found duplicate
native error delivery, insufficient real-bridge consumer coverage and missing
integration destination containment. Fix round1 addressed all three; scoped
re-review PASS/APPROVED, Node21 and staging20 passed (5 symlink skips). The signed
`20260916T155928Z-repack` APK excludes InventoryBridge and is not proof for this
task. Native bootstrap/activation and device smoke remain open independently.

User requested integration into recovered client. Add reviewed staged
project transform embedding the ES5 bridge and lifecycle glue before the original
bundle; hook the exact socket.request entry, never pinned project.js. Default
lab bootstrap is unchanged. InventoryBridge requires LabBootstrap+LabLocalAuth,
accepts optional PowerDisplay predecessor, and records source/patch/output hashes.

Activation is explicit trusted online bootstrap only: same player/server identity,
PostgreSQL inventory provenance, session, content version and secure action UUID
provider. No guessed provider API or legacy SQLite token conversion. Pre-activation
legacy behavior unchanged; once selected, prevent all legacy writes/fallback.
Replace snapshots with tombstones via original bag merge; apply ordered deltas;
display rewards once through a dedicated callback and suppress duplicate native
success-callback popup. Detached/error connections stay fenced until safe attach.

Stage helper must reject symlink/reparse/containment escapes, input/output aliases
and existing independent-asset target; no blind overwrite. Test transformation
pin counts/hash, opt-in prerequisites, actual socket interception, identity guards,
snapshot/delta/reward/error/reconnect behavior and source immutability. No full
recovered-bundle host execution, native install or automatic credential storage.

This integrates loadable client glue, not full online login/bootstrap or native
acceptance. Trusted bootstrap still supplies runtime context, and native smoke
requires the matching isolated lab. Detail brief is in the plan's SDD workspace.

### Remaining M2 work package

### Task7: Native client form and Pomelo login integration

Owner direction2026-09-17: implement actual recovered client contracts rather
than another lab-only API. Direct source references: loginPanel/loginScene31169ff,
serverMain51711ff, socket53945ff, playerHandler39869ff. Preserve existing plan;
do not extend compatibility runner or manufacture a full player snapshot.

- [ ] Native form `/user/register/login/serverInfo` over PostgreSQL, original
  consumed DTOs/errors; registration metadata never grants authority. Public
  server list from actual open/published rows, no username-based player leak.
- [ ] Native Pomelo '/' gate/connector handshake and session binding, owned
  getPlayers, code500 denial for unimplemented create/entry/gameplay. No invented
  roles/maps or SQLite fallback. Full snapshot follows as separate dependency.
- [ ] Explicit loopback native listener CLI, no seed/migrate/public exposure;
  source-backed protocol checks, record exact reachable native flow. Owner asks
  no further broad lab-test cycles as substitute for implementation/acceptance.

### Task 6: M2 loopback account and inventory bootstrap

Status2026-09-17: SERVICE/WIRE_TESTED, independent spec/quality APPROVED. Full
backend379 passed195.69s; focused74 passed42.27s. No native or public-service
acceptance. Evidence: docs/release/2026-09-17-online-bootstrap.md and progress log.
Runtime auth-role provisioning and complete player/native bootstrap remain open.

Continue the approved M2 auth/session/bootstrap design, separate from the legacy
SQLite writer. No public deployment, legacy cutover, player seed or fabricated
full snapshot. New `/v1` endpoints are an authored online adapter, not historical
provider protocol. Existing default HTTP command listener stays unchanged.

- [x] Add Argon2id password hashing with a pinned dependency. Preserve and upgrade
  existing scrypt hashes on successful login only; unknown schemes fail closed.
  Add account ACTIVE/LOCKED status through additive migration0013; issue/resolve
  deny locked accounts, never reset passwords. Legacy SQLite import remains open.
- [x] Add service + opt-in `serve-bootstrap` loopback HTTP listener (21003):
  POST `/v1/accounts` `{login,password}` ->201 accountId (no automatic session);
  POST `/v1/sessions` same body ->200 bearer token and expiry duration;
  DELETE `/v1/sessions/current` bearer ->204; GET `/v1/players` bearer -> owned
  player summaries with bounded limit/cursor; POST `/v1/inventory/bootstrap`
  bearer + `{playerId,serverId}` -> selected current published release hello,
  server-configured loopback inventory URL, postgres-v1 provenance, bag snapshot
  and explicit fullPlayerSnapshot=false. Do not create missing players/items.
- [x] Bound request bodies to4096 bytes, reject extra fields/bool IDs/non-JSON,
  sanitize all errors (no Pydantic input echo/password/token/SQL), no-store all
  replies. Deny browser Origin and query credentials. Bound auth attempt rate
  and expensive concurrent hashing; no forwarded-IP trust or unbounded key cache.
- [x] TDD real HTTP+PostgreSQL: register/login/wrong password/duplicates,
  normalization, Argon2id + valid scrypt upgrade + malformed hashes, locked/
  expired/revoked sessions, ownership/release change, restart, bad input and
  redaction, denial without writes; returned hello negotiates real Pomelo
  connection and performs existing test-funded fixed-box command exactly once.
- [x] Run scoped/full suites, read-only review, update README/CHANGELOG/progress.
  Native activation still needs complete player bootstrap/client login wiring;
  report this adapter independently, no online-game completion claim.

Inventory boundary continuation: opt-in NativeInventoryAdapter translates the
native useItem fields and persists native bag/reward DTOs inside command receipts.
Stable online bag keys reuse PostgreSQL inventory IDs; bag-only snapshot checks
ownership and published release consistently. This does not complete full player
snapshots, legacy identity migration, Pomelo/capability negotiation or APK smoke.

Per-connection InventoryConnection now negotiates the bounded inventory capability,
pins authenticated player/server/content and offers replacement-bag resync.
Session state is rechecked and exact command replay survives reconnect; actual
transport handshake wiring/client queue/full player snapshot remain pending.

**Create:** `server-online/src/kbht_server/auth/{accounts,sessions}.py`,
`server-online/src/kbht_server/adapters/{http,pomelo,snapshots,errors}.py`,
`client-recovered/patches/command-envelope.js`,
`server-online/tests/protocol/test_native_session.py`.
**Interfaces:** `login -> session`, `select_player`, `snapshot(player_id)`,
`translate(command_result)`; command DTO from M1; versioned socket wrapper.

- [ ] RED: getPlayers/create/entry/login wrong owner/session expired/revoked,
  password upgrade, reconnect request replay and snapshot defaults.

```python
def test_snapshot_has_fields_beli_and_daily_panels_read(pg_lab):
    snapshot = pg_lab.snapshot(10001)
    assert snapshot["vip"]["buyCoinTimes"] == 0
    assert snapshot["point"]["gemTimes"] == 0
    assert snapshot["task"]["dailyActivePoint"] == 0
    assert snapshot["friend"]["actionPointReceiveTimes"] == 0
```

- [ ] Implement Argon2id, hashed tokens, TTL, generation/revoke, single-active
  session policy and account lock checks. Import legacy hashes by marked scheme
  and upgrade after successful verification, not by password resets.
- [ ] Reuse codec, map errors without generic crash; reject GM/admin routes.
  Add durable command ID/content/version envelope through one negotiated client
  socket boundary. Preserve bare legacy builders behind legacy mode, no silent
  extra-field mismatch. Retry same command after response loss returns same result.
- [ ] Send complete defaults, role records, inventory tombstones and map subtrees
  matching `player.update`. Serialize safe wire IDs; sign-in day fields stay
  numeric; render current server time independent of old payload timestamp.
- [ ] Run new protocol suite, legacy suite and native login/reconnect/home checks.
  Invalid old session must not be able to mutate a different player. Commit docs.

## M3: complete economy, inventory and acquisition paths

Bounded service continuation: `inventory.useFixedBox` now consumes a selected
owned PostgreSQL stack and grants a staged fixed fragment recipe atomically via
the shared ledger/reward/receipt path (migration0012). Service/HTTP tests use
explicit opening-box fixtures. Actual acquisition, runtime release publication,
native bag mapping and APK acceptance remain open; M3 is not complete.

**Create:** `server-online/src/kbht_server/economy/{wallets,inventory,rewards,shop,purchases}.py`,
`server-online/tests/integration/test_economy.py`,
`server-online/tests/protocol/test_economy_routes.py`.
**Interfaces:** registry routes buyCoin/buyAP/buySkillPoint/useItem/sell/composeItem/
shop.buy/refresh; `grant(source, recipient, rewards)` uses M1 receipt/ledger.

- [ ] RED: owner screenshot counter/first price, insufficient gem, daily cap,
  duplicate key, null tombstone, overdraw, split stacks, box reward UI vs DB.

```python
def test_first_beli_purchase_uses_counter_not_undefined(pg_lab):
    before = pg_lab.snapshot(10001)
    result = pg_lab.call(10001, "logic.playerHandler.buyCoin", {}, key="beli-1")
    assert result["vip"]["buyCoinTimes"] == 1
    assert result["gem"] == before["gem"] - 10
    assert result["coin"] > before["coin"]
    assert pg_lab.call(10001, "logic.playerHandler.buyCoin", {}, key="beli-1") == result
```

- [ ] Port exact price/limit/AP/EXP values from table/consumer; persist RNG
  multipliers once. Money route returns wallet + counters + exact `_temp` callback
  fields. Admin grants, game loot and mail all call the same reward service.
- [ ] Implement stack/unique item ownership, full fixed/weighted box behavior,
  sell exclusions and compose recipes. Signed inventory quantities, never trust
  client item count as owned count. Add content acquisition validator for 49902
  and every evolution material. An absent source requires a published approved
  new source or actual recovered source, not hidden test seeding.
- [ ] Test day boundary at 05:00 for daily purchases, no AP overflow loss, batch
  atomicity and store reopen. Native buy/sell/use/shop and ledger reconcile pass.
  Update README/CHANGELOG and commit.

## M4: stats, skills and equipment progression

**Create:** `server-online/src/kbht_server/players/{stats,roles,equipment,skills,teams}.py`,
`server-online/tests/integration/test_progression.py`,
`server-online/tests/protocol/test_equipment_routes.py`.
**Interfaces:** `recompute_stats(player_id, content_version)`; registry team
equipment/skill/role-star/evolve/EXP commands; M1 UnitOfWork and M3 inventory.

- [ ] RED for LV1->LV2/max/all, skill point cost, ownership, max level, exhausted
  materials, stat recompute, full preRole and postRole; exact screenshot costs.

```python
def test_level_four_equipment_max_costs(pg_lab):
    pg_lab.setup_role_level(10001, role_slot="1", level=4, coin=3000)
    result = pg_lab.call(10001, "logic.teamHandler.upgradeAllEquipmentMax",
                         {"teamIndex": "1"}, key="eq-all-1")
    assert result["coin"] == 840
    assert all(item["level"] == 4 for item in result["team"]["roles"]["1"]["equipments"].values())
    assert result["power"] == pg_lab.snapshot(10001)["power"]
```

- [ ] Compute costs from `costData`, new level thresholds and equipment effects;
  debit+upgrade+derived stats+progress events in one command. No role whitelist
  as substitute for validated content definitions. Unsupported passive effects
  require a bounded combat/content implementation task before that tier opens.
- [ ] Unlock skills by color while preserving levels; star/awake/friendship
  bonuses flow through one calculator. Retain fixed-point raw power and integer
  display across home/roster/team/rank. Upgrade own role; never use kindId as
  ownership identity. Green evolution requires six next-tier pieces, no extra
  guessed role fee.
- [ ] Run real DB and native progression with organically acquired materials;
  add tests for overflow/max cap/after relog. Commit docs with results/limits.

## M5: real recruitment

**Create:** `server-online/src/kbht_server/players/recruitment.py`,
`server-online/alembic/versions/0003_recruitment.py`,
`server-online/tests/integration/test_recruitment.py`.
**Interfaces:** four pointHandler commands; `draw_history`, `recruit_counters`,
content drop/guarantee definitions; RNG persisted by receipt.

- [ ] RED: first draw/second draw, free cooldown/daily count, paid coin/gem,
  ten draws, insufficient funds, duplicate role conversion and replay.

```python
def test_ten_draw_retry_returns_ten_recorded_outcomes_once(pg_lab):
    pg_lab.fund(10001, "gem", 3000, reason="test-opening")
    first = pg_lab.call(10001, "logic.pointHandler.gemTen", {}, key="draw10-1")
    assert len(first["_temp"]["dropList"]) == 10
    assert pg_lab.call(10001, "logic.pointHandler.gemTen", {}, key="draw10-1") == first
    assert pg_lab.draw_count("draw10-1") == 10
    assert pg_lab.currency_spent("draw10-1", "gem") == 2520
```

- [ ] Resolve static guarantee-counter ambiguity in matrix; record rule origin,
  publisher and version. First tutorial award happens once; next genuine action
  draws again, not idempotent-by-role-ownership. Entire ten-draw charge/outcomes/
  conversions/counters atomic. Never reroll upon reconnect.
- [ ] Boundary tests force each published weight/guarantee outcome using internal
  test RNG; distribution test checks configured weights without flaky exact
  frequencies. Native single+ten+retry/relog pass. Commit docs.

## M6: map continuation and authoritative combat

**Create:** `server-online/src/kbht_server/battles/{maps,engine,actions,abilities,settlement,replays}.py`,
`server-online/tests/battle-fixtures/`,
`server-online/tests/integration/test_battle_settlement.py`,
`server-online/tests/protocol/test_map_continuation.py`.
**Interfaces:** `begin -> battle_id`, `submit_action(battle_id, seq, skill, target)`,
`finish -> report`, `settle(battle_id)`, `replay(version, seed, input_log)`.

- [ ] RED for graph progression beyond 10106, chapter edges, level/AP/attempt
  limits/reset, loss/win reward paths, forging stars, manual skills and resume.

```python
def test_same_battle_settles_once_and_unlocks_next_map(pg_lab):
    battle = pg_lab.begin_verified_fixture(10001, map_id=10106, fixture="first-chapter-win")
    report = pg_lab.finish_battle(battle)
    assert report.winner == "player"
    first = pg_lab.settle(battle)
    assert pg_lab.settle(battle) == first
    assert pg_lab.reward_grants(source_id=battle.id) == 1
    assert pg_lab.map_unlocked(10001, 10107)
```

- [ ] Import full normal map graph/waves, validate no dangling mobs/skills,
  unreachable evolution materials or circular locks. Daily map limits keyed by
  reset date; chapter award keyed by threshold, not UI clicks.
- [ ] Port real recovered action ordering/targeting/buffs/MP/cooldown/hit/crit/
  death/revive. Test literal reports for representative active/passive/AOE/heal/
  control abilities before porting more. No simplified auto-win damage loop.
- [ ] Extend versioned client bridge for sequenced ability input and authoritative
  result presentation; validate timestamps/order/team snapshot. Settlement
  verifies report and uses M3 reward service with immutable battle source ID.
- [ ] Implement sweep/reset/chapter award with exact counters, AP/tickets/gems;
  concurrency, expiry, reconnect and rollback fixtures. Native 10106->10107->
  chapter2 plus ability animation/report parity mandatory. Commit docs.

## M7: social, tasks, sign-in and mail

**Create:** `server-online/src/kbht_server/social/{friends,gifts,mail}.py`,
`server-online/src/kbht_server/liveops/{tasks,sign_in,calendar}.py`,
`server-online/alembic/versions/0004_social_liveops.py`,
`server-online/tests/integration/test_social_daily.py`.
**Interfaces:** friendHandler/mailHandler/player task+sign-in routes;
`consume_progress_event(event_id)` dedups outbox events; `business_date(policy)`.

- [ ] RED: A->B request/accept both directions, deny self/blocked/cross-scope,
  gift once/day, task progress from actual upgrade/draw/battle events, double
  claim, week boundary and offline return.

```python
def test_duplicate_upgrade_event_cannot_double_daily_reward(pg_lab):
    event = pg_lab.equipment_upgrade_event(player_id=10001)
    pg_lab.consume_progress_event(event)
    pg_lab.consume_progress_event(event)
    assert pg_lab.task_progress(10001, requirement="upgradeEquipmentTimes") == 1
    claim = pg_lab.claim_completed_daily_task(10001)
    assert pg_lab.replay_claim(claim) == claim
    assert pg_lab.reward_grants(source_id=claim.id) == 1
```

- [ ] Implement pair constraints/stable lock order, search limits, real presence
  TTL not fake online status. AP gifts use economy ledger and donor/recipient
  daily caps. Empty lists still have complete client-consumed shape.
- [ ] Import task requirements/rewards, initialize only eligible tasks; domain
  events count once, claims progress exactly once. Sign-in midnight, other daily
  reset05:00, weekly Monday05:00, all Asia/Ho_Chi_Minh. Rewarded role duplicates
  convert through recruitment policy instead of blocking sign-in forever.
- [ ] System mail/unread/read/claim/remove-read and gift-code redemption use
  shared reward dedup. Native two-account, daily-task, sign-in, relog and mailbox
  checks pass. Commit docs.

## M8: admin, notices, events and game content operations

**Create:** `server-online/src/kbht_server/admin/{auth,rbac,commands,audit,api}.py`,
`server-online/src/kbht_server/liveops/{events,notices,campaigns}.py`,
`admin-panel/`, `server-online/tests/security/test_admin_roles.py`,
`admin-panel/tests/admin.spec.ts`.
**Interfaces:** `/admin/v1` surface/DTOs/roles from spec; adjustment approval
calls M1/M3 services, publishes immutable content releases; never SQL editing UI.

- [ ] RED: unauthenticated/forbidden server scope, CSRF, expired session, creator
  approving own request, stale preview version, script-containing notice.

```python
def test_admin_creator_cannot_approve_own_grant(admin_lab):
    request = admin_lab.create_adjustment(actor="support", player_id=10001,
                                          gem_delta=100, reason="ticket-123")
    denied = admin_lab.approve(request.id, actor="support")
    assert denied.status_code == 403
    assert admin_lab.gem_delta(request.id) == 0
    approved = admin_lab.approve(request.id, actor="approver")
    assert approved.status_code == 200
    assert admin_lab.gem_delta(request.id) == 100
    assert admin_lab.audit_count(request.id) >= 2
```

- [ ] Build real API-backed user/session/ban/player timeline, grant preview/
  approval, item/content config, notice/mail, event/sign-in/task, gifts, finance
  and audit pages. Query pagination/filter scopes; loading/empty/error/conflict
  screens; no mock datasets after API integration.
- [ ] Implement event requirements as validated DSL (allowlisted counters, no
  executable expressions), draft->validated->published->active->expired, version
  rollback, once-only claims. Freeze mail recipient sets on send and preview
  affected users/reward totals before approval. Sanitize rich text.
- [ ] Playwright real API+DB roles tests, mobile/desktop admin checks, audit and
  denied side-effect assertions. Native notice/event publish/claim flow confirms
  both systems agree. Update docs and commit.

## M9: top-ups, gifts, refunds and withdrawal workflows

**Create:** `server-online/src/kbht_server/payments/{orders,callbacks,reconciliation,refunds,withdrawals}.py`,
`server-online/tests/integration/test_payment_sandbox.py`,
`admin-panel/src/features/finance/`, `docs/operations/payment-sandbox.md`.
**Interfaces:** spec order/refund/withdrawal state machines; provider adapter
uses signed callbacks/status query/idempotency. Only sandbox adapters at first.

- [ ] RED: repeated/out-of-order callback, wrong amount/currency/account/SKU,
  forged signature, timeout after accepted payout, duplicate bonus claim.

```python
def test_paid_callback_credits_once_with_gift_qualification(payment_lab):
    order = payment_lab.order(player_id=10001, amount_minor=10000, gem_amount=100)
    event = payment_lab.signed_paid_event(order)
    payment_lab.deliver(event)
    payment_lab.deliver(event)
    assert payment_lab.order_status(order.id) == "CREDITED"
    assert payment_lab.credited_gems(order.id) == 100
    assert payment_lab.gift_qualifications(order.id) == 1
```

- [ ] Implement order verification then atomic credit+gift qualification; manual
  reconciliation needs evidence/two actors. Refunds append reversal ledger;
  spent assets produce a documented hold, not history deletion.
- [ ] Withdrawal request/reserve/review/approve/status and admin audit work in
  sandbox. Real payout feature flag fails closed; game gem withdrawal is not
  enabled by this spec. Owner must resolve withdrawable asset/legal/provider/KYC
  policy before provider integration can be activated.
- [ ] Verify sandbox fixtures, command replays, payout-status reconciliation,
  approval roles, admin/native top-up-gift claim, documented settlement reports.
  No live financial transaction. Commit docs.

## M10: release, backup, security and online staging acceptance

**Create:** `tools/ops/{release_manifest,backup,restore,verify_release}.py`,
`docs/operations/{deploy,backup-restore,incident-response}.md`,
`server-online/tests/load/`, complete native acceptance matrix under `docs/release/`.
**Interfaces:** release identity from runbook; migrate/check-invariants/import/
serve/worker CLI; restore target guard; health/metrics endpoint.

- [ ] RED: mismatched APK/content/protocol/schema release, stale session/delta,
  restore to non-test target, missing backup checksum, expired signing manifest.
- [ ] Implement health/readiness, graceful gateway drain, worker leases, bounded
  retries, metrics/error logs with redaction; HTTPS/WSS verified on Android,
  authenticated admin reachable only via approved internal access.
- [ ] Run fresh real DB/protocol/security suites and full native core checklist.
  Baseline unit test skip count cannot mask skipped PostgreSQL or native tests.
  Record remaining expansion routes explicitly; core valid actions have no
  NOT_IMPLEMENTED/500/undefined state.
- [ ] Restore drill and spec load/soak/contended-economy gates pass on recorded
  hardware. Reconcile ledgers after each run and prove command replay after
  process restart. Public exposure requires owner approval and rights/security
  review; no automatic deployment from a docs commit.
- [ ] Publish a versioned private release with exact APK+manifest+content+schema+
  commit hashes, smoke evidence, rollback and on-call checklist. Both README and
  CHANGELOG updated; verify private remote SHA if pushed.

## Scope/consistency review and next task

Review mapping: F01/F12 -> M1/M2; F03 -> M0/M4; F04/F02 -> M6; F05 -> M5;
F06/F10 -> M3/M4; F07/F08 -> M7; F09 -> M2/M3; F11 -> M8; F13/F14 -> M0/M10.
Admin user/game/item/notice/event -> M8; top-up/withdrawal/gifts -> M9.
Original recovery R1-R4 remains evidence and toolchain, not repeated work.

Milestones M1-M10 are subsystem work packages, not a claim their harnesses or
commands exist today. Before executing each package, expand its bounded tests
and transaction design in-place against M0 contracts; stop only for a material
new decision, not routine method naming. Helpers shown (`pg_lab`, `admin_lab`,
`payment_lab`) are implemented in the matching test fixture task and never added
to production as test-only methods. Code is written test-first during execution.

Next execution: finish remaining M0 consumer/schema evidence and native M0.2
smoke; finish M1.1 operational role provisioning, polling/backoff and delivery
checks before M1.2 content import/legacy migration. Runtime grant and synthetic
restore/disconnect tests are recorded in the progress log. Implemented tooling
does not mark M0 or the online server
complete. Remote push is paused for the historical SDK secret-shaped literals
found in pinned source; no source history is rewritten.

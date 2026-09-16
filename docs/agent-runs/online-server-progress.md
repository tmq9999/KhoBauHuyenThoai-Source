# Online server execution progress

Plan: `docs/superpowers/plans/2026-09-16-online-game-server.md`

## 2026-09-16 - M0 evidence and staged-client implementation

- Starting commit: `88a5cae1f870a3ed819fa617c56ec088574f6623`.
- Workspace: existing `feat/native-game-entry`, initially clean; kept in place
  as the approved runbook directs. No DB/device/network mutation.
- Baseline: scoped tests 215 passed, 3 skipped (`.pytest-tmp/m0-baseline`).
- TDD: behavioral RED 9 failed/10 passed with inert skeleton; inventory
  implementation GREEN 19 passed; added parser/output-identity regressions RED
  2 failures, then GREEN 25 passed/1 skipped (Windows symlink privilege).
- Output: `tools/protocol/route_inventory.py`,
  `tests/protocol/test_route_inventory.py`, `docs/protocol/vn-route-inventory.json`,
  `docs/protocol/vn-core-consumers.json`. Inventory: 230 routes / 231 call sites,
  77 CORE, 150 EXPANSION, 3 DENIED_ADMIN_ONLY; 14 unresolved dynamic request sites.
- Consumer profiles reference shared merge/error/decompression plus direct UI
  reads. Four CORE builders and content-specific nested shapes remain unresolved;
  M0.1 is partial, not a completed schema catalog.
- Raw APK source SHA: `9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.
- Scope: static evidence only; no new gameplay or native acceptance claimed.

### Preflight decisions

| Plan interface | Inspection | Decision |
| --- | --- | --- |
| M0.1 regex -> route inventory | literal-only sample misses two adjacent variable bootstrap calls and can count comments | Use non-executing lexical extraction; preserve interface `inventory(source)` and flag unresolved expressions. |
| M0.1 evidence -> M2 adapters | request keys alone cannot describe callback/UI state | Keep request inventory generated; maintain reviewed consumer profiles separately with source refs and explicit unresolved shapes. |
| M0.2 patch -> pinned source | production source hash is a loader invariant | Stage patches only; never rewrite recovered `src/project.js`. |
| M1-M10 dependencies | implementation needs complete core contracts and real DB harness | Do not claim M0 or database complete from route counts; deliver evidence then continue in dependency order. |

### Safety finding and delivery gate

Static reading revealed hardcoded historical SDK secret-shaped literals in the
already tracked recovered `project.js` wxApi module. Values are deliberately not
copied here, used, or contacted. The previous narrow token-pattern scan did not
detect this secret class; private GitHub visibility is not a complete secret
review. Pause further remote pushes pending owner decision on restricted raw
evidence vs a sanitized distributable source snapshot. Do not alter pinned
history or credentials automatically. Local work/tests/commits may continue.

### Review status

`m0_core_consumers` subagent failed to initialize with provider credentials 404.
Controller performs static consumer review locally; no independent verdict.

### M0.2 implemented, native verification pending

- New pure ES5-compatible formatter and 12 exact display replacements in staged
  source only (home/role/team/arena/settings/view/rank). Numeric combat state is
  unchanged. Rank formatting is conditional on a power rank; unknown `?` stays `?`.
- `-PowerDisplay` requires both `-LabBootstrap` and `-LabLocalAuth`; default build
  remains unchanged. Reference alias/hardlink, mutated stage and pin drift fail
  before writing. Callback diagnostics still refer to staged source line numbers.
- Added missing purchase/draw/friend AP counters through existing transactional
  snapshot normalization; tested create/reopen and preservation of nonzero data.
  No running server was restarted and no live DB row was changed in this run.
- Per-commit docs checker covers both files, invalid/divergent refs, historical
  baseline, deletion and side-branch commits. CI checks history after `88a5cae`.
- Test portability: decoder/encoder scratch moved to pytest temporary roots;
  manifest rewrite uses a synthetic schema fixture. Native-input tests skip
  only when private artifacts are absent; tracked source hashes always checked.

### Fresh verification

```text
python -m pytest -q tests server-compatible/tests/protocol -p no:cacheprovider --basetemp .pytest-tmp/m0-final --tb=short
266 passed, 4 skipped in 166.02s

node --test tests/client/test_power_display.mjs
1 passed

python tools/protocol/route_inventory.py --source client-recovered/src/project.js --output docs/protocol/vn-route-inventory.json --check --consumers docs/protocol/vn-core-consumers.json
VERIFIED: 230 routes, 231 sites, 14 dynamic sites
```

The isolated clean-copy test run without `work/` passed 259 / skipped 6 before
the final five consumer/display tests were added; hosted Linux Actions has not
run. Full local suite skips three historical Windows capability cases and the
new Windows symlink-output case. PostgreSQL integration tests were added in the
later M1.1 entry below; this earlier line is retained as a historical snapshot.

### APK packaging evidence (not boot evidence)

```text
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -PowerDisplay -Sign
Exit 0, signature v1/v2/v3 verified
Run: work/apk-vn/20260915T212249Z-repack
Signed APK: artifacts/vn-recovered-debug-signed.apk
APK SHA256: 50df03a4626c0c9cd5d4e97b9de6bc562fc40b2482a8f0817e5927f5979b8360
Staged project SHA256: 4017b696b0995c158c392c48a56fc77ca4a53859b87fabcdabc49490d18b4d0e
Patch SHA256: 2df16322af80099ae21fc9002584c7982ae04ffc6dd731c5432e67c498b09674
Manifest SHA256: cf49d5c96c3e0dee19f4a82a9d3f01cc37a1bce61515ff432e62e6ee8fd73db7
```

Decoded the signed APK `assets/src/project.jsc` and compared byte-for-byte with
the staged source; embedded manifest equals the run manifest. No JS execution.
Original APK and pinned project hashes unchanged. Existing META-INF version-file
signature warnings remain; no signature-parity or full C++ recovery claim.

### Remaining gates and next exact work

1. Finish unresolved consumer schemas / content-profile fixtures; do not mark
   them native-confirmed. Inventory and tooling can be used now.
2. Verify the new APK on the authorized isolated MuMu with matching manifest,
   after checking firewall/device and preserving DB/app state.
3. Resolve historical SDK secret distribution with owner before any new push.
   The local changes contain no new secret values and keep pinned history intact.
4. The initial M1 environment probe found no Docker/psql executable; PostgreSQL
   was subsequently installed portably as recorded below. Do not substitute
   SQLite for PostgreSQL transaction acceptance.

The review subagent `m0_review` also failed before starting (provider 404).
Controller review and local checks are recorded; no independent review verdict.

## 2026-09-16 - M1.1 PostgreSQL foundation installed

- Network approval was restored. Downloaded the official EDB redirect for
  PostgreSQL `18.6-3` Windows x64 (`344414106` bytes), saved under ignored
  `work/m1-env/download/`, and extracted to ignored `work/m1-env/postgresql-18.6`.
  Local SHA-256 is
  `59f8ce701c63c2ed623c665a5e51b3ef6f2e37ccf837b68ffeed0742d0ae6abd`; no
  vendor sidecar checksum/signature was found on the page, so no stronger
  provenance claim is made.
- Initialized a fresh checksummed cluster in `work/m1-env/pgdata` with SCRAM,
  password file outside Git, `listen_addresses=127.0.0.1`, port `25432`, UTC;
  created only `kbht_test` and `kbht_dev`. No Windows service or global PATH.
- Verified restart persistence: `m1_install_probe` survived a fast restart;
  `psql` reported database `kbht_test`, address `127.0.0.1`, port `25432`, UTC.
- Installed only in `server-online/.venv`: psycopg 3.3.5 + binary, SQLAlchemy
  2.0.54, Alembic 1.20.0, FastAPI 0.141.1, Pydantic 2.13.5, Uvicorn 0.53.0,
  pytest 9.1.1, Redis client 6.4.0; generated hash-pinned `requirements.lock`
  and installed the package editable without changing global Python.
- Added a frozen Alembic core revision under the package, loopback target
  validation, append-only ledger guards, double-entry postings, read-only
  invariant checks and isolated-schema fixtures. CLI migration returned
  `0001_core`; `check-invariants` returned zero mismatches on `kbht_dev`.
- TDD evidence: first RED was the unimplemented command; after the minimal
  implementation, PostgreSQL suite reports 44 passed. Coverage includes
  replay/conflict/ownership/validation, rollback, append-only history,
  double-entry posting, partial-schema refusal and competing wallet spends.
- Status: PostgreSQL install/migration `VERIFIED`; M1 transaction slice is
  `IMPLEMENTED_NOT_VERIFIED` for native gameplay. Content import, M2 auth,
  native adapter and all gameplay/admin milestones remain open. No push was
  made; the historical recovered-source secret review gate remains active.

### M0 commit attempt (historical authority failure)

The scoped `git add` escalation was rejected by the approval service with a
provider credentials 404. No staging/commit/push was completed for this M0 batch;
HEAD remains `88a5cae`. All listed changes are saved in the workspace. Retry
normal Git approval only after the authority/service is restored; do not bypass
the sandbox using another shell/tool. README and CHANGELOG are already updated
for the eventual deliverable commit.

## 2026-09-16 - M1.1 local prerequisite installation

- Owner authorized prerequisite installation with "cai dat vao". Scope: portable
  PostgreSQL under ignored `work/m1-env`, workspace-only Python venv, loopback
  test DB; no service/global install or migration/cutover of existing game data.
- Used Superpowers executing-plans and verification-before-completion. Kept
  the approved dirty feature branch in place; preserved the M0 changes.
- Context7 tools remain unavailable. Official PostgreSQL Windows download page
  previously identified EDB as its ZIP binary source; no exact archive/version
  or verified checksum has been selected.
- The authorized escalation to read
  `https://www.enterprisedb.com/download-postgresql-binaries` was rejected:
  `Automatic approval review failed: 404 No active credentials for provider: openai`.
  Stopped that network workflow; no alternate shell/tool retry of the denied
  operation. PostgreSQL and online Python dependencies remain uninstalled.
- Independent offline step: ran the existing Python 3.12.9 with
  `-m venv server-online/.venv` (exit 0). No global package/PATH change.
- Verification: venv Python reports 3.12.9, prefix differs from base prefix,
  `include-system-site-packages = false`; FastAPI, SQLAlchemy, psycopg, Alembic,
  pytest and redis are all absent, proving global packages were not inherited.
  `pip list` contains only pip 24.3.1; `pip check` exits 0. This is an empty
  dependency environment, not M1/server acceptance.
- `git check-ignore -v server-online/.venv/pyvenv.cfg` confirms `.gitignore`
  excludes the environment. `work/m1-env` does not exist; no new DB data,
  credentials, Windows service or listening port was created.
- Retrieved the completed prior baseline run: scoped pytest reports
  266 passed, 4 skipped in 167.81s. No backend code was changed during setup.
- Updated README, CHANGELOG and M1.1 status. No staging, commit or push;
  historical SDK-source distribution gate is still open.
- Status: offline venv `VERIFIED`; external installation `BLOCKED_AUTHORITY`.
  Next: restore the tool approval service, then fetch official EDB metadata,
  select/verify the portable binary, pin/install M1 packages into this venv and
  initialize a fresh loopback-only `kbht_test`. Do not use the old SQLite file
  to substitute for PostgreSQL acceptance tests.

### Reconciliation note

The preceding local-prerequisite entry records the earlier blocked attempt and
is retained as historical evidence. It is superseded by the successful M1.1
installation entry; current state is PostgreSQL `18.6` installed,
dependencies present and the cluster listening on loopback only.

### Final installation verification and remaining M1 work

- PostgreSQL installation is usable; network/install authority is no longer a
  blocker. The new CLI migrates only the `kbht_core` schema. Earlier experimental
  `public` tables and installation probe remain intact and unused by the CLI.
- Fresh checks: server suite 44 passed in 11.61s (34 PostgreSQL, 10 config/CLI,
  no skips); recovery suite 266 passed/4 skipped in 125.12s; Node formatter 1
  passed; inventory check 230 routes/231 sites/14 dynamic sites. `pip check`
  and compileall exit 0. Delivery-doc checker has an empty commit range, not
  proof that uncommitted work is published.
- A legacy test originally failed while scanning the whole running workspace:
  PostgreSQL legitimately changed files inside `work/m1-env/pgdata`. Changed
  only the test's scope to its temporary directory; the ZIP validator is
  unchanged. The fresh recovery run above verifies the fix.
- Restart persistence and SQL identity checked: `kbht_test` probe retained,
  `kbht_dev.kbht_core.alembic_version = 0001_core`, loopback port 25432, UTC;
  no leftover `kbht_t_*` test schemas. Password directory/file ACLs permit only
  the current Windows user and SYSTEM. No password values are in source.
- `m1_foundation_review` failed before running with provider credentials 404;
  review was local only, not independent sign-off. The DB binaries inspected
  have no Authenticode signature; the hash is local, not vendor-verified.
- M1.1 is IN_PROGRESS: no inventory/reward repositories, outbox consumer dedup,
  restricted runtime DB role, two-player fixture or full backup/restore drill.
  The test-only purchase handler is not a gameplay route or pricing rule. Redis
  client installed, Redis service not installed. No M1 completion/native claim.
- README, CHANGELOG, server README and plan are synchronized. No commit/push
  this turn; existing M0 work remains alongside this new foundation. The
  recovered-source distribution gate blocks new pushes, not local development.
- Next work: complete M1.1's missing repositories/roles/consumer/restore tests
  before M1.2 content import and legacy migration rehearsal. APK/gameplay/admin
  acceptance remains separate.

## 2026-09-16 - README separation and M1.1 outbox continuation

- Owner approved moving execution status out of README. Root and backend
  READMEs now describe actual module layout, data contracts, configuration,
  installation, migration, commands and testing. No session counters, approval
  errors or milestone status remain there. The Codex runbook's documentation
  section follows this distinction; README+CHANGELOG delivery policy is retained.
- Continued M1.1 with two actual test players (10001/10002), stable UUID command
  labels, opening ledger transactions, durable command replay and cross-account
  spend denial. Fixture counters and purchase amounts are test-only, not recovered
  gameplay rules or a daily-task implementation. Inventory helpers remain pending.
- Added `workers/outbox.py`: explicit event consumption registers an append-only
  `(consumer, event_id)` receipt in the same transaction as the DB projection.
  Concurrent duplicate deliveries wait on the unique receipt. Handler failure
  rolls back receipt/projection, so retry can safely apply the event again.
  This API does not claim exactly-once external HTTP/payment effects or a polling
  scheduler; handlers must use the provided transaction.
- Added packaged migration `0002_worker_receipts` without rewriting `0001_core`.
  The migration adds worker receipt FK/index and immutable receipt/event guards.
  An upgrade test verifies an existing command result, wallet, ledger and event
  survive upgrade and can be replayed/consumed afterward.
- TDD: inert consumer run returned 16 failed/4 passed (one failure was the missing
  receipt table). Implemented migration/consumer: 20 passed. Extra immutable-event
  regression: 1 failed/1 passed, then fixed the guard. Final full M1 suite:
  **66 passed in 17.23s**, no skips. This is service evidence, not native acceptance.
- Verified CLI migration on `kbht_dev.kbht_core` returns `0002_worker_receipts`;
  all four read-only invariant counts are zero. Wheel build includes both the
  consumer and SQL/Python additive revision. `pip check` and `git diff --check`
  pass; 24 local doc links resolve. ZIP integrity tooling: 25 passed; Node power
  formatter: 1 passed. The full legacy suite was not rerun in this continuation.
- Interruption/environment recovery: the active permission profile had reverted
  to workspace-write during the prior turn. Tests initially could not read the
  owner-only password and PostgreSQL was stopped. Restored the owner's original
  FullControl ACL (a grant based on escalated `whoami` had reduced it to Read),
  left SYSTEM/owner-only access, and restarted the same loopback cluster.
  After owner switched execution to full access, no escalation requests were used.
  No SQLite, MuMu, native APK, signing key or historical provider was changed.
- Independent `m1_foundation_review` retry failed before execution (provider
  credentials 404). Local inspection and PostgreSQL tests are the only review
  evidence; no independent sign-off is claimed.
- State: README rewrite verified; outbox delivery/receipt slice service-tested.
  M1.1 remains IN_PROGRESS for inventory/rewards, restricted runtime roles,
  worker polling/backoff and backup/restore rehearsal. Real task processing belongs
  to M7. Next: complete those M1 foundations before M1.2 content/legacy import.
- Files saved locally, no new commit/push in this continuation. Existing M0/M1
  changes are preserved. The historical source-secret distribution decision
  still gates remote pushes, not ordinary local implementation.

## 2026-09-16 - M1.1 inventory/reward persistence, runtime ACL and durability

- Continued the approved runbook in the existing dirty `feat/native-game-entry`
  checkout, preserving the M0 work. No change to native source/APK, running
  compatibility game, SQLite player data, global dependencies or remote source.
- Added versioned item definitions, owned stacks, per-stack ledger/version,
  reward-source uniqueness and normalized item/currency reward lines. Stack
  split/refill/consume and reward grants participate in `CommandExecutor`'s
  player-locked transaction. Source replay does not reissue items/currency/events;
  changed reward data conflicts. Fixture content remains explicitly synthetic.
- Added `0003_inventory_rewards`; after it was applied locally, subsequent
  hardening uses additive `0004_content_immutability`/`0005_runtime_guards`.
  Published content cannot be put back into draft to bypass definition guards.
  Inventory/reward history is append-only and foreign keys tie it to owned
  records and committed receipts. Zero-quantity rows keep their IDs for auditing.
- Added inventory total/history and item/currency reward reconciliation to the
  read-only invariant checker. Corruption tests modify only throwaway schemas
  under test control and confirm each new check detects inconsistency.
- Added `grant_runtime_access`: a dedicated non-owner role gets allowlisted
  SELECT/INSERT and projection-column UPDATE. PostgreSQL requires UPDATE on one
  column even for row locks; immutable-column triggers protect those permissions.
  Rejects elevated/inheriting/member/owner roles and pre-existing excessive ACLs.
  This is provisioning code with temporary-role evidence, not a provisioned
  live gateway account, row-level security, or a replacement for player auth.
- Added real abrupt process exits before/after reward commit; pre-commit work
  rolls back and post-commit retry returns the saved result. A `pg_dump` custom
  archive/`pg_restore --single-transaction` round trip restores a generated test
  schema, compares account/wallet/ledger/inventory/grant/event rows and verifies
  command and worker replay. Only the test's own schema is dropped/restored;
  this is not a production recovery/PITR or SQLite migration rehearsal.
- TDD evidence: initial inert inventory/rewards 11 failures, then 11 passed;
  expanded inventory suite exposed missing reconciliation and definition guard
  (2 failed/38 passed), fixed; content unpublish/provenance regressions failed
  before additive 0004. Runtime no-op grant failed 14 tests; ID mutation test
  then failed before 0005; excess privilege/owner/inheritance probes failed six
  tests before guard implementation. One flaky test helper ordering was fixed
  by ledger transaction/line number rather than timestamp alone.
- Fresh verification: full server suite **150 passed in 53.72s**, no skips;
  recovery suite **266 passed, 4 skipped in 170.41s**. Development migration
  returns `0005_runtime_guards`; all eight invariant counters zero. `pip check`,
  compileall and whitespace checks pass. Secrets remain owner/SYSTEM-only.
- Context7 remains unavailable; official SQLAlchemy 2 constraints and
  PostgreSQL 18 GRANT/row-lock/pg_dump/pg_restore docs were fetched, with private
  copies under `work/m1-env/download`. No historical provider traffic.
- Independent review agent again failed before execution with provider 404.
  Scoped local inspection plus real-DB tests are evidence, not independent sign-off.
- Status: inventory/reward, explicit-delivery worker, schema restore/process-loss
  and runtime-grant functions are SERVICE_TESTED. M1.1 remains IN_PROGRESS for
  operational login provisioning, polling/backoff, reproducible Compose/Redis,
  CI integration/delivery review. Full content/import and native route wiring
  remain M1.2/M2+. No gameplay acceptance is claimed from these service tests.
- Delivery checkpoint includes the preserved, previously uncommitted M0 tooling,
  display patch and snapshot defaults as well as this M1 foundation. This keeps
  README commands and their code together. The local delivery is not a remote
  push or completed M0/M1 acceptance; the SDK-source distribution gate remains.

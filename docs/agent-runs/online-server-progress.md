# Online server execution progress

## 2026-09-17 - Source combat implementation continuation

- Resumed native-first Task3 after actual PG tutorial. Preserved dirty feature
  tree/live state; no SQLite runner or new test-only gameplay path.
- Added battle_bundle closure over pinned maps/mobs/roles/skills/buffs/math,
  including mandatory ship mob0 sentinel. Actual first-map dependency1105010
  is ambiguous; explicit versioned native dataApi lookup policy retains both
  candidates and selects exact native overwritten row, default remains denied.
- Extracted45reviewed pure source battle modules (not full app) with hashes/spans.
  Added bounded deterministic runner and end-tick manual skill input validation.
  Actual PGthree-role source10103 simulation wins3star818ticks, Luffy alone loses;
  legal skill produces692ticks, repeated reports identical. Source10107 under
  explicit lookup policy gives a real loss at level1, not a fake unlock.
- Scoped reviews no Critical/Important, follow-up IO/output guards fixed.
  Fresh focused checks/source hash/syntax pass. Evidence
  docs/release/2026-09-17-recovered-battle-engine.md. No native battle acceptance.
- Exact next: native seed/action recorder bridge + persisted authoritative
  session/report/settlement; map progression and real drop rules, then APK gate.
  Do not mark10107 playable from computation or trust legacy endSmap star.

## 2026-09-17 - Native opening activation

- Owner directed implementation after proposed opening choices; recorded exact
  native-opening-v1 policy/provenance, not claimed recovered historical rules.
- New metadata adapter binds exact SHA-pinned build manifest, config and notice
  under native process. Scoped review approved; no arbitrary asset serving.
- Built NativeAvailability+PowerDisplay APK run20260916T224402Z-repack, SHA256
  345ae73ff50ed4fd6e843d324cc1725ad1495a01026ea2382e7c51736e71f237. Three decoded
  JSCs match stage; embedded manifest matches hash
  0ec71ab180a4cc3311b4a241576327ebd642ed99fdbd8e977b1f7e8c5bb6d65c.
- kbht_dev read-only preflight: no players/servers, revision0006. Backup dump
  work/native-postgres/20260916T224544Z-activation/before-native.dump created and
  archive list verified, then explicit additive migration0014; invariants all0.
- Native runtime role/release setup preview passed. Review found existing-file
  private-ACL check missing; apply waits for fix/review, no publication yet.
  No compatibility runner or existing SQLite/physical-phone operations.
- Credential ACL fix reviewed approved; explicit opening activation succeeded,
  runtime role kbht_native_runtime with private credential and no persistent DDL.
  Published opening45e75135-f701-59bf-b2b7-57902755e9bf on new server1.
- Actual installed new APK hash verified; native register/login/create/home/
  first rename reached PostgreSQL. Read-only counts1player/1role/1opening grant,
  renamed1, invariant counters0. Guide pointScene opened; next recruitment route
  not implemented yet. No direct player seeding. Report native-postgres-opening.
- Tutorial implementation now follows exact source rows10001/class101 Zoro and
  10028/class201 Nami, deterministic first free outcomes. New immutable release
  and explicit existing-player repin required; current published release intact.
- Tutorial cutover review fixed exact opening-state compatibility checks before
  publishing/repinning. Stopped app/runtime, backup231131Z, migrated0015 and
  activateda900fe95-c468-578a-a734-5dac1c5ca48d with1player preserved. Runtime
  role additive SELECTtutorial definitions/claims +INSERTclaims only.
- Actual native pointScene now showed Zoro and Nami on respective first buttons.
  PG3roles, one coin claim/one gem claim, old opening grant1, coin0/gem50 unchanged,
  all invariants0. Evidence native-postgres-tutorial report/screenshots. General
  recruitment and battles/10107 remain unimplemented, no completion claim.

## 2026-09-17 - Native player implementation in progress

- Executing new plan Task2, not rewriting plan. Native player worker owns
  normalized0014 profile/role/skill/equipment/map persistence, source-backed
  content staging, atomic creation and compressed snapshot/entry.
- Controller added NativeAvailability opt-in patch, five exact original-source
  consumer guards (server list, gate, connector, shop badge, absent card catalog),
  staged only with preserved source hashes. No invented products/rewards or
  compatibility-runner fallback. Both PowerDisplay predecessors syntax checked.
- Ambiguous owned-role initialization remains required versioned policy input,
  not guessed historical rules. No content publication or kbht_dev migration.
  Runtime role provisioning remains an explicit separate prerequisite.
- No broad suite, device launch, source push or gameplay acceptance claimed.
- Availability review found aliasUrl could redirect a loopback-looking gate
  response; actual resolved host/port are now validated before connect. Fix
  reviewed addressed, no new Important issue. Six exact source pins retained.
- Implemented0014 normalized native state, draft-only content/policy staging,
  atomic create/entry/one-time rename and source300000ms resource recovery.
  Gateway now dispatches real create/entry/rename when release policy exists.
  Controller direct PG/native wire verification passed: compressed snapshot,
  four concurrent creates produce one player/grant, rollback, ownership,
  revoke-during-wait, recovery and relog with all ledger invariants zero.
  Generated schema removed, no live release/approval/native acceptance implied.
- Server task review pending. Remaining activation prerequisites are explicit
  owner-approved missing rule choices and published native definitions/runtime
  role grants; current content drafts are not silently published.
- Final scoped reviews approved after skill-prefix and missing class63 fixes.
  Controller fresh source/PG/native-wire check exits0, removes generated schema,
  and verifies compressed entry, create-once/concurrency, rollback/revoke/relog,
  resource recovery and ledger invariants. Guard staging both predecessors and
  Node branches/syntax pass; wheel includes all0014/players/content files.
- No default activation policy was fabricated. Exact missing owner choices:
  getPower second argument, initial skill prefix/levels, skill recovery cap and
  unavailable opening state. Hidden missing class63 is an explicit source
  compatibility choice. Until approved/published, native creation fails closed.
  No new APK/native acceptance or10107 claim; no commit/push.

## 2026-09-17 - APK visibly running on named MuMu lab

- Owner explicitly requested running APK. MuMu index2 KBHT-Online-Lab started,
  mapped to127.0.0.1:16448 by manager; physical Pixel left untouched. Existing
  firewall blocks verified. Backed up existing installed APK and SQLite state.
- Upgraded to signed InventoryBridge APK with install-r, firstInstallTime
  retained; installed hash afc37cc3fb77846c6e477fa6c507110e7405f9754c53d8f159a2542abddbd79c.
- Started one loopback compatibility runner with matching manifest and old DB,
  added four ADB reverse mappings, launched/showed native activity. Registered
  disposable account via UI, logged in, entered tutorial Luffy/home rename UI.
  No direct grants, live PG migration or existing account alteration.
- Native visible smoke details: docs/release/2026-09-17-native-visible-smoke.md.
  Runtime remains SQLite; PostgreSQL full player/bootstrap still incomplete.
  Emulator and runner left open for user. No commit/push.

## 2026-09-17 - M2 account/bootstrap implementation started

- Owner requested implementation after the bridge APK delivery. Continue existing
  M2 plan with opt-in loopback auth and inventory bootstrap, no public deploy,
  native install, SQLite conversion, full-player mock or content publication.
- Added dependency argon2-cffi25.1.0 with hash-locked transitive bindings26.1.0,
  cffi2.1.1 and pycparser3.0 to workspace venv. Existing dependency versions
  unchanged; pip check passes. No global Python change.
- Context7 tools unavailable; fetched official FastAPI handling-errors and
  argon2-cffi howto documentation. Node/Express-only backend skill not applied
  to this Python service; API boundary and Superpowers TDD/SDD apply.
- Baseline sessions/inventory-connection/HTTP38 passed19.32s against existing
  isolated PostgreSQL fixtures. New endpoint behavior and migration pending.
- Authored contract: docs/protocol/vn-online-bootstrap.md; `/v1` is not a
  historical provider API. Source51711ff uses form `/user/*`; complete native
  account/player bridge will need exact consumer mapping, not a fake snapshot.
- Task6 initial RED11 expected failures covered missing boundary/lock column,
  old scrypt hashing and unknown scheme acceptance. First GREEN31 passed14.46s
  (bootstrap + sessions + migrations); expanded focused73 passed37.33s before
  final read-deadline regression. Final review/full suite pending.
- Recovery/protocol393 passed9 Windows symlink skips115.89s, Node21 passed.
  A Windows unread-body reset found during HTTP tests prompted one bounded
  body-read path and total5s deadline before deferred header rejection.
- Final focused74 passed42.27s, no skips. Real HTTP registration/login returns
  owned inventory hello used by real Pomelo useItem/replay; receipt/invariant
  checks pass with explicit test-funded boxes. Tests cover revoke while snapshot
  waits, lock on an existing connection, password change during rehash and
  0012->0013 migration preserving account/password/session history.
- Wheel build includes bootstrap service/HTTP module and0013 migration; CLI
  serve-bootstrap help verified. Code frozen and independent review dispatched;
  full backend379 passed195.69s (379 collected after freeze). Independent review
  spec PASS/quality APPROVED, no Critical/Important within loopback scope. Minor
  deferred: two-owned-player non-null pagination cursor test. No public listener left running, live migration,
  APK rebuild/install, database cutover or commit/push in this task.

## 2026-09-17 - Acceptance correction after owner feedback

- Owner correctly identified that visible APK boot/tutorial is not a playable
  online-game delivery. The running APK used `server-compatible/src/game_server.py`
  with `game-playable3.sqlite3`, not the PostgreSQL `server-online` service.
- Root cause of map continuation failure is explicit: `server-compatible/src/game_rules.py`
  defines only 10101-10106 and `game_state.py:769` rejects 10107. The online route
  matrix also records missing buyCoin, equipment, friend, task and activity routes.
- The packaged InventoryBridge cannot activate because recovered
  `/user/register`, `/user/login`, `/user/serverInfo` and gate/connector flow are
  not wired to the new `/v1` bootstrap. It therefore does not change native game
  writes in the smoke run.
- Correct status: `NATIVE_BOOT_CONFIRMED`, `GAME_ENTRY_CONFIRMED`,
  `ONLINE_GAMEPLAY_NOT_DELIVERED`. No date is claimed for full completion until
  a real vertical slice passes native acceptance: PostgreSQL player bootstrap,
  10106->10107 authoritative battle/reward, then economy/progression/social
  routes with no SQLite fallback.

## 2026-09-17 - Native-client-first execution mode

- Owner requested stopping lab-as-product work. Stopped runner PID9560 only after
  verifying its command line targeted `server-compatible/src/game_server.py` and
  `game-playable3.sqlite3`; shut down MuMu `KBHT-Online-Lab` index2 and disconnected
  ADB endpoint16448. Physical Pixel remained untouched. Firewall rules unchanged.
- No new compatibility-runner routes will be counted as online delivery. The next
  implementation must consume the recovered native contracts at
  `project.js:51711` (`/user/register/login/serverInfo`), `39872` (player entry),
  `53958` (gate/connector) and `53521` (smap), with PostgreSQL as the only writer.
- First native vertical slice is 10106 -> 10107 using imported content and an
  authoritative battle/reward service. The SQLite six-stage runner is retired as
  an acceptance target; its tests remain historical regression evidence only.

## 2026-09-17 - New native-first spec/plan/runbook

- Added `docs/superpowers/specs/2026-09-17-native-client-first-online-slice.md`,
  `docs/superpowers/plans/2026-09-17-native-client-first-online-slice.md` and
  `docs/superpowers/runbooks/2026-09-17-native-client-first-online-slice.md`.
  These replace lab-runner acceptance for this work and define source refs,
  native status vocabulary and the 10106->10107 gate.
- Task7 implementer is working on exact recovered `/user/*`, gate and connector
  contracts. No compatibility runner, SQLite or native device action resumed.
- Native auth/gateway source and serve-native CLI are now implemented. Controller
  direct HTTP/Pomelo/PG protocol check passed, generated schema removed; this is
  wire evidence only. Review caught final-content-wait session revocation race;
  fix in progress, plus native initial heartbeat required by source40721ff.
- Client-first snapshot analysis found eager shop/card catalog reads and mandatory
  guide single recruitment; new plan now records those before the10107 gate.
  No fabricated goods, full player or additional roles were emitted.
- Independent native adapter review approved after final-content-wait session
  revalidation fix; native3second heartbeat sends initial package afterACK as
  required by actual client40721ff. Inventory-only transport retains no-op hook.
- Source-cited snapshot field contract saved to
  docs/protocol/vn-native-player-snapshot.md. Real starter role/equipment/stats,
  eager home dependencies, guide recruitment and unresolved opening policies
  are listed explicitly rather than copying the SQLite candidate.
- AGENTS/README/CHANGELOG route new execution to the replacement documents.
  No commit/push, device launch or deployment performed. Native adapter is
  wire-tested only; createPlayer/entry/maps still fail explicitly until Task2/3.

## 2026-09-17 - Resume native inventory integration review

- Preserved dirty `feat/native-game-entry` and all preceding source/evidence.
  Resumed unfinished Task4 review fixes through Superpowers SDD; no new plan.
- Prior packaging artifact `work/apk-vn/20260916T155928Z-repack` is signed and
  excludes InventoryBridge. Its SHA256 is
  `b7892b903f59f37f352a45516968ee3d8e418c7f8358920b58ab4964a22b2794`;
  no install/launch or online cutover was performed.
- Removed obsolete root E2E launcher from discovery by preserving it in the
  ignored SDD archive. Real Node/socket/PG acceptance remains in the backend
  suite, not skipped or mocked. Root collection now reaches tests without the
  backend package; initial broad result384 passed6skips1failure (PowerShell
  diagnostic line wrap only). Fixer owns that assertion correction.
- PostgreSQL was stopped after interruption. Started the same loopback25432
  cluster; WAL recovery completed and pg_isready accepts connections. Early
  tests failed during startup; fresh transport+real E2E then10 passed4.93s.
  No reset, development migration, SQLite mutation or live player grants.
- Review fixes and new opt-in packaging evidence follow below when verified.
  Native runtime remains IMPLEMENTED_NOT_VERIFIED; full bootstrap, content
  publication and organic box acquisition are still dependencies.

### Task4 fresh service/glue verification

- Fixed duplicate native error sync by making bridge onError authoritative.
  Real bridge and minimal source-cited native consumer tests cover errors,
  loading dismissal, snapshot tombstones, ordered deltas and one reward popup.
- Staging now requires explicit source-stage containment; rejects reparse and
  hardlink escape before mutation. Builder command executes in a temporary stage
  in tests, including optional PowerDisplay predecessor and syntax checking.
- Node21 passed; staging20 passed5 skipped (Windows symlink privilege only,
  junction and hardlink rejection passed). Full backend356 passed161.99s;
  separately transport+Node/PG E2E10 passed4.93s. Source/APK hashes match pins,
  pip check and route inventory check pass. Scoped fix re-review PASS/APPROVED:
  all three findings addressed, no new Critical/Important issue.
- Final broad recovery/protocol393 passed9 skipped107.21s; skips are Windows
  symlink-capability cases, not PostgreSQL or native acceptance. No native test
  was run. All existing uncommitted changes remain; no commit/push.
- Built signed opt-in InventoryBridge APK at
  `work/apk-vn/20260916T190803Z-repack/artifacts/vn-recovered-debug-signed.apk`.
  SHA256 `afc37cc3fb77846c6e477fa6c507110e7405f9754c53d8f159a2542abddbd79c`;
  matching manifest SHA256 `af3932c97bb23da816369e8ac751dbc922228778b1201003f0fde9bb33928816`.
  Decode/manifest/source verification returned `PACKAGING_VERIFIED_NOT_NATIVE`.
  APK signature v1/v2/v3 verified. No installation, launch or device mutation.

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

## 2026-09-16 - Leased worker, Compose model and M1.1 hardening

- Added `0006_outbox_delivery`: persisted READY/LEASED/RETRY/DONE/DEAD state,
  immutable retry budget, lease token/expiry, next-attempt and sanitized error
  code. Poller discovers registered event types, claims with `SKIP LOCKED`, fences
  stale workers and executes handler/receipt/DONE state in one transaction.
- Added direct-delivery quarantine and delivery reconciliation. Completed receipts
  win over stale leases; terminal DEAD/DONE records cannot reopen; retry budget and
  identity are immutable. Full server suite now reports 206 passed after all
  poller/ACL/recovery additions.
- Added `compose.yaml` with pinned PostgreSQL 18 dev/test and Redis 8.2.9 images,
  loopback ports, PostgreSQL 18 volume layout and required secret paths. Compose
  v5.5.1 binary plus hash/sidecar were verified; CLI model tests pass. Docker
  Engine is absent, so no container smoke or Redis health claim is made.
- M1.1 service evidence now covers inventory/reward, runtime ACL, process loss,
  schema restore, outbox consumer and leased poller. Operational login
  provisioning, engine smoke, production backup policy and real task processing
  remain. Next runbook task is M1.2 non-executing content import and legacy
  SQLite reconciliation after delivery review.
- Final checks after lease/receipt fixes: server **206 passed in 94.67s**;
  recovery **266 passed, 4 skipped**; Node formatter 1 passed; route inventory
  230/231 verified; Compose CLI config pass; `pip check`, compileall and diff
  checks pass. PostgreSQL `kbht_core` is at `0006_outbox_delivery` with eight
  invariant counters zero. Docker Engine is absent, so no container smoke claim.

## 2026-09-16 - M1.1 delivery checkpoint

- Current uncommitted continuation is bounded to leased outbox delivery and
  local Compose reproducibility. It does not add gameplay routes, auth, content
  import or native APK wiring.
- M1.1 service tests now cover the poller, runtime ACL, inventory/rewards,
  crash/restore and command ledger. Compose is validated by the official
  `docker-compose-v5.5.1.exe` CLI using digest-pinned images; Docker Engine is
  absent and the model has not been started.
- Next implementation task after this checkpoint is M1.2: non-executing
  content import from pinned `project.js`, validation of item/role/map references,
  immutable content version publication and read-only legacy SQLite reconciliation.

## 2026-09-16 - M1.2 normal-map draft continuation

- Preserved the uncommitted content/auth/HTTP work on `feat/native-game-entry`;
  no commit or remote push in this continuation. Root/backend README and
  CHANGELOG updated; corrected unsupported HTTP register/login endpoint claims.
- Added explicit sparse trailing-cell parsing without changing strict defaults.
  Chapter-type relationships, not ID ranges, select 376 normal stages across
  27 chapters. Literal transitions include 10106 -> 10107 and 10112 -> 10201.
  Provenance: `docs/protocol/vn-normal-map-content.md`.
- Added `0009_normal_maps`: immutable chapter source archive, version-scoped
  normal-map definitions and 3,722 ordered mob-wave references. Raw drops and
  excluded source rows retained. Draft preparation serializes same-import
  requests and atomically writes version/maps/waves. Replay compares actual
  saved projections; missing/changed/extra rows fail. Published projections
  reject mutation. Old smap-only imports backfill only against verified source.
- TDD: 22 new pure tests RED before parser/graph implementation, then content
  tooling35 GREEN; 11 PostgreSQL tests RED before migration/materialization,
  then content/map18 GREEN. A suppressed database-write regression failed
  before absent chapter results were rejected; map suite12 GREEN afterward.
  Tooling37 GREEN after additional sparse-row probes. Independent scoped review
  found missing rank-gap validation; two new tests failed before the fix, then
  content tooling39 and PostgreSQL content/map19 passed after the fix.
- Regression evidence: full online243 passed in103.72s; recovery/protocol303
  passed,4 skipped in109.76s before the final rank-gap guard. Final guard covered
  by the above39+19 reruns. Four skips are Windows symlink privileges, not skipped
  PostgreSQL tests. Node formatter1 passed; compileall, pip check and diff checks
  pass. Static route inventory230 routes/231 sites verified; no hosted CI claim.
- Independent scoped review `/root/map_review`: sole Important rank-gap finding
  fixed and re-reviewed ADDRESSED; final spec compliant / quality Approved.
  This is a task-level content review, not whole-branch or production sign-off.
- Initial DB baseline failed because portable PostgreSQL was stopped; documented
  `pg_ctl` command started the existing loopback25432 cluster. Only generated
  schemas in `kbht_test` were migrated/modified/removed by tests. No `kbht_dev`
  migration, player-state repair, SQLite mutation, APK install or client launch.
- SHA256 checks match pinned project.js and APK. Context7 tools absent; official
  PostgreSQL18 locking and SQLAlchemy2 transaction docs fetched/read. Private
  evidence and review material: `work/online-content-20260916/`.
- Status: bounded M1.2 map projection is SERVICE_TESTED, not full M1.2 or M6
  acceptance. Publication stays closed. Next: mob/skill/buff/item imports and
  full consumed-reference validation (mob ID0 sentinel and sparse skill rows
  mapped in provenance doc), then reward rules/release validation. Legacy SQLite
  reconciliation, actual battle/actions, runtime consumer and native flows remain.

## 2026-09-16 - M1.2 dependency archives and transitive reference audit

- Added `source.read_table_archive`, preserving ordered cells, missing trailing
  fields, duplicate IDs and mob0. Safe normalization supports literal !0/!1;
  strict `read_table` retains duplicate/nonpositive-ID rejection. No JS executed.
- Added `content/dependencies.py` and `archive.py`, migration0010 and
  `import-dependencies` CLI. Seven source tables and deterministic reference
  report are immutable evidence, not normalized/published gameplay definitions.
- Traced normal-map mobs -> skills -> buffs -> child skills/summoned mobs with
  cycle-safe visitation; checked displayed entities and equipment/consumable
  entity references. Extra skill levels/raw drop values retained, not invented
  rewards. Report records19,355 edges and14,063 consumed mob-skill bindings.
- Real source contains skill1105010 twice (rows466/467) and buff10006 twice
  (rows6/7); skill1105010 is transitively reachable. Report therefore has two
  DUPLICATE_ID and one AMBIGUOUS_REFERENCE and remains BLOCKED/publishable=false.
  No last-wins correction to source or publication bypass. Evidence and exact
  consumer references: `docs/protocol/vn-combat-content-dependencies.md`.
- TDD: parser9 RED -> GREEN, audit12 RED -> GREEN; DB7 RED before implementation.
  Concurrent import then exposed primary-key conflict outside the narrower
  conflict target; ON CONFLICT DO NOTHING plus exact post-insert bundle check
  fixed the observed race. DB7 passed; two additional real-DB mismatch/suppressed
  write probes also passed (final archive suite9 passed17.64s).
- Fresh broad verification: online250 passed117.95s; recovery/protocol326 passed,
 4 Windows symlink skips113.82s. Broad online run predates only the two added
  test cases (production code unchanged); final scoped run includes both.
- Independent read-only review found no Important/Critical issues. Its minor
  mismatch-coverage suggestion was implemented. Root/backend README, CHANGELOG,
  plan and active runbook updated. Work remains uncommitted; no push, live DB
  migration, SQLite changes, APK install/launch or player-state mutation.
- Next bounded task: compare duplicate definitions with recovered comparator
  and exact native lookup behavior; establish explicit versioned policy before
  unambiguous combat definitions. Remaining gates include numeric/effect/drop
  semantics, recipe cycles/acquisition, battle replay and native acceptance.

## 2026-09-16 - M1.2 equipment graph and durable draft

- Comparator SHA verified; ZIP has assets/assets/main/index.jsc, not VN's
  assets/src/project.jsc. VN pinned-native decoder was not misapplied. Combat
  duplicate resolution remains BLOCKED_EVIDENCE pending comparator loader or
  scoped native evidence; no default last-wins policy adopted.
- Continued independent in-scope equipment content: equipment.py validates
  matched IDs/types/effects/counts plus separate evolution/material cycles.
  120 equipment definitions and342 requirement rows match pinned source.
  Target30102 costs40102/42102/49902 x1 per client consumer19730-19733.
- Added equipment_store.py, migration0011 and prepare-equipment CLI. Atomic
  DRAFT includes immutable source snapshot, relational entities, definitions and
  ingredients. Exact replay comparisons, concurrent calls, rollback and published
  guards tested. No runtime item_definitions, inventory or game_servers writes.
- TDD:21 pure tests initially failed, then passed. Real source exposed terminal
  evolutionItemId0 in six max-tier records; corrected fixture/normalization to
  preserve raw0 and project null, consistent with consumer lookup. DB10 RED
  before persistence;10 passed after implementation.
- Fresh full tests: backend262 passed112.08s; recovery/protocol347 passed,
 4 symlink-permission skips96.48s. compileall, pip check, CLI help and diff check
  pass. Pinned project.js SHA unchanged. Independent scoped review found no
  Critical/Important issues and confirmed literal source counts/target costs.
- README/CHANGELOG/backend docs/plan/runbook updated. Work uncommitted; no push,
  player/SQLite mutation, development migration, APK install/launch or provider
  traffic. Tests use generated kbht_test schemas only.
- Next: source-backed material acquisition/drop-group graph and semantic checks;
  comparator loader/native evidence remains needed for combat duplicate policy.
  Equipment upgrade route, ledger spend, stats and APK acceptance remain open.

## 2026-09-16 - Drop structure and material acquisition audit

- Added content/acquisition.py with strict fixed/random descriptor grammar,
  W/R distinction, class/box reference validation and cycle rejection. Normal
  map previews count only repeatable stages; raw125 values are not quantities.
- Added audit-acquisition CLI and shared immutable bundle persistence using
  existing archive schema. Dependency archive IDs/digests remain compatible;
  acquisition uses material-acquisition-v1 and JSON-canonical replay comparison.
- Real report:379 drop rows,75 classes,37 class edges,19 boxes and78 materials.
  177 count0 rows remain unresolved. Material49902 has fixed box321 x6 and five
  direct drop rows, but no repeatable normal map. All materials remain static
  candidates with gameplay_verified=false. Source evidence recorded separately.
- TDD31 unit RED ->31 GREEN;5 DB RED -> combined acquisition/dependency14 GREEN.
  Fresh full suites: backend267 passed149.53s; recovery/protocol378 passed,
 4 symlink skips127.19s. compileall/pip/diff checks pass; project.js SHA unchanged.
- Independent scoped review approved, no Important/Critical findings; reviewer
  reran31 unit tests and checked literal49902 evidence, not DB/native acceptance.
- Updated README/CHANGELOG/backend README/plan/runbook/provenance. No new schema
  revision, development migration, inventory/SQLite mutation, APK action,
  publication, commit or push. Tests used generated kbht_test schemas only.
- Next: trace coin recruitment class102 and box321 acquisition/eligibility,
  settle drop-selection semantics before connecting a genuine material source
  to shared ledger/rewards. Combat duplicate policy and native gates stay open.

## 2026-09-16 - M3 fixed material-box command

- Added content/fixed_boxes.py staging and migration0012 definitions/reward rows
  tied to existing item definitions, explicit stack policies and matched DRAFT
  source hash. Published content guards and exact restage comparisons apply.
- Added economy/boxes.py command. Selected owned stack is consumed and fixed
  fragment rewards are granted atomically through shared item ledger/rewards,
  receipt and outbox. Safe payload,100-box service batch limit, content checks,
  tombstones and denied random/unsupported boxes. Default gateway stays unbound.
- Tested real authenticated HTTP command transport with durable sessions and
  explicit test-only route allowlist. Runtime gets SELECT-only recipe privileges;
  its attempted edit is denied. This is not native useItem/bagIndex mapping.
- TDD initial staging absence blocked fixture setup; after staging,13 handler
  tests failed correctly for absent command. Then19 passed. Runtime ACL test
  failed permission-denied before SELECT grants;22 passed afterward. Added
  restage/published/capacity tests:26 passed11.74s. Child-loss tests before/after
  commit both passed3.12s; final broad suite result follows.
- Broad initial run289 passed131.92s preceded six added test cases; recovery
 378 passed,4 symlink skips95.68s. Production unchanged during final test additions.
  compileall/pip/diff checks pass; original APK and project.js hashes unchanged.
- Independent scoped reviewer found no Critical/Important issues. Non-blocking
  suggested published-restage/drift/capacity coverage was added. Crash-test
  follow-up review requested separately.
- No source rewrite, live inventory seed, production/development migration,
  native install/launch, commit or push. PG test fixtures publish controlled
  content and fund opening boxes only in disposable kbht_test schemas. This
  proves service accounting, not an organic acquisition loop or native acceptance.
- Next: durable native bag identity/snapshot mapping, combined content release
  and actual box acquisition eligibility before enabling logic.playerHandler.useItem.
  Evidence: docs/protocol/vn-fixed-box-service.md.

- Final box checkpoint: full backend295 passed166.55s; crash/capacity assertions
  strengthened for outbox counts then targeted3 passed4.15s. Production code
  unchanged after full run. Follow-up independent crash-helper review found no
  Critical/Important issues. Recovery suite remains378 passed,4 symlink skips
 from this continuation. No native/client or organic acquisition claim.

## 2026-09-16 - M2/M3 opt-in native inventory adapter

- Added adapters/native_inventory.py: capability-gated native useItem payload
  translation to existing fixed-box handler and bag/reward response conversion
  inside the same receipt transaction. No latest-state reserialization on retry.
- Fresh online bag IDs use canonical decimal strings of stable inventory PKs;
  no new mapping table or legacy SQLite identity equivalence. Bag-only snapshots
  lock owned aggregate/content and reject mixed releases/unsupported item kinds.
- TDD19 tests failed for missing adapter;19 then22 passed with authenticated
  HTTP/revocation and safe-ID boundary probes. Added snapshot/commit concurrency
  probe and _temp.route regression (failed before fix); final scoped result23
  passed. Tests explicitly seed controlled inventory, not real acquisition.
- Full backend317 passed155.28s; recovery378 passed,4 Windows symlink skips
 107.30s before final _temp.route change/concurrency test addition. Final scoped
  suite covers those additions. compileall/pip/diff checks pass; source unchanged.
- Independent review found no must-fix issue; nonblocking _temp.route omission
  addressed. New-online identity choice and reconnect replace-vs-merge caveat
  documented in docs/protocol/vn-native-inventory-adapter.md.
- No production/development migration, public/default route activation, native
  patch/build/install/launch, SQLite change, commit or push. No native acceptance.
- Next: negotiated gateway/version queue and full player snapshot/reconnect;
  retain organic box-acquisition/release publication gates.

## 2026-09-16 - M2 negotiated inventory connection

- Added adapters/inventory_connection.py and native_inventory reexport. One
  object per transport connection negotiates protocol/capability using durable
  token auth, selects owned player/server/content, clears binding on failure,
  and revalidates session before command/snapshot. No account identity from body.
- Reconnect returns replace-bag snapshot and forwards exact original receipt
  envelope unchanged. No command-ID/version rewriting or fabricated full player
  snapshot. Cross-scope commands denied; unsupported capabilities not granted.
- Connection methods serialize; close waits for admitted command completion.
  Token revoke is an admission check, not forced cancellation of in-flight TX.
  Snapshot-time invalidation is checked before returning data. Tokens remain
  only private process binding, cleared on close and absent from outputs/repr.
- TDD22 tests RED for missing connection, then22 GREEN. Expanded26 then28
  passed17.29s with snapshot/resync-time revocation and concurrent-close probes.
  Full backend344 passed179.53s (before final two test-only additions were
  discovered); final28 scoped includes both. Recovery378 passed,4 Windows
  symlink skips113.94s. compileall/pip/diff checks pass; source SHA unchanged.
- Independent scoped review found no Critical/Important findings; suggested
  resync-revoke and close-serialization coverage added. No listener, new schema,
  default route, APK patch/action, live/SQLite change, commit or push.
- Next: transport handshake integration and client queue/version ordering;
  full snapshots/account creation and actual acquisition/release gates remain.
  Contract: docs/protocol/vn-inventory-negotiation.md.

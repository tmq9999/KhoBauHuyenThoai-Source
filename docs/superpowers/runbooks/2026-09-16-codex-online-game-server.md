# Codex Runbook: Kho Báu Huyền Thoại Online

Executor: Codex. Date: 2026-09-16. The owner approved the online-server direction
and switched the execution handoff from Antigravity to Codex. This is the active
runbook; the 2026-09-14 Antigravity document remains historical recovery evidence.

[Spec](../specs/2026-09-16-online-game-server-design.md) |
[Implementation plan](../plans/2026-09-16-online-game-server.md) |
[Reported defects and route matrix](../../protocol/vn-online-route-matrix.md)

## 1. Instruction to start execution

```text
Read AGENTS.md, the online-server spec, route matrix and implementation plan.
Execute the first incomplete task in M0, then progress in dependency order.
Use installed Superpowers: using-superpowers, executing-plans or
subagent-driven-development, systematic-debugging, test-driven-development,
requesting-code-review and verification-before-completion as applicable.
Preserve existing source edits, player state, native engine and recovery evidence.
Build a PostgreSQL-authoritative online server and admin system, not a set of
success responses. Each feature must include acquisition/spending/progression,
durability, error/retry behavior, client response and native verification.
Update README.md and CHANGELOG.md in each deliverable commit and verify them
after commit. Never report a roadmap checkbox done from a unit test alone.
Stop only for new authority, an unresolved safety gate, or a specific blocking
dependency; continue other independent in-scope tasks when safe.
```

This document authorizes no new production deployment, live payment, broad
filesystem cleanup or unknown-device install. Those operations require the
owner's scoped permission when reached. An already connected ADB serial is not
permission. The earlier `emulator-5554` authorization was for the named lab;
re-check that it is still the same isolated instance.

## 2. Read current state, not stale completion claims

At the start of each resumed execution:

```powershell
Set-Location 'D:/GeminiWorkspaceNew/KhoBauHuyenThoai'
git status --short
git branch --show-current
git log --oneline -8
git remote -v
Get-Content -Raw AGENTS.md
Get-Content -Raw README.md
Get-Content -Raw CHANGELOG.md
Get-Content -Raw docs/superpowers/plans/2026-09-16-online-game-server.md
```

If the checkout is dirty, record exact paths and preserve them. Use the current
feature branch for this handoff; create isolation only after consent and ensure
all current dependencies are included. The source snapshot includes
`game_rules.py`/`game_content.py`, both required by the working runner. Verify
they are tracked before moving to a worktree. Never reset, clean, amend or
force-push the user's work.

Baseline facts to re-check:

- Git exists on `feat/native-game-entry`; the five recovery commits through
  `e1a2045` are preserved beneath the source snapshot. Read current HEAD with
  `git log`, not this historical hash. No `git init` is needed.
- `server-compatible/src/game_server.py` is the lab runner; `probe_server.py`
  deliberately rejects application routes.
- APK in use: `work/apk-vn/20260915T112626Z-repack-first-map-runtime/artifacts/vn-recovered-debug-signed.apk`.
  SHA256 `f5564e5c375266ec41258d3dc4729c6ce2550cc420f2548ff537b6798a042156`.
- Matching manifest: `work/apk-vn/20260915T112626Z-repack-first-map-runtime/lab-bootstrap/project.manifest`.
- Existing local player DB: `work/apk-vn/20260915T001024Z-game-entry/runtime/game-playable3.sqlite3`.
- 2026-09-16 install returned Success, and a runner was launched with PID 24488.
  PID is historical, not safe to kill/reuse. Verify the live process/ports.
- Backup made before that launch:
  `work/apk-vn/20260915T194734Z-server-launch/state-before-start.sqlite3`.
- Historical tests: 215 passed, 3 skipped. Owner screenshots still show real
  defects; those test counts are not acceptance of gameplay.

Run the scoped baseline, never bare pytest at repo root (it discovers archived
copies under `work/`):

```powershell
python -m pytest -q tests server-compatible/tests/protocol -p no:cacheprovider
git diff --check
```

Test output, APK source hash and change list go in a unique private run folder.
Capture only sanitized diagnostic fields; never paste tokens/passwords/payment
payloads into logs, docs or chat.

## 3. GitHub private source repository

Requested display title: **KhoBauHuyenThoai Source**. Valid repository slug:
`KhoBauHuyenThoai-Source`. Use the authenticated owner's account, verify it with
the owner if it differs from `tmq9999`, and require private visibility before
pushing any content. Never overwrite an existing `origin`.

On 2026-09-16 the owner created the repository. `gh repo view` confirmed
`tmq9999/KhoBauHuyenThoai-Source`, `isPrivate=true`; Git read access succeeded
and `origin` was configured to the URL below. The earlier authentication and
approval blocker no longer prevents the first source upload. Always compare
remote/local SHA to determine whether a particular commit has been pushed.

Recovery when authorized tooling is available:

```powershell
gh auth status
gh api user --jq .login
gh repo view tmq9999/KhoBauHuyenThoai-Source --json nameWithOwner,isPrivate,url
git remote -v
```

Reuse the existing private repo; do not create a second repository. Do not treat
auth or permission errors as "repo absent". If authentication is invalid, the owner
logs in using `gh auth login`; never request a PAT in chat or read credential
files. If escalation is denied, do not switch tools to circumvent it.

Before the first push, scan the **entire reachable history** and staged tree:
private repo is not a secrets exemption. Exclude APK binaries, signing keys,
SQLite/DB backups, raw logcat, `.env*`, provider secrets, tokens and `work/`
runtime data. Recovered third-party source/assets may also have redistribution
restrictions; private visibility is not a license. Inspect the currently tracked
`work/apk-vn/20260915T001024Z-game-entry/run/battle-report.md` separately. If history contains secrets, stop and
plan rotation/removal with the owner; do not rewrite history silently.

After source/doc commit and verified private repository:

```powershell
git remote get-url origin
git push -u origin feat/native-game-entry
git ls-remote origin refs/heads/feat/native-game-entry
git rev-parse HEAD
```

Expected origin: `https://github.com/tmq9999/KhoBauHuyenThoai-Source.git`.
Add it only if origin is absent; do not replace a different existing remote.
Substitute a different authenticated owner only after identity verification.
Success means remote SHA equals local SHA and `isPrivate=true`. Preserve all
existing commits. No automatic merge/PR/publish is implied by a source backup.

## 4. Work unit protocol

For each task in the plan:

1. Read the cited APK builder, full callback/consumer and relevant data rows.
   Produce source references and a literal fixture independently of the server.
2. Name the missing behavior and write the failing regression against a real
   service/DB or socket. Observe the expected failure, not only an import error.
3. Implement the smallest complete vertical path: schema -> domain command ->
   adapter -> response/notification -> client. Use the shared ledger/reward path.
4. Test success, denied ownership, invalid fields, insufficient resources,
   rollback, retry, concurrent requests, restart and business-day transition.
5. Run read-only review. Use subagents only as directed by the selected skill
   and with non-overlapping tasks. If agents fail (previous provider `404`),
   do the scoped review locally and record that no independent review happened.
6. Perform native smoke when the matching release is ready and lab authority
   is confirmed. A feature awaiting native smoke is `IMPLEMENTED_NOT_VERIFIED`,
   not done. Do not repair test data with grants just to make gameplay pass.
7. Update plan task status and the progress log. Update README technical
   structure/contracts/configuration/usage and CHANGELOG release changes
   **before** committing them together. Session status, test counts, rules and
   temporary blockers belong in the run/progress documents, not README.
8. After commit verify files/sha; record commit SHA in the next progress entry
   (a commit cannot contain its own SHA). Push only if private remote is verified.

Maintain one progress file during implementation:
`docs/agent-runs/online-server-progress.md`. Create it in M0 with task ID, status,
files, test command/result, evidence refs, decision owner and exact next step.
Do not create a replacement plan after every error. Source plan remains the
single task list; run reports contain evidence, not duplicate roadmaps.

Status vocabulary: `NOT_STARTED`, `IN_PROGRESS`, `IMPLEMENTED_NOT_VERIFIED`,
`VERIFIED`, `BLOCKED_AUTHORITY`, `BLOCKED_EVIDENCE`. A blocker names the missing
symbol/decision/tool, attempts and an independent task that can still proceed.

## 5. Execution order and handoffs

| Milestone | Owner-facing result | Prerequisite | Mandatory gate |
| --- | --- | --- | --- |
| M0 | Defect fixtures, complete route inventory, release/content identity, integer power display contract | current recovery sources | exact source references, no game mutations; docs and CI policy |
| M1 | PostgreSQL schema, ledger, command receipts, content import, SQLite migration rehearsal | M0 | zero unexplained import diffs; transaction/concurrency/restore tests |
| M2 | Durable auth/session, native adapter snapshot, defaults, error and retry protocol | M1 | client command-ID/reconnect tests; no public GM route |
| M3 | Beli/gem/AP, inventory, boxes, shop, material acquisition paths | M2 | balances/ledger agree; purchase retry and actual item use through APK |
| M4 | Stats, equipment level/max/all, skills, stars/evolution | M3 | owner's equipment and power screenshots corrected; valid resource sources |
| M5 | Real free/paid single/ten recruitment and duplicate conversion | M3/M4 | RNG/guarantee rules pinned, outcomes persistent, no repeated tutorial gift |
| M6 | Full normal-map continuation, authoritative battle/abilities, sweep and rewards | M2-M5 | 10106->10107->next chapter; forged results denied; all basics reachable |
| M7 | Friends, gifts, daily/weekly tasks, sign-in, mail | M3-M6 | two-account flow; reset, event dedup and once-only claims |
| M8 | Admin RBAC, user/item/game/notice/event management, content publication | M1-M7 | role matrix, preview/audit/approval, real UI+API tests |
| M9 | Top-up orders/gifts, refunds/withdrawal record workflows | M3/M8 | authenticated sandbox callback, reconciliation, two-person approval |
| M10 | Synchronized native release and online staging readiness | M0-M9 | restore/load/security/native checklist; no unresolved core 500 |

Expand arena/guild/boss/ship/advanced tier plans only after those definitions
and runtime contracts are captured. Track them explicitly, never claim the
whole game's 36 scenes work from first-session acceptance.

## 6. Environment and database discipline

New production implementation root: `server-online/` (does not exist yet).
Admin UI: `admin-panel/` (does not exist yet). M1 creates an installable backend
package, lockfile, migrations and `compose.yaml`; M8 creates the UI build.
Commands below are **future interfaces**, not commands claimed to work today:

```powershell
# After M1 creates package/dependencies and isolated Compose services:
python -m pip install -e './server-online[dev]'
docker compose --project-name kbht-dev up -d postgres redis
python -m kbht_server.cli migrate --environment development
python -m kbht_server.cli import-content --source client-recovered/src/project.js --dry-run
python -m kbht_server.cli check-invariants --environment development
python -m pytest -q server-online/tests
```

Only install/download through approved network access. Fetch version-specific
library docs with Context7 when available; otherwise record official sources
and version. Do not fabricate Context7 results. No global JDK/SDK/Python changes.

Dev defaults: DB and Redis bind loopback, database `kbht_dev`, separate test DB
`kbht_test`; destructive test setup refuses other database names. DSNs/secrets
are read from ignored environment files, never command-line strings in reports.
Tests must never point at the existing SQLite or a production DSN.

Migration rehearsal: backup SQLite read-only -> isolated PostgreSQL import ->
counts/ledger/inventory/ID mapping reconciliation -> reopen/retry -> report.
Cutover is a separate approved maintenance operation with the spec rollback
procedure. A schema migration is not permission to wipe old state.

## 7. Native client/server synchronization

Preserve `client-recovered/src/project.js` as the pinned recovery input.
Create reviewed transforms/patches under `client-recovered/patches/` and stage
them via the existing builder; keep source hash, patch hash and resulting hash.
An imported content snapshot, gateway schema and APK patch must share a release
ID: `{sourceCommit, apkSha256, contentVersion, rulesVersion, protocolVersion,
schemaRevision, manifestSha256}`.

Power formatting changes apply at the shared UI formatter/read sites, not a
single label. Missing `vip.buyCoinTimes`/point/task/friend defaults are corrected
in the versioned snapshot serializer and its migration, not only visual fallbacks.
Patch only the transport wrapper for command IDs/ability inputs unless the
specific consumer requires more. Preserve original scene/resources/JNI IDs.

Current build command (available now, packaging only):

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -Sign
```

For a lab smoke, first verify APK/signature/hash/manifest pair, DB backup, device
identity and these firewall rules are enabled/block:
`KBHT-MuMu-egress-temp-device`, `KBHT-MuMu-egress-temp-main`. Do not disable Wi-Fi
if it would break the emulator ADB link. Start one runner only, bound loopback.
Then authorized installation can use:

```powershell
$labAdb = 'C:/Users/tranm/AppData/Local/Android/Sdk/platform-tools/adb.exe'
& $labAdb -P 5037 -s emulator-5554 get-state
& $labAdb -P 5037 -s emulator-5554 reverse tcp:20001 tcp:20001
& $labAdb -P 5037 -s emulator-5554 reverse tcp:20003 tcp:20003
& $labAdb -P 5037 -s emulator-5554 reverse tcp:20100 tcp:20100
& $labAdb -P 5037 -s emulator-5554 reverse tcp:20101 tcp:20101
& $labAdb -P 5037 -s emulator-5554 reverse --list
```

Resolve the exact newly built signed APK path before `install -r`; never use a
glob or pick only by timestamp. Verify installed hash, package/activity and
firstInstallTime retained. Do not uninstall or `pm clear` to fix an upgrade.
Client hot-update cache must match the same release; preserve unknown cached
data for diagnosis, not broad deletion. Record raw logs privately and redact
before committing.

## 8. Acceptance and operational stop gates

Native core checklist: fresh/returning account; home integer power; roster and
equipment upgrades; new/retried recruitment; map continuation and abilities;
item reward visible and still present after relog; Beli counter/price/debit;
sign-in/daily task once; two-account friendship/gifts; notice/mail/event claims.
Every row needs DB invariant + wire test + screenshot/trace reference. A test
requiring seeded items is a service test, not proof the gameplay economy works.

Admin checklist: login/MFA, role denial, user ban/revoke, item/currency preview
and two-actor approval, notice publish and cancel, event preview/activation,
gift qualification, payment sandbox reconciliation, audit export and restore.
Payment/withdrawal real operations remain disabled until their explicit gate.

Release stop conditions:

- Any unexplained wallet/quantity change, duplicate reward or ownership bypass.
- A core route returns generic 500 or client shows NaN/undefined for valid state.
- Server trusts client star/damage/loot without validating an authoritative report.
- Private visibility, device identity, egress block or signing provenance unknown.
- Database migration/restore not rehearsed; production exposure unapproved.
- Build/test command advertised in README is absent or has not been run.

Keep dev/CI usable when these gates block public release; finish independent
safe work and record the precise gate. Do not call it a production game early.

## 9. Commit and documentation contract

Every deliverable commit includes `README.md` and `CHANGELOG.md`. README explains
technical structure, contracts, configuration and exact usage commands. It is
not a milestone dashboard, agent instruction file or execution journal.
Next tasks, test-run evidence and blockers go in the plan/progress log.
CHANGELOG records user-visible changes, migrations/compatibility and known issues
under an accurate date/Unreleased entry. Historical tests retain their dates;
fresh verification is identified separately.

Stage explicit paths, inspect staged diff/secret scan, then commit. Afterward:

```powershell
git show --name-only --format=short HEAD
git show --format= --name-only HEAD -- README.md CHANGELOG.md
git status --short
```

If either document is missing, create a follow-up docs correction with both
files; do not amend without permission. The correction describes the actual
previous commit SHA, not a fabricated build version. M0 adds a CI policy check
that enforces both files per delivery commit with a documented initial-history
baseline; legacy history is preserved, not retroactively rewritten.

## 10. Handoff format

```text
Milestone/task and status
Commit (or uncommitted paths) and README/CHANGELOG verification
Rules/content/protocol/schema/APK version
Tests executed + counts/skips + evidence paths
Native flows verified vs still pending
Data changed, migrations/backup/rollback status
Open findings/decisions and scope blocked by authority
Exact next task, command and required input
Private repository URL/SHA only when actually verified
```

The next executor starts M0 from the implementation plan. It does not resume
JSC decompilation, launch Antigravity, or restart the current lab process merely
to read this runbook.

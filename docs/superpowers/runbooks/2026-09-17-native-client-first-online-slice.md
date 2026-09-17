# Native-client-first execution runbook

This replaces lab-runner acceptance for the current slice. Read the spec,
`AGENTS.md`, route matrix and this runbook before execution.

Active documents: [spec](../specs/2026-09-17-native-client-first-online-slice.md)
and [plan](../plans/2026-09-17-native-client-first-online-slice.md). This file is
the active runbook; the2026-09-16 runbook supplies only retained operational
safety rules. Owner approved immediate execution, no repeat plan approval.

## Resume and ownership

Use the existing `feat/native-game-entry` checkout as owner previously directed.
Run `git status --short` and preserve all unrelated edits. Read
`docs/agent-runs/online-server-progress.md`, then work the first incomplete native
task, not an old M0 checklist. Existing native adapter work is old-plan Task7
in `.superpowers/sdd/2026-09-16-online-game-server/`; preserve that ledger identity
and map it to new Task1 rather than copying/moving or redispatching it.
Further new-plan work records progress under its own named SDD directory.

One implementer owns gateway/CLI at a time. Use bounded read-only review after
the implementation. Source hashes, errors and verified wire behavior matter;
there is no full-suite-count gate that substitutes for a playable APK.

## Startup discipline

1. Stop any compatibility runner only after checking its command line and PID.
2. Start PostgreSQL loopback only; migrate explicitly, never seed players/items
   through the command line. Use a disposable schema for service checks.
3. Start `serve-native` with the same process lifecycle for form HTTP, gate and
   connector. Bind `127.0.0.1`; no provider/payment/analytics traffic.
4. Build a fresh signed APK from the pinned source. Record APK/source/manifest
   hashes. Never reuse an unrelated manifest or install on a physical phone.
5. For the named isolated MuMu only, verify egress firewall blocks, device
   identity and ADB reverse ports. Preserve app data with `install -r`; never
   uninstall or `pm clear` to repair a test.

## Native flow gate

Capture sanitized request/response traces and screenshots for each step:

1. `/user/register` -> `/user/login` returns native `{uid,token}`.
2. `/user/serverInfo` lists only open/published PostgreSQL servers.
3. Gate queryEntry with `{uid}` returns connector host/port.
4. Each connection performs handshake and client HANDSHAKE_ACK, then connector
   entry validates token/server/oldServerId.
5. `getPlayers` returns owned rows. `createPlayer` persists a real player;
   `entry` returns the full client-consumed snapshot or fails explicitly.
6. Home/team opens with no undefined counters or fractional power; complete
   original rename and guide-required single recruitment without direct grants.
7. Begin 10106, finish server-verified battle, then select 10107. Reward and
   map progress persist after relog. Forged client star/report is rejected.

Stop and record `BLOCKED_NATIVE` if any full snapshot field or content rule is
missing. Do not add a success response merely to move the screen forward.

## Evidence and shutdown

Run only focused source/protocol checks while implementing; no broad SQLite
regression can substitute for native acceptance. Store release evidence under
`docs/release/` and session details under `docs/agent-runs/`. On failure capture
the exact route, callback fields, server log code and screenshot, then stop the
APK/servers cleanly. Keep PostgreSQL backups and immutable APK/source hashes.

## Concrete current commands and limits

From repository root, after the explicit PostgreSQL migration has been approved
and performed on the chosen database:

```powershell
& './server-online/.venv/Scripts/python.exe' -I -m kbht_server.cli serve-native --help
$env:KBHT_DB_PASSWORD_FILE = (Resolve-Path 'work/m1-env/secrets/postgres-superuser.txt').Path
& './server-online/.venv/Scripts/python.exe' -I -m kbht_server.cli serve-native --environment test --host 127.0.0.1 --http-port 20003 --gate-port 20100 --connector-port 20101
```

Credential path is the existing local lab owner configuration, never a public
runtime account. Do not print password/token values or leave tokens in command
arguments. Listener start creates no servers/content/players. Native metadata
20001 is enabled by --manifest and --manifest-sha256 in the same process.
Native create/entry requires published starter content/policy. Do not start the
old SQLite runner to supply missing pieces. Run the listener under the separate
native runtime role, not the migration-owner credential shown above.

No screenshot/boot experiment is requested now. When the native slice is ready,
validate the owner's named isolated instance again (manager index2
KBHT-Online-Lab, historically loopback16448); do not infer identity from an ADB
serial. A connected physical Pixel is not authorized. Firewall blocks remain
enabled. Previously granted boot-smoke authority is not permission for a
production migration, public bind or real-money operation.

Every delivery updates root README technical commands and CHANGELOG changes,
plus the single progress log. Commit only a reviewed coherent batch with both
documents; do not sweep the dirty tree into a commit. Remote push stays blocked
by the recorded historical-source secret/distribution review, not by test count.

## Delivery status vocabulary

`STATIC_CONTRACT`, `SERVICE_TESTED`, `WIRE_TESTED`, `NATIVE_CONFIRMED`,
`BLOCKED_NATIVE`. Only `NATIVE_CONFIRMED` can move a route out of missing for
this slice; service tests and APK boot alone cannot.

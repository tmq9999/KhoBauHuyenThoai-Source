# Recovered native APK client (partial)

Current owner directive: no Lab/emulator/ADB execution. Follow the
[online backend runbook](../docs/superpowers/runbooks/2026-09-17-apk-online-backend-delivery.md).
Commands/artifacts below are retained as historical build references, not the
current task queue. `-OnlineProfile` is planned, not implemented. NativeBattle
staging exists in checkpoint990d8dc but does not establish APK battle acceptance.

Status: **EDITABLE_CLIENT_BUILD_PARTIAL**, native lab boot/home confirmed. The editable `src/` files are exact copies of recovered JavaScript. Android resources, smali, and native libraries remain from the original Apktool tree; native C++ and a complete Cocos project have not been recovered.

For the installed MuMu client and working game runner, use the
[server/emulator instructions](../server-compatible/README.md).
The native client has reached home, first rename, recruitment and team selection.
Packaging, boot, individual protocol flows and complete-game parity are separate milestones.

Validate without creating a run:

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -ValidateOnly
```

Repack edited JavaScript into a fresh unsigned APK:

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1
```

Each run stages a copy under `work/apk-vn/<UTC>-repack/`, verifies selected payloads directly against the pinned APK ZIP, encodes only `settings.js`, `jsb_polyfill.js`, and `project.js`, and writes `repack-build-report.md` with sanitized commands, exit codes, and hashes. The original APK and baseline are never overwritten. No APK is installed or launched and no network/provider is contacted.

Optional disposable lab signing uses build-tools 34.0.0 and a project-owned key:

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -Sign -CreateDebugKeystore
```

Signing is not the original signature. This workflow proves packaging only (`APK_REPACKED`), not boot parity, full source recovery, or server compatibility.

The local-account/loopback lab variant is built with:

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -Sign
```

Add `-CreateDebugKeystore` only if the project lab key does not yet exist.
These flags patch a fresh build stage, not the recovered reference `src/`.
Serve the generated `lab-bootstrap/project.manifest` from the same build run.
The installed artifact verified on 2026-09-16 is the
`20260915T112626Z-repack-first-map-runtime` run (SHA-256
`f5564e5c375266ec41258d3dc4729c6ce2550cc420f2548ff537b6798a042156`);
server-only handler changes do not require rebuilding or reinstalling it.

The M0 display-only patch is opt-in with `-PowerDisplay` together with both lab
flags. It formats power labels without changing combat values or pinned source.
The signed run `work/apk-vn/20260915T212249Z-repack` has been built and its JSC /
manifest payloads verified, but it has not been installed or native-smoke-tested.
Use that run's manifest when testing it; keep the installed artifact separate.

## Opt-in online inventory bridge

```powershell
pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -LabBootstrap -LabLocalAuth -PowerDisplay -InventoryBridge -Sign
```

This embeds the ES5 bridge and guarded socket hook into staged `project.js`,
then encodes it into the existing `project.jsc` payload. The reference source
is not modified. `-InventoryBridge` requires both lab flags; `-PowerDisplay`
is optional. `-ValidateOnly` checks build inputs, not this transform or APK boot.

The trusted bootstrap must call `window.kbhtInventoryIntegration.attach(options)`
with `inventoryIdentity="postgres-v1"`, matching player/server selection, a
session token and content hello, loopback inventory URL, WebSocket/timer deps,
`getPlayer`, `sync`, `showRewards`, `nextActionId` and `suspendLegacy` callbacks.
There is no automatic credential conversion or full online bootstrap. Before
activation legacy behavior remains unchanged; after activation legacy requests
are fenced, including after detach, to prevent two independent database writers.
Only the bounded fixed-box useItem path is supported. Pair every APK with its own
generated manifest and use only the isolated lab; packaging is not native proof.

The latest packaged bridge artifact is
`work/apk-vn/20260916T190803Z-repack/artifacts/vn-recovered-debug-signed.apk`
(SHA-256 `afc37cc3fb77846c6e477fa6c507110e7405f9754c53d8f159a2542abddbd79c`).
Its matching manifest is under the same run's `lab-bootstrap/project.manifest`.
The payload was decoded and compared with the staged source after signing;
device install/launch was not performed.

## Native PostgreSQL availability guards

`-NativeAvailability` is an opt-in patch for the full native gateway path. It
requires `-LabBootstrap -LabLocalAuth` and may include `-PowerDisplay`. It cannot
be combined with the separate inventory-only `-InventoryBridge` protocol.
The existing lab flags select local endpoints and skip the historical SDK;
they do not select SQLite or turn this into native gameplay acceptance.

This stages five narrow consumer guards: unavailable server lists, rejected
gate/connector responses, empty normal-shop badges and absent paid-card catalog
entries. No products, balances, roles or rewards are invented. Existing populated
catalog rendering remains unchanged. The original source is hash-pinned and
untouched; every replacement requires an exact unique source pin and the expected
prior local-auth/display transformation.

`tools/apk-recovery/prepare-native-availability.py --help` exposes the staging
interface; the builder invokes it within its validated source stage. Creating
an artifact with these guards does not activate PostgreSQL player entry by itself.

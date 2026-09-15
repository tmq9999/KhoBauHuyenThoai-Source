# Recovered native APK client (partial)

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

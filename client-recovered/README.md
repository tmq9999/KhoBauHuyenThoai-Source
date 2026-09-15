# Recovered native APK client (partial)

Status: **EDITABLE_CLIENT_BUILD_PARTIAL**. The editable `src/` files are exact copies of recovered JavaScript. Android resources, smali, and native libraries remain from the original Apktool tree; native C++ and a complete Cocos project have not been recovered.

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

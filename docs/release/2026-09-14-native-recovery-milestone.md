# Native APK recovery milestone — 2026-09-14

## Completed with real evidence

- Recovered the three bootstrap JSC blobs using the APK native loader's actual XXTEA → gzip path.
- settings.js: 237,138 bytes, SHA-256 9c172efdc2c20f0543d25bce3a40c42b6aa6e8953bff873d1e8ec914ef482d47.
- jsb_polyfill.js: 549,023 bytes, SHA-256 a5ba198936479dbbdaf14c03a88f9e70eb56a01509956b6ac963c93f886ac4a3.
- project.js: 6,039,275 bytes, SHA-256 9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818.
- All three pass node --check without executing source. jsb_polyfill.js directly declares cc.ENGINE_VERSION="1.10.3". project.js has279 top-level module-header candidates (202named +77numeric); this is static structure, not a claim that every module is understood.
- Settings index: 37 serialized scenes including test.fire, 3,472 raw assets, launch logo_scene, landscape. Product scene count remains 36 after excluding test.
- Client-recovered contains editable recovered JS copies, provenance ledger and a reproducible Apktool repack script.
- Actual unsigned build succeeded; project debug signing succeeded. apksigner verified v1/v2/v3; v1 META-INF version-file warnings remain and are not treated as boot verification.
- Signed APK: work/apk-vn/20260914T142000Z-repack/artifacts/vn-recovered-debug-signed.apk.
- Signed APK SHA-256: 42afcb97b7a3a3170e545380aa5853a088301d18aaf823093d1a3114b59c2791.
- Package/activity/ABI match original: com.kbht.gg, org.cocos2dx.javascript.AppActivity, arm64-v8a/armeabi-v7a/x86, minSDK16/targetSDK26.

## Protocol evidence and code

- Recovered project.js uses Pomelo WebSocket framing, handshake/heartbeat, route dictionaries/protobuf tables and gate→connector→player bootstrap routes.
- Static contract and protocol-marker report have source lines/offsets; runtime-confirmed values remain UNKNOWN.
- server-compatible contains a stdlib codec/probe (not a playable production server); application route responses deliberately remain UNKNOWN.

## Verification

- Final combined run: python -m pytest -q -p no:cacheprovider tests/apk-recovery server-compatible/tests/protocol tests/tooling/test_reference_integrity.py: 77 passed, 2 skipped (Windows symlink privileges).
- Decoder/input/output preservation and protocol-probe review findings addressed. No remaining Important/Critical finding in scoped reviews; native runtime/production gameplay remains unverified.
- Python source compilation: pass for tools/apk-recovery, client-recovered/scripts and server-compatible/src.
- build-repacked.ps1 -ValidateOnly: pass.
- Input APK SHA-256 unchanged: d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4; 7,083 ZIP entries; full ZIP CRC test found no bad entry.
- Decoding all3 JSC members from the signed APK matches client-recovered/src byte-for-byte. Build uses the recovered source, not the original opaque JSC blobs.

## Not yet verified

- ORIGINAL_CLIENT_BOOT: NOT_RUN. Connected ADB device is not verified disposable emulator; no install/launch performed.
- Full Cocos editor project/native C++ source: NOT_RECOVERED; native .so remains prebuilt.
- PROTOCOL_VERIFIED_RUNTIME and SERVER_COMPATIBLE_GAMEPLAY: NOT_RUN.
- No original provider endpoints, accounts, payments or remote scripts were contacted or executed.
- Complete per-ZIP-member inventory/asset dependency validation is still open; ZIP entry count/CRC and selected pinned input/source/payload hashes were verified.

## Working files and reproducible command

- Editable source: client-recovered/src/settings.js, jsb_polyfill.js, project.js.
- Build/sign: pwsh -NoProfile -File client-recovered/scripts/build-repacked.ps1 -Sign -CreateDebugKeystore.
- Original raw/decoded evidence stays under work/apk-vn/20260914T180000Z and work/apk-vn/20260914T140500Z-efc5da6a.
- Coordination/loader proof: work/apk-vn/20260914T135911Z-efc5da6a. Run directory names are identifiers; the inherited baseline and manually supplied repack names must not be treated as measured execution timestamps.
- Windows LLVM tools required sandbox escalation; Context7 was unavailable, so CLI behavior and the local APK source were checked directly. No framework or web dependency was installed.

## Next exact work

Use the signed APK only in an isolated disposable lab with egress blocked; capture original boot/login scene and traffic to locally controlled endpoints. Continue mapping actual client consumers and fill compatible server routes one group at a time. Do not reintroduce web demo/synthetic-v1.

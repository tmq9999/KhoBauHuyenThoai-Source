# APK-first development

- Always start with the installed Superpowers using-superpowers skill, then the relevant implementation/testing/verification workflow.
- Owner's objective: decompile and recover APK/KhoBauHuyenThoai-VN.apk, rebuild that native client, then implement its observed protocol. APK/sp-071023.apk is a comparator.
- Continue the existing reconstruction plan at docs/superpowers/plans/2026-09-14-vn-apk-client-reconstruction.md. Read client-recovered/README.md and the latest native recovery report before changing client build/loader/protocol.
- Work from recovered JavaScript, Android glue, resources and native evidence. Do not substitute a web demo, mock UI, synthetic gameplay/server, or a new Cocos shell. Ask before changing engine or replacing recovery with a rewrite.
- Preserve original APK hashes and previous evidence. Keep decoded reference files separate from editable client-recovered/src. Never claim prebuilt .so files are recovered C++ source.
- Repack/sign success does not prove APK boot, visual parity or server compatibility. Report these milestones separately with real evidence.
- Use disposable, network-isolated lab devices for APK runtime. A connected ADB device is not permission to install, overwrite, or launch on it. Do not contact historical provider/payment endpoints or log tokens/keys.
- Keep progress concrete: source files, decoder output, APK artifacts, tests and client traces. Do not spend another turn generating replacement plans or reviewing retired web code.
- For online-server work, read `docs/superpowers/specs/2026-09-16-online-game-server-design.md`, `docs/protocol/vn-online-route-matrix.md`, `docs/superpowers/plans/2026-09-16-online-game-server.md` and `docs/superpowers/runbooks/2026-09-16-codex-online-game-server.md` before editing server/admin code. Execute the Codex runbook, not the historical Antigravity runbook.
- Every deliverable commit must include an accurate `README.md` and `CHANGELOG.md` update. A unit-test pass is not native-client or online-service acceptance.

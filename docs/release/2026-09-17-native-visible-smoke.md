# Native visible lab smoke — 2026-09-17

User requested actually running the APK. Selected MuMu index2 named
KBHT-Online-Lab, VM MuMuPlayerGlobal-15.0-2, created timestamp1789536513770329.
Manager reports its ADB endpoint127.0.0.1:16448. Connected physical Pixel device
was not used. Both KBHT-MuMu-egress-temp-device/main firewall rules remained
Enabled/Outbound/Block, matching running main/device executable paths.

Installed artifact: work/apk-vn/20260916T190803Z-repack/artifacts/
vn-recovered-debug-signed.apk. Installed base.apk hash verified:
`afc37cc3fb77846c6e477fa6c507110e7405f9754c53d8f159a2542abddbd79c`.
Old/new signer certificate digest matched; adb install-r returned Success.
First install timestamp retained2026-09-16 12:34:34; last update2026-09-17
04:50:34. No uninstall or pm-clear. App is not debuggable; no run-as data export.

Private run: work/apk-vn/20260917T-native-visible-smoke. Contains prior installed
APK and state-before-start.sqlite3 backup (SQLite integrity_check=ok). Existing
state source remains game-playable3.sqlite3. No old player overwritten.

Runner PID9560 was launched after verifying ports vacant, bound127.0.0.1 only:
20001/20003/20100/20101, matching new build manifest. MuMu reverse bindings map
those four ports. Native activity com.kbht.gg/org.cocos2dx.javascript.AppActivity
was foreground; application PID1947 at capture time. PIDs are historical evidence,
not permission to kill/reuse a later process with the same number.

Observed through the native UI:
- Fresh disposable lab account registered, then logged in.
- Local server selected; gate20100 then connector20101 connected.
- Tutorial Luffy recruitment screen displayed; home power label shows980.
- Home rename dialog rendered. Screenshots boot.png, logged-in.png,
  server-select.png, home.png and current-game.png remain in private run.

Runner/app intentionally left open for owner. This is native boot/game-entry
evidence against server-compatible SQLite only. The packaged inventory bridge is
inactive until trusted online bootstrap; no PostgreSQL gameplay acceptance,
full game, public deployment, combat or organically acquired materials claimed.

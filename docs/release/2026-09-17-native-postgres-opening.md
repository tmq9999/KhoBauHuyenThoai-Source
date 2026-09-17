# Native PostgreSQL opening execution

This run uses server-online PostgreSQL, not the historical SQLite compatibility
runner. It confirms account creation/login/native player creation/home/first
rename only. Recruitment and map10107 are not completed by this evidence.

## Release identity

- APK run: work/apk-vn/20260916T224402Z-repack.
- APK SHA256:345ae73ff50ed4fd6e843d324cc1725ad1495a01026ea2382e7c51736e71f237.
- Manifest SHA256:0ec71ab180a4cc3311b4a241576327ebd642ed99fdbd8e977b1f7e8c5bb6d65c.
- Published opening content:45e75135-f701-59bf-b2b7-57902755e9bf.
- Rules digest:c158b5c870ef1b376215112b3603d24a3a4ab5ae42d3b4a2a8720840294d3099.
- Policy: server-online/config/native-opening-v1.json; source-backed starter
  constants plus explicitly authored rules in vn-native-opening-v1.md.
- Schema0014_native_players. Original APK/project source hashes unchanged.

## Operations

kbht_dev preflight had revision0006, zero players/no servers. Created backup
work/native-postgres/20260916T224544Z-activation/before-native.dump (archive
listing checked, not a new restore drill), applied additive0014 and verified
all nine invariant counters zero. Explicit reviewed native_setup --apply created
only new opening release/server1 and restricted kbht_native_runtime role.
Password file generated exclusively under ignored private path with private ACL;
existing credential reuse checks ownership/ACL/links. No plaintext password SQL.
Public TEMP capability inherited from database defaults is unchanged; role has
no persistent schema/definition DDL privileges. This is loopback-only, not public.

Runtime wrapper process7648/python18884 at capture time served all four ports
20001,20003,20100,20101 on127.0.0.1. Identity query returned kbht_native_runtime,
not migration owner. Historical PIDs must be rechecked before later operations.
No server-compatible process or SQLite access in the native runtime.

## Actual client path

MuMu manager verified index2 KBHT-Online-Lab, creation1789536513770329,
ADB127.0.0.1:16448. Both egress Block rules remained enabled. Physical Pixel
untouched. Install-r succeeded; installed SHA matches new artifact, original
firstInstallTime2026-09-16 12:34:34 preserved, lastUpdate2026-09-17 05:51:58.

Native UI registered an account through /user/register, logged in through
/user/login, selected server, passed gate/connector, called createPlayer, showed
starter Luffy and home, then renamed through logic.playerHandler.rename.
Read-only PG evidence: accounts1, players1, owned_roles1, opening_grants1,
first_rename_completed1, wallets gem50/coin0/AP60/skill10. All nine invariants0.
Home displayed integer power1059 under the declared opening rules.

Force-stop/relaunch/login/entry retained one player/role/opening grant and renamed
name. After elapsed recovery, native UI showed AP61 matching PG, skill wallet11,
all invariants0. Private relog.png records persisted home. No DB state repair.

Private screenshot evidence under work/native-postgres/20260916T224544Z-activation:
login.png,entry.png,home.png,renamed.png,recruit-open.png. Login-field screenshots
may include credentials and must not be published/committed. Only sanitized
game screens should be shared. Guide advanced to actual original pointScene;
recruitment route remains unavailable until next release, no fake role granted.

## Limits

This is native-confirmed onboarding, not finished Task3/gameplay. Map entry,
server-authoritative battle, tutorial single recruitment, later economy/social
features and public deployment still need implementation and native evidence.
No first-map or1-7 claim is inferred from reaching home.

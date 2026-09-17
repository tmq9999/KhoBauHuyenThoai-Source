# Acquisition audit checkpoint

Implemented safe descriptor parsing, structural drop/box graph checks and
per-material static candidate reporting. CLI `audit-acquisition` archives
source/report under its own format in the existing immutable PostgreSQL table.
No new migration or gameplay route.

Real source:379 drop rows,177 zero-count rows,19 boxes,78 required materials.
Material49902: box321 contains6 units; five direct drop rows mention it; no
repeatable normal map previews it. These are candidates, not gameplay proof.
No rates, zero-count interpretation or normal-map125 quantity was invented.

Verification:31 new unit tests RED then GREEN;5 new DB tests RED then GREEN;
combined acquisition/dependency archive14 passed. Full backend267 passed in
149.53s; recovery/protocol378 passed,4 Windows symlink skips in127.19s.
Independent scoped review approved; compileall/pip/diff checks passed.
Source hash unchanged. No native-client acceptance claimed.

Work uncommitted; no push, development migration, player-state/SQLite change,
APK installation/launch or provider traffic. README/CHANGELOG/plan/progress
updated. See [evidence and remaining gates](../protocol/vn-material-acquisition.md).

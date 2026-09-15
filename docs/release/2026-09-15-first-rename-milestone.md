# First-name milestone — 2026-09-15

## Implemented

- Added a loopback Pomelo `logic.playerHandler.rename` path for the recovered first-login flow.
- Persisted the selected name in the existing SQLite player row without changing the immutable account username, player ID, role data, home fixtures, or gem balance.
- Bound the route to the authenticated connection's selected, owned player. Failed entry clears that selection.
- Made the first-name write transactional; same-name retries succeed, paid/different follow-up renames remain unsupported.

## Verification

```text
python -m pytest -q server-compatible/tests/protocol/test_game_state.py server-compatible/tests/protocol/test_game_server.py -p no:cacheprovider --basetemp .pytest-tmp/rename-review-check
28 passed
```

The tests use real loopback sockets, masked WebSocket frames, SQLite persistence, rollback triggers, and concurrent stores. No APK was installed or launched during this milestone.

## Remaining boundary

The next runtime check is the signed recovered APK on the already identified disposable MuMu target. It must show the original first rename panel advancing into home before this route can be labeled runtime-confirmed. No historical provider or payment endpoint is contacted.

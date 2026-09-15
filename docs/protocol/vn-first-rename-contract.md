# VN first-name contract (static + local server evidence)

This note records the smallest name flow needed to pass the recovered first-login panel. It does not claim compatibility with paid renames.

## Static client evidence

`client-recovered/src/project.js` shows `renamePanel.onYes_` calling `logic.playerHandler.rename` with `{name}`. The first-name branch runs when `userName == playerName`; it then emits the create-player/login events and advances the first guide. The client does not send a player ID in this request.

## Local implementation

`server-compatible/src/game_server.py` accepts the route only after the connection has selected an owned player through `connector.playerHandler.createPlayer` or `connector.playerHandler.entry`. `server-compatible/src/game_state.py` updates only a player whose stored name still equals its immutable `userName`; a retry with the same name is idempotent, while a second different rename returns the fixed application error. The update is transactional and ownership-scoped.

The local input guard rejects empty, whitespace-only, non-printable, non-string, and over-64-character names. This is a lab safety policy, not a recovered historical length rule. No gem deduction or paid rename behavior is implemented because no server evidence proves it.

## Evidence labels

- **STATIC_INFERRED:** route, request field, first-name branch, and absence of a client-side player ID.
- **LOCAL_TEST_CONFIRMED:** ownership, selected-player requirement, retry behavior, persistence, rollback, cross-owner rejection, and concurrent first-name selection in the loopback server tests.
- **RUNTIME_CONFIRMED:** not yet run through the disposable APK lab after this route was added.

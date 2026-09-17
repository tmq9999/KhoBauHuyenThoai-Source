# Native inventory boundary — 2026-09-16

Source project.js SHA256:
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.

Recovered bag constructor/update at5837-5850 uses an object of items, sets
each record's `idx` to its object key, and deletes falsy/tombstone entries.
getItemCount reads `kindId` and `count`. UI5757 passes `_item.idx` and a numeric
quantity to useItem; builder39959 sends `{bagIndex,itemCount}`. player.update
40126-40129 merges `bag.items`; callback5761 reads `_temp.entityCountMap`.

## New online-only identity policy

For a new PostgreSQL inventory, the bag key is the canonical positive decimal
string of inventory_items.id, bounded by9007199254740991. The existing PK and
ledger references make it durable; no additional generated mapping table is
needed. Zero, booleans, floating/exponent strings, padded/noncanonical strings
and unsafe IDs reject. This is an explicit new online policy, not a claim that
an old SQLite bagIndex already equals a PostgreSQL primary key. Legacy import
still needs an explicit old-to-new mapping.

`NativeInventoryAdapter` requires a trusted caller identity and explicitly
negotiated `native-inventory-v1` capability. It accepts only the existing durable
command envelope plus route logic.playerHandler.useItem and exactly the two
native payload fields. Bare legacy messages are not silently promoted. The
gateway must authenticate and negotiate before calling; capability is not auth.

The transactional handler calls the fixed-fragment-box service, serializes its
saved result to bag.items `{kindId,count}` records/null tombstones and reward
entityCountMap, then CommandExecutor saves that exact response. Later replay
does not query newer inventory state. `_temp.route` uses the full request route
for the new adapter so player.update's temporary cache has an explicit key.

Snapshot locks the owned player then active published release in the same order
as mutation commands, returning a consistent aggregate version/content version
and bag. It excludes zero stacks and rejects foreign/mixed-version state and
unsupported item classes rather than discarding required metadata. Current
support is deliberately limited to staged fixed boxes and their fragment kinds.

## Boundaries still open

Outer response remains the versioned command adapter envelope. This is not a
Pomelo listener/full player snapshot, error-to-legacy code mapping or a client
queue/version-gap implementation. Full snapshots must replace/reset the client
bag on reconnect; passing a full snapshot through merge-only bag.update would
retain items absent from it. Delta responses use tombstones for that reason.

No APK patches/build/install/runtime were performed. Default HTTP serve remains
closed to gameplay routes. Tests explicitly enable a negotiated bridge with
durable sessions; fixture opening boxes do not prove organic acquisition.
Combined release publication, identity migration, remaining snapshot fields,
transport negotiation and APK smoke remain mandatory before cutover.

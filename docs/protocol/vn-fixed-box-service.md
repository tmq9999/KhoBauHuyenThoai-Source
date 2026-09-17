# Fixed material-box command boundary

The source-backed box321 descriptor at project.js19273-19274 contains twelve
green fragments at1 each and49902 at6. Fixed preview at5720-5727 describes all
contents; descriptor reader49941-49958 supplies the quantities. The source hash
remains9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818.

`stage_fixed_box` reads verified entity literals and stages only fragment-only,
fixed descriptors into an existing DRAFT whose source hash matches. Required
item definitions and stack policy must exist first. No guessed maxNum=-1 cap,
random weights, currencies or role extras are accepted. Raw box/reward entity
records accompany normalized recipe quantities. Migration0012 links recipes to
item definitions and prevents edits after publication.

Core handler `economy.boxes.use_fixed_box` consumes `inventory_id` and quantity,
not native bagIndex. Under CommandExecutor it validates ownership, published
content, safe counts and an operational100-box batch ceiling. The ceiling is a
new service resource limit, not a recovered gameplay rule. It debits only that
owned stack and grants the persisted recipe via RewardService in the same TX.
Item ledger, reward grant, two outbox events and saved command result commit
together. Retry never reapplies; stale/different inputs conflict. Inventory
projections expose zero-quantity rows as null tombstones.

Test HTTP apps explicitly register `inventory.useFixedBox` behind durable bearer
session resolution. Default `serve` still has no gameplay registrations. Native
builder39959-39965 uses `logic.playerHandler.useItem` with bagIndex/itemCount;
that is not silently equated with PostgreSQL IDs or the new core DTO. Native
mapping/version negotiation and `_temp.entityCountMap` serialization are pending.

Tests create opening inventory using existing test-only ledger helpers; these
are not a real source of boxes. No public grant endpoint, live seed or native
acquisition claim is added. Material acquisition, combined publication, runtime
account provisioning and actual APK flow remain acceptance gates.

Durability probes exit a disposable child process after handler mutations but
before commit, and immediately after executor commit. Retry in a new connection
must produce one consumed box and one reward in both cases. Probes accept only
generated kbht_t_* schemas in kbht_test; they never kill a real server process.

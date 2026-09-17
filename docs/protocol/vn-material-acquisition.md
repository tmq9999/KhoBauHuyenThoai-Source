# Material acquisition evidence — 2026-09-16

Source project.js SHA256:
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.
Static evidence only, not a reward sampler or gameplay acceptance.

## Descriptor contracts

Client49941-49958 parses `entityId x count` and optional
`entityId_field_value x count`. Thus `49902x6` means six units and
`100201_star_2x1` retains star2. Client49959-49978 parses `_Wweight` or `_Rrate`.
The server parser keeps weights/rates distinct without inferring probability
scale or sampling. Invalid segments reject the whole input rather than silently
dropping part of a reward. Only this bounded literal grammar is accepted.

Box preview5720-5727 distinguishes random choices from all fixed contents. It
does not prove eligibility, RNG or how the containing box is acquired.

## Structural checks and findings

- 379 drop rows,75 classes,37 distinct class-reference edges. Checks cover IDs,
 groups, exactly one class/entity target, references, positive weights,
 nonnegative integer counts and cycles. Raw extra fields are preserved.
- 177 rows have count0: retained as unresolved, not positive reward sources.
- 19 box descriptors; nested box references reject missing entities and cycles.
- 78 required equipment materials have at least one static candidate; every row
 remains `STATIC_CANDIDATES_ONLY`, `gameplay_verified=false`.
- Repeatable normal-map previews follow itemFromPanel26560. Nonrepeatable previews
 are not treated as farmable sources. Other modes/eligibility are outside scope.

Material49902 has no repeatable normal-map preview. Box321 explicitly contains
six units. Positive direct rows10010,10054,10113,10115,10118 belong to
classes102,301,613,614,615. POINT.CONSTS.COIN_CLASS_ID=102 at49931 establishes a
static recruitment mapping, not a working acquisition route or validated RNG.
Nested class references are validated but no class probability/multiplier or
invoked-root reachability is claimed.

Normal-stage specifyDropValues125 remains raw, not a quantity. The consumer
at19214 uses that field for **endless** chapter401; this does not establish its
meaning for normal maps.

## Durable report and next gate

CLI `audit-acquisition` stores sources+report in existing immutable
content_dependency_archives under format `material-acquisition-v1`. It coexists
with the dependency archive and compares complete bundles on replay. No new
migration, published rules, inventory grant, wallet or server activation.

Next: map class invocation/eligibility and actual draw semantics, then implement
one acquisition/spending loop through ledger/rewards. Count0 meaning, probability
scale, box acquisition, combat duplicate policy and native acceptance remain
open. Finding a candidate never licenses a test grant as gameplay evidence.

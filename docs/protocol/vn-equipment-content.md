# Equipment draft evidence — 2026-09-16

Source project.js SHA256
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.

`eqptScene.genData` at19730 looks up the current item's `evolutionItemId`, then
at19732 checks the resulting target's `requiredIds` and `requiredCounts`. Thus
source30101 -> target30102 consumes40102,42102,49902 at one each. It does not
read source30101's null requirement arrays as a free evolution.

The source has120 equipment records (six chains of20),342 material lines and
six terminal zero references:30120,30220,30320,30420,30520,30620. All equipment
entities have type `evolutionItem`; all342 required slots point to `fragment`
entities. `maxNum=-1` is preserved and is not converted to a guessed stack cap.
Raw numeric effects are retained without inventing their combat formula.

Validation checks safe positive IDs and quantities, matched entity identities,
finite numeric effects, duplicate materials, dangling next-tier/material refs
and cycles. Evolution-next edges and recipe dependencies are separate graphs:
their directions have different meaning and must not be merged for cycle tests.
Raw entity/recipe source is snapshotted; zero terminal markers become null only
in normalized next-tier pointers.

Migration0011 creates equipment_source_snapshots, equipment_entities,
equipment_definitions and equipment_requirements. A separate DRAFT digest pins
source+projection format. Full replay comparisons detect missing/altered/extra
rows; publication is not provided and no game_server or inventory rows change.
These drafts cannot substitute for a validated combined gameplay release.

## Comparator check and retained combat gate

`APK/sp-071023.apk` SHA256 was verified as
`b69427af63e668364a20c64c3a9d9440e498f9e88c15ddbe233fe5929edaf14b`.
ZIP inspection found no `assets/src/project.jsc`. Instead it contains
`assets/assets/main/index.jsc` (2,255,072 bytes), settings.jsc and separate
engine/adapter assets. The VN decoder is pinned to a different native binary;
it was not applied to this comparator blindly. No comparator code ran and no
decryption key was printed. Duplicate skill1105010 and buff10006 therefore
remain unresolved; no last-wins server policy has been adopted.

Next safe work: map the comparator's loader/bundle when needed; independently
trace material acquisition and drop-group semantics. Equipment commands still
need owned-role state, shared transaction/ledger spending, stats, protocol
translation and real native verification.

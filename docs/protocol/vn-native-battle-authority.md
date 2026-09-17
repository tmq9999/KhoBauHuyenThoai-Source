# Native battle authority implementation contract

In progress, not native battle acceptance. Recovered source hash
9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818.

## Exact client lookup compatibility policy

`vn-data-api-observed-lookup-v1` reproduces the actual lookup algorithm in
project.js18445-18454: iterate ordered rows, assign `data[row.kindId]=row`.
This is an explicit source-derived compatibility decision for the user's
client-first requirement, NOT proof of the historical server's intended data.
The battle builder defaults to rejecting duplicates unless this policy is
explicitly requested. It resolves only these hash-pinned pairs:

| Table/id | Candidates, 1-based source data row | Selected |
| --- | --- | --- |
| fightSkill/1105010 |466:23de13cbc33f9bf7145e0b0c8c55ad9b7dc56881dd97ff3fc5cb503efc0bdad6;467:b948f90a0014333c6fa21c71638b5f10b729d7994b64d1d46a3269bd2245b4ce |467 |
| buff/10006 |6:2d5de81cdadfc6e58b38b3872a5ae4e6d8e2c86ee8ec3b98a951fbdea40f54c5;7:7b28ce5d2bd8db23761ee3ad5e7a58e4d78bb6c1dcc946981f9edfc1bc0fbd56 |7 |

Every reached conflict retains both rows, hashes, chosen ordinal and policy in
the bundle digest. Any new/different conflict fails; no general silent last-wins.
Raw archival evidence/imports are not rewritten or retroactively approved.

## Engine seam

Allowlisted source battle modules are extracted with original span/hash evidence;
the full recovered application, SDK, provider and UI modules are not executed.
The driver supplies validated table lookup, explicit nonzero uint32 seed and
deterministic stepping of the original scheduler/actions. Presentation messages
are captured, not rendered. Missing data/capability/limit fails computation.
Only server-owned persisted team inputs may call the wrapper; exposing raw team
JSON from a player as authority is prohibited.

The initial no-input engine now also accepts bounded manual first-skill commands
`{zone,tick,skillId}`. Tick means the end of the recovered50ms tick; the original
timer increments its tick counter then consumes useSkillIds. Zone/tick must be
monotonic, same-tick distinct skills retain recorded input order, at most256.
Actor must be owned/living and full-MP; skill cooldown and once-use checks are
explicit server admission policy. Native UI only checks its light state at click
time, so not every original click is guaranteed accepted; bridge must surface
denial/resync and preserve actual consumed-tick order. Ships remain unsupported.

Native battle activation additionally
requires server seed/action bridge and replay parity. Source map dependency
closure is not a publication gate for drops or battle rewards.

## Explicit remaining gates

Manual native queue/pause parity, multi-wave native parity, published content and
readiness, AP/attempt state, authoritative report persistence/settlement and
organic item-drop semantics remain. `specifyDropValues=125` is retained raw;
no fake fixed loot or auto-win routine is permitted. Client star is never proof.

`client-recovered/patches/battle-command.js` now provides an ES5 recorder for
server battleId/nonzero seed, original consumed zone/tick/skill order, bounded
action count and frozen settlement retry. It is NOT staged or activated yet.
Successful server acknowledgment must match battleId before clearing state;
starting another battle while the previous one is unresolved fails. The star
field remains only a client report for comparison, never settlement authority.
Every seed/consume/settlement call also requires the bound battleId to reject
late callbacks from an older scene. The future native hook must capture that ID
in its scene/timer, not read a mutable global latest battle ID at callback time.

## Focused source computation evidence

Using a read-only snapshot of the actual three PostgreSQL tutorial roles and
unique source map10103, seed12345: no manual input wins3stars in818ticks; same
Luffy alone loses wave2 in972ticks. Fresh processes repeat exactly. Legal input
zone2/tick231/skill100101 wins in692ticks; invalid early/foreign/duplicate/unused
commands reject. No player state or progression is changed by these computations.
With explicit client-lookup policy, map10107 is simulatable; the current level1
team/no manual input loses in1203ticks. This is not a native10107 acceptance or
permission to fake a win. Source engine extraction45modules carries exact spans
and body hashes; reviewed artifact hash
73a690818bc83f3857c7032cae8340f723963691efc2baa3194a7be788486168.

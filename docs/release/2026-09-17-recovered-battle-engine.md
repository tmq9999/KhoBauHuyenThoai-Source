# Recovered battle engine implementation

Source-computation checkpoint, NOT native battle/10107 acceptance.

Implemented allowlisted extraction45modules, isolated Node driver and Python
trusted-input wrapper in server-online/battles. Exact recovered battle formulas,
AI, actions, scheduler, targets, buffs and RNG remain; UI/provider/whole bundle
are not executed. No auto-win, direct loot or client-star settlement added.

Original source SHA9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818;
artifact SHA73a690818bc83f3857c7032cae8340f723963691efc2baa3194a7be788486168.
Output includes original onOver outcomes, remaining state, actions, input/artifact
hashes and event digest. Fresh child/context per run, no inherited credentials
or preload options, dynamic code/ambient time/random denied, bounded input,
output, steps, memory and execution. Node VM is defense-in-depth for pinned code,
not an arbitrary hostile-code sandbox claim.

Verified actual persisted PostgreSQL tutorial-team snapshot read-only, source
map10103 seed12345: three roles win3stars818ticks; same actual Luffy alone loses
wave2,0stars972ticks. Repeat reports match in fresh processes. Manual first skill
100101 at zone2/tick231 wins692ticks; early/foreign/duplicate/unconsumed/unordered
inputs rejected. No stats or mob values were modified to force these results.

Native dataApi source has duplicate1105010/10006. Default bundle build rejects
reachable ambiguity. Explicit vn-data-api-observed-lookup-v1 reproduces only the
two exact source row-overwrite cases with both candidates retained and digest
bound. This is client compatibility, not historical backend intent. With that
explicit policy,10107 computes a real loss for current level1/no-action team in
1203ticks. No stage is unlocked and no reward issued by this computation.

Independent initial engine and manual/input-policy scoped reviews found no
Critical/Important issues. Fixed follow-up suggestions: total subprocess timeout
covers stdin feeding; pipe close errors sanitized; extractor refuses path escapes/
links/different-existing output. Direct extractor, syntax, five source probes,
manual and bundle checks rerun successfully. No broad SQLite suite or native
acceptance substituted for missing runtime work.

Remaining: native staged seed/action queue bridge and actual queue/pause parity,
durable battle session/report/replay, map unlock/AP/attempt and reward settlement,
validated drop semantics/content activation, actual APK10106->10107 proof.
No live database migration, provider/device action, APK build or source upload
was performed during this engine task.

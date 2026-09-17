# Native opening rules v1

The owner instructed immediate implementation in response to the proposed opening
rule choices. These are versioned new-server rules, not recovered historical
backend facts. Exact policy: server-online/config/native-opening-v1.json.

- Initial level1 uses getPower second argument1 (role level); the current starter
  implementation rejects progressed role levels rather than keeping this fixed
  argument for later progression. A progression implementation must version or
  derive the argument from actual role level.
- Starter Luffy owns source skill100101 at level1, no awakening skills. Owned
  skills form the prefix expected by the original native skill consumer.
- Opening AP60/skill10; AP cap61 at level1; skill cap15. Source interval300000ms
  drives capped, ledgered recovery when entering/reconnecting.
- Hide absent source role class63 to prevent friendship consumer dereference.
- Source-preview floor-growth math is chosen for owned starter attributes.
- Unimplemented activity/shop/mail/task/social/battle state is explicitly
  unavailable/empty; no fake goods, paid products, rewards or completed progress.
  open_days1 is informational for this opening-only release, not event eligibility.

This policy enables only persisted onboarding: register/login/create/entry/first
rename/recovery. It does not approve fabricated tutorial recruits, client-star
settlement, unresolved normal-map drops, public deployment or complete gameplay.

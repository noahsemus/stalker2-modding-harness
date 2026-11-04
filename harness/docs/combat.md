# Combat internals: damage resolution and NPC corpse looting

Native logic read out of the retail exe (`reverse-engineering.md` for the method), joined with the cfg values that
feed it. **Build stamp for every address on this page:** retail `Stalker2-Win64-Shipping.exe`, 174,730,288 bytes,
dated 2026-08-28; addresses are VAs at the default image base `0x140000000`. They will move on a patch; names and
mechanisms survive. Sources per number: **[bin]** read from the exe, **[cfg]** from `GameLite/GameData`,
**[inferred]** where stated.

## Damage resolution
| VA | Role |
|---|---|
| `0x140cb0446` | main hit/damage resolution (~9.5 KB) |
| `0x140cb358f` | pre-scale: friendly-fire scaler x `BoneDamageCoefficients` x headshot difficulty multiplier |
| `0x140cb2ce6` | picks `ArmorDifferenceCoefProjectiles` / `...MeleeAttacks` by `EDamageSource` |
| `0x140cb3da3` | strike protection getter (effect param id `0x46`) |
| `0x140749799` | protection getter for every other `EDamageType` |
| `0x140cb2d75` | armor core: exponential term, calls the two below |
| `0x140cb303e` | deflect roll |
| `0x140cb3a44` | per-damage-type / per-source armor term |
| `0x1434a856b` | thin wrapper over the same core (3 other call sites) |

```c
// main, one hit. ctx: Damage +0x00, ArmorPiercing +0x08, bIgnoreArmor +0x18, InstigatorObjIndex +0x20
// (0xFFFFFFFF = none), DamageType +0x78, DamageSource +0x79
dmg *= FriendlyFireScaler;                                   // 1.0 vs hostiles
if (type == Strike && src not in {Explosion, Knife, WeaponButt})
    dmg *= ObjPrototype.BoneDamageCoefficients[bone];
if (player shooter) dmg *= PlayerWeapon_HeadshotMultiplier;  // difficulty
dmg = max(dmg, 0);

prot = (type == Strike) ? StrikeProtection(target) : Protection(target, type);
// armor Protection.<Type> + artifact/effect contributions + difficulty Armor_Strike_Add / NPC_Armor_Strike_Add,
// clamped to ObjEffectMaxParamsPrototypes MaxValue, then the effect-modifier pass. Strike cap 4.5 [cfg]

if (src in {Bullet, BulletHeavy, Buckshot, StrikeVfEOneshot})              coef = ArmorDifferenceCoefProjectiles;
else if (src in {ShockWave, BiteSmall, BiteLarge, CutSmall, CutLarge,
                 RamSmall, RamLarge, Knife, WeaponButt})                    coef = ArmorDifferenceCoefMeleeAttacks;
else coef = 1.0;                                                            // Explosion and the rest

if (ctx.bIgnoreArmor) return dmg;
expTerm = (pen != 0 && type == Strike) ? powf(coef, pen - prot) : 1.0;     // THE formula
deflected = DeflectRoll(ctx, prot);
dmg = ArmorTerm(ctx, dmg, prot, deflected, bIsHuman) * expTerm;
```
```c
DeflectRoll: if (src == Explosion || instigator > 0x07FFFFFF) return false;
             chance = clamp(pen - prot + 1, ArmorDeflectMinChance, ArmorDeflectMaxChance);
             return SRand01() > chance;
ArmorTerm:   if (type != Strike) {
                 if (type in {Burn, Shock, ChemicalBurn, PSY, Fall, SteamBurn}) dmg *= (100 - prot) * 0.01;
                 return dmg;                                   // Radiation etc. untouched here
             }
             if (inst >= 0xFFFFFFF0 && inst != 0xFFFFFFFE) return dmg;     // no armor pass
             if ((inst & 0xF8000000) == 0x08000000) k = StrikeAnomalyArmorDifferenceCoef;
             else if (src == Explosion)                k = ExplosionArmorDifferenceCoef;
             else if (src in {Knife, WeaponButt})      k = PlayerMeleeArmorDifferenceCoef;
             else { if (deflected) dmg *= bIsHuman ? ArmorDeflectDamageCoefHuman : ArmorDeflectDamageCoefMutant;
                    return dmg; }                      // plain bullets end here
             return dmg * max(0, 1 - k * min(prot / 5.0, 1));          // 5.0 is a CoreVariable
```

### What it means
- **Bullets:** `final = BaseDamage x BoneDamageCoefficients[bone] x ArmorDifferenceCoefProjectiles ^ (ArmorPiercing -
  Protection.Strike) x (7% of hits: ArmorDeflectDamageCoef)`. Human NPCs have coef 2.0 [cfg]: each point of
  protection above the bullet's piercing halves damage, each point of piercing above protection doubles it. Mutants use
  1.3-1.5 [cfg], so armor matters much less for them. The exponent dominates every number in the weapon files.
- **Deflect is a flat 7% roll and raises damage.** `ArmorDeflectMinChance = ArmorDeflectMaxChance = 0.93` [cfg], so
  the clamp discards `pen - prot + 1`; a deflect multiplies damage by 1.5 (`ArmorDeflectDamageCoefHuman` / `Mutant`,
  both 1.5 [cfg]) despite the name ([bin]: `minss`/`maxss` against two equal globals, `mulss` on the damage). How the
  bool drives VFX/SFX was not traced.
- **Explosions:** coef 1.0, so no exponential term and no deflect; only the linear term `1 - k x min(prot/5, 1)` with
  `ExplosionArmorDifferenceCoef` k = 0.5 [cfg, kit `CoreVariables.cfg`]: at most 50% less, 45% at the strike cap 4.5.
- **Anomaly strikes:** `StrikeAnomalyArmorDifferenceCoef` k = 1.0 [cfg]: full protection (prot/5) comes off linearly.
- **Knife / weapon butt:** both terms, `ArmorDifferenceCoefMeleeAttacks ^ (pen - prot)` and `1 - 0.6 x min(prot/5, 1)`
  (`PlayerMeleeArmorDifferenceCoef` 0.6 [cfg]).
- **Non-strike damage** (Burn, Shock, ChemicalBurn, PSY, Fall, SteamBurn): flat `dmg x (100 - prot) / 100`,
  protections capped at 90 [cfg].
- **Health** is only the pool: player `MaxHP = 100`, human NPC base 200 [cfg], scaled by difficulty `NPC_HP`;
  `HPThresholdToKill = 0.1` [cfg]. Nothing in the armor chain reads HP.

### Worked example (player AK-74 into a human NPC in a Zorya suit, body shot; inputs [cfg])
| Input | Value | Authored in |
|---|---|---|
| `BaseDamage` / `ArmorPiercing` | 23.0 / 1.0 | `GunAK74_ST_Player`, `WeaponData/CharacterWeaponSettingsPrototypes/PlayerWeaponSettingsPrototypes.cfg` |
| `Protection.Strike` | 2.0 | `Zorya_Neutral_Armor`, `ItemPrototypes/ArmorPrototypes.cfg` |
| `BoneDamageCoefficients` | Body 1.0, Head 6.0, Limbs 0.7 | `ObjPrototypes/GeneralNPCObjPrototypes.cfg` |
| `ArmorDifferenceCoefProjectiles` | 2.0 | same |

`23 x 1.0 x 2^(1 - 2) = 11.5` off 200 HP, ~18 shots.

| Change | Multiplier | Damage |
|---|---|---|
| headshot (6.0) | 6 x 0.5 | 69.0 |
| unarmored (prot 0) | 2^1 | 46.0 |
| best armor (prot 4.5, the cap) | 2^-3.5 = 0.088 | 2.0 |
| AP ammo, *if* `ArmorPiercingMod 0.5` adds → pen 1.5 [inferred] | 2^-0.5 | 16.3 |
| deflect roll fires | x 1.5 | 17.3 |

Protection 2.0 → 4.5 against this rifle is a 5.7x survivability swing.

### Notes and open points
- `ArmorDifferenceCoefProjectiles` / `MeleeAttacks` are stored as **FP16 half-floats** on the ObjPrototype
  (`proto+0x58A`, `+0x58C`; the parser at `0x140c0b2c5` converts on load). They are wide-string-only names: hand-parsed,
  no UPROPERTY, no validation.
- The `.data` defaults compiled in for these CoreVariables (0.9 / 0.1 / 0.1 / 0.2 / 1.0) are overwritten by
  `CoreVariables.cfg` at load; the cfg values are authoritative.
- `ctx+0x20` is an object-pool index (pool walk `idx < 0x400`, stride `0x700`, at `0x140cb361d`); the
  `(x & 0xF8000000) == 0x08000000` anomaly tag scheme was not traced.
- Not traced: how ammo `ArmorPiercingMod` / `DamageMod` fold into `pen` and `BaseDamage`; the difficulty multipliers
  (`NPC_Weapon_BaseDamage`, `Weapon_BaseDamage`, `NPCToPlayerDamageScaler`, `Mutant_BaseDamage`) applied upstream of
  `ctx.Damage`.

## NPC corpse looting
| Question | Answer |
|---|---|
| Do NPCs swap to a better gun after looting? | Yes, and "better" means **higher price** only. |
| Do NPCs swap to better armor? | No: no comparison, no equip path, armor is tied to the spawn-time appearance mesh. |
| Do NPCs repair gear? | No: broken gear is never picked up, and no repair code is reachable from AI. |

There is one looting goal in the AI, `ProcessCorpseGoal`; no armor-, artifact- or grenade-related goal names exist.

```c
// caller 0x140b0b7f8 reads AISettings; scans the corpse inventory, and, if AllowWeaponPickupWhenLooting and the
// corpse's dropped weapon lies within WeaponLootDistance, that weapon too. Scan at 0x140b0ebd5:
myMax = max(GetPrice(x) for x in self.inventory);               // GetPrice 0x140c2309a
for (item in corpse.inventory) {
    if (!CanLoot(item)) continue;                               // 0x14042eae9
    if (itemClass == 0 /* weapon, inferred */) {                // prototype +0xD0
        if (AllowWeaponPickupBasedOnPrice && Price(item) > myMax) take;
        else if (Durability(item) > LowDurabilityPercentage)    take;
        else item-container op 0x142f819ec (called with container -1; reads as detach/drop, unconfirmed);
    } else take;
}
// a second loop at 0x140b0f2ea processes the take-list
```
- **Price is the NPC weapon-preference curve.** No read of damage, accuracy, calibre, wear or ammo compatibility: an
  NPC trades a working rifle for a pricier one it cannot feed. Changing weapon `Cost` changes what NPCs carry after
  a fight.
- **Durability gate** in `CanLoot`: items with durability (prototype class < 2: weapons and armor, predicate
  `0x14042ebf8`) below cvar `gsc.ItemLootHelper.LowDurabilityPercentage` are rejected (registered at `0x143fcd1b4`,
  default 0.10 [bin]; help "Describes the low durability percentage of items that can be picked up."). Before that a
  prototype flag (`proto+0xD4 & 0x10`) and an instance flag (`item+0x41 & 2`) exclude quest/unlootable items. Ammo,
  consumables and artifacts skip the durability test.
- **Armor:** the non-weapon branch has no ranking, no protection read, no equip call; nothing in the AI calls an
  equipment-slot setter. The character generator (`0x1408c7af6`) binds armor to the appearance mesh at spawn (log
  "Character has generated body armor item with SID %s for NPC obj prototype %s, but mesh generator %s has no
  appropriate body armor..."); armor prototypes carry an `NpcMeshGenerator` block for this. No runtime re-dress path
  exists.
- **Repair:** every repair symbol is economy/UI (`Repair_Cost`, `BaseRepairCostModifier`,
  `ReputationRepairCostModifiers`, `ArmorSellMinDurability`, `DurabilityBeforeRepair`, `URepairPriceWidget`); the one
  code entry `RepairItem` sits in a debug-command table with `UpgradeItem`, `UninstallUpgrade`, `SetZoom`.

**Knobs.** Three hand-parsed `AISettings` fields in `AIGlobals.cfg` (wide-string-only: no UPROPERTY, no
validation; parser stores at `0x140bd9e7e` / `0x140bd9ea2` / `0x140bd9ec4`):

| Field | Global [bin] | Kit value [cfg, kit copy] |
|---|---|---|
| `WeaponLootDistance` (float) | `0x149edd110` | 300.0 |
| `AllowWeaponPickupWhenLooting` (bool) | `0x149edd10c` | true |
| `AllowWeaponPickupBasedOnPrice` (bool) | `0x149edd13c` | true |

The kit is an older revision than retail; read these values from the retail pak before relying on them. Plus the cvar
`gsc.ItemLootHelper.LowDurabilityPercentage` (0.10).

**Not verified:** whether an armor item in the take-list is ever equipped by another consumer of the list; callers and
frequency of the corpse scan (when an NPC decides to loot at all); `itemClass == 0` = weapon (inferred from the gate,
not the enum table); artifact auto-equip (`bAutoEquipArtifacts`) and grenade selection (`GrenadePrototypes`).

## Linux / Proton
Nothing here is platform-specific: the same Windows exe runs under Proton, so addresses and behaviour are identical
for the same build. Reading the exe on Linux: `reverse-engineering.md` § Linux / Proton.

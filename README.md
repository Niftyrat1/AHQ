# Advanced HeroQuest - Digital Adaptation

A single-player desktop adaptation of Advanced HeroQuest focused on the solo rules.

Current repository status: early `Phase 1` implementation. The project has working hero creation, dungeon exploration, basic melee combat, save/load, and partial solo-GM automation, but it does not yet implement the full solo AHQ ruleset.

The project now runs on `pygame-ce` by default via [main.py](F:\Agents\CascadeProjects\windsurf-project\AHQ\main.py). The older Tk frontend files remain in the repo only as legacy references during cleanup.

## Phase 1 Features

- **Tavern Screen:** Create heroes with rolled stats, manage party of up to 4
- **Dungeon Exploration:** Procedurally generated dungeon with fog of war
- **Combat:** Melee combat with heroes vs monsters
- **Save/Load:** Game state persists between sessions

## Current Gaps

- Solo rules are only partially implemented
- Henchmen, fuller treasure/economy flow, and some solo-fidelity edge cases are still missing
- Between-expeditions systems now have a first tavern-service pass for training, healer actions, supplies/ammo, post-expedition gear buying, and wizard spell/component purchases, but they are not yet a full campaign layer
- Several solo/AHQ fidelity issues still remain, especially around turn structure, dungeon counters, and equipment depth

## Rules-First Execution Plan

The repo now uses a `ledger-driven` completion plan.

Source of truth:
- [RULES_CONFORMANCE.md](F:\Agents\CascadeProjects\windsurf-project\AHQ\RULES_CONFORMANCE.md)

Working rules:
1. Only implement one coherent rules cluster at a time.
2. Read only the exact cited rule lines for that cluster.
3. Patch only the files needed for that cluster.
4. Run targeted validation, not broad re-audits.
5. Update the ledger immediately after each batch.

The remaining issues are locked to this order:
1. Fate full rules
2. KO / carry / drag final conformance
3. Gold carry cap
4. Full item carry limits
5. Missile recovery rolls
6. Chest / hidden / leave-behind treasure handling
7. Monster-carried loot full pass
8. Henchmen system
9. Between-expedition campaign loop
10. Magic economy and learning
11. Trap fidelity sweep
12. Hazard fidelity sweep
13. Exploration final audit
14. Combat final audit
15. Monster audit final pass

## Costs Table Status

The full AHQ campaign `Costs Table` from [Advanced HeroQuest.md](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3532) is now represented in [data/tables.json](F:\Agents\CascadeProjects\windsurf-project\AHQ\data\tables.json) under `costs_table`.

Implemented in the live game:
- Core tavern purchase flow for combat equipment: melee weapons, ranged weapons, shields, and armour
- AHQ combat-stat effects for the supported weapon and armour profiles
- First between-expedition tavern services: training, Fate increase, healer services, expedition supplies, ammo bundles, post-expedition gear buying, and wizard spell/component purchasing

Still partial or missing:
- Gold carry-cap enforcement and the rulebook's cited carried-item category limits are now enforced; broader campaign/economy conformance still remains
- Between-expedition summary/recovery flow now exists as a first pass, but henchmen management and fuller campaign handling are still missing
- Broader post-expedition shop coverage and more polished tavern UX

Known approximation:
- The current tavern sells direct weapon profiles. The rulebook prices bows and crossbows as weapon-plus-ammo bundles, so the shop still remains an approximation even though ammo is now spent in play and recovered after victorious combats.

## Implementation Roadmap

### Phase A - Correctness Fixes
- Completed in current work:
  - Room handling now uses shared room metadata for reveal, combat placement, and save/load
  - Hero movement path validation now uses BFS in both game logic and UI prechecks
  - Melee fumbles now trigger free attacks, monster ranged attacks use a separate resolver, and critical damage is no longer a flat `+1 wound`
  - KO heroes no longer stand back up automatically every GM combat phase
- Still remaining in Phase A:
  - Remove or replace WHQ-specific placement/flow assumptions that conflict with solo AHQ behavior
  - Tighten KO recovery and ranged-hit rules against the solo rule text rather than current pragmatic placeholders

### Phase B - Core Solo Rules
- Implement dungeon counter resolution rather than logging placeholder counter names
- Continue completing trap consequences and chest/room-feature interactions from the AHQ tables
- Current work now includes a reusable hero status-effects layer plus rules-backed gas, mould, rats, bats, mushrooms, chasm leaps, grate rooms, wandering-monster hazard rooms, NPC encounters and follow-up, witches that can escape with loot, and throne encounters
- Lair, quest, and chasm rooms now place visible chests, chest opening resolves traps and gold, and hidden-treasure gold now updates hero state correctly
- Revealed pit traps can now be leapt, portcullises can be lifted for a hero phase, and persistent trap markers now affect movement instead of being visual-only
- Implement hero ranged combat, LOS/range bands, and equipment effects
- Expand solo GM tactics and targeting to match the solo rules more closely
- Continue replacing placeholder counter effects with rules-faithful outcomes as the trap/hazard systems land

### Phase C - Remaining Systems
- Tighten the new between-expedition systems into a full campaign layer: exact gold carry handling, deeper item-carry enforcement, richer summary/recovery flow, and henchmen
- Add treasure resolution, monster-carried treasure, and remaining economy details
- Add quest-specific and scripted solo content where procedural generation is not appropriate

### Phase D - Map And Screen Overhaul
- Replace placeholder board rendering with proper tile artwork for floors, walls, doors, stairs, and feature squares
- Integrate token/counter art from `assets/` for heroes, monsters, and dungeon features instead of simple placeholders
- Increase board square size to fit real token art cleanly
- Add a minimap so larger on-board tiles do not reduce navigation clarity
- Rework the dungeon screen layout so the larger board, sidebars, and log remain readable together
- Finish polishing the `pygame-ce` frontend and remove remaining legacy Tk assumptions from docs/assets over time

### Phase E - Documentation and Validation
- Keep architecture docs aligned with the live code shape
- Add regression tests for dungeon generation, room state persistence, and combat edge cases
- Document which AHQ solo rules are implemented, simplified, or intentionally deferred
- Add a dedicated audit pass for monster stat fidelity, armour-adjusted monster profiles, and monster-carried equipment/treasure

## Immediate Next Work

Until the list above is exhausted, new feature work should not be started outside the numbered issues in [RULES_CONFORMANCE.md](F:\Agents\CascadeProjects\windsurf-project\AHQ\RULES_CONFORMANCE.md).

## Setup

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the game:
```bash
python main.py
```

Alternate entry alias:

```bash
python main_pygame.py
```

## How to Play

1. **Tavern:** Create heroes using the "Create Hero" button
2. **Party Selection:** Add up to 4 heroes to your party
3. **Begin Quest:** Enter the dungeon
4. **Exploration:** Click a hero to select, click a destination to move
5. **Combat:** Click adjacent monsters to attack
6. **Exit:** Find stairs out to return to tavern

## Controls

- **Mouse:** Click to select heroes, move, attack, interact
- **End Hero Phase:** Button to pass turn to GM

## Python Path

```
C:\Users\Niftyrat\AppData\Local\Python\bin\python.exe
```

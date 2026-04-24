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
- Magic, richer room-feature treasure logic, henchmen, training, healer services, and broader between-expedition shopping are still missing
- Between-expeditions systems and the full quest-book/solo content are not implemented
- Several solo/AHQ fidelity issues still remain, especially around turn structure, dungeon counters, and equipment depth

## Costs Table Status

The full AHQ campaign `Costs Table` from [Advanced HeroQuest.md](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3532) is now represented in [data/tables.json](F:\Agents\CascadeProjects\windsurf-project\AHQ\data\tables.json) under `costs_table`.

Implemented in the live game:
- Core tavern purchase flow for combat equipment: melee weapons, ranged weapons, shields, and armour
- AHQ combat-stat effects for the supported weapon and armour profiles

Captured in data but not yet implemented in gameplay/UI:
- Training costs
- Spell purchases and spell components
- Healer services
- Rope, iron spikes, Greek Fire, Rat Poison, and Screetch Bug
- Ammo-bundle purchasing and ammunition tracking

Known approximation:
- The current tavern sells direct weapon profiles. The rulebook prices bows and crossbows as weapon-plus-ammo bundles, so the shop still needs an inventory/ammo pass to become fully rules-faithful.

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
- Add magic and wizard spell management
- Add treasure resolution, monster-carried treasure, and magic treasure
- Add henchmen and between-expeditions systems
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

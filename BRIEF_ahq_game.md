# Advanced HeroQuest — Digital Adaptation
## Cascade Build Brief

---

## Vision

A single-player desktop game adaptation of Advanced HeroQuest, inspired by the Gold Box CRPGs (Pool of Radiance, Curse of the Azure Bonds). The player manages a party of up to 4 Heroes, exploring a procedurally generated dungeon governed by the AHQ solo rules. The computer acts as the GM. Played entirely with mouse clicks — click a Hero, click a destination to move; click an enemy to attack.

The tone is functional and atmospheric — dark dungeon aesthetic, clear readable UI, no animations required for the first version. Think character portraits in a sidebar, a top-down grid dungeon, and a scrolling combat log.

---

## Technology Stack

- **Language:** Python
- **UI Framework:** `pygame` (2D grid rendering, mouse input, portraits)
- **Data storage:** JSON files for saved heroes and game state
- **No external AI/Ollama required** — all game logic is deterministic dice + tables from the rulebook
- **Python path:** `C:\Users\Niftyrat\AppData\Local\Python\bin\python.exe`

---

## Project Location

```
F:\Agents\CascadeProjects\windsurf-project\
└── ahq_game\
    ├── main.py               # Entry point
    ├── game.py               # Core game loop and state machine
    ├── dungeon.py            # Procedural dungeon generation
    ├── combat.py             # Combat resolution engine
    ├── hero.py               # Hero data model and creation
    ├── monster.py            # Monster data model
    ├── gm.py                 # Solo GM logic (tactics table, counter draws)
    ├── ui/
    │   ├── tavern.py         # Tavern / party management screen
    │   ├── dungeon_view.py   # Main dungeon exploration screen
    │   └── combat_log.py     # Scrolling log widget
    ├── data/
    │   ├── heroes.json       # Saved hero roster
    │   ├── monsters.json     # Monster reference tables
    │   ├── tables.json       # All rulebook dice tables
    │   └── spells.json       # Spell definitions
    ├── assets/
    │   └── fonts/            # Monospace/retro fonts if available
    ├── requirements.txt
    └── README.md
```

---

## Screen 1: The Tavern (Party Management)

This is the first screen the player sees. Inspired by Bard's Tale's tavern — a place to create, view and load heroes before embarking.

### Layout
- **Left panel:** Roster of saved heroes (scrollable list). Each entry shows: Name | Race | Class | WS | Wounds | Fate
- **Right panel:** Selected hero's full character sheet — all stats, equipment, spells if wizard
- **Bottom bar:** Party slots (4 max). Drag or click-to-add heroes from the roster into the party
- **Buttons:** "Create Hero" | "Delete Hero" | "Begin Quest" (disabled until at least 1 hero in party)

### Hero Creation
Clicking "Create Hero" opens a creation flow:
1. **Roll Race** — button rolls D12 and applies the Hero's Race Table (1-6 Human, 7-9 Dwarf, 10-12 Elf). Player can re-roll once.
2. **Choose Class** — Warrior or Wizard (with tooltip explaining Wizard restrictions: no armour, dagger only)
3. **Roll Stats** — button rolls all characteristics using the Hero Creation Table:
   - Human: WS D6+4, BS D4+3, STR D4+4, T D4+4, Sp D6+4, Br D8+3, Int D8+3, W D4+1, Fate 2
   - Dwarf: WS D6+5, BS D4+3, STR D4+4, T D4+4, Sp D6+3, Br D8+3, Int D8+3, W D4+1, Fate 2
   - Elf: WS D6+4, BS D4+5, STR D4+3, T D4+2, Sp D6+5, Br D8+3, Int D8+3, W D4+1, Fate 2
   - Player can re-roll stats once
4. **Starting Gold** — roll D4+4 × 10 gold crowns
5. **Buy Equipment** — simple shop: weapons, armour, ranged weapons. Prices from rulebook. Wizard cannot buy armour.
6. **Name Hero** — text input
7. **Save** — writes to heroes.json

### Starting Equipment Prices (gold crowns)
| Item | Cost | Notes |
|------|------|-------|
| Dagger | 2gc | All heroes start with one free |
| Sword | 10gc | |
| Axe | 8gc | |
| Spear | 6gc | |
| Halberd | 20gc | Two-handed, critical on 11-12, fumble on 1-2 |
| Double-handed sword | 25gc | Two-handed, critical on 11-12, fumble on 1-2 |
| Short bow | 15gc | |
| Long bow | 20gc | |
| Crossbow | 25gc | Cannot move and fire |
| Light armour | 20gc | |
| Heavy armour | 50gc | |
| Shield | 10gc | |

---

## Screen 2: The Dungeon

### Layout
- **Centre:** Top-down dungeon grid (tile-based). Each tile is a fixed pixel square (suggest 32px). Dungeon generates outward as heroes explore.
- **Left sidebar:** Party status panel — 4 hero slots, each showing portrait placeholder, name, current Wounds / max Wounds, Fate Points remaining. Currently selected hero highlighted.
- **Right sidebar:** Action log — scrolling text combat/event log, most recent at bottom.
- **Bottom bar:** Selected hero's name, stats summary, and available actions for the current phase.
- **Top bar:** Current turn type (EXPLORATION / COMBAT), current phase (HERO PHASE / GM PHASE), and dungeon level.

### Dungeon Tile Types
- Floor (explored)
- Floor (unexplored / fog of war — dark)
- Wall
- Door (closed)
- Door (open)
- Passage end / dead end
- Stairs down
- Stairs out (exit)
- Treasure chest (closed / open)
- Pit trap (revealed)
- Portcullis
- Chasm

---

## Game State Machine

The game has two top-level modes, each with phases:

### EXPLORATION MODE

**Hero Phase:**
1. Player clicks a hero to select it (highlights on map and in sidebar)
2. Player clicks a destination square — hero moves up to Speed squares (Manhattan distance, no diagonal)
3. If hero reaches a junction with unexplored exits, dungeon generation triggers automatically
4. If hero reaches an unexplored door, player can click door to open it — dungeon generation triggers
5. Hero can search for secret doors (button) or search for hidden treasure (button) once per wall/room per expedition
6. Phase ends when player clicks "End Hero Phase"

**GM Phase (automated):**
1. Roll D12 — on 1 or 12, draw a dungeon counter and apply it
2. Log result in combat log
3. Auto-advance to next Hero Phase

### COMBAT MODE
Triggered when monsters are placed in a dungeon section.

**Surprise Roll:**
- Both sides roll D12
- If Elf in party with line of sight: Heroes +1
- If Sentry present: GM +1
- Winner places monsters; loser loses first turn if GM wins

**Hero Phase:**
1. Player selects a hero
2. Can choose: Move then Attack, OR Attack then Move (choose via button)
3. **Moving:** Click destination square within Speed value. Hero cannot pass through occupied squares.
4. **Attacking (melee):** Hero must be in a square adjacent (not diagonal) to target. Click enemy to attack.
5. **Attacking (ranged):** If hero has ranged weapon and is not adjacent to any enemy: click enemy. Check range in squares (Manhattan), check line of sight (no walls or figures between them unless adjacent to attacker).
6. Attack resolution (see Combat Resolution below)
7. Repeat for each hero. Click "End Hero Phase" when done.

**GM Phase (automated):**
1. Roll on Tactics Table:
   - If all monsters melee only: 1=Reinforcements, 2-6=Move+Attack, 7-12=Attack+Move
   - If any monster has ranged: 1=Reinforcements, 2-4=Move+Attack, 5-8=Attack+Move, 9-12=Ranged Attack
2. Move monsters according to tactic:
   - Melee monsters: move to adjacent square of lowest-WS hero, or closest if none reachable
   - Ranged monsters: move to line-of-sight square not adjacent to any hero
3. Resolve monster attacks (target hero with lowest WS; ties broken by lowest Toughness; further ties random)
4. Apply damage, log results
5. Check for deaths
6. Return to Hero Phase

---

## Dungeon Generation (Computer GM)

On every new passage or room discovery, the computer automatically rolls and places tiles.

### Passage Generation
1. Roll D12 → Passage Length Table:
   - 1-2: 1 section (4 tiles)
   - 3-8: 2 sections (8 tiles)
   - 9-12: 3 sections (12 tiles)
2. Roll 2D12 → Passage Features Table:
   - 2-4: Wandering monsters
   - 5-15: Nothing
   - 16-19: 1 door (side wall)
   - 20-21: 2 doors
   - 22-24: Wandering monsters
3. Roll 2D12 → Passage End Table:
   - 2-3: T-junction
   - 4-8: Dead end
   - 9-11: Right turn
   - 12-14: T-junction
   - 15-17: Left turn
   - 18-19: Stairs down
   - 20-22: Stairs out
   - 23-24: T-junction

### Room Generation
1. Roll D12 → Room Type Table:
   - 1-6: Normal (small, empty)
   - 7-8: Hazard (small, roll hazard table)
   - 9-10: Lair (large, roll Lairs Monster Matrix)
   - 11-12: Quest Room (large, roll Quest Rooms Monster Matrix)
2. Roll D12 → Room Doors Table:
   - 1-4: No extra doors
   - 5-8: 1 extra door
   - 9-12: 2 extra doors

### Overlap Prevention
Keep a grid array of placed tiles. Before placing a new section, check for overlap. If overlap detected, try rotating/mirroring. If still impossible, treat as dead end and log "passage blocked."

### Dungeon Counters
Maintain a pool of counters (4× Trap, 4× Wandering Monster, 4× Ambush, 4× Escape, 4× Character, 4× Fate). Draw is random. Each counter type has specific timing rules (see rulebook). Apply effects automatically and log them.

---

## Combat Resolution

### Hand-to-Hand Hit Roll
1. Look up attacker WS vs defender WS in the Hit Roll Table (hardcode this as a 12×12 array)
2. Roll D12 — if >= required score, hit
3. Roll of 12 = Critical Hit (free additional attack)
4. Roll of 1 = Fumble (defender gets free attack on attacker)
5. Large weapons (halberd, double-handed): critical on 11-12, fumble on 1-2

### Wound Roll
1. On a hit, roll damage dice (number depends on weapon)
2. Each die that scores >= defender's Toughness = 1 Wound
3. Roll of 12 on damage = critical damage; roll again and add (keep rolling on 12s)
4. Deduct wounds from target's current Wounds total

### Ranged Hit Roll
Use Ranged Hit Rolls Table (hardcode as 12×5 array — BS vs range band):
- Range bands: 1-3, 4-12, 13-24, 25-36, 37+
- Some entries marked * (11/12 only) — no critical possible on these rolls

### Death
- Monster reaches 0 Wounds: remove from map, log kill, award PV as XP
- Hero reaches 0 Wounds: Hero is KO'd (not dead unless 0 Fate Points remain)
- If KO'd hero has Fate Points: auto-spend 1 Fate Point to negate the killing blow (prompt player first)
- If no Fate Points remain: Hero is dead. Remove from party. Mark as dead in heroes.json.

### Fate Points
- Player can spend a Fate Point after seeing damage result but before it is applied
- Negates all damage from that attack
- Log "Heinrich spends a Fate Point — damage negated!"

---

## Monster Data (monsters.json)

Each monster entry:
```json
{
  "name": "Skaven Warrior",
  "WS": 4,
  "BS": 3,
  "S": 3,
  "T": 3,
  "Sp": 5,
  "Br": 6,
  "Int": 4,
  "W": 1,
  "PV": 2,
  "weapons": [{"name": "Sword", "damage_dice": 1, "critical": 12, "fumble": 1}],
  "ranged": null,
  "is_sentry": false,
  "is_character": false
}
```

Include these monsters for the Shattered Amulet quest (Skaven-themed):
- Skaven Warrior (standard)
- Skaven Champion (tougher, sentry type)
- Skaven Warlord (character monster, runesword)
- Clan Eshin Assassin (character monster, fast)
- Clan Pestilens Plague Monk (character monster)
- Clan Skyre Warpweaver (character monster, magic)

---

## Solo GM Tactics (gm.py)

Implement the Tactics Table from the Solo rules exactly:

```python
def get_tactics(monsters):
    has_ranged = any(m.ranged for m in monsters)
    roll = roll_d12()
    if not has_ranged:
        if roll == 1: return "REINFORCE"
        elif roll <= 6: return "MOVE_ATTACK"
        else: return "ATTACK_MOVE"
    else:
        if roll == 1: return "REINFORCE"
        elif roll <= 4: return "MOVE_ATTACK"
        elif roll <= 8: return "ATTACK_MOVE"
        else: return "RANGED_ATTACK"
```

Monster targeting priority: lowest WS → lowest T → random.

---

## Between Expeditions Screen

After the dungeon is completed (all heroes exit via stairs out, or quest complete):
- Show summary: monsters killed, gold found, heroes lost
- Each surviving hero can spend gold on:
  - Training (increase WS, BS, or STR — costs from rulebook)
  - New equipment (same shop as creation)
  - Healing (restore wounds — 10gc per wound)
- Save updated heroes to heroes.json
- Return to Tavern screen

---

## Hit Roll Table (hardcode in combat.py)

```python
HIT_ROLLS = [
#  def WS: 1   2   3   4   5   6   7   8   9  10  11  12
    [7,   8,  9, 10, 10, 10, 10, 10, 10, 10, 10, 10],  # att WS 1
    [6,   7,  8,  9, 10, 10, 10, 10, 10, 10, 10, 10],  # att WS 2
    [5,   6,  7,  8,  9, 10, 10, 10, 10, 10, 10, 10],  # att WS 3
    [4,   5,  6,  7,  8,  9, 10, 10, 10, 10, 10, 10],  # att WS 4
    [3,   4,  5,  6,  7,  8,  9, 10, 10, 10, 10, 10],  # att WS 5
    [2,   3,  4,  5,  6,  7,  8,  9, 10, 10, 10, 10],  # att WS 6
    [2,   2,  3,  4,  5,  6,  7,  8,  9, 10, 10, 10],  # att WS 7
    [2,   2,  2,  3,  4,  5,  6,  7,  8,  9, 10, 10],  # att WS 8
    [2,   2,  2,  2,  3,  4,  5,  6,  7,  8,  9, 10],  # att WS 9
    [2,   2,  2,  2,  2,  3,  4,  5,  6,  7,  8,  9],  # att WS 10
    [2,   2,  2,  2,  2,  2,  3,  4,  5,  6,  7,  8],  # att WS 11
    [2,   2,  2,  2,  2,  2,  2,  3,  4,  5,  6,  7],  # att WS 12
]
```

---

## Save / Load

- `heroes.json` — roster of all created heroes (persists between sessions)
- `save_game.json` — current dungeon state, hero positions, monster positions, dungeon counter pool, current level. Written after every turn.
- On launch, if save_game.json exists, offer "Continue" and "New Game"

---

## Phase 1 Scope (Build This First)

Do not try to build everything at once. Phase 1 is a playable core:

1. Tavern screen with hero creation and party selection
2. Dungeon generation (passages, rooms, doors, fog of war)
3. Hero movement (click to move)
4. Monster placement on room discovery
5. Combat — melee only, hero phase + GM phase
6. Wound and death tracking
7. Combat log
8. Exit via stairs out

Phase 2 (add after Phase 1 works):
- Ranged combat
- Fate Points
- Dungeon counters
- Treasure chests
- Traps
- Hazard rooms
- Spells

Phase 3:
- Between expeditions screen
- Training and shopping
- Campaign progression (Shattered Amulet quest chain)
- Character monsters

---

## Requirements (requirements.txt)

```
pygame>=2.5.0
```

---

## Definition of Done (Phase 1)

- [ ] Tavern screen opens, heroes can be created with rolled stats
- [ ] Up to 4 heroes can be added to a party
- [ ] "Begin Quest" launches the dungeon screen
- [ ] Dungeon generates passages and rooms procedurally on exploration
- [ ] Fog of war hides unexplored tiles
- [ ] Heroes can be selected by clicking and moved by clicking destination
- [ ] Rooms generate monsters on discovery
- [ ] Combat mode activates with surprise roll
- [ ] Heroes can attack adjacent monsters; monsters attack back in GM phase
- [ ] Wounds tracked correctly; death handled
- [ ] Combat log scrolls with all events
- [ ] Heroes can exit via stairs out, returning to tavern
- [ ] Game state saves after each turn

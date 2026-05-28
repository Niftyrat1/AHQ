# Advanced HeroQuest Rules Conformance

This document is a `core rules only` conformance ledger built from the extracted rulebook at [Advanced HeroQuest.md](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md).

It intentionally excludes:

- quest text
- campaign flavour
- examples unless they clarify a rule
- narrative-only material

It includes both:

- `table` rules
- `text` rules stated outside tables

Status values:

- `Implemented`
- `Partial`
- `Missing`
- `Audit needed`

## Scope Notes

- Source of truth for line references: [Advanced HeroQuest.md](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md)
- Current codebase focus: solo play with a `pygame-ce` frontend
- This file is a working conformance tracker, not a design brief

## Completion Plan

This file is now the authoritative backlog for rules work. To minimise token use and avoid repeated broad audits, the remaining project should only be advanced through the following process:

1. Pick one numbered issue from `Remaining Issues` below.
2. Read only the exact cited rule lines for that issue.
3. Patch only the files directly involved in that issue.
4. Run targeted validation for that issue only.
5. Update the affected status rows in this ledger immediately.

Execution rules:

- Work from `Missing` items first, then `Partial`, unless a blocking bug forces a local reorder.
- Keep each implementation batch to one coherent rule cluster.
- Avoid UI polish, layout, or visual work unless it is required to expose the rule being implemented.
- If a batch would touch more than `4` files, split it into smaller sub-batches.

## Remaining Issues

| # | Issue | Priority | Ledger Focus | Notes |
| --- | --- | --- | --- | --- |
| 1 | Fate full rules | Highest | Fate, KO, And Death | Finish turn-scoped damage negation and failed-roll conversion. |
| 2 | KO / carry / drag final conformance | Highest | Fate, KO, And Death | Current implementation is playable but still marked Partial. |
| 3 | Gold carry cap | High | Costs And Between Expeditions | Enforce `250` gold crowns per hero/henchman. |
| 4 | Full item carry limits | High | Costs And Between Expeditions, Treasure | Extend beyond the current simplified carried-item checks. |
| 5 | Missile recovery rolls | High | Ranged Combat | Replace flat recovery with per-missile AHQ recovery rolls. |
| 6 | Chest / hidden / leave-behind treasure handling | High | Searches And Traps, Treasure | Record treasure left on the map and support later recovery. |
| 7 | Monster-carried loot full pass | High | Treasure, Monster Special Rules | Replace heuristic drops with rule-backed carried treasure where possible. |
| 8 | Henchmen system | High | Costs And Between Expeditions, Hazards | Promote current follower flags into real henchmen rules. |
| 9 | Between-expedition campaign loop | High | Costs And Between Expeditions | Tighten services, recovery, shopping, summary, and progression. |
| 10 | Magic economy and learning | High | Magic | Spell buying/learning/components are live; remaining magic work is now limited to spell/item edge-case audit. |
| 11 | Trap fidelity sweep | High | Traps | Finish Fireball, Mindstealer, Mantrap, Guillotine, Blocks, and gas details. |
| 12 | Hazard fidelity sweep | High | Hazards | Finish item-based hazard solutions and remaining follow-up rules. |
| 13 | Exploration final audit | Medium | Exploration Turn Structure, Searches And Traps | Close remaining transition/reveal/search edge cases. |
| 14 | Combat final audit | Medium | Combat Turn Structure, Hand-To-Hand Combat, Ranged Combat | Close pursuit, escape bookkeeping, focus, and remaining LOS/placement edges. |
| 15 | Monster audit final pass | Medium | Global Audit Items, Monster Special Rules | Final monster equipment/treasure/special-case review after core rules settle. |

## Recommended Order

The remaining issues should be completed in this order to minimise context switching and rework:

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

## Global Audit Items

| Area | Source | Status | Notes |
| --- | --- | --- | --- |
| Monster stat fidelity versus AHQ tables/reference cards | [Advanced HeroQuest.md:3883](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3883) | Audit needed | We need a later dedicated pass over monster stats, armour-adjusted stats, carried treasure, and monster-specific equipment/special roles. |
| Table rules vs text rules drift | Multiple | Audit needed | Some behavior is defined by surrounding prose rather than a table. We need to keep checking both. |

## Hero Creation

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Race roll: Human `1-6`, Dwarf `7-9`, Elf `10-12` | table | [Advanced HeroQuest.md:626](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:626), [Advanced HeroQuest.md:4007](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4007) | Implemented | Matches current hero creation flow. |
| Hero stat generation by race | table | [Advanced HeroQuest.md:642](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:642) | Implemented | Current rolls match the extracted table. |
| Starting gold is `D4+4 x 10` | text | [Advanced HeroQuest.md:4007](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4007) | Implemented | Current tavern flow matches this. |
| Must choose Warrior or Wizard during creation | text | [Advanced HeroQuest.md:613](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:613) | Implemented | Current flow supports class choice. |
| Wizard exceptions for starting spells/components | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Implemented | Wizard spellcasting, starting spells, starting components, and post-expedition spell/component buying are now live. |
| Dwarfs get `+2` to spot/disarm traps | text | [Advanced HeroQuest.md:636](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:636) | Implemented | Trap logic includes dwarf bonus. |

## Exploration Turn Structure

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| There are two turn types: exploration and combat | text | [Advanced HeroQuest.md:600](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:600) | Implemented | `GameState.ensure_phase_consistency()` is now enforced at load, movement, door opening, action availability, and phase-end boundaries, so play always resolves as either exploration or combat. |
| There must never be monsters in sight during an exploration turn | text | [Advanced HeroQuest.md:610](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:610) | Implemented | Visible monsters now force an immediate switch to combat before movement, exploration actions, or further exploration door handling can proceed. |
| Exploration turn phases: Hero Player, Exploration, Gamesmaster | text | [Advanced HeroQuest.md:612](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:612) | Implemented | `end_hero_phase()` now cleanly separates the hero-player segment from the exploration GM segment: heroes act one at a time, exploration generation/resolution happens during those actions, then `_run_exploration_gm_phase()` resolves the Gamesmaster counter step before the next hero turn resets. |
| GM draws a dungeon counter on `1` or `12` only | text | [Advanced HeroQuest.md:620](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:620) | Implemented | Current exploration GM phase uses this. |
| Heroes/Henchmen move one at a time, no diagonal movement | text | [Advanced HeroQuest.md:623](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:623) | Implemented | Grid/pathing respects orthogonal movement. |
| Entering unexplored space must stop before the unexplored area | text | [Advanced HeroQuest.md:625](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:625) | Implemented | Unexplored tiles remain non-walkable, door-opening is a turn-ending exploration action, and junction/passage generation now reveals from the boundary tile reached rather than allowing movement through unrevealed space. |
| Opening a door in exploration ends movement; cannot open and move through in same turn | text | [Advanced HeroQuest.md:627](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:627) | Implemented | Current exploration actions consume the turn. |
| Opening a chest requires ending next to it | text | [Advanced HeroQuest.md:628](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:628) | Implemented | `Open Chest` is only available from orthogonally adjacent squares and ends the Hero Player turn. |
| Armour changing takes whole Hero Player phases | text | [Advanced HeroQuest.md:615](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:615), [Advanced HeroQuest.md:630](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:630) | Implemented | Heroes can now spend a whole exploration turn removing or putting on carried armour/shields. |

## Searches And Traps

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Secret doors may only be searched in dead ends or rooms with only the entrance door | text | [Advanced HeroQuest.md:651](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:651) | Implemented | Eligibility and start-of-turn checks are enforced, and dead-end searches now use the board-targeted action flow so the player chooses the actual searchable wall section rather than relying on a fixed adjacent-wall shortcut. |
| Each wall may only be searched once | text | [Advanced HeroQuest.md:653](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:653) | Implemented | Room/wall search state is now tracked. |
| Secret Door Table outcomes | table | [Advanced HeroQuest.md:656](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:656) | Implemented | Secret-door searches now resolve the `1 / 2-6 / 7-12` outcome table directly, including the dungeon-counter result and creation of a closed secret door on the searched wall section. |
| Each room may only be searched once for hidden treasure | text | [Advanced HeroQuest.md:662](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:662) | Implemented | Room metadata tracks treasure searches. |
| Hidden Treasure Table outcomes | table | [Advanced HeroQuest.md:665](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:665) | Implemented | Hidden-treasure searches now resolve the correct `2-6 / 7-16 / 17-24` branches, award gold through the carry-cap system, and route magical finds through the live Magic Treasure Table generator. |
| Traps can be introduced by counters when moving onto a new square or opening a chest first time | text | [Advanced HeroQuest.md:671](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:671) | Implemented | Trap counters are now held and only played on new-square entry or first chest opening instead of resolving immediately in the GM phase. |
| Spotted trap can be disarmed by any adjacent hero | text | [Advanced HeroQuest.md:674](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:674) | Implemented | Spotted traps now persist visibly on the board and can be disarmed by an adjacent hero as an exploration action. |
| Roll `12` on disarm grants `+1` to future disarm rolls | text | [Advanced HeroQuest.md:677](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:677) | Implemented | Current trap logic tracks disarm bonus. |
| Roll `1` on disarm causes `+1` extra wound | text | [Advanced HeroQuest.md:677](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:677) | Implemented | Visible-trap disarm failures now apply the extra wound on a natural `1`. |
| Spotted but ignored trap blocks chest or movement area | text | [Advanced HeroQuest.md:678](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:678) | Implemented | Spotted traps now create blocking trap zones; chest traps block the chest until disarmed and square traps block the affected area. |

## Dungeon Generation

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| New sections are only placed from unexplored junction exits or unopened doors | text | [Advanced HeroQuest.md:742](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:742) | Implemented | This is the current generation entry point. |
| Door in room: even `passage`, odd `room` | text | [Advanced HeroQuest.md:755](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:755) | Implemented | Current door generation uses this rule. |
| Passage doors always lead to rooms | text | [Advanced HeroQuest.md:756](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:756) | Implemented | Current generation follows this. |
| Passage Length Table | table | [Advanced HeroQuest.md:759](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:759) | Implemented | Current generator matches. |
| Passage Features Table | table | [Advanced HeroQuest.md:765](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:765) | Implemented | Passage generation now rolls the live `2D12` feature table and resolves the full set of outcomes in-engine: wandering monsters, no feature, one side door, or two side doors, with dungeon logging for the generated result. |
| Passage End Table | table | [Advanced HeroQuest.md:775](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:775) | Implemented | Current generator uses corrected 2D12 behavior. |
| Room Type Table | table | [Advanced HeroQuest.md:828](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:828) | Implemented | Normal/hazard/lair/quest flow is live. |
| Room Doors Table | table | [Advanced HeroQuest.md:840](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:840) | Implemented | Current room generation uses this. |

## Combat Turn Structure

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Combat ends when no monsters remain or heroes escape | text | [Advanced HeroQuest.md:1042](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1042) | Implemented | Combat now ends only when the monster list is cleared by defeat or when the escape/pursuit logic resolves the heroes successfully out of sight. |
| Closing a door does not guarantee immediate escape; one more combat turn may occur | text | [Advanced HeroQuest.md:1043](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1043) | Implemented | Combat door-closing now sets a pending escape state and explicitly grants the monsters one further pursuit turn before the heroes can escape if they remain unseen. |
| On first contact, surprise is rolled before monsters are finally set up in the discovered section | text | [Advanced HeroQuest.md:982](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:982) | Implemented | The main combat-entry paths now preview the encounter, roll surprise first, and only then perform final AHQ section placement. |
| First setup keeps monsters in the encountered room/passage section only | text | [Advanced HeroQuest.md:986](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:986) | Implemented | Initial room, passage, wandering-monster, and visible-contact combat setup now places monsters in the encountered section rather than across the wider explored map. |
| Models move up to Speed, orthogonally only | text | [Advanced HeroQuest.md:1050](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1050) | Implemented | Hero and monster movement both use orthogonal BFS pathing only, and GM monster movement now spends up to the model's `Speed` rather than a one-step approximation. |
| Entering an enemy death zone stops movement immediately | text | [Advanced HeroQuest.md:1051](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1051) | Implemented | Hero combat movement rejects any path that continues past the first enemy death-zone tile, and monster GM movement likewise stops once it enters a hero death zone unless a flying rule explicitly overrides it. |
| Doors may be opened/closed instead of attacking | text | [Advanced HeroQuest.md:1061](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1061) | Implemented | Combat door actions now replace the hero's attack, require adjacency, and are blocked while the hero is in an enemy death zone. |
| Running replaces attack and adds extra movement on `2-12`, stumble on `1` | text | [Advanced HeroQuest.md:1066](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1066) | Implemented | Heroes can now run in combat, spending their attack for a `D12` extra-movement roll with a stumble on `1`. |
| Pursuit rules after attempted escape | text | [Advanced HeroQuest.md:1069](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1069) | Implemented | Closed-door escape now grants the monsters one further pursuit turn, pursuing monsters gain the run bonus when needed, and monsters that reach the sealed door can force it open before visibility is re-evaluated. |

## Hand-To-Hand Combat

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Adjacent enemies only, unless long reach allows diagonals | text | [Advanced HeroQuest.md:1079](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1079) | Implemented | Current melee reach logic follows this. |
| Hit roll uses attacker WS vs target WS | text | [Advanced HeroQuest.md:1083](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1083) | Implemented | Current combat uses the hit table. |
| Critical hit on `12`; large weapons crit on `11-12` | text | [Advanced HeroQuest.md:1086](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1086) | Implemented | Current weapon profiles support this. |
| Fumble on `1`; large weapons fumble on `1-2` | text | [Advanced HeroQuest.md:1090](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1090) | Implemented | Current weapon profiles support this. |
| Free attacks from crits/fumbles can chain | text | [Advanced HeroQuest.md:1094](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1094) | Implemented | Fumble/free-attack resolution now allows chained free attacks instead of artificially stopping after one bounce. |
| Damage dice depend on weapon; wounds on rolls `>= Toughness` | text | [Advanced HeroQuest.md:1097](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1097) | Implemented | Current melee damage model matches this. |
| Damage roll `12` causes critical damage and rerolls | text | [Advanced HeroQuest.md:1100](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1100) | Implemented | Current damage resolver supports exploding `12`s. |

## Ranged Combat

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Must carry ranged weapon | text | [Advanced HeroQuest.md:1195](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1195) | Implemented | Current ranged checks enforce this. |
| Must not be adjacent to target | text | [Advanced HeroQuest.md:1197](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1197) | Implemented | Enforced. |
| Target must not be in an enemy death zone | text | [Advanced HeroQuest.md:1198](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1198) | Implemented | Current ranged targeting blocks this. |
| Range counted without diagonals | text | [Advanced HeroQuest.md:1199](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1199) | Implemented | Current range checks use orthogonal count. |
| Must have line of sight | text | [Advanced HeroQuest.md:1161](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1161) | Implemented | Ranged LOS now uses model-aware blockers, door blocking, large-monster endpoint exceptions, large-monster blocker footprints, and target-footprint range/visibility selection. |
| Only thrown weapons can move and fire; bows/crossbows require no movement | text | [Advanced HeroQuest.md:1202](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1202) | Implemented | Current ranged checks enforce this distinction. |
| Friendly model between attacker and target blocks LOS unless adjacent to attacker | text | [Advanced HeroQuest.md:1206](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1206) | Implemented | Intervening models now block LOS outright unless the blocker is a friendly model adjacent to the attacker, matching the ranged-combat text. |
| Partial obscurity counts as `+4` range | text | [Advanced HeroQuest.md:1208](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1208) | Implemented | Ranged attack legality now applies the +4 effective-range penalty for partial cover. |
| Ranged crit halves target Toughness for damage | text | [Advanced HeroQuest.md:1230](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1230) | Implemented | Ranged crits now halve Toughness for damage resolution. |
| Ranged fumble hits nearby ally if available | text | [Advanced HeroQuest.md:1232](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1232) | Implemented | Ranged fumbles now redirect onto a model friendly to the original target within two squares of that target; otherwise the shot misses. |
| Recover missiles after combat only if monsters killed, not if heroes escape | text | [Advanced HeroQuest.md:1224](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1224) | Implemented | Heroes now spend arrows/bolts when firing, recover them with per-missile AHQ recovery rolls after victorious combats, and recover nothing if the heroes escape. |

## Monster Special Rules

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Fearsome Monster: heroes in death zone test Bravery at start of combat phases or cower | text | [Advanced HeroQuest.md:3748](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3748) | Implemented | Start-of-phase fear checks now apply cowering status that blocks normal move, attack, and spellcasting for that phase. |
| Large Monsters occupy four squares, have 8-square death zones, and need space for full footprint | text | [Advanced HeroQuest.md:3754](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3754) | Implemented | Footprint occupancy, click targeting, LOS visibility, death zones, rendering, placement, and GM movement/pathing now use full 2x2 large-monster footprints and block illegal wall/overlap placements. |
| Regenerates: recover 1 wound at start of each GM phase | text | [Advanced HeroQuest.md:3728](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3728) | Implemented | Supported in GM turn processing. |
| Invulnerable: only damage dice rolling `12` cause wounds unless hit by exempt attack | text | [Advanced HeroQuest.md:3732](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3732) | Implemented | Current melee and ranged resolution enforce this, including magical-weapon and free-attack exceptions. |
| Two Attacks: monster makes two separate melee attacks | text | [Advanced HeroQuest.md:3736](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3736) | Implemented | GM melee resolution now performs both attacks where flagged. |
| Cause Disease: successful hit can infect hero on toughness-based test | text | [Advanced HeroQuest.md:3738](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3738) | Implemented | Disease status is applied and persists through saves. |
| Poisoned Wind Globadier: 6 globes, target square and adjacent squares force Intelligence breath tests | text | [Advanced HeroQuest.md:4746](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4746) | Implemented | The attack now tracks a six-globe supply, affects the target square and adjacent squares, leaves lingering poisoned-wind cloud markers, and failed breath tests route through the shared Fate system. |
| Warpfire Thrower Team: stationary template attack, fumble kills team and burns adjacent models | text | [Advanced HeroQuest.md:4750](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4750) | Implemented | Stationary crew-pair LOS handling, fumble self-destruction, adjacent blast damage, friendly/enemy model damage, and successful-shot fireball-template coverage now work; successful shots use the shared grid fireball template centered on the selected LOS target square. |
| Jezzailachis Team: stationary shot, ignores armour toughness bonus, takes full turn to reload | text | [Advanced HeroQuest.md:4754](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4754) | Implemented | Paired-team placement/LOS, armour-ignoring damage against base Toughness, and a full following-turn reload lockout are implemented. |

## Fate, KO, And Death

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Fate can affect only things that happened this turn | text | [Advanced HeroQuest.md:1214](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1214) | Implemented | Fate decisions are now centralised in `fate.py`, remain explicit across save/load, and only apply to the current turn's damage or currently pending failed-roll outcome. |
| Fate can negate all damage suffered in a turn | text | [Advanced HeroQuest.md:1217](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1217) | Implemented | Lethal damage now queues a player choice that restores the hero to their turn-start wound state if Fate is spent. |
| Fate can convert a failed dice roll into a success | text | [Advanced HeroQuest.md:1219](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1219) | Implemented | Failed-roll Fate is now centralised and live for the current hero-facing rule tests in the engine: chasm leaps, pit leaps, pit climb-outs, disarm attempts, portcullis lifts, poisoned-wind breath tests, fearsome Bravery tests, Warpscroll resistance, Choke resolution, and spell Intelligence tests such as Power of the Phoenix and Inferno of Doom. |
| Monsters and Henchmen die at `0` or below wounds | text | [Advanced HeroQuest.md:1221](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1221) | Implemented | Monsters die at `0` or below wounds, and henchmen now use the same death threshold instead of the hero KO rule. |
| Heroes are KO at `0`, dead below `0` | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Implemented | Hero damage now distinguishes exact `0` from below `0` correctly. |
| KO hero counts as `WS 1` if attacked | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Implemented | Current melee-defense resolution treats KO heroes as `WS 1`. |
| Another hero can drag KO hero `3` spaces instead of a normal move | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Implemented | Combat dragging is a dedicated board action with the adjacent-start requirement and a hard `3`-square cap, replacing the mover's normal combat movement for the phase. |
| KO hero can be carried during exploration at `6` squares max | text | [Advanced HeroQuest.md:1223](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1223) | Implemented | Exploration carrying is a dedicated board action with the adjacent-start requirement and a hard `6`-square cap, consuming the carrier's exploration move for that turn. |
| Adjacent hero may administer Healing Potion to KO hero if neither is in an enemy death zone | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Implemented | Adjacent Healing Potion administration is now supported with the death-zone restriction. |

## Equipment Tables

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hand-to-hand weapon Strength table | table | [Advanced HeroQuest.md:4028](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4028) | Implemented | Current melee profiles use AHQ-style Strength bands. |
| Certain melee weapons have minimum Strength | text | [Advanced HeroQuest.md:4018](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4018) | Implemented | Weapon profiles now encode the AHQ minimum-Strength requirements for spear, sword, axe, warhammer, halberd, double-handed sword, and double-handed axe, and `hero.can_equip_item()` enforces them in tavern, creation, and later equipment changes. |
| Spears and halberds attack diagonally | text | [Advanced HeroQuest.md:4044](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4044) | Implemented | Current long-reach rules cover this. |
| Ranged weapon table | table | [Advanced HeroQuest.md:4055](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4055) | Implemented | Current ranged profiles use this table. |
| Long bow requires Strength `6` | text | [Advanced HeroQuest.md:4065](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4065) | Implemented | Enforced. |
| Crossbow requires a turn to reload | text | [Advanced HeroQuest.md:4067](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4067) | Implemented | Current turn-end reload supports this. |
| Armour table modifies BS, Toughness, Speed | table | [Advanced HeroQuest.md:4077](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4077) | Implemented | Current armour logic uses these modifiers. |

## Costs And Between Expeditions

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Full Costs Table exists and should govern purchases | table | [Advanced HeroQuest.md:3532](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3532) | Implemented | The live between-expedition tavern flow now buys and prices training, Fate increases, healer services, expedition supplies, ammo bundles, arms and armour, wizard spells, and spell components directly from the captured `costs_table` data. |
| Cannot buy training before first expedition | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Implemented | Training and spell buying are now gated behind `expeditions_completed > 0`. |
| Starting spells are free; extra spells only after first expedition | text | [Advanced HeroQuest.md:4011](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4011) | Implemented | Extra spell buying is supported between expeditions and locked until after the first delve. |
| Starting spell components are free by wizard race | text | [Advanced HeroQuest.md:4013](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4013) | Implemented | Wizards still start with free components by race, and tavern spell-component purchases now top them up afterward. |
| Heroes/Henchmen can carry only `250` gold crowns each | text | [Advanced HeroQuest.md:1884](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1884) | Implemented | Expedition treasure awards and left-behind treasure collection respect the `250` gc cap, tavern withdrawals are capped by remaining carry space, and between-expedition bookkeeping automatically deposits excess carried gold into the shared stash. |
| Heroes/Henchmen can only carry limited item categories | text | [Advanced HeroQuest.md:1898](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1898) | Implemented | The live model enforces the cited carried-item limits: one suit of armour, up to three weapons, one ring, one amulet, plus the corresponding worn-slot checks used by the project for shields and helms. Treasure that exceeds those limits is left on the expedition map for later recovery or reallocation. |

## Dungeon Counters

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Dungeon counters are drawn from specific trigger points, not arbitrarily | text | [Advanced HeroQuest.md:620](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:620), [Advanced HeroQuest.md:665](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:665), [Advanced HeroQuest.md:671](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:671) | Implemented | The live code now draws counters only from the legal AHQ trigger points: the exploration GM roll, hidden-treasure/secret-door search results that call for a counter, and held trap/ambush timing when their rule-specific triggers occur. |
| Ambush is combat-only | text | [Advanced HeroQuest.md:1520](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1520) | Implemented | Ambush counters are no longer played in exploration: they are held until combat, then resolved either at first setup in the encountered section or later in combat using the far-line-of-sight placement path. |
| Escape, Character, Fate, Trap, Wandering Monster counters have specific procedures | text/table | [Advanced HeroQuest.md:1490](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1490) | Implemented | Trap counters are held for legal exploration triggers, Wandering counters drawn outside the end-of-exploration timing are held and then use far-line-of-sight placement, Ambush counters are combat-only with the one-per-combat-turn limit, Escape counters remove and persist live character monsters, Character counters wait until monsters are next placed and return escaped character monsters before adding the next configured character, and Fate counters can now either negate a monster killing blow or turn a failed monster combat dice roll into a success. Covered by `test_dungeon_counter_row246.py`. |

## Traps

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Trap counters may be played during exploration when entering an unentered room/passage or opening a chest | text | [Advanced HeroQuest.md:5442](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5442), [Advanced HeroQuest.md:5444](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5444), [Advanced HeroQuest.md:680](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:680) | Implemented | Exploration trap counters are now held until those legal triggers occur. |
| Trap type is rolled on the Traps Table, using different columns for room/passage vs chest | table | [Advanced HeroQuest.md:5455](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5455) | Implemented | Current trap resolver uses the central table. |
| Pit Trap: spotted but unavoidable; fall, possible wound on `9+`, climb out on `<= Speed`, others may leap | text | [Advanced HeroQuest.md:5461](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5461) | Implemented | Pit traps are spotted-but-unavoidable, apply the `9+` wound check, use `<= Speed` climb-out, and allow other heroes to leap them with the same Speed test. |
| Crossfire: roll count of bolts, each bolt does `3` damage dice | text | [Advanced HeroQuest.md:5475](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5475) | Implemented | Crossfire now rolls a D12, divides by four rounding up to get the number of bolts, and resolves `3` damage dice per hit bolt. |
| Portcullis: may be placed in doorway or across room, lifted by combined Strength `20+`, lift attempt costs full exploration turn | text | [Advanced HeroQuest.md:5463](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5463) | Implemented | Portcullises lift with `D12 + combined Strength >= 20`; all helpers must still have their full exploration turn available and then spend it. Doorway and across-room non-diagonal placement options are recorded, and the GM/player can queue the exact legal line with deterministic engine placement retained as fallback. |
| Poison Dart: `1` damage die, if any wound is caused target is reduced to `0` wounds (KO) | text | [Advanced HeroQuest.md:5467](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5467) | Implemented | Poison Dart now rolls a single damage die and reduces the victim straight to `0` wounds if any wound is caused. |
| Fireball trap: initial `5` damage dice to all under template, then persists/moves for `3` later turns | text | [Advanced HeroQuest.md:5468](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5468) | Implemented | Fireball traps apply the initial `5` damage dice to the shared AHQ fireball template, wait through the next GM phase, then move 8 squares and damage the new template area for three later GM phases. The GM/player can queue each movement direction; deterministic movement toward the party remains the fallback. |
| Gas trap has area-of-effect and then gas subtype table | text/table | [Advanced HeroQuest.md:5478](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5478) | Implemented | Gas traps now check the full centre/adjacent/outer-ring cloud, apply the starting-Toughness resistance roll with the AHQ ring modifiers, then roll one gas subtype for all affected heroes. |
| Gas subtype `Mild Poison`: `1` wound and no movement for `3` turns | table | [Advanced HeroQuest.md:5481](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5481) | Implemented | Status layer supports this. |
| Gas subtype `Nausea`: rest-of-expedition movement/WS/BS/Strength penalties | table | [Advanced HeroQuest.md:5482](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5482) | Implemented | Nausea applies the expedition-long exploration move cap of 8, half combat movement, half WS/BS, and Strength -2. |
| Gas subtype `Madness`: GM controls hero for `6` turns | table | [Advanced HeroQuest.md:5483](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5483) | Implemented | Gas Madness gives `6` turns of GM control, blocks player-directed movement/actions, allows Mindstealer-style restraint, and does not attack other Heroes. The GM/player can queue the controlled hero's destination, with deterministic disruptive movement away from allies retained as fallback. |
| Gas subtype `Strong Poison`: `8` damage dice | table | [Advanced HeroQuest.md:5484](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5484) | Implemented | Strong Poison now resolves exactly as `8` damage dice. |
| Gas subtype `Deadly Poison`: needs Healing Potion or dies | table | [Advanced HeroQuest.md:5485](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5485) | Implemented | Deadly Poison now consumes a carried Healing Potion if present; otherwise the victim must spend Fate or dies. |
| Shock: `5` damage dice or `10` if wearing metal armour | text | [Advanced HeroQuest.md:5488](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5488) | Implemented | Current trap logic handles metal-armour escalation. |
| Magic trap casts a spell from its spell table | table | [Advanced HeroQuest.md:5489](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5489) | Implemented | Magic traps now resolve their listed spell outcomes through the shared spell engine; the moving Fireball sequence is tracked separately under the dedicated Fireball trap row. |
| Mindstealer: GM controls hero for `6` turns unless restrained by total Strength `>= 3x` target Strength | text | [Advanced HeroQuest.md:5497](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5497) | Implemented | Mindstealer gives `6` turns of hostile GM control, blocks player-directed movement/actions, lets the victim move and attack allies during GM phases, and allows adjacent allies to restrain with combined Strength at least `3x` the victim's Strength. The GM/player can queue the victim's move destination and optional ally attack, with deterministic hostile movement and attack retained as fallback. |
| Guillotine: `2` damage dice, loss of hand if any wound is caused, then Mantrap-style effects | text | [Advanced HeroQuest.md:5500](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5500) | Implemented | Guillotine now applies `2` damage dice and, if any wound is caused, inflicts the same hand-loss penalties as Mantrap: halved Weapon Skill, no bows, no two-handed weapons, and no 2+-component wizard spells until healed between expeditions. |
| Alarm: place wandering monsters along line of sight as far away as possible | text | [Advanced HeroQuest.md:5501](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5501) | Implemented | Alarm traps now start wandering-monster combat using the far-line-of-sight placement path instead of the generic nearby spawn. |
| Blocks: dodge on `<= Speed`, otherwise `12` damage dice; if spotted but not disarmed can be bypassed only at half speed | text | [Advanced HeroQuest.md:5502](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5502) | Implemented | Spotted Blocks sections now remain traversable and cost double movement, giving the AHQ half-speed bypass behaviour while the trap remains armed. |
| Mantrap: limb loss with permanent weapon/speed restrictions, only healed between expeditions | text | [Advanced HeroQuest.md:5504](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5504) | Implemented | Mantrap now applies the correct limb by source (`hand` for chest traps, `leg` for room/passage traps) and enforces the associated persistent WS/Speed, movement-cap, shield, two-handed-weapon, bow, and multi-component-spell restrictions until healed between expeditions. |
| Spike: `3` damage dice and poison-dart follow-up on `8+` | text | [Advanced HeroQuest.md:5507](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5507) | Implemented | Spike now rolls `3` damage dice, then on `8+` applies the poison-dart style follow-up that can still force a Fate-or-KO poison outcome. |

## Hazards

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hazard rooms roll on the Hazard Table | table | [Advanced HeroQuest.md:1560](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1560) | Implemented | Current room generation uses this table. |
| Wandering Monster hazard rolls wandering monsters | text | [Advanced HeroQuest.md:1566](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1566) | Implemented | Supported. |
| Non-Player Character hazard rolls Maiden / Witch / Man-at-Arms / Rogue | table | [Advanced HeroQuest.md:1570](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1570) | Implemented | Supported, with follower state tracked. |
| Maiden: guarded by wandering monsters; escort reward `100` gold | text | [Advanced HeroQuest.md:1576](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1576) | Implemented | Maiden hazards start with guard combat, successful rescue is tracked as an expedition follower state, and a successful dungeon exit awards the party the rulebook `100` gold crown reward. |
| Witch: one combat round to kill or close door, else teleports away with half the heroes' gold | text | [Advanced HeroQuest.md:1578](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1578) | Implemented | Witch hazards now use a true one-round escape timer, and closing the hazard room's entrance door seals her away before she can teleport off with half the party's gold. |
| Man-at-Arms becomes a henchman for current leader if rescued | text | [Advanced HeroQuest.md:1595](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1595) | Implemented | Rescued Man-at-Arms now becomes a persistent henchman for the current leader after the expedition and enters the normal upkeep flow. |
| Rogue joins temporarily and modifies trap spotting/disarming; expedition-end betrayal table applies | text/table | [Advanced HeroQuest.md:1596](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1596) | Implemented | Recruiting the Rogue now applies the expedition-long trap penalties, and expedition end resolves the betrayal table live: he may steal half the party's gold, leave peacefully, or remain with the current leader as a Sergeant-style henchman. |
| Chasm: heroic leap, sensible leap with rope, rope ladder, or leave | text | [Advanced HeroQuest.md:1607](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1607) | Implemented | Heroic leaps, rope-secured sensible leaps, party-supply rope ladders (`20` feet rope plus `10` iron spikes), and safe ladder crossing are live; leaving remains the no-action/close-door option. |
| Chasm room also places monsters, door, and chest on the far side | text | [Advanced HeroQuest.md:1607](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1607) | Implemented | Chasm room generation now ensures a far-side door, and reveal-time setup records far-side tiles and places the visible chest and guardian monsters there when valid far-side floor exists. |
| Statue table: curse / animated statue / skaven warlord / safe jewel removal | table | [Advanced HeroQuest.md:1622](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1622) | Implemented | Statue interaction now resolves the live table outcomes directly: curse, animated statue combat, Skaven Warlord transformation, or safe ruby recovery. |
| Statue ruby is worth `400` gold once recovered | text | [Advanced HeroQuest.md:1627](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1627) | Implemented | Safe statue-ruby recovery now awards `400` gold crowns through the live carry-cap and left-behind-treasure system. |
| Rats hazard has five options including poison, Greek Fire, spell, fighting, or leaving | text | [Advanced HeroQuest.md:1632](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1632) | Implemented | Rat Poison, two Greek Fire flasks, Flames of Death, fighting through `60` rats, and leaving the unresolved room are supported through hazard actions and persistent room state. |
| Rat bites cannot be negated by Fate | text | [Advanced HeroQuest.md:1635](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1635) | Implemented | Rat-hazard wounds use the uncancellable-damage path and do not queue Fate. |
| Bats hazard has Screech Bug / Greek Fire / spell / fight / leave options | text | [Advanced HeroQuest.md:1640](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1640) | Implemented | Screetch Bug, two Greek Fire flasks, Flames of Death, fighting, and leaving the unresolved room are supported through hazard actions and persistent room state. |
| Bat wounds cannot be stopped by Fate | text | [Advanced HeroQuest.md:1644](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1644) | Implemented | Bat-hazard wounds use the uncancellable-damage path and do not queue Fate. |
| Mould hazard: Greek Fire, wet hankies, or leave; mould table applies | text/table | [Advanced HeroQuest.md:1648](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1648) | Implemented | Mould rooms now support the rulebook choices directly: Greek Fire clears the room, wet cloths allow safe crossing without triggering the mould table, and leaving remains available as the no-action option. |
| Mushrooms are rolled in quantity; each mushroom uses the Mushroom table | text/table | [Advanced HeroQuest.md:1655](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1655) | Implemented | Mushroom rooms now roll and persist a finite `D12` mushroom count in hazard metadata, and each eaten mushroom resolves on the live Mushroom table until the supply is exhausted. |
| Grate reveals lower room with special prisoner rules, rope escape, one model per combat turn | text | [Advanced HeroQuest.md:1666](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1666) | Implemented | Grate opening rolls and creates a physical no-exit lower-room layout, tracks heroes below, places lair/quest prisoner monsters in the lower room with 1-damage-die attacks and the +2/no-Elf surprise rule, requires rope to climb out, and enforces one enter/leave transfer per turn. |
| Pool table: deadly poison / sleep / temporary Fate / full healing | table | [Advanced HeroQuest.md:1680](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1680) | Implemented | Pool interaction exists. |
| Magic Circle table: curse / summon / nothing / free spell / heal / temporary Fate, one-use drain | table | [Advanced HeroQuest.md:1685](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1685) | Implemented | Magic Circle entry now resolves the full live table, drains after use, and supports curse, summoning, nothing, one free next spell, healing, and temporary Fate outcomes. |
| Trapdoor table: trapped / lower room / crypt / maze / stairs | table | [Advanced HeroQuest.md:1693](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1693) | Implemented | Trapdoor rooms suppress random extra doors; trapped results use the chest trap column without spot/disarm; lower-room results share the grate lower-room/prisoner flow; crypts resolve live; maze results create an enterable Heroquest sub-level when available or find nothing when unavailable; stairs lead down unless quest-specific stairs rules override them into the lower-room result. |
| Crypt table includes mould spores / empty / gold ring / undead skaven | table | [Advanced HeroQuest.md:1697](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1697) | Implemented | Crypt searches now resolve mould spores, empty crypts, 25-gold rings, and an Undead Skaven that appears on the trapdoor square and forces monster surprise. |
| Throne grants chosen monster aura bonus to others while throne monster lives | text | [Advanced HeroQuest.md:1706](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1706) | Implemented | Current throne-leader state supports this. |

## Hazards, Chests, And Room Features

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hazard rooms use their own room table/results | table/text | Hazard sections and room tables | Implemented | Hazard rooms roll the AHQ hazard table, persist hazard metadata on the room, and dispatch reveal/action procedures by hazard type. The table rows above now carry the remaining per-hazard residuals. |
| Chests, crypts, trapdoors, statues, pools, circles, grates, chasms each have distinct procedures | text/table | Hazard and treasure sections | Implemented | Distinct procedures exist for the listed hazards and room-feature treasure, including chasm far-side setup, shared grate/trapdoor lower-room handling with physical lower-room traversal, the Heroquest maze sub-level branch, and the quest-specific trapdoor stairs override. |

## Magic

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Wizards use spells and spell components recorded on the character sheet | text | [Advanced HeroQuest.md:568](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:568), [Advanced HeroQuest.md:3525](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3525) | Implemented | Heroes persist known spells and per-spell component counts, can buy spells/components between expeditions, and the live pygame UI casts from spellbooks, wands, and scrolls using that stored state. |
| A Wizard may learn one new spell after each expedition by paying its listed cost | text | [Advanced HeroQuest.md:3547](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3547) | Implemented | Between-expedition spell purchase is supported, gated behind at least one completed expedition, and limited to one paid spell per completed expedition. |
| Spell components all cost the same but differ by spell | text | [Advanced HeroQuest.md:3525](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3525) | Implemented | Wizards can now buy spell-specific components between expeditions at the shared listed cost. |
| Starting wizards get free starting spells/components and cannot buy extra until after first expedition | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Implemented | New Wizard heroes start with the Bright starter spellbook and free components, and further spell buying is gated until after the first expedition. |
| A model in an opponent's death zone cannot cast certain spells | text | [Advanced HeroQuest.md:1057](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1057), [Advanced HeroQuest.md:4676](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4676) | Implemented | The supported explicit death-zone casting bans are enforced: Flames of the Phoenix is blocked while the caster is in an enemy death zone and still requires no model other than the wounded comrade in the wizard's own death zone; Plague Monk Warpscroll startup now uses the full hero death-zone check instead of simple adjacency. No other currently supported spell description adds a caster death-zone ban. |
| Magic Circle can permit a wizard to cast next spell without components | table | [Advanced HeroQuest.md:1689](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1689) | Implemented | Magic Circle free-cast state now carries through to the next spell cast and correctly bypasses missing spell components once. |
| Magic trap can cast Inferno of Doom / Lightning Bolt / Choke / Flames of Death / Fireball | table | [Advanced HeroQuest.md:5489](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5489) | Implemented | Magic-trap resolution now routes these spell results through the shared spell engine, including the lingering Fireball-trap sequence. |
| Treasure and character monsters can carry magical weapons/items/spell books/components | text | [Advanced HeroQuest.md:1712](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1712), [Advanced HeroQuest.md:4720](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4720) | Implemented | Defeated special and spellcasting monsters now award magical weapons/items, scrolls, spellbooks, spell components, poison supplies, and ammo through the live carry-limit and left-behind-treasure systems. |
| Magic Treasure Table governs discovery of rings, wands, potions, bows, scrolls, etc. | table | [Advanced HeroQuest.md:1718](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1718) | Implemented | Hidden-treasure magic finds generate actual treasure items; wands/scrolls cast from the live UI; Dawnstones spend stored non-regenerating Fate through the normal Fate decision flow; rings/amulets use live spell-protection checks; Strength Potions can be drunk at turn start for the listed 3-turn Strength and melee damage bonus; magic arrows/bolts are consumed as finite treasure ammunition and apply Death, True Flight, and Assassin effects during ranged combat. |
| Healing Potions restore wounds to starting level at beginning of next turn; do not restore dead heroes | text | [Advanced HeroQuest.md:3558](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3558) | Implemented | Healing Potions are now delayed-recovery items: drinking one, or administering one to an adjacent KO hero, restores the target to full strength at the start of the next turn and does not revive the dead. |

## Explicitly Deferred From This Document

- quest maps
- quest treasures unique to a scenario
- quest-specific scripted monster groups
- campaign flavour text
- narrative examples unless they state a mechanical rule we later need

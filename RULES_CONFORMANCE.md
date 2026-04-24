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
| Wizard exceptions for starting spells/components | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Partial | Costs/components are now captured in data, but spell systems are not implemented yet. |
| Dwarfs get `+2` to spot/disarm traps | text | [Advanced HeroQuest.md:636](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:636) | Implemented | Trap logic includes dwarf bonus. |

## Exploration Turn Structure

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| There are two turn types: exploration and combat | text | [Advanced HeroQuest.md:600](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:600) | Partial | Supported in code, but some edge-case transitions still need checking. |
| There must never be monsters in sight during an exploration turn | text | [Advanced HeroQuest.md:610](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:610) | Partial | Several fixes landed; this still needs ongoing validation. |
| Exploration turn phases: Hero Player, Exploration, Gamesmaster | text | [Advanced HeroQuest.md:612](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:612) | Partial | Current loop approximates this but is not fully rules-audited. |
| GM draws a dungeon counter on `1` or `12` only | text | [Advanced HeroQuest.md:620](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:620) | Implemented | Current exploration GM phase uses this. |
| Heroes/Henchmen move one at a time, no diagonal movement | text | [Advanced HeroQuest.md:623](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:623) | Implemented | Grid/pathing respects orthogonal movement. |
| Entering unexplored space must stop before the unexplored area | text | [Advanced HeroQuest.md:625](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:625) | Partial | Door/junction exploration is supported, but this should be revisited carefully in movement/reveal rules. |
| Opening a door in exploration ends movement; cannot open and move through in same turn | text | [Advanced HeroQuest.md:627](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:627) | Implemented | Current exploration actions consume the turn. |
| Opening a chest requires ending next to it | text | [Advanced HeroQuest.md:628](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:628) | Partial | Chest opening is supported, but chest contents are still simplified. |
| Armour changing takes whole Hero Player phases | text | [Advanced HeroQuest.md:615](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:615), [Advanced HeroQuest.md:630](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:630) | Implemented | Heroes can now spend a whole exploration turn removing or putting on carried armour/shields. |

## Searches And Traps

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Secret doors may only be searched in dead ends or rooms with only the entrance door | text | [Advanced HeroQuest.md:651](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:651) | Partial | Eligibility and start-of-turn checks are now enforced, but dead-end wall-section choice is still a simplified approximation. |
| Each wall may only be searched once | text | [Advanced HeroQuest.md:653](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:653) | Implemented | Room/wall search state is now tracked. |
| Secret Door Table outcomes | table | [Advanced HeroQuest.md:656](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:656) | Partial | Search exists; dungeon-counter side effects and precise placement should be checked. |
| Each room may only be searched once for hidden treasure | text | [Advanced HeroQuest.md:662](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:662) | Implemented | Room metadata tracks treasure searches. |
| Hidden Treasure Table outcomes | table | [Advanced HeroQuest.md:665](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:665) | Partial | The search table now uses the correct `2-6 / 7-16 / 17-24` branches and hidden magical treasure rolls on the Magic Treasure Table, but some treasure types still depend on the later full spell/item-use system. |
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
| Passage Features Table | table | [Advanced HeroQuest.md:765](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:765) | Partial | Implemented, but feature-specific logging/edge cases still need audit. |
| Passage End Table | table | [Advanced HeroQuest.md:775](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:775) | Implemented | Current generator uses corrected 2D12 behavior. |
| Room Type Table | table | [Advanced HeroQuest.md:828](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:828) | Implemented | Normal/hazard/lair/quest flow is live. |
| Room Doors Table | table | [Advanced HeroQuest.md:840](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:840) | Implemented | Current room generation uses this. |

## Combat Turn Structure

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Combat ends when no monsters remain or heroes escape | text | [Advanced HeroQuest.md:1042](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1042) | Partial | End-combat exists, but escape/pursuit needs a fuller audit. |
| Closing a door does not guarantee immediate escape; one more combat turn may occur | text | [Advanced HeroQuest.md:1043](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1043) | Missing | This exact pursuit/escape edge case is not fully modelled yet. |
| Models move up to Speed, orthogonally only | text | [Advanced HeroQuest.md:1050](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1050) | Implemented | Current combat movement respects this. |
| Entering an enemy death zone stops movement immediately | text | [Advanced HeroQuest.md:1051](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1051) | Partial | Death-zone logic exists, but full focus/pursuit behavior needs audit. |
| Doors may be opened/closed instead of attacking | text | [Advanced HeroQuest.md:1061](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1061) | Partial | Door actions exist, but combat-order nuances should be checked. |
| Running replaces attack and adds extra movement on `2-12`, stumble on `1` | text | [Advanced HeroQuest.md:1066](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1066) | Missing | Not yet implemented. |
| Pursuit rules after attempted escape | text | [Advanced HeroQuest.md:1069](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1069) | Missing | Needs dedicated implementation. |

## Hand-To-Hand Combat

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Adjacent enemies only, unless long reach allows diagonals | text | [Advanced HeroQuest.md:1079](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1079) | Implemented | Current melee reach logic follows this. |
| Hit roll uses attacker WS vs target WS | text | [Advanced HeroQuest.md:1083](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1083) | Implemented | Current combat uses the hit table. |
| Critical hit on `12`; large weapons crit on `11-12` | text | [Advanced HeroQuest.md:1086](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1086) | Implemented | Current weapon profiles support this. |
| Fumble on `1`; large weapons fumble on `1-2` | text | [Advanced HeroQuest.md:1090](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1090) | Implemented | Current weapon profiles support this. |
| Free attacks from crits/fumbles can chain | text | [Advanced HeroQuest.md:1094](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1094) | Partial | Free attacks exist, but chain behavior should be explicitly audited. |
| Damage dice depend on weapon; wounds on rolls `>= Toughness` | text | [Advanced HeroQuest.md:1097](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1097) | Implemented | Current melee damage model matches this. |
| Damage roll `12` causes critical damage and rerolls | text | [Advanced HeroQuest.md:1100](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1100) | Implemented | Current damage resolver supports exploding `12`s. |

## Ranged Combat

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Must carry ranged weapon | text | [Advanced HeroQuest.md:1195](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1195) | Implemented | Current ranged checks enforce this. |
| Must not be adjacent to target | text | [Advanced HeroQuest.md:1197](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1197) | Implemented | Enforced. |
| Target must not be in an enemy death zone | text | [Advanced HeroQuest.md:1198](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1198) | Implemented | Current ranged targeting blocks this. |
| Range counted without diagonals | text | [Advanced HeroQuest.md:1199](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1199) | Implemented | Current range checks use orthogonal count. |
| Must have line of sight | text | [Advanced HeroQuest.md:1200](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1200) | Partial | LOS now respects door blocking and model-based partial cover in ranged combat, but the broader visual/grey-area examples still need a manual audit. |
| Only thrown weapons can move and fire; bows/crossbows require no movement | text | [Advanced HeroQuest.md:1202](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1202) | Implemented | Current ranged checks enforce this distinction. |
| Friendly model between attacker and target blocks LOS unless adjacent to attacker | text | [Advanced HeroQuest.md:1206](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1206) | Partial | Ranged combat now treats intervening models as partial cover unless the blocker is a friendly model adjacent to the attacker. |
| Partial obscurity counts as `+4` range | text | [Advanced HeroQuest.md:1208](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1208) | Implemented | Ranged attack legality now applies the +4 effective-range penalty for partial cover. |
| Ranged crit halves target Toughness for damage | text | [Advanced HeroQuest.md:1230](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1230) | Implemented | Ranged crits now halve Toughness for damage resolution. |
| Ranged fumble hits nearby ally if available | text | [Advanced HeroQuest.md:1232](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1232) | Partial | Nearby-ally friendly fire is now modelled for adjacent allies; wider “nearby” interpretation may still need tuning. |
| Recover missiles after combat only if monsters killed, not if heroes escape | text | [Advanced HeroQuest.md:1224](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1224) | Missing | Ammo economy does not exist yet. |

## Fate, KO, And Death

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Fate can affect only things that happened this turn | text | [Advanced HeroQuest.md:1214](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1214) | Partial | Fate exists, but the full timing options are not yet modelled. |
| Fate can negate all damage suffered in a turn | text | [Advanced HeroQuest.md:1217](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1217) | Partial | Current handling is simplified. |
| Fate can convert a failed dice roll into a success | text | [Advanced HeroQuest.md:1219](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1219) | Missing | Not implemented. |
| Monsters and Henchmen die at `0` or below wounds | text | [Advanced HeroQuest.md:1221](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1221) | Partial | Monsters are correct; henchmen system is missing. |
| Heroes are KO at `0`, dead below `0` | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Partial | KO behavior has improved, but needs full rules audit. |
| KO hero counts as `WS 1` if attacked | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Missing | Not currently enforced. |
| Another hero can drag KO hero `3` spaces instead of a normal move | text | [Advanced HeroQuest.md:1222](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1222) | Missing | Not implemented. |
| KO hero can be carried during exploration at `6` squares max | text | [Advanced HeroQuest.md:1223](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1223) | Missing | Not implemented. |

## Equipment Tables

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hand-to-hand weapon Strength table | table | [Advanced HeroQuest.md:4028](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4028) | Implemented | Current melee profiles use AHQ-style Strength bands. |
| Certain melee weapons have minimum Strength | text | [Advanced HeroQuest.md:4018](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4018) | Partial | Long bow minimum is implemented; melee minimum-strength checks still need audit. |
| Spears and halberds attack diagonally | text | [Advanced HeroQuest.md:4044](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4044) | Implemented | Current long-reach rules cover this. |
| Ranged weapon table | table | [Advanced HeroQuest.md:4055](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4055) | Implemented | Current ranged profiles use this table. |
| Long bow requires Strength `6` | text | [Advanced HeroQuest.md:4065](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4065) | Implemented | Enforced. |
| Crossbow requires a turn to reload | text | [Advanced HeroQuest.md:4067](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4067) | Implemented | Current turn-end reload supports this. |
| Armour table modifies BS, Toughness, Speed | table | [Advanced HeroQuest.md:4077](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4077) | Implemented | Current armour logic uses these modifiers. |

## Costs And Between Expeditions

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Full Costs Table exists and should govern purchases | table | [Advanced HeroQuest.md:3532](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3532) | Partial | Captured in `data/tables.json`; only the combat-equipment subset is currently sold. |
| Cannot buy training before first expedition | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Missing | No between-expeditions training system yet. |
| Starting spells are free; extra spells only after first expedition | text | [Advanced HeroQuest.md:4011](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4011) | Missing | No spell-learning economy yet. |
| Starting spell components are free by wizard race | text | [Advanced HeroQuest.md:4013](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4013) | Missing | Not implemented. |
| Heroes/Henchmen can carry only `250` gold crowns each | text | [Advanced HeroQuest.md:1884](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1884) | Missing | Current economy has no carry-limit system. |
| Heroes/Henchmen can only carry limited item categories | text | [Advanced HeroQuest.md:1898](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1898) | Missing | Inventory limits not implemented. |

## Dungeon Counters

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Dungeon counters are drawn from specific trigger points, not arbitrarily | text | [Advanced HeroQuest.md:620](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:620), [Advanced HeroQuest.md:665](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:665), [Advanced HeroQuest.md:671](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:671) | Partial | Counter pool exists, but full timing legality still needs audit. |
| Ambush is combat-only | text | [Advanced HeroQuest.md:1520](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1520) | Partial | We fixed the major misuse, but all counter timing still needs review. |
| Escape, Character, Fate, Trap, Wandering Monster counters have specific procedures | text/table | [Advanced HeroQuest.md:1490](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1490) | Partial | Counter framework exists; not all outcomes are fully rules-tight yet. |

## Traps

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Trap counters may be played during exploration when entering an unentered room/passage or opening a chest | text | [Advanced HeroQuest.md:5442](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5442), [Advanced HeroQuest.md:5444](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5444), [Advanced HeroQuest.md:680](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:680) | Implemented | Exploration trap counters are now held until those legal triggers occur. |
| Trap type is rolled on the Traps Table, using different columns for room/passage vs chest | table | [Advanced HeroQuest.md:5455](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5455) | Implemented | Current trap resolver uses the central table. |
| Pit Trap: spotted but unavoidable; fall, possible wound on `9+`, climb out on `<= Speed`, others may leap | text | [Advanced HeroQuest.md:5461](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5461) | Partial | Pit state and leap actions exist; wound/climb details should be rechecked against the exact text. |
| Crossfire: roll count of bolts, each bolt does `3` damage dice | text | [Advanced HeroQuest.md:5475](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5475) | Partial | Trap exists; needs direct audit of bolt-count math and full effect messaging. |
| Portcullis: may be placed in doorway or across room, lifted by combined Strength `20+`, lift attempt costs full exploration turn | text | [Advanced HeroQuest.md:5463](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5463) | Partial | Core lift logic exists; exact placement fidelity still needs work. |
| Poison Dart: `1` damage die, if any wound is caused target is reduced to `0` wounds (KO) | text | [Advanced HeroQuest.md:5467](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5467) | Partial | Implemented at rules-engine level, but should be rechecked against KO handling. |
| Fireball trap: initial `5` damage dice to all under template, then persists/moves for `3` later turns | text | [Advanced HeroQuest.md:5468](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5468) | Missing | Current trap set does not model moving fireball templates. |
| Gas trap has area-of-effect and then gas subtype table | text/table | [Advanced HeroQuest.md:5478](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5478) | Partial | Gas statuses exist, but AoE shape, starting Toughness test, and exact penalties still need full audit. |
| Gas subtype `Mild Poison`: `1` wound and no movement for `3` turns | table | [Advanced HeroQuest.md:5481](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5481) | Implemented | Status layer supports this. |
| Gas subtype `Nausea`: rest-of-expedition movement/WS/BS/Strength penalties | table | [Advanced HeroQuest.md:5482](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5482) | Partial | Implemented broadly, but exact halving/cap behavior should be rechecked. |
| Gas subtype `Madness`: GM controls hero for `6` turns | table | [Advanced HeroQuest.md:5483](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5483) | Partial | Current status blocks direct control, but full GM-driven movement is not implemented. |
| Gas subtype `Strong Poison`: `8` damage dice | table | [Advanced HeroQuest.md:5484](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5484) | Partial | Needs targeted verification. |
| Gas subtype `Deadly Poison`: needs Healing Potion or dies | table | [Advanced HeroQuest.md:5485](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5485) | Partial | Current handling exists but depends on incomplete potion economy. |
| Shock: `5` damage dice or `10` if wearing metal armour | text | [Advanced HeroQuest.md:5488](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5488) | Implemented | Current trap logic handles metal-armour escalation. |
| Magic trap casts a spell from its spell table | table | [Advanced HeroQuest.md:5489](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5489) | Partial | Magic traps now resolve through the shared spell engine, but the separate moving Fireball trap sequence still needs its own full implementation. |
| Mindstealer: GM controls hero for `6` turns unless restrained by total Strength `>= 3x` target Strength | text | [Advanced HeroQuest.md:5497](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5497) | Partial | GM-control timer exists, restraint system does not. |
| Guillotine: `2` damage dice, loss of hand if any wound is caused, then Mantrap-style effects | text | [Advanced HeroQuest.md:5500](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5500) | Partial | Limb-loss aftereffects are not fully modelled. |
| Alarm: place wandering monsters along line of sight as far away as possible | text | [Advanced HeroQuest.md:5501](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5501) | Partial | Counter/reinforcement machinery exists, but exact trap behavior should be audited. |
| Blocks: dodge on `<= Speed`, otherwise `12` damage dice; if spotted but not disarmed can be bypassed only at half speed | text | [Advanced HeroQuest.md:5502](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5502) | Partial | Damage exists, but half-speed traversal is still not fully enforced. |
| Mantrap: limb loss with permanent weapon/speed restrictions, only healed between expeditions | text | [Advanced HeroQuest.md:5504](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5504) | Missing | Limb-loss restrictions are not yet fully implemented. |
| Spike: `3` damage dice and poison-dart follow-up on `8+` | text | [Advanced HeroQuest.md:5507](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5507) | Partial | Needs explicit verification. |

## Hazards

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hazard rooms roll on the Hazard Table | table | [Advanced HeroQuest.md:1560](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1560) | Implemented | Current room generation uses this table. |
| Wandering Monster hazard rolls wandering monsters | text | [Advanced HeroQuest.md:1566](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1566) | Implemented | Supported. |
| Non-Player Character hazard rolls Maiden / Witch / Man-at-Arms / Rogue | table | [Advanced HeroQuest.md:1570](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1570) | Implemented | Supported, with follower state tracked. |
| Maiden: guarded by wandering monsters; escort reward `100` gold | text | [Advanced HeroQuest.md:1576](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1576) | Partial | Reward/follower flow exists; full escort fragility should be rechecked. |
| Witch: one combat round to kill or close door, else teleports away with half the heroes' gold | text | [Advanced HeroQuest.md:1578](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1578) | Partial | Escape-state support exists, but exact round timing should be audited. |
| Man-at-Arms becomes a henchman for current leader if rescued | text | [Advanced HeroQuest.md:1595](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1595) | Partial | Follower outcome is recorded, but full henchman system is missing. |
| Rogue joins temporarily and modifies trap spotting/disarming; expedition-end betrayal table applies | text/table | [Advanced HeroQuest.md:1596](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1596) | Partial | Expedition-end outcomes exist; full henchman conversion still missing. |
| Chasm: heroic leap, sensible leap with rope, rope ladder, or leave | text | [Advanced HeroQuest.md:1607](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1607) | Partial | Leap logic exists; rope ladder/bridge systems are incomplete. |
| Chasm room also places monsters, door, and chest on the far side | text | [Advanced HeroQuest.md:1607](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1607) | Partial | Monsters/chest are supported; exact room setup should be rechecked. |
| Statue table: curse / animated statue / skaven warlord / safe jewel removal | table | [Advanced HeroQuest.md:1622](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1622) | Partial | Main outcomes are implemented. |
| Statue ruby is worth `400` gold once recovered | text | [Advanced HeroQuest.md:1627](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1627) | Partial | Reward flow still needs a tighter economy integration. |
| Rats hazard has five options including poison, Greek Fire, spell, fighting, or leaving | text | [Advanced HeroQuest.md:1632](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1632) | Partial | Current handling exists, but item-based solutions await expedition gear support. |
| Rat bites cannot be negated by Fate | text | [Advanced HeroQuest.md:1635](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1635) | Missing | Not explicitly enforced. |
| Bats hazard has Screech Bug / Greek Fire / spell / fight / leave options | text | [Advanced HeroQuest.md:1640](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1640) | Partial | Similar to Rats: item-based options still incomplete. |
| Bat wounds cannot be stopped by Fate | text | [Advanced HeroQuest.md:1644](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1644) | Missing | Not explicitly enforced. |
| Mould hazard: Greek Fire, wet hankies, or leave; mould table applies | text/table | [Advanced HeroQuest.md:1648](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1648) | Partial | Mould outcomes exist, but wet-hankies and item use are not complete. |
| Mushrooms are rolled in quantity; each mushroom uses the Mushroom table | text/table | [Advanced HeroQuest.md:1655](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1655) | Partial | Main effect outcomes are implemented. |
| Grate reveals lower room with special prisoner rules, rope escape, one model per combat turn | text | [Advanced HeroQuest.md:1666](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1666) | Partial | Lower-room encounter exists in abstracted form; full traversal is not complete. |
| Pool table: deadly poison / sleep / temporary Fate / full healing | table | [Advanced HeroQuest.md:1680](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1680) | Implemented | Pool interaction exists. |
| Magic Circle table: curse / summon / nothing / free spell / heal / temporary Fate, one-use drain | table | [Advanced HeroQuest.md:1685](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1685) | Partial | Most circle outcomes exist; full spell dependency remains limited by magic system. |
| Trapdoor table: trapped / lower room / crypt / maze / stairs | table | [Advanced HeroQuest.md:1693](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1693) | Partial | Current trapdoor logic covers several branches, but maze/sub-levels are still abstracted. |
| Crypt table includes mould spores / empty / gold ring / undead skaven | table | [Advanced HeroQuest.md:1697](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1697) | Partial | Crypt search exists, but some outcomes are simplified. |
| Throne grants chosen monster aura bonus to others while throne monster lives | text | [Advanced HeroQuest.md:1706](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1706) | Implemented | Current throne-leader state supports this. |

## Hazards, Chests, And Room Features

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Hazard rooms use their own room table/results | table/text | Hazard sections and room tables | Partial | Many hazard interactions exist now, but conformance still needs a detailed per-hazard audit. |
| Chests, crypts, trapdoors, statues, pools, circles, grates, chasms each have distinct procedures | text/table | Hazard and treasure sections | Partial | A large amount is implemented, but this area needs a rule-by-rule follow-up pass. |

## Magic

| Rule | Type | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| Wizards use spells and spell components recorded on the character sheet | text | [Advanced HeroQuest.md:568](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:568), [Advanced HeroQuest.md:3525](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3525) | Partial | Heroes now persist known spells and per-spell component counts, and the live pygame UI can cast from spellbooks, wands, and scrolls. |
| A Wizard may learn one new spell after each expedition by paying its listed cost | text | [Advanced HeroQuest.md:3547](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3547) | Missing | Cost data exists, learning flow does not. |
| Spell components all cost the same but differ by spell | text | [Advanced HeroQuest.md:3525](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3525) | Missing | Not implemented. |
| Starting wizards get free starting spells/components and cannot buy extra until after first expedition | text | [Advanced HeroQuest.md:4009](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4009) | Partial | New Wizard heroes now start with the four Bright spells shown as starting spells and one starting component for each; the between-expeditions tuition restriction is still not modelled. |
| A model in an opponent's death zone cannot cast certain spells | text | [Advanced HeroQuest.md:1057](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1057), [Advanced HeroQuest.md:4676](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4676) | Partial | Spell targeting now enforces the adjacent/death-zone spells we currently support, but this still needs a full spell-by-spell audit. |
| Magic Circle can permit a wizard to cast next spell without components | table | [Advanced HeroQuest.md:1689](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1689) | Partial | Free-cast state exists, but full spell use does not. |
| Magic trap can cast Inferno of Doom / Lightning Bolt / Choke / Flames of Death / Fireball | table | [Advanced HeroQuest.md:5489](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:5489) | Partial | Trap resolution now routes these spells through the shared spell engine; lingering moving-fireball behavior remains separate work. |
| Treasure and character monsters can carry magical weapons/items/spell books/components | text | [Advanced HeroQuest.md:1712](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1712), [Advanced HeroQuest.md:4720](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:4720) | Partial | Some monster/item metadata exists, but looting/equipment integration is incomplete. |
| Magic Treasure Table governs discovery of rings, wands, potions, bows, scrolls, etc. | table | [Advanced HeroQuest.md:1718](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:1718) | Partial | Hidden-treasure magic finds now generate actual treasure items and wands/scrolls can be cast from the live UI, but some spell/item edge cases remain simplified. |
| Healing Potions restore wounds to starting level at beginning of next turn; do not restore dead heroes | text | [Advanced HeroQuest.md:3558](F:\Agents\CascadeProjects\windsurf-project\document_extractor\output\Advanced%20HeroQuest.md:3558) | Partial | Healing Potions now exist as carried treasure and are consumed by deadly-poison hazard/trap logic, but general-use potion actions and exact next-turn timing are not complete yet. |

## Explicitly Deferred From This Document

- quest maps
- quest treasures unique to a scenario
- quest-specific scripted monster groups
- campaign flavour text
- narrative examples unless they state a mechanical rule we later need

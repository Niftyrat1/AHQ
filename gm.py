"""
Solo GM logic for Advanced HeroQuest.
Handles monster tactics and automated GM phase.
"""

import random
from typing import Callable, List, Tuple, Optional
from hero import Hero
from monster import Monster
from dungeon import Dungeon
from combat import (
    apply_damage_to_hero,
    get_fireball_template_area,
    get_ranged_los_state_for_models,
    get_hit_roll_needed,
    resolve_monster_attack,
    resolve_monster_ranged_attack,
    find_target_hero,
    roll_d,
    roll_damage,
)


DUNGEON_COUNTER_SET = [
    "trap", "trap", "trap", "trap",
    "wandering", "wandering", "wandering", "wandering",
    "ambush", "ambush", "ambush", "ambush",
    "escape", "escape", "escape", "escape",
    "character", "character", "character", "character",
    "fate", "fate", "fate", "fate",
]

MonsterFateRoll = Callable[[Monster, str, int, int], bool]


def get_tactics(monsters: List[Monster]) -> str:
    """
    Roll on Tactics Table to determine monster behavior.
    
    Returns:
        "REINFORCE", "MOVE_ATTACK", "ATTACK_MOVE", or "RANGED_ATTACK"
    """
    has_ranged = any(m.has_ranged() or m.has_special_rule("special_ranged_attack") for m in monsters)
    roll = roll_d(12)
    
    if not has_ranged:
        if roll == 1:
            return "REINFORCE"
        elif roll <= 6:
            return "MOVE_ATTACK"
        else:
            return "ATTACK_MOVE"
    else:
        if roll == 1:
            return "REINFORCE"
        elif roll <= 4:
            return "MOVE_ATTACK"
        elif roll <= 8:
            return "ATTACK_MOVE"
        else:
            return "RANGED_ATTACK"


def find_nearest_hero(monster: Monster, heroes: List[Hero], dungeon: Dungeon) -> Optional[Hero]:
    """Find the nearest hero to a monster."""
    living_heroes = [h for h in heroes if not h.is_dead and not h.is_ko]
    if not living_heroes:
        return None
    
    nearest = None
    min_distance = float('inf')
    
    for hero in living_heroes:
        dist = dungeon.get_distance(monster.x, monster.y, hero.x, hero.y)
        if dist < min_distance:
            min_distance = dist
            nearest = hero
    
    return nearest


def get_adjacent_positions(x: int, y: int) -> List[Tuple[int, int]]:
    """Get Manhattan-adjacent positions."""
    return [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]


def _hero_threatens_tile(hero: Hero, x: int, y: int) -> bool:
    """Whether a hero threatens a tile with melee."""
    dx = abs(hero.x - x)
    dy = abs(hero.y - y)
    if hero.has_long_reach_weapon():
        return max(dx, dy) == 1 and (dx != 0 or dy != 0)
    return dx + dy == 1


def _tile_in_hero_death_zone(x: int, y: int, heroes: List[Hero]) -> bool:
    """Whether any living hero threatens the tile."""
    return any(not hero.is_dead and not hero.is_ko and _hero_threatens_tile(hero, x, y) for hero in heroes)


def _hero_in_monster_death_zone(monster: Monster, hero: Hero) -> bool:
    """Whether a hero stands in the monster's melee threat zone."""
    return (hero.x, hero.y) in monster.get_death_zone_tiles()


def _monster_is_adjacent_to_hero(monster: Monster, hero: Hero) -> bool:
    """Whether any occupied monster tile touches the hero orthogonally."""
    return any(abs(mx - hero.x) + abs(my - hero.y) == 1 for mx, my in monster.get_occupied_tiles())


def _discard_monster_footprint(occupied: set, monster: Monster):
    """Remove all occupied tiles used by the monster footprint from a set."""
    for pos in monster.get_occupied_tiles():
        occupied.discard(pos)


def _add_monster_footprint(occupied: set, monster: Monster):
    """Add all occupied tiles used by the monster footprint to a set."""
    occupied.update(monster.get_occupied_tiles())


def _monster_blocks_tile(monster: Monster, x: int, y: int) -> bool:
    """Whether a living monster footprint covers a tile."""
    return (x, y) in monster.get_occupied_tiles()


def _monster_can_occupy_position(
    monster: Monster,
    anchor_x: int,
    anchor_y: int,
    dungeon: Dungeon,
    occupied: set,
    *,
    ignore_tiles: Optional[set] = None,
) -> bool:
    """Whether a monster footprint can legally occupy an anchor position."""
    ignore_tiles = ignore_tiles or set()
    footprint = {(anchor_x, anchor_y)}
    if monster.is_large_monster():
        footprint = {
            (anchor_x, anchor_y),
            (anchor_x - 1, anchor_y),
            (anchor_x, anchor_y + 1),
            (anchor_x - 1, anchor_y + 1),
        }
    for tile_x, tile_y in footprint:
        if (tile_x, tile_y) in occupied and (tile_x, tile_y) not in ignore_tiles:
            return False
        if not dungeon.is_walkable(tile_x, tile_y):
            return False
    return True


def _choose_target_hero_for_special_ranged(
    monster: Monster,
    heroes: List[Hero],
    monsters: List[Monster],
    dungeon: Dungeon,
) -> Optional[Hero]:
    """Pick the nearest living hero the special-ranged attacker can see."""
    candidates: List[Tuple[int, Hero]] = []
    origins = _get_special_team_tiles(monster, dungeon)
    for hero in heroes:
        if hero.is_dead or hero.is_ko:
            continue
        los_state, origin, _ = get_ranged_los_state_for_models(
            dungeon,
            monster,
            hero,
            friendly_models=monsters,
            hostile_models=heroes,
            attacker_tiles=origins,
        )
        if los_state != "blocked":
            candidates.append((dungeon.get_distance(origin[0], origin[1], hero.x, hero.y), hero))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _get_special_team_tiles(monster: Monster, dungeon: Dungeon) -> List[Tuple[int, int]]:
    """Return the effective squares occupied by a two-model specialist weapon team."""
    if not monster.is_special_weapon_team():
        return [(monster.x, monster.y)]
    tiles = [(monster.x, monster.y)]
    dx, dy = monster.get_support_offset()
    current_support = (monster.x + dx, monster.y + dy)
    if dungeon.is_walkable(current_support[0], current_support[1]):
        tiles.append(current_support)
        return tiles
    preferences = [
        (monster.x - 1, monster.y),
        (monster.x, monster.y - 1),
        (monster.x + 1, monster.y),
        (monster.x, monster.y + 1),
    ]
    for pos in preferences:
        if dungeon.is_walkable(pos[0], pos[1]):
            monster.set_support_offset(pos[0] - monster.x, pos[1] - monster.y)
            tiles.append(pos)
            break
    return tiles


def _resolve_globadier_attack(monster: Monster, target: Hero, heroes: List[Hero], dungeon: Dungeon, log: List[str]) -> bool:
    """Resolve Poisoned Wind Globadier fumes."""
    globes_left = int(monster.spellcasting.get("globes_remaining", 6))
    if globes_left <= 0:
        log.append(f"  {monster.name} is out of poisoned wind globes.")
        return False
    monster.spellcasting["globes_remaining"] = globes_left - 1
    log.append(f"  {monster.name} lobs poisoned wind at {target.name}.")
    affected = []
    for hero in heroes:
        if hero.is_dead:
            continue
        if max(abs(hero.x - target.x), abs(hero.y - target.y)) <= 1:
            affected.append(hero)
    if not affected:
        log.append("  The globe bursts harmlessly away from the party.")
        return True
    for hero in affected:
        test_roll = roll_d(12)
        if test_roll > hero.intelligence:
            log.append(f"  {hero.name} fails the breath test ({test_roll} vs Int {hero.intelligence})!")
            if hero.has_fate_available():
                hero.queue_failed_roll_fate_decision(
                    "poisoned_wind_breath",
                    position=[target.x, target.y],
                    roll=test_roll,
                )
                log.append(f"  {hero.name} may spend Fate to hold their breath.")
            else:
                apply_damage_to_hero(hero, hero.current_wounds, log)
        else:
            log.append(f"  {hero.name} holds their breath ({test_roll} vs Int {hero.intelligence}).")
    for gx in range(target.x - 1, target.x + 2):
        for gy in range(target.y - 1, target.y + 2):
            if dungeon.is_walkable(gx, gy):
                dungeon.trap_markers[(gx, gy)] = {
                    "type": "poisoned_wind_cloud",
                    "symbol": "PW",
                    "gm_phases_remaining": 2,
                }
    return True


def _resolve_warpfire_attack(
    monster: Monster,
    target: Hero,
    heroes: List[Hero],
    monsters: List[Monster],
    dungeon: Dungeon,
    log: List[str],
    monster_fate_roll: Optional[MonsterFateRoll] = None,
) -> bool:
    """Resolve a Warpfire Thrower attack."""
    team_tiles = _get_special_team_tiles(monster, dungeon)
    los_state, _, target_tile = get_ranged_los_state_for_models(
        dungeon,
        monster,
        target,
        friendly_models=monsters,
        hostile_models=heroes,
        attacker_tiles=team_tiles,
    )
    if los_state == "blocked":
        log.append(f"  {monster.name} cannot place the warpfire template in line of sight.")
        return False
    hit_needed = get_hit_roll_needed(max(monster.bs, 1), max(target.get_effective_bs(), 1))
    hit_roll = roll_d(12)
    log.append(f"  {monster.name} unleashes warpfire at {target.name}: rolled {hit_roll} (need {hit_needed}+)")
    if hit_roll < hit_needed and hit_roll < 12 and monster_fate_roll is not None:
        if monster_fate_roll(monster, "warpfire hit roll", hit_roll, hit_needed):
            hit_roll = hit_needed
    if hit_roll <= 1:
        log.append(f"  FUMBLE! {monster.name} explodes in a sheet of warpfire.")
        monster.take_damage(monster.current_wounds)
        for hero in heroes:
            if hero.is_dead:
                continue
            if any(abs(mx - hero.x) + abs(my - hero.y) == 1 for mx, my in team_tiles):
                damage, rolls = roll_damage(5, hero.get_effective_toughness(), False)
                log.append(f"  {hero.name} is caught in the blast: {rolls} vs T{hero.get_effective_toughness()} = {damage} wounds")
                apply_damage_to_hero(hero, damage, log)
        for other in monsters:
            if other is monster or other.is_dead:
                continue
            if any(
                abs(mx - ox) + abs(my - oy) == 1
                for mx, my in team_tiles
                for ox, oy in other.get_occupied_tiles()
            ):
                damage, rolls = roll_damage(5, other.toughness, False)
                log.append(f"  {other.name} is caught in the blast: {rolls} vs T{other.toughness} = {damage} wounds")
                if damage and other.take_damage(damage):
                    log.append(f"  {other.name} is killed by the blast! (+{other.pv} PV)")
        return True
    if hit_roll < hit_needed and hit_roll < 12:
        log.append("  The fireball misses and gutters out.")
        return True
    template_area = set(get_fireball_template_area(target_tile[0], target_tile[1]))
    affected = [
        hero for hero in heroes
        if not hero.is_dead and (hero.x, hero.y) in template_area
    ]
    for hero in affected:
        damage, rolls = roll_damage(5, hero.get_effective_toughness(), hit_roll >= 12)
        log.append(f"  {hero.name} is engulfed: {rolls} vs T{hero.get_effective_toughness()} = {damage} wounds")
        apply_damage_to_hero(hero, damage, log)
    affected_monsters = [
        other for other in monsters
        if other is not monster and not other.is_dead and any(tile in template_area for tile in other.get_occupied_tiles())
    ]
    for other in affected_monsters:
        damage, rolls = roll_damage(5, other.toughness, hit_roll >= 12)
        log.append(f"  {other.name} is engulfed: {rolls} vs T{other.toughness} = {damage} wounds")
        if damage and other.take_damage(damage):
            log.append(f"  {other.name} is killed by warpfire! (+{other.pv} PV)")
    return True


def _resolve_jezzail_attack(
    monster: Monster,
    target: Hero,
    heroes: List[Hero],
    monsters: List[Monster],
    dungeon: Dungeon,
    log: List[str],
    monster_fate_roll: Optional[MonsterFateRoll] = None,
) -> bool:
    """Resolve a Jezzailachis team shot."""
    team_tiles = _get_special_team_tiles(monster, dungeon)
    los_state, _, _ = get_ranged_los_state_for_models(
        dungeon,
        monster,
        target,
        friendly_models=monsters,
        hostile_models=heroes,
        attacker_tiles=team_tiles,
    )
    if los_state == "blocked":
        log.append(f"  {monster.name} cannot line up a jezzail shot.")
        return False
    hit_needed = get_hit_roll_needed(max(monster.bs, 1), max(target.get_effective_bs(), 1))
    hit_roll = roll_d(12)
    log.append(f"  {monster.name} fires a jezzail at {target.name}: rolled {hit_roll} (need {hit_needed}+)")
    if hit_roll < hit_needed and hit_roll < 12 and monster_fate_roll is not None:
        if monster_fate_roll(monster, "jezzail hit roll", hit_roll, hit_needed):
            hit_roll = hit_needed
    if hit_roll <= 1:
        log.append("  Miss!")
        monster.add_status_effect("jezzail_reloading", scope="combat", turns=2, cannot_move=True, cannot_attack=True)
        return True
    if hit_roll < hit_needed and hit_roll < 12:
        log.append("  Miss!")
        monster.add_status_effect("jezzail_reloading", scope="combat", turns=2, cannot_move=True, cannot_attack=True)
        return True
    is_critical = hit_roll >= 12
    toughness = max(1, target.toughness)
    if is_critical:
        toughness = max(1, (toughness + 1) // 2)
    damage, rolls = roll_damage(6, toughness, is_critical)
    log.append(f"  Jezzail round ignores armour: {rolls} vs base T{toughness} = {damage} wounds")
    apply_damage_to_hero(target, damage, log)
    monster.add_status_effect("jezzail_reloading", scope="combat", turns=2, cannot_move=True, cannot_attack=True)
    return True


def _resolve_special_monster_ranged_attack(
    monster: Monster,
    heroes: List[Hero],
    monsters: List[Monster],
    dungeon: Dungeon,
    log: List[str],
    monster_fate_roll: Optional[MonsterFateRoll] = None,
) -> bool:
    """Resolve bespoke Skaven special-ranged attacks from the AHQ tables."""
    target = _choose_target_hero_for_special_ranged(monster, heroes, monsters, dungeon)
    if target is None:
        return False

    monster_id = str(monster.id)
    if "globadier" in monster_id:
        return _resolve_globadier_attack(monster, target, heroes, dungeon, log)
    if "warpfire" in monster_id:
        return _resolve_warpfire_attack(monster, target, heroes, monsters, dungeon, log, monster_fate_roll)
    if "jezzail" in monster_id:
        return _resolve_jezzail_attack(monster, target, heroes, monsters, dungeon, log, monster_fate_roll)
    return False


def find_path_bfs(
    start_x: int, start_y: int,
    target_x: int, target_y: int,
    dungeon: Dungeon,
    occupied: set,
    monster: Optional[Monster] = None,
) -> Optional[List[Tuple[int, int]]]:
    """Find path using BFS. Returns list of positions from start to target, or None."""
    from collections import deque
    
    if (start_x, start_y) == (target_x, target_y):
        return []
    
    queue = deque([[(start_x, start_y)]])
    visited = {(start_x, start_y)}
    
    while queue:
        path = queue.popleft()
        x, y = path[-1]
        
        for nx, ny in get_adjacent_positions(x, y):
            if (nx, ny) in visited:
                continue
            if monster is None:
                if (nx, ny) in occupied and (nx, ny) != (target_x, target_y):
                    continue
                if not dungeon.is_walkable(nx, ny):
                    continue
            else:
                if not _monster_can_occupy_position(
                    monster,
                    nx,
                    ny,
                    dungeon,
                    occupied,
                    ignore_tiles=monster.get_occupied_tiles(),
                ):
                    continue
            
            new_path = path + [(nx, ny)]
            
            if (nx, ny) == (target_x, target_y):
                return new_path
            
            visited.add((nx, ny))
            queue.append(new_path)
    
    return None


def move_monster_toward(
    monster: Monster,
    target_x: int,
    target_y: int,
    dungeon: Dungeon,
    occupied: set,
    heroes: List[Hero],
    *,
    max_steps: int = 1,
) -> bool:
    """
    Move monster one step toward target using BFS pathfinding.
    Returns True if moved.
    """
    moved = False
    for _ in range(max(1, max_steps)):
        path = find_path_bfs(monster.x, monster.y, target_x, target_y, dungeon, occupied, monster=monster)
        if not path or len(path) < 2:
            moves = []
            for nx, ny in get_adjacent_positions(monster.x, monster.y):
                if _monster_can_occupy_position(
                    monster,
                    nx,
                    ny,
                    dungeon,
                    occupied,
                    ignore_tiles=monster.get_occupied_tiles(),
                ):
                    dist = dungeon.get_distance(nx, ny, target_x, target_y)
                    moves.append((dist, nx, ny))
            if not moves:
                break
            moves.sort()
            _, new_x, new_y = moves[0]
        else:
            new_x, new_y = path[1]

        _discard_monster_footprint(occupied, monster)
        monster.x, monster.y = new_x, new_y
        _add_monster_footprint(occupied, monster)
        moved = True
        if (target_x, target_y) in monster.get_death_zone_tiles():
            break
        if any(_tile_in_hero_death_zone(mx, my, heroes) for mx, my in monster.get_occupied_tiles()) and not monster.can_fly():
            break
    return moved


def move_monster_away_from_heroes(
    monster: Monster,
    heroes: List[Hero],
    dungeon: Dungeon,
    occupied: set,
    *,
    max_steps: int = 1,
) -> bool:
    """
    Move monster to get line of sight while not being adjacent to heroes.
    For ranged attackers.
    """
    moved = False
    for _ in range(max(1, max_steps)):
        candidates = []
        for nx, ny in get_adjacent_positions(monster.x, monster.y):
            if not _monster_can_occupy_position(
                monster,
                nx,
                ny,
                dungeon,
                occupied,
                ignore_tiles=monster.get_occupied_tiles(),
            ):
                continue

            candidate_tiles = {(nx, ny)}
            if monster.is_large_monster():
                candidate_tiles = {(nx, ny), (nx - 1, ny), (nx, ny + 1), (nx - 1, ny + 1)}
            adjacent_to_hero = any(
                any(abs(cx - hero.x) + abs(cy - hero.y) == 1 for cx, cy in candidate_tiles)
                for hero in heroes
                if not hero.is_dead and not hero.is_ko
            )
            if adjacent_to_hero:
                continue

            has_los = any(dungeon._has_los(nx, ny, hero.x, hero.y) for hero in heroes if not hero.is_dead and not hero.is_ko)
            if has_los:
                min_dist = min(dungeon.get_distance(nx, ny, h.x, h.y) for h in heroes)
                candidates.append((min_dist, nx, ny))

        if not candidates:
            break

        candidates.sort(reverse=True)
        _, new_x, new_y = candidates[0]
        _discard_monster_footprint(occupied, monster)
        monster.x, monster.y = new_x, new_y
        _add_monster_footprint(occupied, monster)
        moved = True
    return moved


def _monster_can_reach_attack_normally(monster: Monster, target: Hero, dungeon: Dungeon, occupied: set) -> bool:
    """Whether the monster can make a normal move and end adjacent to attack."""
    if _hero_in_monster_death_zone(monster, target):
        return True
    for nx, ny in get_adjacent_positions(target.x, target.y):
        if not dungeon.is_walkable(nx, ny):
            continue
        blocker_occupied = occupied.copy()
        _discard_monster_footprint(blocker_occupied, monster)
        if (nx, ny) in blocker_occupied:
            continue
        path = find_path_bfs(monster.x, monster.y, nx, ny, dungeon, blocker_occupied, monster=monster)
        if path is not None and max(0, len(path) - 1) <= monster.speed:
            return True
    return False


def run_gm_phase(
    monsters: List[Monster],
    heroes: List[Hero],
    dungeon: Dungeon,
    log: List[str],
    monster_spell_action: Optional[Callable[[Monster], bool]] = None,
    pursuit_mode: bool = False,
    monster_fate_roll: Optional[MonsterFateRoll] = None,
) -> Tuple[List[Monster], List[str]]:
    """
    Execute the GM phase.
    
    Returns:
        (updated_monsters, combat_log_messages)
    """
    # Remove dead monsters
    monsters = [m for m in monsters if not m.is_dead]
    
    if not monsters:
        return monsters, log
    
    # Get tactics
    tactic = get_tactics(monsters)
    log.append(f"GM Phase: Tactics roll = {tactic}")
    
    if tactic == "REINFORCE":
        log.append("  Reinforcements would arrive (Phase 2+)")
        return monsters, log
    
    # Track occupied positions
    occupied = set()
    for hero in heroes:
        if not hero.is_dead:
            occupied.add((hero.x, hero.y))
    for m in monsters:
        if not m.is_dead:
            occupied.update(m.get_occupied_tiles())
    
    # Process each monster
    for monster in monsters:
        if monster.is_dead:
            continue
        if monster.can_regenerate() and monster.current_wounds < monster.max_wounds:
            monster.current_wounds = min(monster.max_wounds, monster.current_wounds + 1)
            log.append(f"  {monster.name} regenerates 1 wound.")

        can_attack = not any(effect.get("cannot_attack") for effect in monster.status_effects)
        if any(effect.get("cannot_move") and effect.get("cannot_attack") for effect in monster.status_effects):
            log.append(f"  {monster.name} is held fast by magic.")
            continue

        if getattr(monster, "throne_leader", False):
            target = find_target_hero(heroes, monsters)
            if can_attack and target and _hero_in_monster_death_zone(monster, target):
                log.append(f"  {monster.name} attacks {target.name} from the throne")
                resolve_monster_attack(monster, target, log, attack_index=0, monster_fate_roll=monster_fate_roll)
                if monster.has_two_attacks() and not target.is_dead and not target.is_ko:
                    log.append(f"  {monster.name} makes a second attack from the throne.")
                    resolve_monster_attack(
                        monster,
                        target,
                        log,
                        damage_dice=monster.get_attack_damage_dice(1),
                        attack_index=1,
                        monster_fate_roll=monster_fate_roll,
                    )
            else:
                log.append(f"  {monster.name} holds the throne.")
            continue

        if monster_spell_action is not None and monster.has_spellcasting():
            if monster_spell_action(monster):
                continue
        
        target = find_target_hero(heroes, monsters)
        movement_steps = max(1, int(monster.speed))
        if pursuit_mode and target and not _monster_can_reach_attack_normally(monster, target, dungeon, occupied):
            run_roll = roll_d(12)
            if run_roll <= 1 and monster_fate_roll is not None:
                if monster_fate_roll(monster, "pursuit run roll", run_roll, 2):
                    run_roll = 2
            if run_roll > 1:
                movement_steps += run_roll
                log.append(f"  {monster.name} runs in pursuit for +{run_roll} movement.")
            else:
                log.append(f"  {monster.name} stumbles while pursuing and gains no extra movement.")

        if tactic == "RANGED_ATTACK" and (monster.has_ranged() or monster.has_special_rule("special_ranged_attack")):
            if monster.has_status_effect("jezzail_reloading"):
                log.append(f"  {monster.name} spends the turn reloading.")
                continue
            if monster.has_special_rule("special_ranged_attack"):
                if can_attack:
                    if _resolve_special_monster_ranged_attack(monster, heroes, monsters, dungeon, log, monster_fate_roll):
                        continue
                else:
                    log.append(f"  {monster.name} is choking and cannot attack.")
                    continue
            # Try to move to LOS position
            moved = False
            moved = move_monster_away_from_heroes(monster, heroes, dungeon, occupied, max_steps=movement_steps)
            if moved:
                log.append(f"  {monster.name} moves to ranged position")
            
            # Attack if in range and has LOS
            target = find_target_hero(heroes, monsters)
            if target:
                los_state, attack_origin, target_tile = get_ranged_los_state_for_models(
                    dungeon,
                    monster,
                    target,
                    friendly_models=monsters,
                    hostile_models=heroes,
                )
                effective_dist = dungeon.get_distance(
                    attack_origin[0],
                    attack_origin[1],
                    target_tile[0],
                    target_tile[1],
                ) + (4 if los_state == "partial" else 0)
                attack_range = monster.ranged.get("range", 12) if monster.ranged else 12
                if effective_dist <= attack_range:
                    if los_state != "blocked":
                        log.append(f"  {monster.name} ranged attack on {target.name}")
                        if can_attack:
                            fumble_target = next(
                                (
                                    other for other in heroes
                                    if not other.is_dead
                                    and other is not target
                                    and abs(other.x - target.x) + abs(other.y - target.y) <= 2
                                ),
                                None,
                            )
                            resolve_monster_ranged_attack(
                                monster,
                                target,
                                log,
                                partial_obscured=(los_state == "partial"),
                                fumble_target=fumble_target,
                                monster_fate_roll=monster_fate_roll,
                            )
                        else:
                            log.append(f"  {monster.name} is choking and cannot attack.")
        
        elif tactic in ("MOVE_ATTACK", "ATTACK_MOVE"):
            if not target:
                continue
            
            # Check if already adjacent
            if _hero_in_monster_death_zone(monster, target):
                # Attack
                if can_attack:
                    log.append(f"  {monster.name} attacks {target.name}")
                    resolve_monster_attack(monster, target, log, attack_index=0, monster_fate_roll=monster_fate_roll)
                    if monster.has_two_attacks() and not target.is_dead and not target.is_ko:
                        log.append(f"  {monster.name} makes a second attack.")
                        resolve_monster_attack(
                            monster,
                            target,
                            log,
                            damage_dice=monster.get_attack_damage_dice(1),
                            attack_index=1,
                            monster_fate_roll=monster_fate_roll,
                        )
                else:
                    log.append(f"  {monster.name} staggers but cannot attack.")
            else:
                # Move toward target
                if tactic == "MOVE_ATTACK":
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied, heroes, max_steps=movement_steps)
                    if moved:
                        log.append(f"  {monster.name} moves toward {target.name}")
                        # Check if now adjacent
                        if _hero_in_monster_death_zone(monster, target):
                            if can_attack:
                                log.append(f"  {monster.name} attacks {target.name}")
                                resolve_monster_attack(monster, target, log, attack_index=0, monster_fate_roll=monster_fate_roll)
                                if monster.has_two_attacks() and not target.is_dead and not target.is_ko:
                                    log.append(f"  {monster.name} makes a second attack.")
                                    resolve_monster_attack(
                                        monster,
                                        target,
                                        log,
                                        damage_dice=monster.get_attack_damage_dice(1),
                                        attack_index=1,
                                        monster_fate_roll=monster_fate_roll,
                                    )
                            else:
                                log.append(f"  {monster.name} staggers but cannot attack.")
                else:  # ATTACK_MOVE
                    # Move as close as possible
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied, heroes, max_steps=movement_steps)
                    if moved:
                        log.append(f"  {monster.name} moves toward {target.name}")
    
    return monsters, log


def create_dungeon_counter_pool() -> List[str]:
    """Create and shuffle a fresh dungeon counter pool."""
    pool = list(DUNGEON_COUNTER_SET)
    random.shuffle(pool)
    return pool


def check_dungeon_counter(counter_pool: List[str]) -> Optional[str]:
    """
    Check for dungeon counter (GM phase roll of 1 or 12) and draw from the pool.
    Returns counter type or None.
    """
    roll = roll_d(12)
    if roll == 1 or roll == 12:
        if not counter_pool:
            counter_pool.extend(create_dungeon_counter_pool())
        return counter_pool.pop()
    return None

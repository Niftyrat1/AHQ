"""
Solo GM logic for Advanced HeroQuest.
Handles monster tactics and automated GM phase.
"""

import random
from typing import Callable, List, Tuple, Optional
from hero import Hero
from monster import Monster
from dungeon import Dungeon
from combat import resolve_monster_attack, resolve_monster_ranged_attack, find_target_hero, roll_d


DUNGEON_COUNTER_SET = [
    "trap", "trap", "trap", "trap",
    "wandering", "wandering", "wandering", "wandering",
    "ambush", "ambush", "ambush", "ambush",
    "escape", "escape", "escape", "escape",
    "character", "character", "character", "character",
    "fate", "fate", "fate", "fate",
]


def get_tactics(monsters: List[Monster]) -> str:
    """
    Roll on Tactics Table to determine monster behavior.
    
    Returns:
        "REINFORCE", "MOVE_ATTACK", "ATTACK_MOVE", or "RANGED_ATTACK"
    """
    has_ranged = any(m.has_ranged() for m in monsters)
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


def find_path_bfs(
    start_x: int, start_y: int,
    target_x: int, target_y: int,
    dungeon: Dungeon,
    occupied: set
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
            if (nx, ny) in occupied and (nx, ny) != (target_x, target_y):
                continue
            if not dungeon.is_walkable(nx, ny):
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
    occupied: set
) -> bool:
    """
    Move monster one step toward target using BFS pathfinding.
    Returns True if moved.
    """
    # Find actual path to target using BFS
    path = find_path_bfs(monster.x, monster.y, target_x, target_y, dungeon, occupied)
    
    if not path or len(path) < 2:
        # No valid path found, try greedy fallback
        moves = []
        for nx, ny in get_adjacent_positions(monster.x, monster.y):
            if dungeon.is_walkable(nx, ny) and (nx, ny) not in occupied:
                dist = dungeon.get_distance(nx, ny, target_x, target_y)
                moves.append((dist, nx, ny))
        
        if not moves:
            return False
        
        moves.sort()
        _, new_x, new_y = moves[0]
    else:
        # Move to first step of the path (path[0] is current position, path[1] is next step)
        new_x, new_y = path[1]
    
    occupied.remove((monster.x, monster.y))
    monster.x, monster.y = new_x, new_y
    occupied.add((new_x, new_y))
    
    return True


def move_monster_away_from_heroes(
    monster: Monster,
    heroes: List[Hero],
    dungeon: Dungeon,
    occupied: set
) -> bool:
    """
    Move monster to get line of sight while not being adjacent to heroes.
    For ranged attackers.
    """
    # Find positions that have LOS to any hero and aren't adjacent to any hero
    candidates = []
    
    for nx, ny in get_adjacent_positions(monster.x, monster.y):
        if not dungeon.is_walkable(nx, ny) or (nx, ny) in occupied:
            continue
        
        # Check if adjacent to any hero
        adjacent_to_hero = False
        for hero in heroes:
            if dungeon.is_adjacent(nx, ny, hero.x, hero.y):
                adjacent_to_hero = True
                break
        
        if adjacent_to_hero:
            continue
        
        # Check LOS to any hero
        has_los = False
        for hero in heroes:
            if dungeon._has_los(nx, ny, hero.x, hero.y):
                has_los = True
                break
        
        if has_los:
            # Prefer positions further from heroes
            min_dist = min(dungeon.get_distance(nx, ny, h.x, h.y) for h in heroes)
            candidates.append((min_dist, nx, ny))
    
    if not candidates:
        return False
    
    # Sort by distance (descending - further is better)
    candidates.sort(reverse=True)
    _, new_x, new_y = candidates[0]
    
    occupied.remove((monster.x, monster.y))
    monster.x, monster.y = new_x, new_y
    occupied.add((new_x, new_y))
    
    return True


def run_gm_phase(
    monsters: List[Monster],
    heroes: List[Hero],
    dungeon: Dungeon,
    log: List[str],
    monster_spell_action: Optional[Callable[[Monster], bool]] = None,
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
            occupied.add((m.x, m.y))
    
    # Process each monster
    for monster in monsters:
        if monster.is_dead:
            continue

        can_attack = not any(effect.get("cannot_attack") for effect in monster.status_effects)
        if any(effect.get("cannot_move") and effect.get("cannot_attack") for effect in monster.status_effects):
            log.append(f"  {monster.name} is held fast by magic.")
            continue

        if getattr(monster, "throne_leader", False):
            target = find_target_hero(heroes, monsters)
            if can_attack and target and dungeon.is_adjacent(monster.x, monster.y, target.x, target.y):
                log.append(f"  {monster.name} attacks {target.name} from the throne")
                resolve_monster_attack(monster, target, log)
            else:
                log.append(f"  {monster.name} holds the throne.")
            continue

        if monster_spell_action is not None and monster.has_spellcasting():
            if monster_spell_action(monster):
                continue
        
        if tactic == "RANGED_ATTACK" and monster.has_ranged():
            # Try to move to LOS position
            moved = move_monster_away_from_heroes(monster, heroes, dungeon, occupied)
            if moved:
                log.append(f"  {monster.name} moves to ranged position")
            
            # Attack if in range and has LOS
            target = find_target_hero(heroes, monsters)
            if target:
                dist = dungeon.get_distance(monster.x, monster.y, target.x, target.y)
                blocker_positions = {
                    (hero.x, hero.y) for hero in heroes
                    if not hero.is_dead and not hero.is_ko and (hero.x, hero.y) not in {(monster.x, monster.y), (target.x, target.y)}
                }
                blocker_positions.update(
                    (other.x, other.y) for other in monsters
                    if not other.is_dead and other is not monster and (other.x, other.y) != (target.x, target.y)
                )
                adjacent_friendlies = {
                    (other.x, other.y) for other in monsters
                    if not other.is_dead and other is not monster and dungeon.is_adjacent(monster.x, monster.y, other.x, other.y)
                }
                los_state = dungeon.get_los_state(
                    monster.x,
                    monster.y,
                    target.x,
                    target.y,
                    model_blockers=blocker_positions,
                    adjacent_friendly_blockers=adjacent_friendlies,
                )
                effective_dist = dist + (4 if los_state == "partial" else 0)
                if effective_dist <= monster.ranged.get("range", 12):
                    if los_state != "blocked":
                        log.append(f"  {monster.name} ranged attack on {target.name}")
                        if can_attack:
                            fumble_target = next(
                                (
                                    other for other in monsters
                                    if not other.is_dead
                                    and other is not monster
                                    and dungeon.is_adjacent(monster.x, monster.y, other.x, other.y)
                                ),
                                None,
                            )
                            resolve_monster_ranged_attack(
                                monster,
                                target,
                                log,
                                partial_obscured=(los_state == "partial"),
                                fumble_target=fumble_target,
                            )
                        else:
                            log.append(f"  {monster.name} is choking and cannot attack.")
        
        elif tactic in ("MOVE_ATTACK", "ATTACK_MOVE"):
            target = find_target_hero(heroes, monsters)
            if not target:
                continue
            
            # Check if already adjacent
            if dungeon.is_adjacent(monster.x, monster.y, target.x, target.y):
                # Attack
                if can_attack:
                    log.append(f"  {monster.name} attacks {target.name}")
                    resolve_monster_attack(monster, target, log)
                else:
                    log.append(f"  {monster.name} staggers but cannot attack.")
            else:
                # Move toward target
                if tactic == "MOVE_ATTACK":
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied)
                    if moved:
                        log.append(f"  {monster.name} moves toward {target.name}")
                        # Check if now adjacent
                        if dungeon.is_adjacent(monster.x, monster.y, target.x, target.y):
                            if can_attack:
                                log.append(f"  {monster.name} attacks {target.name}")
                                resolve_monster_attack(monster, target, log)
                            else:
                                log.append(f"  {monster.name} staggers but cannot attack.")
                else:  # ATTACK_MOVE
                    # Move as close as possible
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied)
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

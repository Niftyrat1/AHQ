"""
Solo GM logic for Advanced HeroQuest.
Handles monster tactics and automated GM phase.
"""

import random
from typing import List, Tuple, Optional
from hero import Hero
from monster import Monster
from dungeon import Dungeon
from combat import resolve_monster_attack, find_target_hero, roll_d


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
            if dungeon.check_line_of_sight(nx, ny, hero.x, hero.y):
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
    log: List[str]
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
        
        if tactic == "RANGED_ATTACK" and monster.has_ranged():
            # Try to move to LOS position
            moved = move_monster_away_from_heroes(monster, heroes, dungeon, occupied)
            if moved:
                log.append(f"  {monster.name} moves to ranged position")
            
            # Attack if in range and has LOS
            target = find_target_hero(heroes, monsters)
            if target:
                dist = dungeon.get_distance(monster.x, monster.y, target.x, target.y)
                if dist <= monster.ranged.get("range", 12):
                    if dungeon.check_line_of_sight(monster.x, monster.y, target.x, target.y):
                        log.append(f"  {monster.name} ranged attack on {target.name}")
                        # For Phase 1, treat as melee with penalty
                        resolve_monster_attack(monster, target, log)
        
        elif tactic in ("MOVE_ATTACK", "ATTACK_MOVE"):
            target = find_target_hero(heroes, monsters)
            if not target:
                continue
            
            # Check if already adjacent
            if dungeon.is_adjacent(monster.x, monster.y, target.x, target.y):
                # Attack
                log.append(f"  {monster.name} attacks {target.name}")
                resolve_monster_attack(monster, target, log)
            else:
                # Move toward target
                if tactic == "MOVE_ATTACK":
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied)
                    if moved:
                        log.append(f"  {monster.name} moves toward {target.name}")
                        # Check if now adjacent
                        if dungeon.is_adjacent(monster.x, monster.y, target.x, target.y):
                            log.append(f"  {monster.name} attacks {target.name}")
                            resolve_monster_attack(monster, target, log)
                else:  # ATTACK_MOVE
                    # Move as close as possible
                    moved = move_monster_toward(monster, target.x, target.y, dungeon, occupied)
                    if moved:
                        log.append(f"  {monster.name} moves toward {target.name}")
    
    return monsters, log


def check_dungeon_counter() -> Optional[str]:
    """
    Check for dungeon counter (GM phase roll of 1 or 12).
    Returns counter type or None.
    """
    roll = roll_d(12)
    if roll == 1 or roll == 12:
        # Draw random counter (Phase 2)
        counters = ["trap", "wandering", "ambush", "escape", "character", "fate"]
        return random.choice(counters)
    return None

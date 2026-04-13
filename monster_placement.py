"""Monster placement according to Warhammer Quest rules."""
from typing import List, Tuple, Optional, Callable
from monster import Monster
from hero import Hero
from dungeon import Dungeon


def place_monsters_whq_rules(
    monster_ids: List[str],
    valid_tiles: List[Tuple[int, int]],
    dungeon: Dungeon,
    heroes: List[Hero],
    monster_library,
    combat_log: List[str]
) -> List[Monster]:
    """Place monsters according to Warhammer Quest rules.

    Rules:
    1. Ranged/spell monsters placed after hand-to-hand monsters
    2. First monster must be placed in a square as close to the party as possible
    3. If the monster can be placed in a square from which it can make an attack,
       it must be placed in that square
    4. Remaining monsters must be placed in a square adjacent to an already-placed monster
    """
    if not monster_ids or not valid_tiles:
        return []

    # Separate into hand-to-hand and ranged/spell
    hh_monsters = []
    ranged_monsters = []
    for monster_id in monster_ids:
        monster = monster_library.create_monster(monster_id)
        if monster:
            if monster.has_ranged():
                ranged_monsters.append(monster)
            else:
                hh_monsters.append(monster)

    placed_monsters = []
    placed_positions = []

    # Get hero positions for distance calculation
    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    if not hero_positions:
        return []

    def distance_to_party(pos):
        return min(abs(pos[0] - hx) + abs(pos[1] - hy) for hx, hy in hero_positions)

    def can_attack_hero(pos):
        """Check if a monster at this position could attack any hero."""
        for hx, hy in hero_positions:
            if abs(pos[0] - hx) + abs(pos[1] - hy) == 1:  # Adjacent
                return True
        return False

    def get_adjacent_to_placed():
        """Get valid tiles adjacent to already placed monsters."""
        adjacent = []
        for px, py in placed_positions:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                adj = (px + dx, py + dy)
                if adj in valid_tiles and adj not in placed_positions:
                    adjacent.append(adj)
        return adjacent

    # Place hand-to-hand monsters
    combat_log.append("  Placing hand-to-hand monsters:")
    for i, monster in enumerate(hh_monsters):
        available = valid_tiles if i == 0 else get_adjacent_to_placed()

        if not available:
            available = [t for t in valid_tiles if t not in placed_positions]

        if not available:
            combat_log.append(f"  No valid position for {monster.name}")
            continue

        if i == 0:
            # First monster: closest to party, preferring attack positions
            attack_positions = [p for p in available if can_attack_hero(p)]
            if attack_positions:
                pos = min(attack_positions, key=distance_to_party)
                combat_log.append(f"  {monster.name} at {pos} (can attack!)")
            else:
                pos = min(available, key=distance_to_party)
                combat_log.append(f"  {monster.name} at {pos} (closest)")
        else:
            # Subsequent monsters: adjacent to placed, preferring attack positions
            attack_positions = [p for p in available if can_attack_hero(p)]
            if attack_positions:
                pos = min(attack_positions, key=distance_to_party)
                combat_log.append(f"  {monster.name} at {pos} (can attack!)")
            else:
                pos = min(available, key=distance_to_party)
                combat_log.append(f"  {monster.name} at {pos}")

        monster.x, monster.y = pos
        placed_positions.append(pos)
        placed_monsters.append(monster)

    # Place ranged/spell monsters
    if ranged_monsters:
        combat_log.append("  Placing ranged/spell monsters:")
    for monster in ranged_monsters:
        available = get_adjacent_to_placed()
        if not available:
            available = [t for t in valid_tiles if t not in placed_positions]

        if not available:
            combat_log.append(f"  No valid position for {monster.name}")
            continue

        # Place ranged monsters preferring positions with LOS to heroes
        def has_los_to_hero(pos):
            for hx, hy in hero_positions:
                if dungeon._has_los(pos[0], pos[1], hx, hy):
                    return True
            return False

        los_positions = [p for p in available if has_los_to_hero(p)]
        if los_positions:
            pos = min(los_positions, key=distance_to_party)
            combat_log.append(f"  {monster.name} at {pos} (has LOS)")
        else:
            pos = min(available, key=distance_to_party)
            combat_log.append(f"  {monster.name} at {pos}")

        monster.x, monster.y = pos
        placed_positions.append(pos)
        placed_monsters.append(monster)

    return placed_monsters


def surprise_move_monster(
    monster: Monster,
    dungeon: Dungeon,
    heroes: List[Hero],
    all_monsters: List[Monster]
) -> bool:
    """Move monster up to 1 square during surprise (towards heroes for attack)."""
    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    if not hero_positions:
        return False

    # Find adjacent positions
    best_move = None
    best_dist = float('inf')

    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        new_x, new_y = monster.x + dx, monster.y + dy

        # Must be walkable and not occupied
        if not dungeon.is_walkable(new_x, new_y):
            continue
        occupied = any(m.x == new_x and m.y == new_y for m in all_monsters if m != monster)
        if occupied:
            continue

        # Check distance to nearest hero
        dist = min(abs(new_x - hx) + abs(new_y - hy) for hx, hy in hero_positions)

        # Prefer positions that allow attack
        can_attack = dist == 1

        if can_attack or dist < best_dist:
            best_dist = dist
            best_move = (new_x, new_y)
            if can_attack:
                break  # Best possible move

    if best_move:
        monster.x, monster.y = best_move
        return True
    return False

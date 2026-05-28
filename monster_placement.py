"""Monster placement helpers for Advanced HeroQuest combat starts."""
from typing import List, Tuple, Optional, Callable
from monster import Monster
from hero import Hero
from dungeon import Dungeon


ORTHOGONAL_DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def _footprint_for(monster: Monster, x: int, y: int, support_offset: Optional[Tuple[int, int]] = None) -> set[Tuple[int, int]]:
    """Return the occupied tiles for a monster if anchored at a position."""
    if monster.is_large_monster():
        return {(x, y), (x - 1, y), (x, y + 1), (x - 1, y + 1)}
    if monster.is_special_weapon_team():
        dx, dy = support_offset if support_offset is not None else monster.get_support_offset()
        return {(x, y), (x + dx, y + dy)}
    return {(x, y)}


def _find_support_offset(
    monster: Monster,
    x: int,
    y: int,
    valid_tile_set: set[Tuple[int, int]],
    occupied: set[Tuple[int, int]],
) -> Optional[Tuple[int, int]]:
    """Find an adjacent support-crew square for a specialist weapon team."""
    if not monster.is_special_weapon_team():
        return (0, 0)
    current = monster.get_support_offset()
    ordered = [current] + [direction for direction in ORTHOGONAL_DIRS if direction != current]
    for dx, dy in ordered:
        pos = (x + dx, y + dy)
        if pos in valid_tile_set and pos not in occupied:
            return dx, dy
    return None


def _can_place_monster(
    monster: Monster,
    pos: Tuple[int, int],
    valid_tile_set: set[Tuple[int, int]],
    occupied: set[Tuple[int, int]],
) -> bool:
    """Check whether a monster's full footprint fits on valid, unoccupied tiles."""
    x, y = pos
    support_offset = _find_support_offset(monster, x, y, valid_tile_set, occupied)
    if support_offset is None:
        return False
    footprint = _footprint_for(monster, x, y, support_offset)
    return footprint.issubset(valid_tile_set) and footprint.isdisjoint(occupied)


def _place_monster(
    monster: Monster,
    pos: Tuple[int, int],
    valid_tile_set: set[Tuple[int, int]],
    occupied: set[Tuple[int, int]],
) -> set[Tuple[int, int]]:
    """Anchor a monster and return the occupied footprint now claimed."""
    x, y = pos
    support_offset = _find_support_offset(monster, x, y, valid_tile_set, occupied)
    if support_offset is not None and monster.is_special_weapon_team():
        monster.set_support_offset(*support_offset)
    monster.x, monster.y = pos
    return _footprint_for(monster, x, y, support_offset)


def _can_move_monster_to(
    monster: Monster,
    x: int,
    y: int,
    dungeon: Dungeon,
    all_monsters: List[Monster],
) -> bool:
    """Check whether a monster can shift its full footprint to a dungeon position."""
    occupied = {
        tile
        for other in all_monsters
        if other is not monster and not other.is_dead
        for tile in other.get_occupied_tiles()
    }
    if monster.is_special_weapon_team():
        support_offset = monster.get_support_offset()
        sx, sy = x + support_offset[0], y + support_offset[1]
        if not dungeon.is_walkable(sx, sy) or (sx, sy) in occupied:
            return False
    else:
        support_offset = monster.get_support_offset()
    footprint = _footprint_for(monster, x, y, support_offset)
    return footprint.isdisjoint(occupied) and all(dungeon.is_walkable(tx, ty) for tx, ty in footprint)


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
    placed_positions: set[Tuple[int, int]] = set()

    # Get hero positions for distance calculation AND occupation check
    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    if not hero_positions:
        return []

    # Filter valid tiles to exclude hero positions
    valid_tile_set = set(valid_tiles)
    occupied_tiles = set(hero_positions)
    valid_tiles = [t for t in valid_tiles if t not in hero_positions]

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
                if adj in valid_tiles and adj not in occupied_tiles:
                    adjacent.append(adj)
        return adjacent

    # Place hand-to-hand monsters
    combat_log.append("  Placing hand-to-hand monsters:")
    for i, monster in enumerate(hh_monsters):
        available = valid_tiles if i == 0 else get_adjacent_to_placed()
        available = [pos for pos in available if _can_place_monster(monster, pos, valid_tile_set, occupied_tiles)]

        if not available:
            available = [t for t in valid_tiles if _can_place_monster(monster, t, valid_tile_set, occupied_tiles)]

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

        footprint = _place_monster(monster, pos, valid_tile_set, occupied_tiles)
        placed_positions.update(footprint)
        occupied_tiles.update(footprint)
        placed_monsters.append(monster)

    # Place ranged/spell monsters
    if ranged_monsters:
        combat_log.append("  Placing ranged/spell monsters:")
    for monster in ranged_monsters:
        available = get_adjacent_to_placed()
        if not available:
            available = [t for t in valid_tiles if t not in occupied_tiles]
        available = [pos for pos in available if _can_place_monster(monster, pos, valid_tile_set, occupied_tiles)]
        if not available:
            available = [t for t in valid_tiles if _can_place_monster(monster, t, valid_tile_set, occupied_tiles)]

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

        footprint = _place_monster(monster, pos, valid_tile_set, occupied_tiles)
        placed_positions.update(footprint)
        occupied_tiles.update(footprint)
        placed_monsters.append(monster)

    return placed_monsters


def place_monsters_ahq_section(
    monster_ids: List[str],
    valid_tiles: List[Tuple[int, int]],
    dungeon: Dungeon,
    heroes: List[Hero],
    monster_library,
    combat_log: List[str],
    *,
    favor_side: str,
) -> List[Monster]:
    """Place monsters within one discovered section using AHQ surprise rules.

    `favor_side` is:
    - `heroes`: place to favor the heroes when monsters are surprised
    - `gm`: place to favor the monsters when heroes are surprised
    """
    if not monster_ids or not valid_tiles:
        return []

    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    valid_tile_set = set(valid_tiles)
    occupied_tiles = set(hero_positions)
    available_tiles = [tile for tile in valid_tiles if tile not in hero_positions]
    if not available_tiles or not hero_positions:
        return []

    monsters: List[Monster] = []
    for monster_id in monster_ids:
        monster = monster_library.create_monster(monster_id)
        if monster is not None:
            monsters.append(monster)

    if not monsters:
        return []

    def nearest_hero_distance(pos: Tuple[int, int]) -> int:
        return min(abs(pos[0] - hx) + abs(pos[1] - hy) for hx, hy in hero_positions)

    def can_attack_hero(pos: Tuple[int, int]) -> bool:
        return any(abs(pos[0] - hx) + abs(pos[1] - hy) == 1 for hx, hy in hero_positions)

    reverse = favor_side == "heroes"
    if favor_side == "heroes":
        sort_key = lambda pos: (nearest_hero_distance(pos), 1 if can_attack_hero(pos) else 0, pos[1], pos[0])
    else:
        sort_key = lambda pos: (-1 if can_attack_hero(pos) else 0, -nearest_hero_distance(pos), -pos[1], -pos[0])

    ordered_tiles = sorted(available_tiles, key=sort_key, reverse=reverse)
    placed_monsters: List[Monster] = []
    for monster in monsters:
        pos = next((tile for tile in ordered_tiles if _can_place_monster(monster, tile, valid_tile_set, occupied_tiles)), None)
        if pos is None:
            combat_log.append(f"  No valid full-footprint position for {monster.name}")
            continue
        footprint = _place_monster(monster, pos, valid_tile_set, occupied_tiles)
        occupied_tiles.update(footprint)
        placed_monsters.append(monster)

    combat_log.append(
        f"  AHQ placement for {favor_side}: {[(monster.name, monster.x, monster.y) for monster in placed_monsters]}"
    )
    return placed_monsters


def move_monster_one_square_away(
    monster: Monster,
    dungeon: Dungeon,
    heroes: List[Hero],
    all_monsters: List[Monster]
) -> bool:
    """Move one monster up to one square to favor the heroes after a monster-surprise setup."""
    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    if not hero_positions:
        return False

    current_dist = min(abs(monster.x - hx) + abs(monster.y - hy) for hx, hy in hero_positions)
    best_move = None
    best_dist = current_dist

    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        new_x, new_y = monster.x + dx, monster.y + dy
        if not _can_move_monster_to(monster, new_x, new_y, dungeon, all_monsters):
            continue
        dist = min(abs(new_x - hx) + abs(new_y - hy) for hx, hy in hero_positions)
        if dist > best_dist:
            best_dist = dist
            best_move = (new_x, new_y)

    if best_move is None:
        return False
    monster.x, monster.y = best_move
    return True


def place_monsters_far_los(
    monster_ids: List[str],
    valid_tiles: List[Tuple[int, int]],
    dungeon: Dungeon,
    heroes: List[Hero],
    monster_library,
    combat_log: List[str],
) -> List[Monster]:
    """Place wandering/ambush reinforcements as far away as possible along line of sight."""
    if not monster_ids or not valid_tiles:
        return []

    hero_positions = [(h.x, h.y) for h in heroes if not h.is_dead]
    available_tiles = []
    valid_tile_set = set(valid_tiles)
    occupied_tiles = set(hero_positions)
    for tile in valid_tiles:
        if tile in hero_positions:
            continue
        if any(dungeon._has_los(tile[0], tile[1], hx, hy) for hx, hy in hero_positions):
            available_tiles.append(tile)
    if not available_tiles:
        available_tiles = [tile for tile in valid_tiles if tile not in hero_positions]
    if not available_tiles:
        return []

    def nearest_hero_distance(pos: Tuple[int, int]) -> int:
        return min(abs(pos[0] - hx) + abs(pos[1] - hy) for hx, hy in hero_positions)

    ordered_tiles = sorted(available_tiles, key=lambda pos: (nearest_hero_distance(pos), pos[1], pos[0]), reverse=True)
    placed_monsters: List[Monster] = []
    for monster_id in monster_ids:
        monster = monster_library.create_monster(monster_id)
        if monster is None:
            continue
        pos = next((tile for tile in ordered_tiles if _can_place_monster(monster, tile, valid_tile_set, occupied_tiles)), None)
        if pos is None:
            combat_log.append(f"  No valid full-footprint position for {monster.name}")
            continue
        footprint = _place_monster(monster, pos, valid_tile_set, occupied_tiles)
        occupied_tiles.update(footprint)
        placed_monsters.append(monster)

    combat_log.append(
        f"  AHQ far-LOS placement: {[(monster.name, monster.x, monster.y) for monster in placed_monsters]}"
    )
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
        if not _can_move_monster_to(monster, new_x, new_y, dungeon, all_monsters):
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

"""Passage generation for dungeon.

Handles 2-wide passage generation from junction tiles.
"""

import random
from typing import TYPE_CHECKING, List, Tuple

from .passage_ends import resolve_passage_end

if TYPE_CHECKING:
    from .dungeon import Dungeon


def generate_passage_from(dungeon: "Dungeon", x: int, y: int,
                          direction: Tuple[int, int], from_room: bool = False):
    """Generate a passage from a junction tile.

    Creates 2-wide passages with 1-3 sections (5-15 tiles).
    Each section is 5 tiles long.
    Places walls along passage edges.
    Resolves passage end with 2D12 roll.

    A 2-wide passage consists of two parallel tracks (track_A and track_B).
    For North/South passages, track_A is at x and track_B at x+1.
    For East/West passages, track_A is at y and track_B at y+1.
    The passage starts one step in direction from the junction tile.
    """
    # Roll for passage length (1-3 sections, each 5 tiles)
    roll = random.randint(1, 12)
    if roll <= 2:
        sections = 1  # 5 tiles
    elif roll <= 8:
        sections = 2  # 10 tiles
    else:
        sections = 3  # 15 tiles

    passage_tiles = []

    # Determine track positions based on direction
    if direction in [(0, -1), (0, 1)]:  # North or South
        # Track A at x, Track B at x+1, both step in y direction
        track_a_x, track_b_x = x, x + 1
        track_a_y = track_b_y = y  # Start AT junction, loop steps first
        wall_offset_a = (-1, 0)  # Left of track A
        wall_offset_b = (1, 0)   # Right of track B
    else:  # East or West
        # Track A at y, Track B at y+1, both step in x direction
        track_a_y, track_b_y = y, y + 1
        track_a_x = track_b_x = x  # Start AT junction, loop steps first
        wall_offset_a = (0, -1)  # Above track A
        wall_offset_b = (0, 1)   # Below track B

    # Place initial tiles at junction (no collision check for first tiles)
    dungeon.grid[(track_a_x, track_a_y)] = dungeon.TileType.FLOOR
    passage_tiles.append((track_a_x, track_a_y))
    last_a = (track_a_x, track_a_y)
    tiles_placed = 1
    wall_a = (track_a_x + wall_offset_a[0], track_a_y + wall_offset_a[1])
    if dungeon.grid.get(wall_a, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
        dungeon.grid[wall_a] = dungeon.TileType.WALL

    dungeon.grid[(track_b_x, track_b_y)] = dungeon.TileType.FLOOR
    passage_tiles.append((track_b_x, track_b_y))
    last_b = (track_b_x, track_b_y)
    tiles_placed = 2
    wall_b = (track_b_x + wall_offset_b[0], track_b_y + wall_offset_b[1])
    if dungeon.grid.get(wall_b, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
        dungeon.grid[wall_b] = dungeon.TileType.WALL

    collision_detected = False
    for section_idx in range(sections):
        if collision_detected:
            break
        for tile_idx in range(5):
            # Calculate next positions
            next_a_x = track_a_x + direction[0]
            next_a_y = track_a_y + direction[1]
            next_b_x = track_b_x + direction[0]
            next_b_y = track_b_y + direction[1]

            # Check for collision with existing tiles (only after placing first tiles)
            # Allow connecting to existing FLOOR/PASSAGE_END but stop at solid walls
            skip_a = False
            skip_b = False
            if tiles_placed >= 2:
                tile_a = dungeon.grid.get((next_a_x, next_a_y), dungeon.TileType.UNEXPLORED)
                tile_b = dungeon.grid.get((next_b_x, next_b_y), dungeon.TileType.UNEXPLORED)

                # Hard collision tiles that completely block passage
                blocking_tiles = (dungeon.TileType.WALL, dungeon.TileType.DOOR_CLOSED,
                                  dungeon.TileType.STAIRS_DOWN, dungeon.TileType.STAIRS_OUT)

                # If both tracks would hit blocking tiles, stop
                if tile_a in blocking_tiles and tile_b in blocking_tiles:
                    collision_detected = True
                    break

                # If one track hits a blocking tile, skip that track only
                if tile_a in blocking_tiles:
                    skip_a = True
                if tile_b in blocking_tiles:
                    skip_b = True

            # Step both tracks forward by direction
            track_a_x, track_a_y = next_a_x, next_a_y
            track_b_x, track_b_y = next_b_x, next_b_y

            if not skip_a:
                dungeon.grid[(track_a_x, track_a_y)] = dungeon.TileType.FLOOR
                passage_tiles.append((track_a_x, track_a_y))
                last_a = (track_a_x, track_a_y)
                tiles_placed += 1
                # Place wall on passage side
                wall_a = (track_a_x + wall_offset_a[0], track_a_y + wall_offset_a[1])
                if dungeon.grid.get(wall_a, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                    dungeon.grid[wall_a] = dungeon.TileType.WALL

            if not skip_b:
                dungeon.grid[(track_b_x, track_b_y)] = dungeon.TileType.FLOOR
                passage_tiles.append((track_b_x, track_b_y))
                last_b = (track_b_x, track_b_y)
                tiles_placed += 1
                # Place wall on passage side
                wall_b = (track_b_x + wall_offset_b[0], track_b_y + wall_offset_b[1])
                if dungeon.grid.get(wall_b, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                    dungeon.grid[wall_b] = dungeon.TileType.WALL

    # Check if we actually generated any tiles
    if not passage_tiles or last_a is None or last_b is None:
        return passage_tiles

    # If collision was detected, we hit an existing wall - don't create passage end
    if collision_detected:
        return passage_tiles

    # Roll for passage features (2D12)
    feature_roll = random.randint(1, 12) + random.randint(1, 12)
    # 2-4 and 22-24: Wandering monsters
    # 5-15: Nothing
    # 16-19: One door
    # 20-21: Two doors

    if 2 <= feature_roll <= 4 or 22 <= feature_roll <= 24:
        if passage_tiles:
            from monster import roll_lair_encounter
            mid = (len(passage_tiles) // 4) * 2
            for i, monster_id in enumerate(roll_lair_encounter()):
                idx = min(mid + i * 2, len(passage_tiles) - 2)
                pos = passage_tiles[idx]
                dungeon._place_monster(monster_id, pos[0], pos[1])

    elif 16 <= feature_roll <= 19:
        _place_side_door(dungeon, passage_tiles, direction)

    elif 20 <= feature_roll <= 21:
        _place_side_door(dungeon, passage_tiles, direction)
        _place_side_door(dungeon, passage_tiles, direction)

    # Roll for passage end (2D12)
    end_roll = random.randint(2, 24)

    # Resolve passage end
    resolve_passage_end(dungeon, last_a, last_b, direction, end_roll)

    return passage_tiles


def _place_side_door(dungeon: "Dungeon", passage_tiles: List[Tuple[int, int]], direction: Tuple[int, int]):
    """Place a door on a side wall of the passage.

    Finds a valid position along the passage and places a closed door.
    The door is placed perpendicular to the passage direction.
    """
    from .passage_ends import _get_both_perpendicular

    perp_dirs = _get_both_perpendicular(direction)

    # Try each passage tile to find a valid door position
    valid_positions = []
    for (tx, ty) in passage_tiles:
        for perp in perp_dirs:
            door_x = tx + perp[0]
            door_y = ty + perp[1]

            # Check if this position is valid for a door
            # Must be a WALL separating passage from unexplored space
            door_tile = dungeon.get_tile(door_x, door_y)
            if door_tile != dungeon.TileType.WALL:
                continue

            # Check that door connects passage to unexplored space
            other_side_x = door_x + perp[0]
            other_side_y = door_y + perp[1]
            other_side_tile = dungeon.get_tile(other_side_x, other_side_y)

            # Door should lead to unexplored space (for rooms)
            if other_side_tile == dungeon.TileType.UNEXPLORED:
                valid_positions.append((door_x, door_y, perp))

    if valid_positions:
        # Pick a random valid position
        door_x, door_y, door_dir = random.choice(valid_positions)
        dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
        dungeon.doors[(door_x, door_y)] = {'is_open': False, 'from_room': False}
    else:
        pass

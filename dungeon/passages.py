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

    last_a = last_b = None

    collision_detected = False
    tiles_placed = 0
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
            # First tiles may overlap with existing passage floor - that's OK
            if tiles_placed >= 2:
                tile_a = dungeon.grid.get((next_a_x, next_a_y), dungeon.TileType.UNEXPLORED)
                tile_b = dungeon.grid.get((next_b_x, next_b_y), dungeon.TileType.UNEXPLORED)

                # Stop if we would overlap with anything other than unexplored
                collision_tiles = (dungeon.TileType.FLOOR, dungeon.TileType.PASSAGE_END,
                                   dungeon.TileType.WALL, dungeon.TileType.DOOR_CLOSED,
                                   dungeon.TileType.STAIRS_DOWN, dungeon.TileType.STAIRS_OUT)
                if tile_a in collision_tiles or tile_b in collision_tiles:
                    dungeon._log(f"    Collision detected at ({next_a_x},{next_a_y})={tile_a} or ({next_b_x},{next_b_y})={tile_b}, stopping passage")
                    collision_detected = True
                    break

            # Step both tracks forward by direction
            track_a_x, track_a_y = next_a_x, next_a_y
            track_b_x, track_b_y = next_b_x, next_b_y

            # Place floor tiles for both tracks
            dungeon.grid[(track_a_x, track_a_y)] = dungeon.TileType.FLOOR
            dungeon.grid[(track_b_x, track_b_y)] = dungeon.TileType.FLOOR
            passage_tiles.append((track_a_x, track_a_y))
            passage_tiles.append((track_b_x, track_b_y))
            tiles_placed += 2

            # Track last positions for passage end calculation
            last_a = (track_a_x, track_a_y)
            last_b = (track_b_x, track_b_y)

            # Place walls on passage sides
            wall_a = (track_a_x + wall_offset_a[0], track_a_y + wall_offset_a[1])
            wall_b = (track_b_x + wall_offset_b[0], track_b_y + wall_offset_b[1])

            # Only place wall if not already something there
            if dungeon.grid.get(wall_a, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                dungeon.grid[wall_a] = dungeon.TileType.WALL
            if dungeon.grid.get(wall_b, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                dungeon.grid[wall_b] = dungeon.TileType.WALL

    # Check if we actually generated any tiles (collision may have stopped us immediately)
    if not passage_tiles or last_a is None or last_b is None:
        dungeon._log(f"    No tiles generated (collision at start), aborting passage")
        return passage_tiles

    dungeon._log(f"    Passage ends at {last_a} and {last_b}, roll: {roll}")

    # Roll for passage end (2D12)
    end_roll = random.randint(2, 24)
    dungeon._log(f"    Passage feature roll: {end_roll}")

    # Resolve passage end
    resolve_passage_end(dungeon, last_a, last_b, direction, end_roll)

    dungeon._log(f"    End tile check at {last_a}: {dungeon.get_tile(*last_a)}")
    dungeon._log(f"  Generated {len(passage_tiles)} tiles")

    return passage_tiles

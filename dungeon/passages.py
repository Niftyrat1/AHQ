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
        track_a_y = track_b_y = y + direction[1]  # First step in direction
        wall_offset_a = (-1, 0)  # Left of track A
        wall_offset_b = (1, 0)   # Right of track B
    else:  # East or West
        # Track A at y, Track B at y+1, both step in x direction
        track_a_y, track_b_y = y, y + 1
        track_a_x = track_b_x = x + direction[0]  # First step in direction
        wall_offset_a = (0, -1)  # Above track A
        wall_offset_b = (0, 1)   # Below track B

    last_a = last_b = None

    for section_idx in range(sections):
        for tile_idx in range(5):
            # Step both tracks forward by direction
            track_a_x += direction[0]
            track_a_y += direction[1]
            track_b_x += direction[0]
            track_b_y += direction[1]

            # Place floor tiles for both tracks
            dungeon.grid[(track_a_x, track_a_y)] = dungeon.TileType.FLOOR
            dungeon.grid[(track_b_x, track_b_y)] = dungeon.TileType.FLOOR
            passage_tiles.append((track_a_x, track_a_y))
            passage_tiles.append((track_b_x, track_b_y))

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

    dungeon._log(f"    Passage ends at {last_a} and {last_b}, roll: {roll}")

    # Roll for passage end (2D12)
    end_roll = random.randint(2, 24)
    dungeon._log(f"    Passage feature roll: {end_roll}")

    # Resolve passage end
    resolve_passage_end(dungeon, last_a, last_b, direction, end_roll)

    dungeon._log(f"    End tile check at {last_a}: {dungeon.get_tile(*last_a)}")
    dungeon._log(f"  Generated {len(passage_tiles)} tiles")

    return passage_tiles

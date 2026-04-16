"""Passage generation for dungeon.

Handles 2-wide passage generation from junction tiles.
"""

import random
from typing import TYPE_CHECKING, List, Tuple

from .passage_ends import resolve_passage_end

if TYPE_CHECKING:
    from .dungeon import Dungeon


def generate_passage_from(dungeon: "Dungeon", x: int, y: int, 
                          direction: Tuple[int, int], from_room: bool = False,
                          row: int = 1, source_dir: Tuple[int, int] = (0, 0)):
    """Generate a passage from a junction tile.
    
    Creates 2-wide passages with 1-3 sections (5-15 tiles).
    Each section is 5 tiles long.
    Places walls along passage edges.
    Resolves passage end with 2D12 roll.
    
    Args:
        row: Which row of the T-junction (1 or 2). Row 1 is closer to the original passage.
        source_dir: The direction of the source passage that created this junction.
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
    
    # Determine left/right offsets based on direction
    if direction in [(0, -1), (0, 1)]:  # North or South
        left_offset = (-1, 0)
        right_offset = (1, 0)
    else:  # East or West
        left_offset = (0, -1)
        right_offset = (0, 1)
    
    # Track current position
    if direction == (0, -1):  # North
        current_x, current_y = x + 1, y  # track right tile (x+1)
    elif direction == (0, 1):  # South
        current_x, current_y = x + 1, y + 1
    elif direction == (1, 0):  # East
        # For East from T-junction, offset depends on source direction and row
        # North source: offset 0 (passage at same y as junction)
        # South source: offset 1 if row 1 (passage one y lower)
        offset = 0
        if source_dir == (0, 1) and row == 1:  # South source, row 1
            offset = 1
        current_x, current_y = x + 1, y + offset  # track right tile (x+1)
    else:  # West
        current_x, current_y = x, y  # track left tile (x)
    last_left = None
    last_right = None
    
    for section_idx in range(sections):
        for tile_idx in range(5):
            current_x += direction[0]
            current_y += direction[1]
            
            # Calculate left and right tile positions
            if direction in [(0, -1), (0, 1)]:  # North/South - left/right are side by side (x +/- 1)
                left_x, left_y = current_x - 1, current_y
                right_x, right_y = current_x, current_y
            elif direction == (1, 0):  # East - left/right are stacked vertically (y +/- 1)
                left_x, left_y = current_x, current_y - 1
                right_x, right_y = current_x, current_y
            else:  # West - left/right are stacked vertically (y +/- 1), but need to track from left tile
                left_x, left_y = current_x, current_y
                right_x, right_y = current_x, current_y + 1
            
            # Place floor tiles
            dungeon.grid[(left_x, left_y)] = dungeon.TileType.FLOOR
            dungeon.grid[(right_x, right_y)] = dungeon.TileType.FLOOR
            passage_tiles.append((left_x, left_y))
            passage_tiles.append((right_x, right_y))
            
            # Track last positions for passage end calculation
            last_left = (left_x, left_y)
            last_right = (right_x, right_y)
            
            # Place walls on passage sides
            wall_left = (left_x + left_offset[0], left_y + left_offset[1])
            wall_right = (right_x + right_offset[0], right_y + right_offset[1])
            
            # Only place wall if not already something there (like an existing wall)
            if dungeon.grid.get(wall_left, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                dungeon.grid[wall_left] = dungeon.TileType.WALL
            if dungeon.grid.get(wall_right, dungeon.TileType.UNEXPLORED) == dungeon.TileType.UNEXPLORED:
                dungeon.grid[wall_right] = dungeon.TileType.WALL
    
    dungeon._log(f"    Passage ends at {last_left} and {last_right}, roll: {roll}")
    
    # Roll for passage end (2D12)
    end_roll = random.randint(2, 24)
    dungeon._log(f"    Passage feature roll: {end_roll}")
    
    # Resolve passage end
    resolve_passage_end(dungeon, last_left, last_right, direction, end_roll)
    
    dungeon._log(f"    End tile check at {last_left}: {dungeon.get_tile(*last_left)}")
    dungeon._log(f"  Generated {len(passage_tiles)} tiles")
    
    return passage_tiles

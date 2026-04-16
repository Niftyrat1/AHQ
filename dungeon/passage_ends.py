"""Passage end generation for dungeon passages.

Handles T-junctions, dead ends, turns, stairs, and their capping walls.
All passage ends are 2x2 grids at forward1 and forward2 positions.
"""

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .dungeon import Dungeon


def _get_both_perpendicular(direction: Tuple[int, int]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Get both perpendicular directions (left and right turns)."""
    if direction == (0, -1):  # North
        return ((-1, 0), (1, 0))  # West, East
    elif direction == (0, 1):   # South
        return ((1, 0), (-1, 0))  # East, West
    elif direction == (1, 0):   # East
        return ((0, -1), (0, 1))  # North, South
    else:  # West
        return ((0, 1), (0, -1))  # South, North


def _explore_passage_end_2x2(dungeon: "Dungeon", p1, p2, p3, p4, extra_walls=None):
    """Explore a 2x2 area, adjacent walls, and any extra walls (e.g., capping walls)."""
    dungeon._log(f"    Exploring 2x2 area: {p1}, {p2}, {p3}, {p4}")
    for (tx, ty) in [p1, p2, p3, p4]:
        dungeon.explored.add((tx, ty))
        dungeon._log(f"      Added to explored: ({tx},{ty}) tile: {dungeon.get_tile(tx, ty)}")
        # Explore adjacent walls
        for wx, wy in [(tx-1, ty), (tx+1, ty), (tx, ty-1), (tx, ty+1)]:
            if dungeon.get_tile(wx, wy) == dungeon.TileType.WALL:
                dungeon.explored.add((wx, wy))
                dungeon._log(f"      Added wall to explored: ({wx},{wy})")
    # Explore any extra walls (e.g., capping walls placed after the 2x2 area)
    if extra_walls:
        for pos in extra_walls:
            dungeon.explored.add(pos)
            dungeon._log(f"      Added extra wall to explored: {pos}")


def resolve_passage_end(dungeon: "Dungeon", left_pos: Tuple[int, int], 
                        right_pos: Tuple[int, int], direction: Tuple[int, int], roll: int):
    """Resolve what happens at passage end (2D12).
    
    The 2x2 passage end is placed at forward1 and forward2 (2 tiles beyond left_pos/right_pos).
    Capping walls are placed one tile beyond forward2.
    Pending junctions are set for the 2x2 passage end tiles.
    """
    if not hasattr(dungeon, 'pending_junctions'):
        dungeon.pending_junctions = {}
    
    # Calculate TWO forward rows for 2x2 passage end
    # Row 1: one step beyond end tiles (e.g., y=-11 for North passage ending at y=-10)
    forward1_left = (left_pos[0] + direction[0], left_pos[1] + direction[1])
    forward1_right = (right_pos[0] + direction[0], right_pos[1] + direction[1])
    # Row 2: two steps beyond end tiles (y=-12) - this completes the 2x2
    forward2_left = (forward1_left[0] + direction[0], forward1_left[1] + direction[1])
    forward2_right = (forward1_right[0] + direction[0], forward1_right[1] + direction[1])
    
    # T-junction (2-3, 12-14, 23-24): 2x2 floor at forward1 and forward2
    if roll <= 3 or 12 <= roll <= 14 or roll >= 23:
        _generate_t_junction(dungeon, left_pos, right_pos, direction,
                            forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Dead end (4-8)
    elif 4 <= roll <= 8:
        _generate_dead_end(dungeon, left_pos, right_pos, direction,
                          forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Right turn (9-11)
    elif 9 <= roll <= 11:
        _generate_turn(dungeon, left_pos, right_pos, direction, 'right',
                      forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Left turn (15-17)
    elif 15 <= roll <= 17:
        _generate_turn(dungeon, left_pos, right_pos, direction, 'left',
                      forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Stairs down (18-19)
    elif 18 <= roll <= 19:
        _generate_stairs(dungeon, left_pos, right_pos, direction, 'down',
                        forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Stairs out (20-22)
    elif 20 <= roll <= 22:
        _generate_stairs(dungeon, left_pos, right_pos, direction, 'out',
                        forward1_left, forward1_right, forward2_left, forward2_right)


def _generate_t_junction(dungeon: "Dungeon", left_pos, right_pos, direction,
                         forward1_left, forward1_right, forward2_left, forward2_right):
    """Generate a T-junction with 2x2 floor and capping walls."""
    dungeon._log(f"    T-junction: passage end at {left_pos},{right_pos}, "
                 f"2x2 at {forward1_left},{forward1_right} and {forward2_left},{forward2_right}")
    
    # Place FLOOR at both forward rows (the 2x2 passage end)
    for pos in [forward1_left, forward1_right, forward2_left, forward2_right]:
        dungeon.grid[pos] = dungeon.TileType.FLOOR
    dungeon._log(f"      Set 2x2 passage end to FLOOR")
    
    # Capping walls one step beyond the 2x2 passage end
    wall_left = (forward2_left[0] + direction[0], forward2_left[1] + direction[1])
    wall_right = (forward2_right[0] + direction[0], forward2_right[1] + direction[1])
    # Side walls adjacent to capping walls (perpendicular to passage direction)
    if direction in [(0, -1), (0, 1)]:  # North/South - side walls at x-1 and x+1
        side_left = (wall_left[0] - 1, wall_left[1])
        side_right = (wall_right[0] + 1, wall_right[1])
    else:  # East/West - side walls at y-1 and y+1
        side_left = (wall_left[0], wall_left[1] - 1)
        side_right = (wall_right[0], wall_right[1] + 1)
    
    dungeon._log(f"    Placing capping walls at {wall_left} and {wall_right}")
    dungeon._log(f"    Placing side walls at {side_left} and {side_right}")
    for pos in [wall_left, wall_right, side_left, side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
    
    # Set pending for all 4 T-junction tiles with exit directions
    perp_dirs = _get_both_perpendicular(direction)
    exits = list(perp_dirs)
    dungeon.pending_junctions[forward1_left] = exits
    dungeon.pending_junctions[forward1_right] = exits
    dungeon.pending_junctions[forward2_left] = exits
    dungeon.pending_junctions[forward2_right] = exits
    dungeon._log(f"    T-junction pending set for: {forward1_left}, {forward1_right}, {forward2_left}, {forward2_right}")
    
    # Explore the 2x2 passage end area and capping walls
    _explore_passage_end_2x2(dungeon, forward1_left, forward1_right, forward2_left, forward2_right,
                              extra_walls=[wall_left, wall_right, side_left, side_right])


def _generate_dead_end(dungeon: "Dungeon", left_pos, right_pos, direction,
                       forward1_left, forward1_right, forward2_left, forward2_right):
    """Generate a dead end with 2x2 PASSAGE_END and capping walls."""
    dungeon._log(f"    Dead end: passage end at {left_pos},{right_pos}, "
                 f"2x2 at {forward1_left},{forward1_right} and {forward2_left},{forward2_right}")
    
    # Place PASSAGE_END at both forward rows (the 2x2 dead end)
    for pos in [forward1_left, forward1_right, forward2_left, forward2_right]:
        dungeon.grid[pos] = dungeon.TileType.PASSAGE_END
    dungeon._log(f"      Set 2x2 dead end to PASSAGE_END")
    
    # Calculate side walls adjacent to the 2x2 dead end (at forward1 and forward2)
    # For vertical passages: side walls are x-1 and x+1
    # For horizontal passages: side walls are y-1 and y+1
    if direction in [(0, -1), (0, 1)]:  # North/South
        f1_side_left = (forward1_left[0] - 1, forward1_left[1])
        f1_side_right = (forward1_right[0] + 1, forward1_right[1])
        f2_side_left = (forward2_left[0] - 1, forward2_left[1])
        f2_side_right = (forward2_right[0] + 1, forward2_right[1])
    else:  # East/West
        f1_side_left = (forward1_left[0], forward1_left[1] - 1)
        f1_side_right = (forward1_right[0], forward1_right[1] + 1)
        f2_side_left = (forward2_left[0], forward2_left[1] - 1)
        f2_side_right = (forward2_right[0], forward2_right[1] + 1)
    
    # Place side walls alongside the 2x2 dead end
    for pos in [f1_side_left, f1_side_right, f2_side_left, f2_side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
    dungeon._log(f"    Dead end side walls at {f1_side_left}, {f1_side_right}, "
                 f"{f2_side_left}, {f2_side_right}")
    
    # Capping walls one step beyond the 2x2 dead end
    wall_left = (forward2_left[0] + direction[0], forward2_left[1] + direction[1])
    wall_right = (forward2_right[0] + direction[0], forward2_right[1] + direction[1])
    # Side walls adjacent to capping walls (perpendicular to passage direction)
    if direction in [(0, -1), (0, 1)]:  # North/South - side walls at x-1 and x+1
        side_left = (wall_left[0] - 1, wall_left[1])
        side_right = (wall_right[0] + 1, wall_right[1])
    else:  # East/West - side walls at y-1 and y+1
        side_left = (wall_left[0], wall_left[1] - 1)
        side_right = (wall_right[0], wall_right[1] + 1)
    
    dungeon._log(f"    Placing capping walls at {wall_left} and {wall_right}")
    dungeon._log(f"    Placing side walls at {side_left} and {side_right}")
    for pos in [wall_left, wall_right, side_left, side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
    
    # Explore the 2x2 dead end and all its walls
    all_walls = [f1_side_left, f1_side_right, f2_side_left, f2_side_right,
                 wall_left, wall_right, side_left, side_right]
    _explore_passage_end_2x2(dungeon, forward1_left, forward1_right, forward2_left, forward2_right,
                             extra_walls=all_walls)
    
    dungeon._log(f"    Placed PASSAGE_END tiles with side walls and capping walls")


def _generate_turn(dungeon: "Dungeon", left_pos, right_pos, direction, turn_type,
                   forward1_left, forward1_right, forward2_left, forward2_right):
    """Generate a turn (right or left) with 2x2 floor and capping walls."""
    # Determine turn direction
    if direction == (1, 0):  # East -> South (right) or North (left)
        turn_dir = (0, 1) if turn_type == 'right' else (0, -1)
    elif direction == (-1, 0):  # West -> North (right) or South (left)
        turn_dir = (0, -1) if turn_type == 'right' else (0, 1)
    elif direction == (0, 1):  # South -> West (right) or East (left)
        turn_dir = (-1, 0) if turn_type == 'right' else (1, 0)
    else:  # North -> East (right) or West (left)
        turn_dir = (1, 0) if turn_type == 'right' else (-1, 0)
    
    dungeon._log(f"    {turn_type.capitalize()} turn: passage end at {left_pos},{right_pos}, "
                 f"2x2 at {forward1_left},{forward1_right} and {forward2_left},{forward2_right}")
    
    # Place FLOOR at both forward rows (the 2x2 turn area)
    for pos in [forward1_left, forward1_right, forward2_left, forward2_right]:
        dungeon.grid[pos] = dungeon.TileType.FLOOR
    
    # Explore the 2x2 turn area (capping walls will be added after placement)
    _explore_passage_end_2x2(dungeon, forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Place side walls along the 2x2 turn area to guide the turn direction
    # For right/left turns, we need to wall off the opposite side to force the turn
    # Direction -> turn_dir mapping:
    #   North (0,-1): right turn -> East (1,0), left turn -> West (-1,0)
    #   South (0,1):  right turn -> West (-1,0), left turn -> East (1,0)
    #   East (1,0):   right turn -> South (0,1), left turn -> North (0,-1)
    #   West (-1,0):  right turn -> North (0,-1), left turn -> South (0,1)
    if direction == (0, -1):  # North passage turning East/West
        # Wall on opposite side (West for right/East, East for left/West)
        turn_side_offset = (-1, 0) if turn_dir == (1, 0) else (1, 0)
    elif direction == (0, 1):  # South passage turning West/East
        # Wall on opposite side (East for right/West, West for left/East)
        turn_side_offset = (1, 0) if turn_dir == (-1, 0) else (-1, 0)
    elif direction == (1, 0):  # East passage turning South/North
        # Wall on opposite side (North for right/South, South for left/North)
        # When turning South (right), wall on North side (y-1)
        # When turning North (left), wall on South side (y+1)
        turn_side_offset = (0, -1) if turn_dir == (0, 1) else (0, 1)
    else:  # West (-1,0) passage turning North/South
        # Wall on opposite side (South for right/North, North for left/South)
        turn_side_offset = (0, 1) if turn_dir == (0, -1) else (0, -1)
    
    # Place side walls on the outer edge of the turn (only on the side opposite to turn)
    # For vertical passages turning horizontal: only wall the left tiles for right turns,
    # or right tiles for left turns
    # For horizontal passages turning vertical: both tiles in the target row need walls
    if direction in [(0, -1), (0, 1)]:  # Vertical passage turning horizontal
        if turn_dir == (1, 0):  # Turning East (right from North, left from South)
            # Wall on West side - both left tiles
            wall_tiles = [forward1_left, forward2_left]
        else:  # Turning West (left from North, right from South)
            # Wall on East side - both right tiles
            wall_tiles = [forward1_right, forward2_right]
    else:  # Horizontal passage turning vertical
        # For horizontal passages, left and right are at different Y coordinates
        # We need to wall both tiles that are on the outer edge (same row)
        if turn_dir == (0, 1):  # Turning South - wall the upper row (lower y, which is left)
            wall_tiles = [forward1_left, forward2_left]
        else:  # Turning North - wall the lower row (higher y, which is right)
            wall_tiles = [forward1_right, forward2_right]
    
    for pos in wall_tiles:
        outer_wall = (pos[0] + turn_side_offset[0], pos[1] + turn_side_offset[1])
        dungeon.grid[outer_wall] = dungeon.TileType.WALL
        dungeon.explored.add(outer_wall)
        dungeon._log(f"    Turn side wall at {outer_wall}")
    
    # Place capping walls to block forward direction (one step beyond the 2x2)
    wall_left = (forward2_left[0] + direction[0], forward2_left[1] + direction[1])
    wall_right = (forward2_right[0] + direction[0], forward2_right[1] + direction[1])
    # Side walls adjacent to capping walls (perpendicular to passage direction)
    if direction in [(0, -1), (0, 1)]:  # North/South - side walls at x-1 and x+1
        side_left = (wall_left[0] - 1, wall_left[1])
        side_right = (wall_right[0] + 1, wall_right[1])
    else:  # East/West - side walls at y-1 and y+1
        side_left = (wall_left[0], wall_left[1] - 1)
        side_right = (wall_right[0], wall_right[1] + 1)
    
    dungeon._log(f"    {turn_type.capitalize()} turn capping walls at {wall_left}, {wall_right}, "
                 f"sides {side_left}, {side_right}")
    # Explore capping walls
    for pos in [wall_left, wall_right, side_left, side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
        dungeon.explored.add(pos)
    
    # Set pending only for forward tiles (the turn extension)
    exits = [turn_dir]
    dungeon.pending_junctions[forward1_left] = exits
    dungeon.pending_junctions[forward1_right] = exits
    dungeon.pending_junctions[forward2_left] = exits
    dungeon.pending_junctions[forward2_right] = exits


def _generate_stairs(dungeon: "Dungeon", left_pos, right_pos, direction, stairs_type,
                     forward1_left, forward1_right, forward2_left, forward2_right):
    """Generate stairs (down or out) with 2x2 stairs and capping walls."""
    tile_type = (dungeon.TileType.STAIRS_DOWN if stairs_type == 'down' 
                 else dungeon.TileType.STAIRS_OUT)
    
    dungeon._log(f"    Stairs {stairs_type}: passage end at {left_pos},{right_pos}, "
                 f"2x2 at {forward1_left},{forward1_right} and {forward2_left},{forward2_right}")
    
    # Place STAIRS at both forward rows (the 2x2 passage end)
    for pos in [forward1_left, forward1_right, forward2_left, forward2_right]:
        dungeon.grid[pos] = tile_type
    
    # Explore the 2x2 stairs (side walls and capping walls will be added after placement)
    _explore_passage_end_2x2(dungeon, forward1_left, forward1_right, forward2_left, forward2_right)
    
    # Calculate side walls adjacent to the 2x2 stairs (at forward1 and forward2)
    # For vertical passages: side walls are x-1 and x+1
    # For horizontal passages: side walls are y-1 and y+1
    if direction in [(0, -1), (0, 1)]:  # North/South
        f1_side_left = (forward1_left[0] - 1, forward1_left[1])
        f1_side_right = (forward1_right[0] + 1, forward1_right[1])
        f2_side_left = (forward2_left[0] - 1, forward2_left[1])
        f2_side_right = (forward2_right[0] + 1, forward2_right[1])
    else:  # East/West
        f1_side_left = (forward1_left[0], forward1_left[1] - 1)
        f1_side_right = (forward1_right[0], forward1_right[1] + 1)
        f2_side_left = (forward2_left[0], forward2_left[1] - 1)
        f2_side_right = (forward2_right[0], forward2_right[1] + 1)
    
    # Place side walls alongside the 2x2 stairs
    for pos in [f1_side_left, f1_side_right, f2_side_left, f2_side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
        dungeon.explored.add(pos)
    dungeon._log(f"    Stairs {stairs_type} side walls at {f1_side_left}, {f1_side_right}, "
                 f"{f2_side_left}, {f2_side_right}")
    
    # Capping walls one step beyond the 2x2 stairs
    wall_left = (forward2_left[0] + direction[0], forward2_left[1] + direction[1])
    wall_right = (forward2_right[0] + direction[0], forward2_right[1] + direction[1])
    cap_side_left = (wall_left[0] - 1, wall_left[1]) if direction in [(0, -1), (0, 1)] else (wall_left[0], wall_left[1] - 1)
    cap_side_right = (wall_right[0] + 1, wall_right[1]) if direction in [(0, -1), (0, 1)] else (wall_right[0], wall_right[1] + 1)
    
    dungeon._log(f"    Stairs {stairs_type} capping at {wall_left}, {wall_right}, "
                 f"sides {cap_side_left}, {cap_side_right}")
    # Place and explore capping walls
    for pos in [wall_left, wall_right, cap_side_left, cap_side_right]:
        dungeon.grid[pos] = dungeon.TileType.WALL
        dungeon.explored.add(pos)

"""Room generation for dungeon.

Handles room creation beyond doors in passages.
"""

import random
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

if TYPE_CHECKING:
    from .dungeon import Dungeon


def _is_valid_door_position(dungeon: "Dungeon", x: int, y: int, 
                            direction: Tuple[int, int]) -> bool:
    """Check if a door position is valid (not at corners/junctions)."""
    # Don't place doors at passage corners or junctions
    # Check if there are walls on both sides perpendicular to direction
    if direction in [(0, -1), (0, 1)]:  # North/South
        left = (x - 1, y)
        right = (x + 1, y)
    else:  # East/West
        left = (x, y - 1)
        right = (x, y + 1)
    
    left_tile = dungeon.get_tile(*left)
    right_tile = dungeon.get_tile(*right)
    
    # Door is valid if both sides are walls
    return (left_tile == dungeon.TileType.WALL and 
            right_tile == dungeon.TileType.WALL)


def generate_room(dungeon: "Dungeon", door_x: int, door_y: int,
                  entrance_dir: Tuple[int, int], from_passage: bool = False):
    """Generate a room beyond a door."""
    roll = random.randint(1, 12)
    
    # Room sizes are interior dimensions
    if roll <= 6:
        room_type = "normal"
        int_width, int_height = 5, 5
    elif roll <= 11:
        room_type = "large"
        int_width, int_height = 5, 11
    else:
        room_type = "large"
        int_width, int_height = 11, 5
    
    # Total size including walls
    total_width = int_width + 2
    total_height = int_height + 2
    
    # Determine room position based on entrance direction
    if entrance_dir == (0, -1):  # North (door is at bottom)
        start_x = door_x - int_width // 2
        start_y = door_y - int_height
    elif entrance_dir == (0, 1):  # South (door is at top)
        start_x = door_x - int_width // 2
        start_y = door_y + 1
    elif entrance_dir == (1, 0):  # East (door is at left)
        start_x = door_x + 1
        start_y = door_y - int_height // 2
    else:  # West (door is at right)
        start_x = door_x - int_width
        start_y = door_y - int_height // 2
    
    room_tiles: Set[Tuple[int, int]] = set()
    
    # Generate room
    for dy in range(total_height):
        for dx in range(total_width):
            x = start_x + dx
            y = start_y + dy
            
            # Check if it's a wall (perimeter)
            is_wall = dx == 0 or dx == total_width - 1 or dy == 0 or dy == total_height - 1
            
            # Don't overwrite the entrance door
            if (x, y) == (door_x, door_y):
                continue
            
            if is_wall:
                # Only place wall if unexplored
                if dungeon.get_tile(x, y) == dungeon.TileType.UNEXPLORED:
                    dungeon.grid[(x, y)] = dungeon.TileType.WALL
            else:
                # Interior floor
                dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
                room_tiles.add((x, y))
                dungeon.explored.add((x, y))
    
    # Store room
    dungeon.rooms.append(room_tiles)
    dungeon._log(f"    Generated {room_type} room at ({start_x}, {start_y}) "
                 f"size {total_width}x{total_height}")
    
    # Place doors and passages
    _add_room_exits(dungeon, start_x, start_y, total_width, total_height, 
                    door_x, door_y, entrance_dir)
    
    return room_tiles


def _add_room_exits(dungeon: "Dungeon", start_x: int, start_y: int,
                   total_width: int, total_height: int,
                   door_x: int, door_y: int, entrance_dir: Tuple[int, int]):
    """Add doors/exits to room walls."""
    int_width = total_width - 2
    int_height = total_height - 2
    
    # Check each wall for potential door locations
    potential_doors = []
    
    # North wall
    if entrance_dir != (0, -1):
        for dx in range(1, int_width + 1):
            x = start_x + dx
            y = start_y
            if _is_valid_door_position(dungeon, x, y, (0, -1)):
                potential_doors.append((x, y, (0, -1)))
    
    # South wall
    if entrance_dir != (0, 1):
        for dx in range(1, int_width + 1):
            x = start_x + dx
            y = start_y + total_height - 1
            if _is_valid_door_position(dungeon, x, y, (0, 1)):
                potential_doors.append((x, y, (0, 1)))
    
    # East wall
    if entrance_dir != (1, 0):
        for dy in range(1, int_height + 1):
            x = start_x + total_width - 1
            y = start_y + dy
            if _is_valid_door_position(dungeon, x, y, (1, 0)):
                potential_doors.append((x, y, (1, 0)))
    
    # West wall
    if entrance_dir != (-1, 0):
        for dy in range(1, int_height + 1):
            x = start_x
            y = start_y + dy
            if _is_valid_door_position(dungeon, x, y, (-1, 0)):
                potential_doors.append((x, y, (-1, 0)))
    
    # Roll for number of exits (1-4)
    exit_roll = random.randint(1, 12)
    if exit_roll <= 2:
        num_exits = 1
    elif exit_roll <= 6:
        num_exits = 2
    elif exit_roll <= 9:
        num_exits = 3
    else:
        num_exits = 4
    
    # Place doors
    exits_placed = 0
    random.shuffle(potential_doors)
    
    for door_x, door_y, door_dir in potential_doors[:num_exits]:
        dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
        dungeon.doors.append((door_x, door_y))
        dungeon._log(f"      Door at ({door_x}, {door_y})")
        exits_placed += 1

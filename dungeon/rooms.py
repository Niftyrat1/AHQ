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


def _check_room_fit(dungeon: "Dungeon", start_x: int, start_y: int,
                    total_width: int, total_height: int) -> bool:
    """Check if room area is completely unexplored (no overlap)."""
    for dy in range(total_height):
        for dx in range(total_width):
            x = start_x + dx
            y = start_y + dy
            if dungeon.get_tile(x, y) != dungeon.TileType.UNEXPLORED:
                return False
    return True


def generate_room(dungeon: "Dungeon", door_x: int, door_y: int,
                  entrance_dir: Tuple[int, int], from_passage: bool = False):
    """Generate a room beyond a door.

    The door tile is shared with the room wall — the room's bounding box
    starts AT the door tile so no gap appears between door and room.
    
    Per the rules: Do not overlap existing sections. If room is too large,
    use smaller size. If that doesn't fit, the door is a false one.
    """
    roll = random.randint(1, 12)

    # Determine room sizes to try (large first, then normal if needed)
    if roll <= 6:
        room_type = "normal"
        sizes_to_try = [(5, 5, "normal")]  # Only normal size
    elif roll <= 11:
        sizes_to_try = [(5, 11, "large"), (5, 5, "normal")]  # Try large, then normal
    else:
        sizes_to_try = [(11, 5, "large"), (5, 5, "normal")]  # Try large, then normal

    # Try each size until one fits
    for int_width, int_height, room_type in sizes_to_try:
        total_width = int_width + 2
        total_height = int_height + 2

        # Calculate room position based on entrance direction
        if entrance_dir == (1, 0):   # East — door on west wall of room
            start_x = door_x
            start_y = door_y - int_height // 2 - 1
        elif entrance_dir == (-1, 0):  # West — door on east wall of room
            start_x = door_x - total_width + 1
            start_y = door_y - int_height // 2 - 1
        elif entrance_dir == (0, 1):   # South — door on north wall of room
            start_x = door_x - int_width // 2 - 1
            start_y = door_y
        else:                          # North — door on south wall of room
            start_x = door_x - int_width // 2 - 1
            start_y = door_y - total_height + 1

        # Check for overlap - room area must be completely unexplored
        if _check_room_fit(dungeon, start_x, start_y, total_width, total_height):
            # Found a fit - place the room
            _place_room(dungeon, door_x, door_y, entrance_dir, start_x, start_y,
                       total_width, total_height, room_type)
            return

    # No size fits - this is a false door per the rules
    dungeon._log(f"    False door at ({door_x}, {door_y}) - no room fits")
    # Convert door to a wall (false door doesn't lead anywhere)
    dungeon.grid[(door_x, door_y)] = dungeon.TileType.WALL
    if (door_x, door_y) in dungeon.doors:
        del dungeon.doors[(door_x, door_y)]


def _place_room(dungeon: "Dungeon", door_x: int, door_y: int,
               entrance_dir: Tuple[int, int], start_x: int, start_y: int,
               total_width: int, total_height: int, room_type: str):
    """Place a room at the specified location (internal helper)."""
    room_tiles: Set[Tuple[int, int]] = set()

    for dy in range(total_height):
        for dx in range(total_width):
            x = start_x + dx
            y = start_y + dy

            is_wall = dx == 0 or dx == total_width - 1 or dy == 0 or dy == total_height - 1

            # The door tile is already placed — don't overwrite it
            if (x, y) == (door_x, door_y):
                continue

            if is_wall:
                dungeon.grid[(x, y)] = dungeon.TileType.WALL
            else:
                dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
                room_tiles.add((x, y))
                dungeon.explored.add((x, y))

    # Also explore the door tile and all wall tiles so the room appears immediately
    dungeon.explored.add((door_x, door_y))
    for dy in range(total_height):
        for dx in range(total_width):
            x = start_x + dx
            y = start_y + dy
            dungeon.explored.add((x, y))

    dungeon.rooms.append(room_tiles)
    dungeon._log(f"    Generated {room_type} room at ({start_x}, {start_y}) "
                 f"size {total_width}x{total_height}")

    # Roll for room type
    from monster import roll_lair_encounter, roll_quest_room_encounter
    room_roll = random.randint(1, 12)
    if 9 <= room_roll <= 10:
        # Lair room
        monster_ids = roll_lair_encounter()
        available = list(room_tiles)
        random.shuffle(available)
        for i, monster_id in enumerate(monster_ids):
            if i >= len(available):
                break
            dungeon.monsters[available[i]] = monster_id
    elif 11 <= room_roll <= 12:
        # Quest room
        monster_ids = roll_quest_room_encounter()
        available = list(room_tiles)
        random.shuffle(available)
        for i, monster_id in enumerate(monster_ids):
            if i >= len(available):
                break
            dungeon.monsters[available[i]] = monster_id

    _add_room_exits(dungeon, start_x, start_y, total_width, total_height,
                    door_x, door_y, entrance_dir)


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
    
    # Roll for number of exits per Room Doors Table (D12)
    # 1-4: None, 5-8: 1 Door, 9-12: 2 Doors
    exit_roll = random.randint(1, 12)
    if exit_roll <= 4:
        num_exits = 0
    elif exit_roll <= 8:
        num_exits = 1
    else:
        num_exits = 2
    
    # Place doors
    exits_placed = 0
    random.shuffle(potential_doors)
    
    for door_x, door_y, door_dir in potential_doors[:num_exits]:
        dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
        dungeon.doors[(door_x, door_y)] = {'is_open': False, 'from_room': True}
        dungeon._log(f"      Door at ({door_x}, {door_y})")
        exits_placed += 1

"""Room generation for dungeon.

Handles room creation beyond doors in passages.
"""

import random
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from hazards import roll_hazard_room, describe_hazard, hazard_blocks_movement

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
                    total_width: int, total_height: int,
                    door_x: int = None, door_y: int = None) -> bool:
    """Check if room fits: interior must be unexplored, walls can overlap walls/doors."""
    for dy in range(total_height):
        for dx in range(total_width):
            x = start_x + dx
            y = start_y + dy
            tile = dungeon.get_tile(x, y)
            is_wall = dx == 0 or dx == total_width - 1 or dy == 0 or dy == total_height - 1
            
            # Skip the entrance door tile
            if door_x is not None and x == door_x and y == door_y:
                continue
            
            if is_wall:
                # Walls can be on unexplored, existing walls, or doors
                if tile not in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL,
                               dungeon.TileType.DOOR_CLOSED, dungeon.TileType.DOOR_OPEN):
                    return False
            else:
                # Interior must be completely unexplored
                if tile != dungeon.TileType.UNEXPLORED:
                    return False
    return True


def _place_room_chest(dungeon: "Dungeon", room_data: dict, occupied_tiles=None):
    """Place a treasure chest on an unoccupied interior tile."""
    occupied = set(occupied_tiles or [])
    candidates = sorted(
        pos for pos in room_data.get("interior_tiles", set())
        if pos not in occupied and dungeon.get_tile(pos[0], pos[1]) == dungeon.TileType.FLOOR
    )
    if not candidates:
        return None

    entrance = room_data.get("entrance")
    if isinstance(entrance, list) and len(entrance) == 2:
        entrance_pos = (int(entrance[0]), int(entrance[1]))
        chest_pos = max(
            candidates,
            key=lambda pos: (abs(pos[0] - entrance_pos[0]) + abs(pos[1] - entrance_pos[1]), pos[1], pos[0]),
        )
    else:
        chest_pos = candidates[-1]

    dungeon.grid[chest_pos] = dungeon.TileType.TREASURE_CLOSED
    dungeon.treasure[chest_pos] = False
    room_data["chest_pos"] = list(chest_pos)
    return chest_pos


def _try_room_position(dungeon: "Dungeon", door_x: int, door_y: int,
                        entrance_dir: Tuple[int, int], int_width: int, int_height: int,
                        room_type: str) -> bool:
    """Try to place room with sliding and rotation. Returns True if placed."""
    total_width = int_width + 2
    total_height = int_height + 2
    
    # Calculate base position (centered on door)
    if entrance_dir == (1, 0):   # East — door on west wall
        base_x = door_x
        base_y = door_y - int_height // 2 - 1
        slide_dir = (0, 1)  # Slide along Y axis
        max_slide = int_height // 2
    elif entrance_dir == (-1, 0):  # West — door on east wall
        base_x = door_x - total_width + 1
        base_y = door_y - int_height // 2 - 1
        slide_dir = (0, 1)  # Slide along Y axis
        max_slide = int_height // 2
    elif entrance_dir == (0, 1):   # South — door on north wall
        base_x = door_x - int_width // 2 - 1
        base_y = door_y
        slide_dir = (1, 0)  # Slide along X axis
        max_slide = int_width // 2
    else:                          # North — door on south wall
        base_x = door_x - int_width // 2 - 1
        base_y = door_y - total_height + 1
        slide_dir = (1, 0)  # Slide along X axis
        max_slide = int_width // 2
    
    # Try positions: centered, slide +1, slide -1, slide +2, slide -2, etc.
    for slide in range(0, max_slide + 1):
        for direction in [1, -1] if slide > 0 else [0]:
            offset = slide * direction
            try_x = base_x + slide_dir[0] * offset
            try_y = base_y + slide_dir[1] * offset
            
            if _check_room_fit(dungeon, try_x, try_y, total_width, total_height,
                              door_x=door_x, door_y=door_y):
                _place_room(dungeon, door_x, door_y, entrance_dir, try_x, try_y,
                           total_width, total_height, room_type)
                return True
    
    return False


def generate_room(dungeon: "Dungeon", door_x: int, door_y: int,
                  entrance_dir: Tuple[int, int], from_passage: bool = False):
    """Generate a room beyond a door.

    The door tile is shared with the room wall — the room's bounding box
    starts AT the door tile so no gap appears between door and room.
    
    Per the rules: Do not overlap existing sections. If room is too large,
    use smaller size. If that doesn't fit, the door is a false one.
    
    Tries sliding and rotation before falling back to smaller size or false door.
    """
    roll = random.randint(1, 12)

    # Determine room sizes to try (large first, then normal if needed)
    if roll <= 6:
        sizes_to_try = [(5, 5, "normal")]  # Only normal size
    elif roll <= 11:
        sizes_to_try = [(5, 11, "large"), (5, 5, "normal")]  # Try large, then normal
    else:
        sizes_to_try = [(11, 5, "large"), (5, 5, "normal")]  # Try large, then normal

    # Try each size with sliding and rotation
    for int_width, int_height, room_type in sizes_to_try:
        # Try original orientation with sliding
        if _try_room_position(dungeon, door_x, door_y, entrance_dir,
                             int_width, int_height, room_type):
            return
        
        # Try rotated orientation (swap width/height) with sliding
        if int_width != int_height:  # Only if dimensions differ
            rotated_type = f"{room_type}_rotated"
            if _try_room_position(dungeon, door_x, door_y, entrance_dir,
                                 int_height, int_width, rotated_type):
                return

    # No size or orientation fits - this is a false door per the rules
    dungeon._log(f"    False door at ({door_x}, {door_y}) - no room fits")
    # Convert door to a wall (false door doesn't lead anywhere)
    dungeon.grid[(door_x, door_y)] = dungeon.TileType.WALL
    if (door_x, door_y) in dungeon.doors:
        del dungeon.doors[(door_x, door_y)]
    return False  # Indicate false door


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

            # Don't overwrite existing walls or doors
            existing_tile = dungeon.get_tile(x, y)
            if existing_tile in (dungeon.TileType.WALL, dungeon.TileType.DOOR_CLOSED,
                                  dungeon.TileType.DOOR_OPEN):
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

    # Store room data with tracking for searches
    room_id = len(dungeon.rooms)
    room_data = {
        'id': room_id,
        'interior_tiles': room_tiles,
        'walls': set(),  # Will be populated by _add_room_exits
        'start_x': start_x,
        'start_y': start_y,
        'width': total_width,
        'height': total_height,
        'searched_secrets': False,
        'searched_treasure': False,
        'searched_walls': set(),
        'room_kind': 'normal',
        'hazard': None,
        'hazard_anchor': None,
        'entrance': [door_x, door_y],
        'chest_pos': None,
        'chest_loot': None,
        'chest_trapped': False,
        'chest_opened': False,
        'chest_trap_resolved': False,
    }
    dungeon.rooms.append(room_data)
    dungeon._log(f"    Generated {room_type} room at ({start_x}, {start_y}) "
                 f"size {total_width}x{total_height}")

    # Roll for room type
    from monster import roll_lair_encounter, roll_quest_room_encounter
    room_roll = random.randint(1, 12)
    if 7 <= room_roll <= 8:
        room_data['room_kind'] = 'hazard'
        room_data['hazard'] = roll_hazard_room()
        if room_tiles:
            sorted_tiles = sorted(room_tiles)
            hazard_anchor = sorted_tiles[len(sorted_tiles) // 2]
            room_data['hazard_anchor'] = list(hazard_anchor)
            hazard_type = room_data["hazard"].get("type")
            if hazard_type == "statue":
                dungeon.grid[hazard_anchor] = dungeon.TileType.STATUE
            elif hazard_type == "chasm":
                dungeon.grid[hazard_anchor] = dungeon.TileType.CHASM
            elif hazard_type == "grate":
                dungeon.grid[hazard_anchor] = dungeon.TileType.GRATE
            elif hazard_type == "throne":
                dungeon.grid[hazard_anchor] = dungeon.TileType.THRONE
        dungeon._log(f"    Hazard room: {describe_hazard(room_data['hazard'])}")
    elif 9 <= room_roll <= 10:
        # Lair room
        room_data['room_kind'] = 'lair'
        monster_ids = roll_lair_encounter()
        room_data['chest_loot'] = {
            'gold': sum(
                int(getattr(dungeon.monster_library, "templates", {}).get(monster_id, {}).get("PV", 1)) * 10
                for monster_id in monster_ids
            )
        }
        dungeon._log(f"    Lair room stocked with {len(monster_ids)} monster(s): {', '.join(monster_ids)}")
        available = list(room_tiles)
        random.shuffle(available)
        for i, monster_id in enumerate(monster_ids):
            if i >= len(available):
                break
            pos = available[i]
            dungeon._place_monster(monster_id, pos[0], pos[1])
        _place_room_chest(dungeon, room_data, occupied_tiles=available[:len(monster_ids)])
    elif 11 <= room_roll <= 12:
        # Quest room
        room_data['room_kind'] = 'quest'
        monster_ids = roll_quest_room_encounter()
        room_data['chest_loot'] = {
            'gold': sum(
                int(getattr(dungeon.monster_library, "templates", {}).get(monster_id, {}).get("PV", 1)) * 10
                for monster_id in monster_ids
            )
        }
        dungeon._log(f"    Quest room stocked with {len(monster_ids)} monster(s): {', '.join(monster_ids)}")
        available = list(room_tiles)
        random.shuffle(available)
        for i, monster_id in enumerate(monster_ids):
            if i >= len(available):
                break
            pos = available[i]
            dungeon._place_monster(monster_id, pos[0], pos[1])
        _place_room_chest(dungeon, room_data, occupied_tiles=available[:len(monster_ids)])

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

"""
Dungeon generation logic for Advanced HeroQuest.

Public interface:
- generate_passage_from(x, y, direction, auto_explore) -> List[Tuple[int, int]]
- _generate_room(door_x, door_y, entrance_dir, from_passage) -> None
- _resolve_passage_end(x, y, direction, roll) -> None
"""
import random
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .dungeon import Dungeon


def generate_passage_from(
    dungeon: "Dungeon",
    x: int, y: int,
    direction: Tuple[int, int],
    auto_explore: bool = True,
    features_enabled: bool = True
) -> List[Tuple[int, int]]:
    """Generate a passage from a junction. Passage is 2 tiles wide, 5 tiles per section."""
    # Roll passage length (1-3 sections, each section is 5 tiles long)
    roll = random.randint(1, 12)
    if roll <= 2:
        sections = 1
    elif roll <= 8:
        sections = 2
    else:
        sections = 3
    
    passage_tiles = []
    
    # Determine left/right offsets based on direction
    # For vertical passages (North/South): left is -1 x, right is +1 x
    # For horizontal passages (East/West): left is -1 y, right is +1 y
    if direction in [(0, -1), (0, 1)]:  # North or South
        left_offset = (-1, 0)
        right_offset = (1, 0)
    else:  # East or West
        left_offset = (0, -1)
        right_offset = (0, 1)
    
    # Track current position (center of passage)
    current_x, current_y = x, y
    
    for section_idx in range(sections):
        # Each section is 5 tiles long
        for tile_idx in range(5):
            current_x += direction[0]
            current_y += direction[1]
            
            # Calculate left and right tile positions
            left_x = current_x + left_offset[0]
            left_y = current_y + left_offset[1]
            right_x = current_x + right_offset[0]
            right_y = current_y + right_offset[1]
            
            # Check for overlap on both tiles
            left_tile = dungeon.get_tile(left_x, left_y)
            right_tile = dungeon.get_tile(right_x, right_y)
            
            # If either tile is blocked (not unexplored), stop
            if left_tile not in (dungeon.TileType.UNEXPLORED, dungeon.TileType.FLOOR):
                return passage_tiles
            if right_tile not in (dungeon.TileType.UNEXPLORED, dungeon.TileType.FLOOR):
                return passage_tiles
            
            # Place both floor tiles
            dungeon.grid[(left_x, left_y)] = dungeon.TileType.FLOOR
            dungeon.grid[(right_x, right_y)] = dungeon.TileType.FLOOR
            passage_tiles.append((left_x, left_y))
            passage_tiles.append((right_x, right_y))
            if auto_explore:
                dungeon.explored.add((left_x, left_y))
                dungeon.explored.add((right_x, right_y))
            
            # Place outer walls (one tile beyond left and right)
            outer_left_x = left_x + left_offset[0]
            outer_left_y = left_y + left_offset[1]
            outer_right_x = right_x + right_offset[0]
            outer_right_y = right_y + right_offset[1]
            
            for wall_x, wall_y in [(outer_left_x, outer_left_y), (outer_right_x, outer_right_y)]:
                existing = dungeon.get_tile(wall_x, wall_y)
                if existing in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                    dungeon.grid[(wall_x, wall_y)] = dungeon.TileType.WALL
                    if auto_explore:
                        dungeon.explored.add((wall_x, wall_y))
            
            # Check for features (doors) - Passage Features Table (2D12)
            # Only roll once per passage (first section, middle tile)
            if features_enabled and section_idx == 0 and tile_idx == 1:
                feature_roll = random.randint(1, 12) + random.randint(1, 12)
                if feature_roll <= 4:
                    feature_name = "Wandering monsters"
                elif feature_roll <= 15:
                    feature_name = "Nothing"
                elif feature_roll <= 19:
                    feature_name = "1 door"
                elif feature_roll <= 21:
                    feature_name = "2 doors"
                else:
                    feature_name = "Wandering monsters"
                dungeon._log(f"    Passage feature roll: {feature_roll} ({feature_name})")
                if 2 <= feature_roll <= 4 or 22 <= feature_roll <= 24:
                    # Wandering monsters - mark this tile for encounter
                    dungeon.wandering_monsters.add((current_x, current_y))
                    dungeon._log(f"    Wandering monsters placed at ({current_x}, {current_y})")
                elif 16 <= feature_roll <= 19:
                    # 1 door on side - place on outer wall of 2-wide passage
                    # Randomly pick left or right side
                    side_dir = left_offset if random.random() < 0.5 else right_offset
                    door_x = current_x + side_dir[0] + side_dir[0]  # 2 tiles out from center
                    door_y = current_y + side_dir[1] + side_dir[1]
                    if dungeon._is_valid_door_position(door_x, door_y, direction):
                        if dungeon.get_tile(door_x, door_y) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                            dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
                            dungeon.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}
                elif 20 <= feature_roll <= 21:
                    # 2 doors on sides - place on both outer walls
                    for side_dir in [left_offset, right_offset]:
                        door_x = current_x + side_dir[0] + side_dir[0]  # 2 tiles out from center
                        door_y = current_y + side_dir[1] + side_dir[1]
                        if dungeon._is_valid_door_position(door_x, door_y, direction):
                            if dungeon.get_tile(door_x, door_y) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                                dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
                                dungeon.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}
    
    # After all sections are placed, roll passage end
    end_roll = random.randint(1, 12) + random.randint(1, 12)
    end_x, end_y = current_x + direction[0], current_y + direction[1]
    _resolve_passage_end(dungeon, end_x, end_y, direction, end_roll)
    
    # After _resolve_passage_end, we may need to cap walls for dead ends and stairs
    # The end tiles are at left_pos and right_pos (one step beyond last passage tiles)
    left_pos = (end_x + left_offset[0], end_y + left_offset[1])
    right_pos = (end_x + right_offset[0], end_y + right_offset[1])
    
    end_tile = dungeon.get_tile(left_pos[0], left_pos[1])
    is_dead_end_or_stairs = end_tile in (dungeon.TileType.PASSAGE_END, dungeon.TileType.STAIRS_DOWN, dungeon.TileType.STAIRS_OUT)
    
    # If dead end or stairs, cap with forward walls
    if is_dead_end_or_stairs:
        beyond_left = (left_pos[0] + direction[0], left_pos[1] + direction[1])
        beyond_right = (right_pos[0] + direction[0], right_pos[1] + direction[1])
        for wall_pos in [beyond_left, beyond_right]:
            if dungeon.get_tile(wall_pos[0], wall_pos[1]) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                dungeon.grid[wall_pos] = dungeon.TileType.WALL
    
    return passage_tiles


def _resolve_passage_end(dungeon: "Dungeon", x: int, y: int, direction: Tuple[int, int], roll: int):
    """Resolve what happens at passage end (2D12). x,y is the center position, we place 2-wide tiles."""
    if not hasattr(dungeon, 'pending_junctions'):
        dungeon.pending_junctions = {}
    
    # Calculate left/right offsets based on direction
    if direction in [(0, -1), (0, 1)]:  # Vertical passage (North/South)
        left_offset, right_offset = (-1, 0), (1, 0)
    else:  # Horizontal passage (East/West)
        left_offset, right_offset = (0, -1), (0, 1)
    
    # Calculate the actual 2-wide tile positions at this center point
    left_pos = (x + left_offset[0], y + left_offset[1])
    right_pos = (x + right_offset[0], y + right_offset[1])
    
    if roll <= 3 or 12 <= roll <= 14 or roll >= 23:
        # T-junction (2-3, 12-14, 23-24): 2x2 floor, wall blocks forward
        # Create 2x2 junction using center and the tile in the forward direction
        forward_pos = (x + direction[0], y + direction[1])
        forward_left = (forward_pos[0] + left_offset[0], forward_pos[1] + left_offset[1])
        forward_right = (forward_pos[0] + right_offset[0], forward_pos[1] + right_offset[1])
        
        junc_tiles = [left_pos, right_pos, forward_left, forward_right]
        for tx, ty in junc_tiles:
            dungeon.grid[(tx, ty)] = dungeon.TileType.FLOOR
        
        # Wall blocks forward direction (beyond the 2x2)
        wall_center = (x + direction[0] * 2, y + direction[1] * 2)
        wall_left = (wall_center[0] + left_offset[0], wall_center[1] + left_offset[1])
        wall_right = (wall_center[0] + right_offset[0], wall_center[1] + right_offset[1])
        dungeon.grid[wall_left] = dungeon.TileType.WALL
        dungeon.grid[wall_right] = dungeon.TileType.WALL
        
        # Side walls at junction
        perp_dirs = _get_both_perpendicular(direction)
        dungeon.pending_junctions[left_pos] = list(perp_dirs)
        
    elif 4 <= roll <= 8:
        # Dead end (4-8) - place PASSAGE_END on both floor tiles
        dungeon.grid[left_pos] = dungeon.TileType.PASSAGE_END
        dungeon.grid[right_pos] = dungeon.TileType.PASSAGE_END
        
    elif 9 <= roll <= 11:
        # Right turn (9-11)
        if direction == (1, 0):  # East -> South
            right_dir = (0, 1)
        elif direction == (-1, 0):  # West -> North
            right_dir = (0, -1)
        elif direction == (0, 1):  # South -> West
            right_dir = (-1, 0)
        else:  # North -> East
            right_dir = (1, 0)
        
        # Create 2-wide turn area - place FLOOR at both positions
        dungeon.grid[left_pos] = dungeon.TileType.FLOOR
        dungeon.grid[right_pos] = dungeon.TileType.FLOOR
        dungeon.pending_junctions[left_pos] = [right_dir]
        
    elif 15 <= roll <= 17:
        # Left turn (15-17)
        if direction == (1, 0):  # East -> North
            left_dir = (0, -1)
        elif direction == (-1, 0):  # West -> South
            left_dir = (0, 1)
        elif direction == (0, 1):  # South -> East
            left_dir = (1, 0)
        else:  # North -> West
            left_dir = (-1, 0)
        
        # Create 2-wide turn area
        dungeon.grid[left_pos] = dungeon.TileType.FLOOR
        dungeon.grid[right_pos] = dungeon.TileType.FLOOR
        dungeon.pending_junctions[left_pos] = [left_dir]
        
    elif 18 <= roll <= 19:
        # Stairs down
        dungeon.grid[left_pos] = dungeon.TileType.STAIRS_DOWN
        dungeon.grid[right_pos] = dungeon.TileType.STAIRS_DOWN
        
    elif 20 <= roll <= 22:
        # Stairs out
        dungeon.grid[left_pos] = dungeon.TileType.STAIRS_OUT
        dungeon.grid[right_pos] = dungeon.TileType.STAIRS_OUT


def _generate_room(dungeon: "Dungeon", door_x: int, door_y: int,
                   entrance_dir: Tuple[int, int], from_passage: bool = False):
    """Generate a room beyond a door."""
    # Roll room type
    roll = random.randint(1, 12)
    # Room sizes are interior dimensions (floor tiles only)
    # Normal: 5x5 interior (7x7 with walls)
    # Large: 5x11 interior (7x13 with walls)
    if roll <= 6:
        room_type = "normal"
        int_width, int_height = 5, 5
    elif roll <= 8:
        room_type = "hazard"
        int_width, int_height = 5, 5
    elif roll <= 10:
        room_type = "lair"
        int_width, int_height = 5, 11
    else:
        room_type = "quest"
        int_width, int_height = 5, 11
    
    # Total size includes 1-tile wall border
    width = int_width + 2
    height = int_height + 2
    
    
    room_tiles = []
    room_walls = []
    entrance_wall_positions = set()
    half_w, half_h = width // 2, height // 2
    
    # Calculate center based on entrance direction
    if entrance_dir == (0, -1):
        center_x, center_y = door_x, door_y - half_h + 1
    elif entrance_dir == (0, 1):
        center_x, center_y = door_x, door_y + half_h - 1
    elif entrance_dir == (-1, 0):
        center_x, center_y = door_x - half_w + 1, door_y
    else:
        center_x, center_y = door_x + half_w - 1, door_y
    
    # Check if room would overlap heavily - try sliding along wall first, then rotation
    def _count_overlap(cx, cy, w_half, h_half):
        count = 0
        for x in range(cx - w_half, cx + w_half + 1):
            for y in range(cy - h_half, cy + h_half + 1):
                if dungeon.get_tile(x, y) not in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                    count += 1
        return count
    
    overlap_count = _count_overlap(center_x, center_y, half_w, half_h)
    rotated = False
    
    # If too much overlap, try sliding the room along the wall
    if overlap_count > 2:
        best_center = (center_x, center_y)
        best_overlap = overlap_count
        best_half_w, best_half_h = half_w, half_h
        
        # Try sliding left/right or up/down along the entrance wall
        for offset in range(-2, 3):  # Try -2, -1, 0, 1, 2 tiles offset
            if offset == 0:
                continue
            if entrance_dir in [(0, -1), (0, 1)]:  # North/South entrance - slide left/right
                try_x = center_x + offset
                try_y = center_y
            else:  # East/West entrance - slide up/down
                try_x = center_x
                try_y = center_y + offset
            
            try_overlap = _count_overlap(try_x, try_y, half_w, half_h)
            if try_overlap < best_overlap:
                best_overlap = try_overlap
                best_center = (try_x, try_y)
        
        # If sliding didn't work, try rotating 90 degrees
        if best_overlap > 2 and width != height:  # Only rotate if not square
            rot_half_w, rot_half_h = half_h, half_w  # Swap dimensions
            
            # Recalculate center for rotated room
            if entrance_dir == (0, -1):
                rot_x, rot_y = door_x, door_y - rot_half_h + 1
            elif entrance_dir == (0, 1):
                rot_x, rot_y = door_x, door_y + rot_half_h - 1
            elif entrance_dir == (-1, 0):
                rot_x, rot_y = door_x - rot_half_w + 1, door_y
            else:
                rot_x, rot_y = door_x + rot_half_w - 1, door_y
            
            rot_overlap = _count_overlap(rot_x, rot_y, rot_half_w, rot_half_h)
            dungeon._log(f"  Rotated room at ({rot_x},{rot_y}) has overlap {rot_overlap}")
            
            # Try sliding the rotated room too
            if rot_overlap > 2:
                for offset in range(-2, 3):
                    if offset == 0:
                        continue
                    if entrance_dir in [(0, -1), (0, 1)]:
                        try_x = rot_x + offset
                        try_y = rot_y
                    else:
                        try_x = rot_x
                        try_y = rot_y + offset
                    
                    try_overlap = _count_overlap(try_x, try_y, rot_half_w, rot_half_h)
                    if try_overlap < rot_overlap:
                        rot_overlap = try_overlap
                        rot_x, rot_y = try_x, try_y
            
            if rot_overlap <= 2:
                center_x, center_y = rot_x, rot_y
                half_w, half_h = rot_half_w, rot_half_h
                width, height = height, width  # Swap for rest of generation
                rotated = True
            elif best_overlap <= 2:
                center_x, center_y = best_center
            else:
                generate_passage_from(dungeon, door_x - entrance_dir[0], door_y - entrance_dir[1], entrance_dir)
                return
        elif best_overlap <= 2:
            center_x, center_y = best_center
        else:
            generate_passage_from(dungeon, door_x - entrance_dir[0], door_y - entrance_dir[1], entrance_dir)
            return
    
    # Clear entrance position if it's a wall
    if dungeon.get_tile(door_x, door_y) == dungeon.TileType.WALL:
        del dungeon.grid[(door_x, door_y)]
    
    # Find entrance wall positions
    for x in range(center_x - half_w, center_x + half_w + 1):
        for y in range(center_y - half_h, center_y + half_h + 1):
            if entrance_dir == (0, -1):
                if y == center_y + half_h and (x, y) != (door_x, door_y):
                    entrance_wall_positions.add((x, y))
            elif entrance_dir == (0, 1):
                if y == center_y - half_h and (x, y) != (door_x, door_y):
                    entrance_wall_positions.add((x, y))
            elif entrance_dir == (-1, 0):
                if x == center_x + half_w and (x, y) != (door_x, door_y):
                    entrance_wall_positions.add((x, y))
            elif entrance_dir == (1, 0):
                if x == center_x - half_w and (x, y) != (door_x, door_y):
                    entrance_wall_positions.add((x, y))
    
    for x in range(center_x - half_w, center_x + half_w + 1):
        for y in range(center_y - half_h, center_y + half_h + 1):
            existing_tile = dungeon.get_tile(x, y)
            if existing_tile != dungeon.TileType.UNEXPLORED:
                continue
            
            if abs(x - center_x) == half_w or abs(y - center_y) == half_h:
                if (x, y) != (door_x, door_y):
                    dungeon.grid[(x, y)] = dungeon.TileType.WALL
                    room_walls.append((x, y))
            else:
                dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
                room_tiles.append((x, y))
    
    # If from passage, place the door at the entrance
    if from_passage:
        dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
        if (door_x, door_y) in room_walls:
            room_walls.remove((door_x, door_y))
    
    # Ensure entrance position is part of the room
    if (door_x, door_y) not in room_tiles and (door_x, door_y) not in room_walls:
        room_tiles.append((door_x, door_y))
    
    # Store room for later revelation
    dungeon.rooms.append(set(room_tiles + room_walls))
    
    # Reveal room from doorway
    dungeon._explore_from(door_x, door_y)
    
    # Add extra doors
    num_doors = _roll_room_doors()
    _add_doors_to_room(dungeon, center_x, center_y, half_w, half_h, num_doors, entrance_dir)
    
    # Add content based on room type
    if room_type == "lair":
        _place_monsters_in_room(dungeon, room_tiles, "lair", door_x, door_y)
    elif room_type == "quest":
        _place_monsters_in_room(dungeon, room_tiles, "quest", door_x, door_y)


def _roll_room_doors() -> int:
    """Roll for number of extra doors in a room."""
    roll = random.randint(1, 12)
    if roll <= 4:
        return 0
    elif roll <= 8:
        return 1
    else:
        return 2


def _add_doors_to_room(dungeon: "Dungeon", cx: int, cy: int, half_w: int, half_h: int,
                      num_doors: int, entrance_dir: Tuple[int, int]):
    """Add doors to room walls."""
    walls = []
    
    for x in range(cx - half_w, cx + half_w + 1):
        if x != cx - half_w and x != cx + half_w:
            walls.append((x, cy - half_h, 0, -1))
            walls.append((x, cy + half_h, 0, 1))
    for y in range(cy - half_h, cy + half_h + 1):
        if y != cy - half_h and y != cy + half_h:
            walls.append((cx - half_w, y, -1, 0))
            walls.append((cx + half_w, y, 1, 0))
    
    # Remove the entrance position
    entrance_pos = (cx - entrance_dir[0] * half_w if entrance_dir[0] != 0 else cx,
                 cy - entrance_dir[1] * half_h if entrance_dir[1] != 0 else cy)
    walls = [w for w in walls if (w[0], w[1]) != entrance_pos]
    
    random.shuffle(walls)
    doors_placed = 0
    for x, y, dx, dy in walls:
        if doors_placed >= num_doors:
            break
        if dungeon.get_tile(x, y) == dungeon.TileType.UNEXPLORED:
            dungeon.grid[(x, y)] = dungeon.TileType.DOOR_CLOSED
            dungeon.doors[(x, y)] = {"is_open": False, "from_room": True}
            dungeon.explored.add((x, y))
            doors_placed += 1


def _place_monsters_in_room(dungeon: "Dungeon", room_tiles: List[Tuple[int, int]], encounter_type: str, door_x: int, door_y: int):
    """Place monsters in a room."""
    from monster import roll_lair_encounter, roll_quest_room_encounter
    
    if encounter_type == "lair":
        monster_ids = roll_lair_encounter()
    else:
        monster_ids = roll_quest_room_encounter()
    
    dungeon._log(f"  Placing monsters in {encounter_type} room: {monster_ids}")
    dungeon._log(f"  Room has {len(room_tiles)} tiles, door at ({door_x},{door_y})")
    
    # Check distance from room entrance (door), not dungeon start
    available = [t for t in room_tiles if abs(t[0] - door_x) + abs(t[1] - door_y) > 2]
    dungeon._log(f"  Available tiles for monsters (not near door): {len(available)}")
    
    for monster_id in monster_ids:
        if available:
            pos = random.choice(available)
            dungeon.monsters[pos] = monster_id
            dungeon._log(f"  Placed {monster_id} at {pos}")
            available.remove(pos)
        else:
            dungeon._log(f"  No available tiles to place {monster_id}")


def _get_perpendicular(direction: Tuple[int, int]) -> Tuple[int, int]:
    """Get perpendicular direction."""
    if direction[0] != 0:
        return (0, 1)
    else:
        return (1, 0)


def _get_both_perpendicular(direction: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Get both perpendicular directions."""
    if direction[0] != 0:
        return [(0, 1), (0, -1)]
    else:
        return [(1, 0), (-1, 0)]

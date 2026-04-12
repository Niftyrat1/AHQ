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
    auto_explore: bool = True
) -> List[Tuple[int, int]]:
    """Generate a passage from a junction."""
    # Roll passage length
    roll = random.randint(1, 12)
    if roll <= 2:
        sections = 1
    elif roll <= 8:
        sections = 2
    else:
        sections = 3
    
    dungeon._log(f"Generating passage from ({x},{y}) direction {direction}: {sections} section(s) (roll {roll})")
    
    passage_tiles = []
    current_x, current_y = x, y
    
    for section_idx in range(sections):
        # Each section is 4 tiles
        for tile_idx in range(4):
            current_x += direction[0]
            current_y += direction[1]
            
            # Check for overlap - stop if hitting existing room or non-floor tiles
            tile = dungeon.get_tile(current_x, current_y)
            if tile == dungeon.TileType.UNEXPLORED:
                pass  # Can generate here
            elif tile == dungeon.TileType.FLOOR:
                # Check if this floor is part of an existing room or passage - if so, stop
                # to prevent passages from crossing through each other
                for room in dungeon.rooms:
                    if (current_x, current_y) in room:
                        dungeon._log(f"    Blocked at ({current_x}, {current_y}) - part of existing room, stopping")
                        return passage_tiles
                # Existing passage floor - stop to prevent passage crossings
                dungeon._log(f"    Blocked at ({current_x}, {current_y}) - existing passage, stopping")
                return passage_tiles
            else:
                # Blocked by wall, door, stairs, etc. - don't overwrite, just stop
                dungeon._log(f"    Blocked at ({current_x}, {current_y}) by {tile.name}, stopping")
                return passage_tiles
            
            dungeon.grid[(current_x, current_y)] = dungeon.TileType.FLOOR
            passage_tiles.append((current_x, current_y))
            if auto_explore:
                dungeon.explored.add((current_x, current_y))
            
            # Place walls on both sides — skip if already floor/door/stairs
            for side in _get_both_perpendicular(direction):
                wall_x = current_x + side[0]
                wall_y = current_y + side[1]
                existing = dungeon.get_tile(wall_x, wall_y)
                if existing in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                    dungeon.grid[(wall_x, wall_y)] = dungeon.TileType.WALL
            
            # Check for features (doors) - Passage Features Table (2D12)
            feature_roll = random.randint(1, 12) + random.randint(1, 12)
            dungeon._log(f"    Passage feature roll: {feature_roll}")
            if 2 <= feature_roll <= 4 or 22 <= feature_roll <= 24:
                # Wandering monsters - mark this tile for encounter
                dungeon.wandering_monsters.add((current_x, current_y))
                dungeon._log(f"    Wandering monsters will appear at ({current_x}, {current_y})")
            elif 16 <= feature_roll <= 19:
                # 1 door on side - check if position is suitable (not at junction)
                side_dir = _get_perpendicular(direction)
                door_x = current_x + side_dir[0]
                door_y = current_y + side_dir[1]
                if dungeon._is_valid_door_position(door_x, door_y, direction):
                    dungeon._log(f"    Attempting door at ({door_x}, {door_y}), tile: {dungeon.get_tile(door_x, door_y).name}")
                    if dungeon.get_tile(door_x, door_y) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                        dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
                        dungeon.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}
                        dungeon._log(f"    Placed 1 door at ({door_x}, {door_y})")
                else:
                    dungeon._log(f"    Skipped door at ({door_x}, {door_y}) - junction/corner position")
            elif 20 <= feature_roll <= 21:
                # 2 doors on sides - check if positions are suitable
                side_dirs = _get_both_perpendicular(direction)
                for side_dir in side_dirs:
                    door_x = current_x + side_dir[0]
                    door_y = current_y + side_dir[1]
                    if dungeon._is_valid_door_position(door_x, door_y, direction):
                        dungeon._log(f"    Attempting door at ({door_x}, {door_y}), tile: {dungeon.get_tile(door_x, door_y).name}")
                        if dungeon.get_tile(door_x, door_y) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                            dungeon.grid[(door_x, door_y)] = dungeon.TileType.DOOR_CLOSED
                            dungeon.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}
                            dungeon._log(f"    Placed door at ({door_x}, {door_y})")
                    else:
                        dungeon._log(f"    Skipped door at ({door_x}, {door_y}) - junction/corner position")
        
        # Roll passage end
        end_roll = random.randint(1, 12) + random.randint(1, 12)
        end_x, end_y = current_x + direction[0], current_y + direction[1]
        _resolve_passage_end(dungeon, end_x, end_y, direction, end_roll)
        
        # Cap the end of the passage with walls perpendicular to travel
        end_tile = dungeon.get_tile(end_x, end_y)
        is_dead_end_or_stairs = end_tile in (dungeon.TileType.PASSAGE_END, dungeon.TileType.STAIRS_DOWN, dungeon.TileType.STAIRS_OUT)
        is_pending_junction = (end_x, end_y) in dungeon.pending_junctions
        
        for side in _get_both_perpendicular(direction):
            wall_x = end_x + side[0]
            wall_y = end_y + side[1]
            if is_dead_end_or_stairs:
                if dungeon.get_tile(wall_x, wall_y) in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                    dungeon.grid[(wall_x, wall_y)] = dungeon.TileType.WALL
                    dungeon._log(f"    Placed side wall at ({wall_x}, {wall_y})")
            elif not is_pending_junction and dungeon.get_tile(wall_x, wall_y) == dungeon.TileType.UNEXPLORED:
                dungeon.grid[(wall_x, wall_y)] = dungeon.TileType.WALL
                dungeon._log(f"    Placed side wall at ({wall_x}, {wall_y})")
        
        # If the end is a dead end or stairs, cap it with a wall in the forward direction
        if is_dead_end_or_stairs:
            beyond_x = end_x + direction[0]
            beyond_y = end_y + direction[1]
            beyond_tile = dungeon.get_tile(beyond_x, beyond_y)
            dungeon._log(f"    Wall cap check at ({beyond_x}, {beyond_y}): {beyond_tile.name}")
            if beyond_tile in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                dungeon.grid[(beyond_x, beyond_y)] = dungeon.TileType.WALL
                dungeon._log(f"    Placed wall cap at ({beyond_x}, {beyond_y})")
            else:
                dungeon._log(f"    SKIPPED wall cap at ({beyond_x}, {beyond_y}) - tile is {beyond_tile.name}")
        
        return passage_tiles


def _resolve_passage_end(dungeon: "Dungeon", x: int, y: int, direction: Tuple[int, int], roll: int):
    """Resolve what happens at passage end (2D12)."""
    if not hasattr(dungeon, 'pending_junctions'):
        dungeon.pending_junctions = {}
    
    dungeon._log(f"  Passage end at ({x},{y}): roll {roll}")
    
    if roll <= 3 or 12 <= roll <= 14 or roll >= 23:
        # T-junction (2-3, 12-14, 23-24): side exits only, wall blocks forward
        dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
        wall_x = x + direction[0]
        wall_y = y + direction[1]
        dungeon.grid[(wall_x, wall_y)] = dungeon.TileType.WALL
        for side in _get_both_perpendicular(direction):
            side_x = wall_x + side[0]
            side_y = wall_y + side[1]
            dungeon.grid[(side_x, side_y)] = dungeon.TileType.WALL
        perp_dirs = _get_both_perpendicular(direction)
        dungeon.pending_junctions[(x, y)] = list(perp_dirs)
        dungeon._log(f"    Generated T_JUNCTION at ({x}, {y}), side exits: {list(perp_dirs)}")
    elif 4 <= roll <= 8:
        # Dead end (4-8)
        dungeon.grid[(x, y)] = dungeon.TileType.PASSAGE_END
        dungeon._log(f"    Generated PASSAGE_END (dead end) at ({x}, {y})")
    elif 9 <= roll <= 11:
        # Right turn (9-11)
        dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
        if direction == (1, 0):
            right_dir = (0, 1)
        elif direction == (-1, 0):
            right_dir = (0, -1)
        elif direction == (0, 1):
            right_dir = (-1, 0)
        else:
            right_dir = (1, 0)
        dungeon.pending_junctions[(x, y)] = [right_dir]
        dungeon._log(f"    Generated RIGHT_TURN at ({x}, {y}), continues {right_dir}")
        right_x, right_y = x + right_dir[0], y + right_dir[1]
        if dungeon.get_tile(right_x, right_y) == dungeon.TileType.WALL:
            del dungeon.grid[(right_x, right_y)]
            dungeon._log(f"    Cleared right exit wall at ({right_x}, {right_y})")
        forward_x, forward_y = x + direction[0], y + direction[1]
        left_dir = (-right_dir[0], -right_dir[1])
        left_x, left_y = x + left_dir[0], y + left_dir[1]
        if dungeon.get_tile(forward_x, forward_y) == dungeon.TileType.UNEXPLORED:
            dungeon.grid[(forward_x, forward_y)] = dungeon.TileType.WALL
        if dungeon.get_tile(left_x, left_y) == dungeon.TileType.UNEXPLORED:
            dungeon.grid[(left_x, left_y)] = dungeon.TileType.WALL
    elif 15 <= roll <= 17:
        # Left turn (15-17)
        dungeon.grid[(x, y)] = dungeon.TileType.FLOOR
        if direction == (1, 0):
            left_dir = (0, -1)
        elif direction == (-1, 0):
            left_dir = (0, 1)
        elif direction == (0, 1):
            left_dir = (1, 0)
        else:
            left_dir = (-1, 0)
        dungeon.pending_junctions[(x, y)] = [left_dir]
        dungeon._log(f"    Generated LEFT_TURN at ({x}, {y}), continues {left_dir}")
        left_x, left_y = x + left_dir[0], y + left_dir[1]
        if dungeon.get_tile(left_x, left_y) == dungeon.TileType.WALL:
            del dungeon.grid[(left_x, left_y)]
            dungeon._log(f"    Cleared left exit wall at ({left_x}, {left_y})")
        forward_x, forward_y = x + direction[0], y + direction[1]
        right_dir = (-left_dir[0], -left_dir[1])
        right_x, right_y = x + right_dir[0], y + right_dir[1]
        if dungeon.get_tile(forward_x, forward_y) == dungeon.TileType.UNEXPLORED:
            dungeon.grid[(forward_x, forward_y)] = dungeon.TileType.WALL
        if dungeon.get_tile(right_x, right_y) == dungeon.TileType.UNEXPLORED:
            dungeon.grid[(right_x, right_y)] = dungeon.TileType.WALL
    elif 18 <= roll <= 19:
        # Stairs down
        dungeon.grid[(x, y)] = dungeon.TileType.STAIRS_DOWN
        dungeon._log(f"    Generated STAIRS_DOWN at ({x}, {y})")
    elif 20 <= roll <= 22:
        # Stairs out
        dungeon.grid[(x, y)] = dungeon.TileType.STAIRS_OUT
        dungeon._log(f"    Generated STAIRS_OUT at ({x}, {y})")


def _generate_room(dungeon: "Dungeon", door_x: int, door_y: int,
                   entrance_dir: Tuple[int, int], from_passage: bool = False):
    """Generate a room beyond a door."""
    # Roll room type
    roll = random.randint(1, 12)
    if roll <= 6:
        room_type = "normal"
        width, height = random.randint(4, 6), random.randint(4, 6)
    elif roll <= 8:
        room_type = "hazard"
        width, height = random.randint(4, 6), random.randint(4, 6)
    elif roll <= 10:
        room_type = "lair"
        width, height = random.randint(6, 10), random.randint(6, 10)
    else:
        room_type = "quest"
        width, height = random.randint(8, 12), random.randint(8, 12)
    
    dungeon._log(f"  Room generation roll: {roll} -> {room_type} ({width}x{height})")
    
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
    
    # Check if room centre would overlap heavily with existing tiles
    overlap_count = 0
    for x in range(center_x - half_w, center_x + half_w + 1):
        for y in range(center_y - half_h, center_y + half_h + 1):
            if dungeon.get_tile(x, y) not in (dungeon.TileType.UNEXPLORED, dungeon.TileType.WALL):
                overlap_count += 1
    
    # If too much overlap, just make a small passage instead
    if overlap_count > 2:
        dungeon._log(f"Room at ({center_x},{center_y}) overlaps too much ({overlap_count}), creating passage instead")
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
            if dungeon.get_tile(x, y) != dungeon.TileType.UNEXPLORED:
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
        _place_monsters_in_room(dungeon, room_tiles, "lair")
    elif room_type == "quest":
        _place_monsters_in_room(dungeon, room_tiles, "quest")


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
            doors_placed += 1


def _place_monsters_in_room(dungeon: "Dungeon", room_tiles: List[Tuple[int, int]], encounter_type: str):
    """Place monsters in a room."""
    from monster import roll_lair_encounter, roll_quest_room_encounter
    
    if encounter_type == "lair":
        monster_ids = roll_lair_encounter()
    else:
        monster_ids = roll_quest_room_encounter()
    
    dungeon._log(f"  Placing monsters in {encounter_type} room: {monster_ids}")
    dungeon._log(f"  Room has {len(room_tiles)} tiles, hero_start at {dungeon.hero_start}")
    
    available = [t for t in room_tiles if not dungeon._is_near_entrance(t[0], t[1])]
    dungeon._log(f"  Available tiles for monsters (not near entrance): {len(available)}")
    
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

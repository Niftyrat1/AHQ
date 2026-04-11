"""
Procedural dungeon generation for Advanced HeroQuest.
"""

import random
import json
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from enum import Enum, auto


class TileType(Enum):
    """Types of dungeon tiles."""
    UNEXPLORED = auto()
    FLOOR = auto()
    WALL = auto()
    DOOR_CLOSED = auto()
    DOOR_OPEN = auto()
    PASSAGE_END = auto()
    STAIRS_DOWN = auto()
    STAIRS_OUT = auto()
    TREASURE_CLOSED = auto()
    TREASURE_OPEN = auto()
    PIT_TRAP = auto()


class Dungeon:
    """Represents a procedurally generated dungeon."""
    
    def __init__(self, size: int = 100, level: int = 1, debug_log: Optional[list] = None):
        self.size = size
        self.level = level
        self.grid: Dict[Tuple[int, int], TileType] = {}
        self.explored: set = set()
        self.doors: Dict[Tuple[int, int], dict] = {}  # (x,y) -> {is_open: bool, from_room: bool}
        self.monsters: Dict[Tuple[int, int], str] = {}  # (x,y) -> monster_instance_id
        self.debug_log = debug_log  # Optional list to append debug messages
        self.treasure: Dict[Tuple[int, int], bool] = {}  # (x,y) -> is_open
        self.hero_start = (0, 0)
        self.pending_junctions: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        self.rooms: List[Set[Tuple[int, int]]] = []  # List of room tile sets
        
        # Initialize with starting room
        self._create_starting_area()
    
    def _log(self, msg: str):
        """Log debug message if debug_log is configured."""
        if self.debug_log is not None:
            self.debug_log.append(msg)
            print(f"[DUNGEON] {msg}")  # Also print to console
    
    def _create_starting_area(self):
        """Create the starting area: stairs, passage East, T-junction with
        North and South passages — all fully placed at game start."""

        # Stairs at origin
        self.grid[(0, 0)] = TileType.STAIRS_DOWN
        self.explored.add((0, 0))

        # West end cap wall
        self.grid[(-1, 0)] = TileType.WALL
        self.grid[(-1, -1)] = TileType.WALL
        self.grid[(-1, 1)] = TileType.WALL
        self.explored.add((-1, 0))
        self.explored.add((-1, -1))
        self.explored.add((-1, 1))

        # Passage tiles 1-7 going East, with walls North and South
        for i in range(1, 8):
            self.grid[(i, 0)] = TileType.FLOOR
            self.explored.add((i, 0))
            self.grid[(i, -1)] = TileType.WALL   # North wall
            self.grid[(i, 1)] = TileType.WALL    # South wall
            # Explore walls alongside passage (but not T-junction extensions)
            self.explored.add((i, -1))
            self.explored.add((i, 1))

        # Stairs North and South walls
        self.grid[(0, -1)] = TileType.WALL
        self.grid[(0, 1)] = TileType.WALL
        self.explored.add((0, -1))
        self.explored.add((0, 1))

        # T-junction at (8, 0)
        self.grid[(8, 0)] = TileType.FLOOR
        self.explored.add((8, 0))
        
        # Wall straight ahead (East) - T-junction blocks this direction
        self.grid[(9, 0)] = TileType.WALL
        self.grid[(9, -1)] = TileType.WALL  # North side
        self.grid[(9, 1)] = TileType.WALL   # South side
        # Make walls visible at start
        self.explored.update([(9, 0), (9, -1), (9, 1)])
        
        # Generate North and South passages but don't explore them yet
        # They'll be revealed when hero steps on the T-junction
        self.generate_passage_from(8, 0, (0, -1), auto_explore=False)  # North
        self.generate_passage_from(8, 0, (0, 1), auto_explore=False)    # South
        
        # Note: (8,0) is NOT registered in pending_junctions because passages
        # are already generated above. When hero steps here, check_and_generate_junction
        # will just explore the existing passages without regenerating them.
        
        # Verify walls are in place
        self._log(f"  After setup: (9,0) is {self.get_tile(9, 0).name}, (9,-1) is {self.get_tile(9, -1).name}, (9,1) is {self.get_tile(9, 1).name}")
    
    def get_tile(self, x: int, y: int) -> TileType:
        """Get tile at position."""
        return self.grid.get((x, y), TileType.UNEXPLORED)
    
    def is_explored(self, x: int, y: int) -> bool:
        """Check if tile has been explored."""
        return (x, y) in self.explored
    
    def is_walkable(self, x: int, y: int) -> bool:
        """Check if heroes can walk on this tile."""
        tile = self.get_tile(x, y)
        if tile in (TileType.FLOOR, TileType.STAIRS_DOWN, TileType.STAIRS_OUT, 
                    TileType.DOOR_OPEN, TileType.TREASURE_OPEN, TileType.PASSAGE_END):
            return True
        return False
    
    def is_blocked(self, x: int, y: int) -> bool:
        """Check if tile blocks movement."""
        tile = self.get_tile(x, y)
        return tile in (TileType.WALL, TileType.UNEXPLORED, TileType.DOOR_CLOSED,
                       TileType.PIT_TRAP, TileType.TREASURE_CLOSED)
    
    def _explore_from(self, x: int, y: int):
        """Reveal tiles using line-of-sight. Walls block vision.
        If inside a room, reveal the entire room."""
        # Always explore the hero's current tile
        self.explored.add((x, y))
        
        # Check if hero is inside a room - if so, reveal entire room
        for room in self.rooms:
            if (x, y) in room:
                # Hero is in this room - reveal all of it
                self._log(f"Hero in room at ({x},{y}), revealing {len(room)} tiles")
                for room_tile in room:
                    self.explored.add(room_tile)
                return  # Room revealed, done
        
        # Not in a room - use line-of-sight (4 cardinal directions only)
        directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # N, E, S, W
        
        max_range = 6  # How far hero can see
        
        for dx, dy in directions:
            curr_x, curr_y = x, y
            for _ in range(max_range):
                curr_x += dx
                curr_y += dy
                pos = (curr_x, curr_y)
                tile = self.get_tile(curr_x, curr_y)
                
                # Stop if we hit unexplored territory
                if tile == TileType.UNEXPLORED:
                    break
                
                # Explore this tile
                self.explored.add(pos)
                
                # Also explore adjacent walls (to see walls alongside passages)
                # Only do this for floor tiles, not walls (can't see past a wall)
                if tile == TileType.FLOOR:
                    for side_dx, side_dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        adj_pos = (curr_x + side_dx, curr_y + side_dy)
                        adj_tile = self.get_tile(adj_pos[0], adj_pos[1])
                        if adj_tile == TileType.WALL:
                            self.explored.add(adj_pos)
                
                # Stop the ray if we hit a wall (can't see through it)
                if tile == TileType.WALL:
                    break
    
    def check_and_generate_junction(self, x: int, y: int) -> bool:
        """Check if position is a pending junction and generate/explore its exits."""
        pos = (x, y)
        if not hasattr(self, 'pending_junctions'):
            self._log(f"check_and_generate_junction at {pos}: NO pending_junctions attribute")
            return False
        
        # Special case: starting T-junction at (8,0) - passages pre-generated, just explore
        if pos not in self.pending_junctions:
            # Check if this has pre-generated passages (like starting area)
            # by looking for FLOOR tiles in cardinal directions
            existing_exits = []
            for direction in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
                check_x = x + direction[0]
                check_y = y + direction[1]
                tile = self.get_tile(check_x, check_y)
                if tile == TileType.FLOOR:
                    existing_exits.append(direction)
            
            if existing_exits:
                # Has existing passages - just explore them without regenerating
                self._log(f"check_and_generate_junction at {pos}: exploring {len(existing_exits)} existing passages")
                for direction in existing_exits:
                    self._log(f"  Exploring existing direction {direction}")
                    curr_x, curr_y = x, y
                    for _ in range(20):  # Max passage length
                        curr_x += direction[0]
                        curr_y += direction[1]
                        tile = self.get_tile(curr_x, curr_y)
                        if tile == TileType.UNEXPLORED:
                            break
                        self.explored.add((curr_x, curr_y))
                        # Explore adjacent tiles (walls, doors)
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                adj_pos = (curr_x + dx, curr_y + dy)
                                adj_tile = self.get_tile(adj_pos[0], adj_pos[1])
                                if adj_tile != TileType.UNEXPLORED and adj_pos not in self.explored:
                                    self.explored.add(adj_pos)
                self._explore_from(x, y)
                return True
            
            pending_list = list(self.pending_junctions.keys())[:5]  # Show first 5
            self._log(f"check_and_generate_junction at {pos}: NOT in pending_junctions (has {pending_list})")
            return False
        
        exits = self.pending_junctions[pos]
        # Determine junction type based on exits
        if len(exits) == 1:
            junc_type = "Turn/Continue"
        elif len(exits) == 2:
            # Check if exits are opposite (straight) or perpendicular (T-junction)
            dx1, dy1 = exits[0]
            dx2, dy2 = exits[1]
            if dx1 == -dx2 and dy1 == -dy2:
                junc_type = "Straight or Side passage"
            else:
                junc_type = "T-junction"
        elif len(exits) == 3:
            junc_type = "X-junction (cross)"
        else:
            junc_type = f"{len(exits)}-way junction"
        
        self._log(f"check_and_generate_junction at {pos}: {junc_type} with exits {exits}")
        self._log(f"  ALL pending_junctions: {dict(self.pending_junctions)}")
        
        # Clear any blocking walls in the exit directions first
        # But don't clear if this is a room wall (part of room boundary)
        for direction in exits:
            wall_x = x + direction[0]
            wall_y = y + direction[1]
            tile = self.get_tile(wall_x, wall_y)
            self._log(f"  Checking exit at ({wall_x}, {wall_y}): {tile.name}")
            if tile == TileType.WALL:
                # Check if this wall is part of a room (surrounded by other room tiles)
                # If so, don't clear it - it's a room wall
                is_room_wall = self._is_room_wall(wall_x, wall_y)
                if is_room_wall:
                    self._log(f"  NOT clearing wall at ({wall_x}, {wall_y}) - it's a room wall")
                else:
                    self._log(f"  Clearing wall at ({wall_x}, {wall_y})")
                    del self.grid[(wall_x, wall_y)]
            elif tile != TileType.UNEXPLORED:
                self._log(f"  Exit at ({wall_x}, {wall_y}) is {tile.name}, not a wall")
        
        # Get and remove this junction from pending
        exits = self.pending_junctions.pop(pos)
        self._log(f"  Removed {pos} from pending_junctions, remaining: {list(self.pending_junctions.keys())}")
        
        # Explore passages in all pending directions
        for direction in exits:
            self._log(f"  Exploring direction {direction}")
            # First generate the passage from this junction (for turns/T-junctions)
            self.generate_passage_from(x, y, direction)
            # Then explore the newly generated passage
            curr_x, curr_y = x, y
            tiles_explored = 0
            walls_explored = 0
            for _ in range(20):  # Max passage length
                curr_x += direction[0]
                curr_y += direction[1]
                tile = self.get_tile(curr_x, curr_y)
                if tile == TileType.UNEXPLORED:
                    self._log(f"    Hit unexplored at ({curr_x}, {curr_y}), stopping")
                    break
                # Explore this tile
                self.explored.add((curr_x, curr_y))
                tiles_explored += 1
                self._log(f"    Explored tile ({curr_x}, {curr_y}): {tile.name}")
                # Explore adjacent tiles (walls, doors)
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        adj_pos = (curr_x + dx, curr_y + dy)
                        adj_tile = self.get_tile(adj_pos[0], adj_pos[1])
                        if adj_tile != TileType.UNEXPLORED and adj_pos not in self.explored:
                            self.explored.add(adj_pos)
                            walls_explored += 1
                            self._log(f"      Adjacent wall at {adj_pos}: {adj_tile.name}")
            self._log(f"  Total: {tiles_explored} tiles, {walls_explored} adjacent tiles explored")
            self._log(f"  After exploring {direction}, ALL pending_junctions: {dict(self.pending_junctions)}")
        # Also re-explore from current position after all directions processed
        self._log(f"  Before _explore_from, ALL pending_junctions: {dict(self.pending_junctions)}")
        self._explore_from(x, y)
        self._log(f"  Final ALL pending_junctions: {dict(self.pending_junctions)}")
        return True
    
    def open_door(self, x: int, y: int) -> bool:
        """Open a door and generate what's beyond."""
        if (x, y) not in self.doors:
            return False
        
        direction = self._get_door_direction(x, y)
        target_x = x + direction[0]
        target_y = y + direction[1]
        
        # Safety check — don't generate into already-explored walkable space
        target_tile = self.get_tile(target_x, target_y)
        if target_tile in (TileType.FLOOR, TileType.STAIRS_DOWN, TileType.STAIRS_OUT):
            self._log(f"Door at ({x},{y}) points toward existing floor at ({target_x},{target_y}), skipping generation")
            door_info = self.doors[(x, y)]
            door_info["is_open"] = True
            self.grid[(x, y)] = TileType.DOOR_OPEN
            return True
        
        door_info = self.doors[(x, y)]
        door_info["is_open"] = True
        self.grid[(x, y)] = TileType.DOOR_OPEN  # Door stays here, just opens
        self.explored.add((x, y))
        
        direction = self._get_door_direction(x, y)
        
        # Generation starts immediately beyond the door tile
        # NOT one tile further — the door IS the threshold
        gen_x = x + direction[0]
        gen_y = y + direction[1]
        
        from_room = door_info.get("from_room", True)
        
        if from_room:
            roll = random.randint(1, 12)
            if roll <= 6:
                self.generate_passage_from(x, y, direction)
            else:
                self._generate_room(gen_x, gen_y, direction, from_passage=False)
        else:
            self._generate_room(gen_x, gen_y, direction, from_passage=False)
        
        return True
    
    def _get_door_direction(self, x: int, y: int) -> Tuple[int, int]:
        """Determine which way the door opens — toward unexplored space."""
        for direction in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + direction[0], y + direction[1]
            tile = self.get_tile(nx, ny)
            # Door opens toward unexplored or passage-end space
            if tile == TileType.UNEXPLORED:
                return direction
        # Fallback: open toward non-floor tile
        for direction in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + direction[0], y + direction[1]
            tile = self.get_tile(nx, ny)
            if tile not in (TileType.FLOOR, TileType.STAIRS_DOWN,
                            TileType.STAIRS_OUT, TileType.DOOR_OPEN):
                return direction
        return (1, 0)  # Last resort
    
    def _generate_room(self, door_x: int, door_y: int, entrance_dir: Tuple[int, int],
                       from_passage: bool = False):
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
        
        # Create room
        room_tiles = []
        room_walls = []
        entrance_wall_positions = set()
        half_w, half_h = width // 2, height // 2
        
        # door_x, door_y is the first tile beyond the door (should be floor)
        # Shift center by 1 toward door so entrance becomes interior, not wall
        if entrance_dir == (0, -1):   # North - shift down (toward door)
            center_x, center_y = door_x, door_y - half_h + 1
        elif entrance_dir == (0, 1):  # South - shift up (toward door)
            center_x, center_y = door_x, door_y + half_h - 1
        elif entrance_dir == (-1, 0): # West - shift right (toward door)
            center_x, center_y = door_x - half_w + 1, door_y
        else:                          # East - shift left (toward door)
            center_x, center_y = door_x + half_w - 1, door_y
        
        # Check if room centre would overlap heavily with existing tiles
        overlap_count = 0
        for x in range(center_x - half_w, center_x + half_w + 1):
            for y in range(center_y - half_h, center_y + half_h + 1):
                if self.get_tile(x, y) not in (TileType.UNEXPLORED, TileType.WALL):
                    overlap_count += 1
        
        # If too much overlap, just make a small passage instead
        if overlap_count > 2:
            self._log(f"Room at ({center_x},{center_y}) overlaps too much ({overlap_count}), creating passage instead")
            self.generate_passage_from(door_x - entrance_dir[0], door_y - entrance_dir[1], entrance_dir)
            return
        
        # Clear entrance position if it's a wall (from passage generation)
        # This ensures the entrance becomes floor and is walkable
        if self.get_tile(door_x, door_y) == TileType.WALL:
            del self.grid[(door_x, door_y)]
        
        # Find entrance wall positions (the side where we came from)
        # Entrance side is OPPOSITE to the direction we're moving (entrance_dir points IN)
        for x in range(center_x - half_w, center_x + half_w + 1):
            for y in range(center_y - half_h, center_y + half_h + 1):
                # Check if on the entrance side of the room
                if entrance_dir == (0, -1):  # Entering from South, entrance is South side
                    if y == center_y + half_h and (x, y) != (door_x, door_y):
                        entrance_wall_positions.add((x, y))
                elif entrance_dir == (0, 1):  # Entering from North, entrance is North side
                    if y == center_y - half_h and (x, y) != (door_x, door_y):
                        entrance_wall_positions.add((x, y))
                elif entrance_dir == (-1, 0):  # Entering from East, entrance is East side
                    if x == center_x + half_w and (x, y) != (door_x, door_y):
                        entrance_wall_positions.add((x, y))
                elif entrance_dir == (1, 0):  # Entering from West, entrance is West side
                    if x == center_x - half_w and (x, y) != (door_x, door_y):
                        entrance_wall_positions.add((x, y))
        
        for x in range(center_x - half_w, center_x + half_w + 1):
            for y in range(center_y - half_h, center_y + half_h + 1):
                # Only place tiles where unexplored - never overwrite existing passage/rooms
                if self.get_tile(x, y) != TileType.UNEXPLORED:
                    continue
                
                if abs(x - center_x) == half_w or abs(y - center_y) == half_h:
                    # Walls - only place if unexplored or forced for entrance
                    if (x, y) in entrance_wall_positions:
                        self.grid[(x, y)] = TileType.WALL
                        room_walls.append((x, y))
                else:
                    # Floor
                    self.grid[(x, y)] = TileType.FLOOR
                    room_tiles.append((x, y))
                    # Note: NOT added to explored - room stays hidden until hero reaches doorway
        
        # If from passage, place the door at the entrance
        if from_passage:
            self.grid[(door_x, door_y)] = TileType.DOOR_CLOSED
            # Remove door position from walls if it was added
            if (door_x, door_y) in room_walls:
                room_walls.remove((door_x, door_y))
        
        # Ensure entrance position is part of the room for visibility
        if (door_x, door_y) not in room_tiles and (door_x, door_y) not in room_walls:
            room_tiles.append((door_x, door_y))
        
        # Store room for later revelation
        # Walls NOT added to explored - room outline hidden until hero reaches doorway
        self.rooms.append(set(room_tiles + room_walls))
        
        # Reveal room from doorway so it's visible when door opens
        # This reveals walls and floor that are within line-of-sight from entrance
        self._explore_from(door_x, door_y)
        
        # Add extra doors
        num_doors = self._roll_room_doors()
        self._add_doors_to_room(center_x, center_y, half_w, half_h, num_doors, entrance_dir)
        
        # Add content based on room type
        if room_type == "lair":
            # Place monsters
            self._place_monsters_in_room(room_tiles, "lair")
        elif room_type == "quest":
            self._place_monsters_in_room(room_tiles, "quest")
        elif room_type == "hazard":
            # Place hazard (Phase 2)
            pass

    def _is_room_wall(self, x: int, y: int) -> bool:
        """Check if a wall is part of a room boundary."""
        # Check if this wall position is surrounded by room tiles
        # A room wall should have floor tiles on at least one side (inside the room)
        floor_neighbors = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_tile = self.get_tile(x + dx, y + dy)
            if neighbor_tile == TileType.FLOOR:
                floor_neighbors += 1
        # If there are floor neighbors, this is likely a room wall
        return floor_neighbors > 0

    def _roll_room_doors(self) -> int:
        """Roll for number of extra doors in a room."""
        roll = random.randint(1, 12)
        if roll <= 4:
            return 0
        elif roll <= 8:
            return 1
        else:
            return 2
    
    def _add_doors_to_room(self, cx: int, cy: int, half_w: int, half_h: int, 
                          num_doors: int, entrance_dir: Tuple[int, int]):
        """Add doors to room walls."""
        walls = []
        
        # Find all wall positions that could have doors
        for x in range(cx - half_w, cx + half_w + 1):
            walls.append((x, cy - half_h, 0, -1))  # North wall
            walls.append((x, cy + half_h, 0, 1))   # South wall
        for y in range(cy - half_h, cy + half_h + 1):
            walls.append((cx - half_w, y, -1, 0))  # West wall
            walls.append((cx + half_w, y, 1, 0))   # East wall
        
        # Remove the entrance position
        entrance_pos = (cx - entrance_dir[0] * half_w if entrance_dir[0] != 0 else cx,
                     cy - entrance_dir[1] * half_h if entrance_dir[1] != 0 else cy)
        walls = [w for w in walls if (w[0], w[1]) != entrance_pos]
        
        # Add doors randomly
        random.shuffle(walls)
        for i in range(min(num_doors, len(walls))):
            x, y, dx, dy = walls[i]
            if self.get_tile(x, y) in (TileType.WALL, TileType.UNEXPLORED):
                self.grid[(x, y)] = TileType.DOOR_CLOSED
                self.doors[(x, y)] = {"is_open": False, "from_room": True}  # From room
    
    def _place_monsters_in_room(self, room_tiles: List[Tuple[int, int]], encounter_type: str):
        """Place monsters in a room."""
        from monster import roll_lair_encounter, roll_quest_room_encounter
        
        if encounter_type == "lair":
            monster_ids = roll_lair_encounter()
        else:
            monster_ids = roll_quest_room_encounter()
        
        # Place monsters in room (not too close to entrance)
        available = [t for t in room_tiles if not self._is_near_entrance(t[0], t[1])]
        
        for monster_id in monster_ids:
            if available:
                pos = random.choice(available)
                self.monsters[pos] = monster_id
                available.remove(pos)
    
    def _is_near_entrance(self, x: int, y: int, distance: int = 3) -> bool:
        """Check if position is near the stairs entrance."""
        return abs(x - self.hero_start[0]) + abs(y - self.hero_start[1]) <= distance
    
    def generate_passage_from(self, x: int, y: int, direction: Tuple[int, int],
                               auto_explore: bool = True) -> List[Tuple[int, int]]:
        """Generate a passage from a junction."""
        # Roll passage length
        roll = random.randint(1, 12)
        if roll <= 2:
            sections = 1
        elif roll <= 8:
            sections = 2
        else:
            sections = 3
        
        self._log(f"Generating passage from ({x},{y}) direction {direction}: {sections} section(s) (roll {roll})")
        
        passage_tiles = []
        current_x, current_y = x, y
        
        for section_idx in range(sections):
            # Each section is 4 tiles
            for tile_idx in range(4):
                current_x += direction[0]
                current_y += direction[1]
                
                # Check for overlap - stop if hitting existing room or non-floor tiles
                tile = self.get_tile(current_x, current_y)
                if tile == TileType.UNEXPLORED:
                    pass  # Can generate here
                elif tile == TileType.FLOOR:
                    # Check if this floor is part of an existing room - if so, stop
                    for room in self.rooms:
                        if (current_x, current_y) in room:
                            self._log(f"    Blocked at ({current_x}, {current_y}) - part of existing room, stopping")
                            return passage_tiles
                    # Already floor from previous passage generation, continue
                    passage_tiles.append((current_x, current_y))
                    if auto_explore:
                        self.explored.add((current_x, current_y))
                    continue
                else:
                    # Blocked by wall, door, stairs, etc. - don't overwrite, just stop
                    self._log(f"    Blocked at ({current_x}, {current_y}) by {tile.name}, stopping")
                    return passage_tiles
                
                self.grid[(current_x, current_y)] = TileType.FLOOR
                passage_tiles.append((current_x, current_y))
                if auto_explore:
                    self.explored.add((current_x, current_y))
                
                # Place walls on both sides — skip if already floor/door/stairs
                # Note: walls at last tile are placed here, then cleared later if it's a junction
                for side in self._get_both_perpendicular(direction):
                    wall_x = current_x + side[0]
                    wall_y = current_y + side[1]
                    existing = self.get_tile(wall_x, wall_y)
                    if existing in (TileType.UNEXPLORED, TileType.WALL):
                        self.grid[(wall_x, wall_y)] = TileType.WALL
            
            # Check for features (doors) - Passage Features Table (2D12)
            feature_roll = random.randint(1, 12) + random.randint(1, 12)  # Proper 2D12 bell curve
            if 2 <= feature_roll <= 4 or 22 <= feature_roll <= 24:
                # Wandering monsters (triggered in game logic)
                pass  # Game will check this and spawn
            elif 16 <= feature_roll <= 19:
                # 1 door on side
                side_dir = self._get_perpendicular(direction)
                door_x = current_x + side_dir[0]
                door_y = current_y + side_dir[1]
                self._log(f"    Attempting door at ({door_x}, {door_y}), tile: {self.get_tile(door_x, door_y).name}")
                if self.get_tile(door_x, door_y) in (TileType.UNEXPLORED, TileType.WALL):
                    self.grid[(door_x, door_y)] = TileType.DOOR_CLOSED
                    self.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}  # From passage
                    self._log(f"    Placed 1 door at ({door_x}, {door_y})")
            elif 20 <= feature_roll <= 21:
                # 2 doors on sides
                side_dirs = self._get_both_perpendicular(direction)
                for side_dir in side_dirs:
                    door_x = current_x + side_dir[0]
                    door_y = current_y + side_dir[1]
                    self._log(f"    Attempting door at ({door_x}, {door_y}), tile: {self.get_tile(door_x, door_y).name}")
                    if self.get_tile(door_x, door_y) in (TileType.UNEXPLORED, TileType.WALL):
                        self.grid[(door_x, door_y)] = TileType.DOOR_CLOSED
                        self.doors[(door_x, door_y)] = {"is_open": False, "from_room": False}  # From passage
                        self._log(f"    Placed door at ({door_x}, {door_y})")
        
        # Roll passage end
        end_roll = random.randint(1, 12) + random.randint(1, 12)  # Proper 2D12 bell curve
        end_x, end_y = current_x + direction[0], current_y + direction[1]
        self._resolve_passage_end(end_x, end_y, direction, end_roll)
        
        # Cap the end of the passage with walls perpendicular to travel
        # Place walls on sides of the end tile
        end_tile = self.get_tile(end_x, end_y)
        is_dead_end_or_stairs = end_tile in (TileType.PASSAGE_END, TileType.STAIRS_DOWN, TileType.STAIRS_OUT)
        # Check if this position is a pending junction (T-junction or turn)
        is_pending_junction = (end_x, end_y) in self.pending_junctions
        
        for side in self._get_both_perpendicular(direction):
            wall_x = end_x + side[0]
            wall_y = end_y + side[1]
            # Always place walls for dead ends/stairs; never for pending junctions (exits must be clear)
            if is_dead_end_or_stairs:
                if self.get_tile(wall_x, wall_y) in (TileType.UNEXPLORED, TileType.WALL):
                    self.grid[(wall_x, wall_y)] = TileType.WALL
                    self._log(f"    Placed side wall at ({wall_x}, {wall_y})")
            elif not is_pending_junction and self.get_tile(wall_x, wall_y) == TileType.UNEXPLORED:
                self.grid[(wall_x, wall_y)] = TileType.WALL
                self._log(f"    Placed side wall at ({wall_x}, {wall_y})")
        
        # If the end is a dead end or stairs, cap it with a wall in the forward direction
        if is_dead_end_or_stairs:
            # Cap it with a wall
            beyond_x = end_x + direction[0]
            beyond_y = end_y + direction[1]
            beyond_tile = self.get_tile(beyond_x, beyond_y)
            self._log(f"    Wall cap check at ({beyond_x}, {beyond_y}): {beyond_tile.name}")
            if beyond_tile in (TileType.UNEXPLORED, TileType.WALL):
                self.grid[(beyond_x, beyond_y)] = TileType.WALL
                self._log(f"    Placed wall cap at ({beyond_x}, {beyond_y})")
            else:
                self._log(f"    SKIPPED wall cap at ({beyond_x}, {beyond_y}) - tile is {beyond_tile.name}")
        
        return passage_tiles
    
    def _get_perpendicular(self, direction: Tuple[int, int]) -> Tuple[int, int]:
        """Get perpendicular direction."""
        if direction[0] != 0:  # Moving horizontally
            return (0, 1)  # North-South
        else:
            return (1, 0)  # East-West
    
    def _get_both_perpendicular(self, direction: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get both perpendicular directions (for 2 doors feature)."""
        if direction[0] != 0:  # Moving horizontally (East/West)
            return [(0, 1), (0, -1)]  # North and South
        else:  # Moving vertically (North/South)
            return [(1, 0), (-1, 0)]  # East and West
    
    def _resolve_passage_end(self, x: int, y: int, direction: Tuple[int, int], roll: int):
        """Resolve what happens at passage end (2D12)."""
        if not hasattr(self, 'pending_junctions'):
            self.pending_junctions = {}
        
        self._log(f"  Passage end at ({x},{y}): roll {roll}")
        
        if roll <= 3 or 12 <= roll <= 14 or roll >= 23:
            # T-junction (2-3, 12-14, 23-14): side exits only, wall blocks forward
            self.grid[(x, y)] = TileType.FLOOR
            # Place wall straight ahead to block forward passage (T-shape)
            wall_x = x + direction[0]
            wall_y = y + direction[1]
            self.grid[(wall_x, wall_y)] = TileType.WALL
            # Side walls to cap the T
            for side in self._get_both_perpendicular(direction):
                side_x = wall_x + side[0]
                side_y = wall_y + side[1]
                self.grid[(side_x, side_y)] = TileType.WALL
            # Register side exits as pending
            perp_dirs = self._get_both_perpendicular(direction)
            self.pending_junctions[(x, y)] = list(perp_dirs)
            self._log(f"    Generated T_JUNCTION at ({x}, {y}), side exits: {list(perp_dirs)}")
            self._log(f"    pending_junctions now has: {list(self.pending_junctions.keys())}")
        elif 4 <= roll <= 8:
            # Dead end (4-8)
            self.grid[(x, y)] = TileType.PASSAGE_END
            self._log(f"    Generated PASSAGE_END (dead end) at ({x}, {y})")
        elif 9 <= roll <= 11:
            # Right turn (9-11) - single exit to the right
            self.grid[(x, y)] = TileType.FLOOR
            # Determine right direction based on current heading
            if direction == (1, 0):  # East -> South
                right_dir = (0, 1)
            elif direction == (-1, 0):  # West -> North
                right_dir = (0, -1)
            elif direction == (0, 1):  # South -> West
                right_dir = (-1, 0)
            else:  # North -> East
                right_dir = (1, 0)
            self.pending_junctions[(x, y)] = [right_dir]
            self._log(f"    Generated RIGHT_TURN at ({x}, {y}), continues {right_dir}")
            self._log(f"    pending_junctions now has: {list(self.pending_junctions.keys())}")
            # Clear the exit wall (right side) so hero can walk there
            right_x, right_y = x + right_dir[0], y + right_dir[1]
            if self.get_tile(right_x, right_y) == TileType.WALL:
                del self.grid[(right_x, right_y)]
                self._log(f"    Cleared right exit wall at ({right_x}, {right_y})")
            # Place walls: forward direction and left side (opposite of right turn)
            forward_x, forward_y = x + direction[0], y + direction[1]
            left_dir = (-right_dir[0], -right_dir[1])  # Opposite of right direction
            left_x, left_y = x + left_dir[0], y + left_dir[1]
            if self.get_tile(forward_x, forward_y) == TileType.UNEXPLORED:
                self.grid[(forward_x, forward_y)] = TileType.WALL
                self._log(f"    Placed forward wall at ({forward_x}, {forward_y})")
            if self.get_tile(left_x, left_y) == TileType.UNEXPLORED:
                self.grid[(left_x, left_y)] = TileType.WALL
                self._log(f"    Placed left wall at ({left_x}, {left_y})")
        elif 15 <= roll <= 17:
            # Left turn (15-17) - single exit to the left
            self.grid[(x, y)] = TileType.FLOOR
            # Determine left direction based on current heading
            if direction == (1, 0):  # East -> North
                left_dir = (0, -1)
            elif direction == (-1, 0):  # West -> South
                left_dir = (0, 1)
            elif direction == (0, 1):  # South -> East
                left_dir = (1, 0)
            else:  # North -> West
                left_dir = (-1, 0)
            self.pending_junctions[(x, y)] = [left_dir]
            self._log(f"    Generated LEFT_TURN at ({x}, {y}), continues {left_dir}")
            # Clear the exit wall (left side) so hero can walk there
            left_x, left_y = x + left_dir[0], y + left_dir[1]
            if self.get_tile(left_x, left_y) == TileType.WALL:
                del self.grid[(left_x, left_y)]
                self._log(f"    Cleared left exit wall at ({left_x}, {left_y})")
            # Place walls: forward direction and right side (opposite of left turn)
            forward_x, forward_y = x + direction[0], y + direction[1]
            right_dir = (-left_dir[0], -left_dir[1])  # Opposite of left direction
            right_x, right_y = x + right_dir[0], y + right_dir[1]
            if self.get_tile(forward_x, forward_y) == TileType.UNEXPLORED:
                self.grid[(forward_x, forward_y)] = TileType.WALL
                self._log(f"    Placed forward wall at ({forward_x}, {forward_y})")
            if self.get_tile(right_x, right_y) == TileType.UNEXPLORED:
                self.grid[(right_x, right_y)] = TileType.WALL
                self._log(f"    Placed right wall at ({right_x}, {right_y})")
        elif 18 <= roll <= 19:
            # Stairs down (18-19)
            self.grid[(x, y)] = TileType.STAIRS_DOWN
            self._log(f"    Generated STAIRS_DOWN at ({x}, {y})")
        elif 20 <= roll <= 22:
            # Stairs out (20-22)
            self.grid[(x, y)] = TileType.STAIRS_OUT
            self._log(f"    Generated STAIRS_OUT at ({x}, {y})")
        # Roll 23 is T-junction (handled above with 2-3, 12-14, 23-24)
        # Roll 24 is T-junction (handled above)
    
    def _has_los(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if there's clear line of sight between two points."""
        # Simple Bresenham line algorithm
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x, y = x1, y1
        n = 1 + dx + dy
        x_inc = 1 if x2 > x1 else -1
        y_inc = 1 if y2 > y1 else -1
        error = dx - dy
        dx *= 2
        dy *= 2
        
        for _ in range(n):
            if (x, y) != (x1, y1) and (x, y) != (x2, y2):
                if self.is_blocked(x, y):
                    return False
            
            if error > 0:
                x += x_inc
                error -= dy
            else:
                y += y_inc
                error += dx
        
        return True
    
    def get_monster_at(self, x: int, y: int) -> Optional[str]:
        """Get monster ID at position."""
        return self.monsters.get((x, y))
    
    def remove_monster(self, x: int, y: int):
        """Remove monster from position."""
        if (x, y) in self.monsters:
            del self.monsters[(x, y)]
    
    def is_adjacent(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if two positions are adjacent (Manhattan distance 1)."""
        return abs(x1 - x2) + abs(y1 - y2) == 1
    
    def get_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        """Get Manhattan distance."""
        return abs(x1 - x2) + abs(y1 - y2)
    
    def to_dict(self) -> dict:
        """Convert dungeon to dictionary for saving."""
        # Convert pending_junctions to string format for JSON serialization
        pending = {}
        for pos, directions in self.pending_junctions.items():
            key = f"{pos[0]},{pos[1]}"
            pending[key] = [f"{d[0]},{d[1]}" for d in directions]
        
        return {
            "size": self.size,
            "level": self.level,
            "grid": {f"{x},{y}": t.name for (x, y), t in self.grid.items()},
            "explored": [f"{x},{y}" for x, y in self.explored],
            "doors": {f"{x},{y}": v for (x, y), v in self.doors.items()},
            "monsters": {f"{x},{y}": v for (x, y), v in self.monsters.items()},
            "treasure": {f"{x},{y}": v for (x, y), v in self.treasure.items()},
            "hero_start": self.hero_start,
            "pending_junctions": pending
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Dungeon":
        """Create dungeon from dictionary."""
        dungeon = cls(data.get("size", 100), data.get("level", 1))
        
        dungeon.grid = {}
        for key, val in data.get("grid", {}).items():
            x, y = map(int, key.split(","))
            dungeon.grid[(x, y)] = TileType[val]
        
        dungeon.explored = set()
        for key in data.get("explored", []):
            x, y = map(int, key.split(","))
            dungeon.explored.add((x, y))
        
        dungeon.doors = {}
        for key, val in data.get("doors", {}).items():
            x, y = map(int, key.split(","))
            dungeon.doors[(x, y)] = val
        
        dungeon.monsters = {}
        for key, val in data.get("monsters", {}).items():
            x, y = map(int, key.split(","))
            dungeon.monsters[(x, y)] = val
        
        dungeon.treasure = {}
        for key, val in data.get("treasure", {}).items():
            x, y = map(int, key.split(","))
            dungeon.treasure[(x, y)] = val
        
        dungeon.pending_junctions = {}
        for key, directions in data.get("pending_junctions", {}).items():
            x, y = map(int, key.split(","))
            dungeon.pending_junctions[(x, y)] = [tuple(map(int, d.split(","))) for d in directions]
        
        dungeon.hero_start = tuple(data.get("hero_start", (0, 0)))
        
        return dungeon

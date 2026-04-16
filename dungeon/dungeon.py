"""
Core Dungeon class for Advanced HeroQuest.
"""
import random
import json
from typing import List, Tuple, Optional, Dict, Set
from pathlib import Path

from .tiles import TileType


class Dungeon:
    """Represents a procedurally generated dungeon."""
    
    TileType = TileType  # Expose for convenience
    
    def __init__(self, size: int = 100, level: int = 1, debug_log: Optional[list] = None):
        self.size = size
        self.level = level
        self.grid: Dict[Tuple[int, int], TileType] = {}
        self.explored: Set[Tuple[int, int]] = set()
        self.doors: Dict[Tuple[int, int], dict] = {}
        self.monsters: Dict[Tuple[int, int], str] = {}
        self.wandering_monsters: Set[Tuple[int, int]] = set()
        self.debug_log = debug_log
        self.treasure: Dict[Tuple[int, int], bool] = {}
        self.hero_start = (0, 0)
        self.pending_junctions: Dict[Tuple[int, int], Tuple[Tuple[int, int], int, List[Tuple[int, int]]]] = {}
        self.rooms: List[Set[Tuple[int, int]]] = []
        
        self._create_starting_area()
    
    def _log(self, msg: str):
        """Log debug message if debug_log is configured."""
        if self.debug_log is not None:
            self.debug_log.append(msg)
            print(f"[DUNGEON] {msg}")
    
    def _create_starting_area(self):
        """Create the starting area: 2x2 stairs, 2-wide passage East, 2x2 T-junction."""
        from .generator import generate_passage_from
        
        # 2x2 Stairs block at origin (0,0)-(1,1)
        self.grid[(0, 0)] = TileType.STAIRS_DOWN
        self.grid[(1, 0)] = TileType.STAIRS_DOWN
        self.grid[(0, 1)] = TileType.STAIRS_DOWN
        self.grid[(1, 1)] = TileType.STAIRS_DOWN
        self.explored.add((0, 0))
        self.explored.add((1, 0))
        self.explored.add((0, 1))
        self.explored.add((1, 1))
        
        # West end cap walls (outer walls of 2-wide passage)
        self.grid[(-1, -1)] = TileType.WALL
        self.grid[(-1, 0)] = TileType.WALL
        self.grid[(-1, 1)] = TileType.WALL
        self.grid[(-1, 2)] = TileType.WALL
        
        # 2-wide passage going East for 7 tiles (starting from x=2, after stairs)
        for i in range(2, 9):
            # Left (y=0) and right (y=1) floor tiles
            self.grid[(i, 0)] = TileType.FLOOR
            self.grid[(i, 1)] = TileType.FLOOR
            self.explored.add((i, 0))
            self.explored.add((i, 1))
            # Outer walls (north at y=-1, south at y=2)
            self.grid[(i, -1)] = TileType.WALL
            self.grid[(i, 2)] = TileType.WALL
            self.explored.add((i, -1))
            self.explored.add((i, 2))
        
        # North and South walls at stairs area
        self.grid[(0, -1)] = TileType.WALL
        self.grid[(1, -1)] = TileType.WALL
        self.grid[(0, 2)] = TileType.WALL
        self.grid[(1, 2)] = TileType.WALL
        self.explored.add((0, -1))
        self.explored.add((1, -1))
        self.explored.add((0, 2))
        self.explored.add((1, 2))
        
        # West wall to complete starting area
        self.grid[(-1, -1)] = TileType.WALL
        self.grid[(-1, 2)] = TileType.WALL
        self.explored.add((-1, -1))
        self.explored.add((-1, 2))
        
        # 2x2 T-junction at (9,0)-(10,1) - this is the junction floor
        self.grid[(9, 0)] = TileType.FLOOR
        self.grid[(9, 1)] = TileType.FLOOR
        self.grid[(10, 0)] = TileType.FLOOR
        self.grid[(10, 1)] = TileType.FLOOR
        self.explored.add((9, 0))
        self.explored.add((9, 1))
        self.explored.add((10, 0))
        self.explored.add((10, 1))
        
        # Wall straight ahead (East) at x=11 - 1 tile beyond the 2x2 junction at 9-10
        self.grid[(11, -1)] = TileType.WALL
        self.grid[(11, 0)] = TileType.WALL
        self.grid[(11, 1)] = TileType.WALL
        self.grid[(11, 2)] = TileType.WALL
        # Also explore these walls so they're visible
        self.explored.add((11, -1))
        self.explored.add((11, 0))
        self.explored.add((11, 1))
        self.explored.add((11, 2))
        
        # Set up pending junction for North and South passages
        # All 4 tiles of the 2x2 junction trigger the same passages
        # Store as (source_direction, row, exits)
        for jx in [9, 10]:
            for jy in [0, 1]:
                self.pending_junctions[(jx, jy)] = ((0, -1), 1, [(0, -1), (0, 1)])
        
    
    def get_tile(self, x: int, y: int) -> TileType:
        """Get tile at position."""
        return self.grid.get((x, y), TileType.UNEXPLORED)
    
    def is_explored(self, x: int, y: int) -> bool:
        """Check if tile has been explored."""
        return (x, y) in self.explored
    
    def is_walkable(self, x: int, y: int) -> bool:
        """Check if heroes can walk on this tile."""
        tile = self.get_tile(x, y)
        return tile in (TileType.FLOOR, TileType.STAIRS_DOWN, TileType.STAIRS_OUT,
                       TileType.DOOR_OPEN, TileType.TREASURE_OPEN, TileType.PASSAGE_END)
    
    def is_blocked(self, x: int, y: int) -> bool:
        """Check if tile blocks movement."""
        tile = self.get_tile(x, y)
        return tile in (TileType.WALL, TileType.UNEXPLORED, TileType.DOOR_CLOSED,
                       TileType.PIT_TRAP, TileType.TREASURE_CLOSED)
    
    def _explore_from(self, x: int, y: int):
        """Reveal tiles using line-of-sight. For 2-wide passages, reveals both rows."""
        self.explored.add((x, y))
        
        # Check if hero is inside a room - reveal entire room
        for room in self.rooms:
            if (x, y) in room:
                for room_tile in room:
                    self.explored.add(room_tile)
                return
        
        # Not in a room - use line-of-sight
        # For 2-wide passages, we need to explore in both rows
        directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        max_range = 30
        
        # Determine if we're in a 2-wide passage and find the offset to the parallel row
        parallel_offsets = [(0, 0)]  # Default: just this row
        
        # Check for 2-wide passage: look for adjacent floor perpendicular to East-West
        if self.get_tile(x, y + 1) in (TileType.FLOOR, TileType.STAIRS_DOWN):
            parallel_offsets = [(0, 0), (0, 1)]  # Two rows: y and y+1
        elif self.get_tile(x, y - 1) in (TileType.FLOOR, TileType.STAIRS_DOWN):
            parallel_offsets = [(0, -1), (0, 0)]  # Two rows: y-1 and y
        # Check for 2-wide passage perpendicular to North-South
        elif self.get_tile(x + 1, y) in (TileType.FLOOR, TileType.STAIRS_DOWN):
            parallel_offsets = [(0, 0), (1, 0)]  # Two rows: x and x+1
        elif self.get_tile(x - 1, y) in (TileType.FLOOR, TileType.STAIRS_DOWN):
            parallel_offsets = [(-1, 0), (0, 0)]  # Two rows: x-1 and x
        
        for dx, dy in directions:
            for offset_x, offset_y in parallel_offsets:
                start_x = x + offset_x
                start_y = y + offset_y
                curr_x, curr_y = start_x, start_y
                
                for _ in range(max_range):
                    curr_x += dx
                    curr_y += dy
                    pos = (curr_x, curr_y)
                    tile = self.get_tile(curr_x, curr_y)
                    
                    if tile == TileType.UNEXPLORED:
                        break
                    
                    self.explored.add(pos)
                    
                    if tile in (TileType.FLOOR, TileType.PASSAGE_END, TileType.STAIRS_DOWN, TileType.STAIRS_OUT):
                        for side_dx, side_dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            adj_pos = (curr_x + side_dx, curr_y + side_dy)
                            adj_tile = self.get_tile(adj_pos[0], adj_pos[1])
                            if adj_tile in (TileType.WALL, TileType.PASSAGE_END, TileType.DOOR_CLOSED, TileType.DOOR_OPEN):
                                self.explored.add(adj_pos)
                    
                    if tile in (TileType.WALL, TileType.PASSAGE_END):
                        break
    
    def check_and_generate_junction(self, x: int, y: int) -> bool:
        """Check if position is a pending junction and generate/explore its exits.
        Only triggers when stepping on the exact 2x2 junction tiles."""
        from .generator import generate_passage_from
        
        pos = (x, y)
        self._log(f"check_and_generate_junction called at {pos}")
        self._log(f"  pending_junctions: {list(self.pending_junctions.keys())}")
        
        if not hasattr(self, 'pending_junctions'):
            self._log(f"  No pending_junctions attribute")
            return False
        
        # Only trigger on exact junction positions (the 2x2 floor tiles)
        if pos not in self.pending_junctions:
            self._log(f"  No junction at exact position, doing normal exploration")
            self._explore_from(x, y)
            return False
        
        self._log(f"  Found junction at exact position {pos}")
        
        # Handle backward compatibility for different pending_junctions formats
        junction_data = self.pending_junctions[pos]
        if isinstance(junction_data, tuple) and len(junction_data) == 3:
            # New format: (source_dir, row, exits)
            source_dir, row, exits = junction_data
        elif isinstance(junction_data, list):
            # Old format: [exit1, exit2, ...]
            source_dir, row, exits = (0, 0), 1, junction_data
        else:
            # Unknown format, use defaults
            source_dir, row, exits = (0, 0), 1, []
        
        # Remove all tiles that share the same exits as this junction
        # Find all positions with matching exits and remove them all at once
        def _get_exits(junction_entry):
            if isinstance(junction_entry, tuple) and len(junction_entry) == 3:
                return junction_entry[2]
            elif isinstance(junction_entry, list):
                return junction_entry
            return []
        
        tiles_to_remove = [p for p, e in self.pending_junctions.items() if _get_exits(e) == exits]
        for jt in tiles_to_remove:
            del self.pending_junctions[jt]
        
        if len(exits) == 1:
            junc_type = "Turn/Continue"
        elif len(exits) == 2:
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
        
        
        # For 2-wide passages, remove walls at both left and right positions
        for direction in exits:
            # Calculate left/right offsets based on direction
            if direction in [(0, -1), (0, 1)]:  # North/South
                left_offset, right_offset = (-1, 0), (1, 0)
            else:  # East/West
                left_offset, right_offset = (0, -1), (0, 1)
            
            # Remove walls at both positions for 2-wide passage
            for offset in [left_offset, right_offset]:
                wall_x = x + direction[0] + offset[0]
                wall_y = y + direction[1] + offset[1]
                tile = self.get_tile(wall_x, wall_y)
                if tile == TileType.WALL:
                    # Always remove passage-blocking walls (not room walls)
                    del self.grid[(wall_x, wall_y)]
        
        self._log(f"  Generating passages for exits: {exits}")

        all_passage_tiles = []
        for direction in exits:
            self._log(f"  Generating passage from {pos} in direction {direction}")
            passage_tiles = generate_passage_from(self, pos[0], pos[1], direction, 
                                                  from_room=False, row=row, source_dir=source_dir)
            self._log(f"  Generated {len(passage_tiles)} tiles")
            all_passage_tiles.extend(passage_tiles)

        # Explicitly explore all generated passage tiles and their adjacent walls
        for (tx, ty) in all_passage_tiles:
            self.explored.add((tx, ty))
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    adj_pos = (tx + dx, ty + dy)
                    adj_tile = self.get_tile(adj_pos[0], adj_pos[1])
                    if adj_tile != TileType.UNEXPLORED and adj_pos not in self.explored:
                        self.explored.add(adj_pos)
        
        # Explore the 2x2 areas at the ends of each passage (turns, stairs, T-junctions)
        # These are the last tiles of each passage plus their forward row
        for direction in exits:
            if direction in [(0, -1), (0, 1)]:  # North/South passage
                # Find the furthest tiles in this direction for each passage
                # Group tiles by their x coordinate
                x_groups = {}
                for (tx, ty) in all_passage_tiles:
                    if tx not in x_groups:
                        x_groups[tx] = []
                    x_groups[tx].append(ty)
                
                # For each x group, find the min/max y (furthest in direction)
                for tx, y_list in x_groups.items():
                    if direction == (0, -1):  # North - smallest y
                        end_y = min(y_list)
                    else:  # South - largest y
                        end_y = max(y_list)
                    
                    # Explore the 2x2 area: (tx-1, end_y), (tx, end_y) and forward row
                    for jx in [tx - 1, tx]:
                        for jy in [end_y, end_y + direction[1]]:
                            if self.get_tile(jx, jy) != TileType.UNEXPLORED:
                                self.explored.add((jx, jy))
                            # Explore adjacent walls
                            for wx, wy in [(jx-1, jy), (jx+1, jy), (jx, jy-1), (jx, jy+1)]:
                                if self.get_tile(wx, wy) == TileType.WALL:
                                    self.explored.add((wx, wy))
            
            else:  # East/West passage
                # Group tiles by their y coordinate
                y_groups = {}
                for (tx, ty) in all_passage_tiles:
                    if ty not in y_groups:
                        y_groups[ty] = []
                    y_groups[ty].append(tx)
                
                # For each y group, find the min/max x (furthest in direction)
                for ty, x_list in y_groups.items():
                    if direction == (-1, 0):  # West - smallest x
                        end_x = min(x_list)
                    else:  # East - largest x
                        end_x = max(x_list)
                    
                    # Explore the 2x2 area: (end_x, ty-1), (end_x, ty) and forward row
                    for jx in [end_x, end_x + direction[0]]:
                        for jy in [ty - 1, ty]:
                            if self.get_tile(jx, jy) != TileType.UNEXPLORED:
                                self.explored.add((jx, jy))
                            # Explore adjacent walls
                            for wx, wy in [(jx-1, jy), (jx+1, jy), (jx, jy-1), (jx, jy+1)]:
                                if self.get_tile(wx, wy) == TileType.WALL:
                                    self.explored.add((wx, wy))
        
        # Also explore the entire 2x2 junction area and any walls placed at passage ends
        # This ensures T-junctions, stairs, and dead ends are fully visible (2x2)
        for direction in exits:
            if direction in [(0, -1), (0, 1)]:  # North/South
                # The 2x2 area spans x-1 to x, and y to y+dir
                for jx in [pos[0] - 1, pos[0]]:
                    for jy in [pos[1], pos[1] + direction[1]]:
                        junc_pos = (jx, jy)
                        if self.get_tile(jx, jy) != TileType.UNEXPLORED:
                            self.explored.add(junc_pos)
                            # Also explore adjacent walls
                            for wx, wy in [(jx-1, jy), (jx+1, jy), (jx, jy-1), (jx, jy+1)]:
                                if self.get_tile(wx, wy) == TileType.WALL:
                                    self.explored.add((wx, wy))
            else:  # East/West
                for jx in [pos[0], pos[0] + direction[0]]:
                    for jy in [pos[1] - 1, pos[1]]:
                        junc_pos = (jx, jy)
                        if self.get_tile(jx, jy) != TileType.UNEXPLORED:
                            self.explored.add(junc_pos)
                            for wx, wy in [(jx-1, jy), (jx+1, jy), (jx, jy-1), (jx, jy+1)]:
                                if self.get_tile(wx, wy) == TileType.WALL:
                                    self.explored.add((wx, wy))

        self._explore_from(x, y)
        return True
    
    def _is_room_wall(self, x: int, y: int) -> bool:
        """Check if a wall is part of a room boundary."""
        floor_neighbors = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_tile = self.get_tile(x + dx, y + dy)
            if neighbor_tile == TileType.FLOOR:
                floor_neighbors += 1
        return floor_neighbors > 0
    
    def _is_near_entrance(self, x: int, y: int, distance: int = 3) -> bool:
        """Check if position is near the stairs entrance."""
        return abs(x - self.hero_start[0]) + abs(y - self.hero_start[1]) <= distance
    
    def _is_junction_position(self, x: int, y: int) -> bool:
        """Check if position is a junction."""
        return (x, y) in self.pending_junctions
    
    def _is_valid_door_position(self, x: int, y: int, direction: Tuple[int, int]) -> bool:
        """Check if a door position is valid (not at corners/junctions)."""
        from .generator import _get_both_perpendicular
        
        perp_dirs = _get_both_perpendicular(direction)
        
        for perp in perp_dirs:
            passage_x = x + perp[0]
            passage_y = y + perp[1]
            if self._is_junction_position(passage_x, passage_y):
                return False
        
        floor_neighbors = 0
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            if self.get_tile(x + dx, y + dy) == TileType.FLOOR:
                floor_neighbors += 1
        if floor_neighbors > 2:
            return False
        
        for perp in perp_dirs:
            diag_x = x + perp[0] + direction[0]
            diag_y = y + perp[1] + direction[1]
            if self.get_tile(diag_x, diag_y) == TileType.FLOOR:
                return False
        
        perp_floor_count = 0
        for perp in perp_dirs:
            side_x = x + perp[0]
            side_y = y + perp[1]
            if self.get_tile(side_x, side_y) == TileType.FLOOR:
                perp_floor_count += 1
        if perp_floor_count >= 2:
            return False
        
        ahead_x = x + direction[0]
        ahead_y = y + direction[1]
        behind_x = x - direction[0]
        behind_y = y - direction[1]
        if self.get_tile(ahead_x, ahead_y) == TileType.FLOOR and \
           self.get_tile(behind_x, behind_y) == TileType.FLOOR:
            return False
        
        return True
    
    def open_door(self, x: int, y: int) -> bool:
        """Open a door and generate what's beyond."""
        from .generator import _generate_room, generate_passage_from
        
        if (x, y) not in self.doors:
            return False
        
        direction = self._get_door_direction(x, y)
        target_x = x + direction[0]
        target_y = y + direction[1]
        
        target_tile = self.get_tile(target_x, target_y)
        if target_tile in (TileType.FLOOR, TileType.STAIRS_DOWN, TileType.STAIRS_OUT):
            door_info = self.doors[(x, y)]
            door_info["is_open"] = True
            self.grid[(x, y)] = TileType.DOOR_OPEN
            return True
        
        door_info = self.doors[(x, y)]
        door_info["is_open"] = True
        self.grid[(x, y)] = TileType.DOOR_OPEN
        self.explored.add((x, y))
        
        gen_x = x + direction[0]
        gen_y = y + direction[1]
        
        from_room = door_info.get("from_room", True)
        
        
        if from_room:
            roll = random.randint(1, 12)
            if roll <= 6:
                generate_passage_from(self, x, y, direction)
                self._explore_from(x, y)
            else:
                _generate_room(self, gen_x, gen_y, direction, from_passage=False)
        else:
            _generate_room(self, gen_x, gen_y, direction, from_passage=False)
        
        return True
    
    def _get_door_direction(self, x: int, y: int) -> Tuple[int, int]:
        """Determine which way the door opens — toward unexplored space."""
        for direction in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + direction[0], y + direction[1]
            tile = self.get_tile(nx, ny)
            if tile == TileType.UNEXPLORED:
                return direction
        for direction in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + direction[0], y + direction[1]
            tile = self.get_tile(nx, ny)
            if tile not in (TileType.FLOOR, TileType.STAIRS_DOWN,
                            TileType.STAIRS_OUT, TileType.DOOR_OPEN):
                return direction
        return (1, 0)
    
    def _has_los(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Check if there's clear line of sight between two points."""
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
        pending = {}
        for pos, junction_data in self.pending_junctions.items():
            key = f"{pos[0]},{pos[1]}"
            if isinstance(junction_data, tuple) and len(junction_data) == 3:
                # New format: (source_dir, row, exits)
                direction, row, exits = junction_data
                pending[key] = {
                    "direction": f"{direction[0]},{direction[1]}",
                    "row": row,
                    "exits": [f"{e[0]},{e[1]}" for e in exits]
                }
            elif isinstance(junction_data, list):
                # Old format: [exit1, exit2, ...]
                exits = junction_data
                pending[key] = {
                    "direction": "0,0",
                    "row": 1,
                    "exits": [f"{e[0]},{e[1]}" for e in exits]
                }
        
        return {
            "size": self.size,
            "level": self.level,
            "grid": {f"{x},{y}": t.name for (x, y), t in self.grid.items()},
            "explored": [f"{x},{y}" for x, y in self.explored],
            "doors": {f"{x},{y}": v for (x, y), v in self.doors.items()},
            "monsters": {f"{x},{y}": v for (x, y), v in self.monsters.items()},
            "wandering_monsters": [f"{x},{y}" for x, y in self.wandering_monsters],
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
        
        dungeon.wandering_monsters = set()
        for pos_str in data.get("wandering_monsters", []):
            x, y = map(int, pos_str.split(","))
            dungeon.wandering_monsters.add((x, y))
        
        dungeon.treasure = {}
        for key, val in data.get("treasure", {}).items():
            x, y = map(int, key.split(","))
            dungeon.treasure[(x, y)] = val
        
        dungeon.pending_junctions = {}
        for key, junction_data in data.get("pending_junctions", {}).items():
            x, y = map(int, key.split(","))
            if isinstance(junction_data, dict):
                # New format: {"direction": "dx,dy", "row": n, "exits": [...]}
                dir_str = junction_data["direction"]
                direction = tuple(map(int, dir_str.split(",")))
                row = junction_data["row"]
                exits = [tuple(map(int, e.split(","))) for e in junction_data["exits"]]
                dungeon.pending_junctions[(x, y)] = (direction, row, exits)
            else:
                # Old format: list of exit directions (for backward compatibility)
                dungeon.pending_junctions[(x, y)] = ((0, 0), 1, [tuple(map(int, d.split(","))) for d in junction_data])
        
        dungeon.hero_start = tuple(data.get("hero_start", (0, 0)))
        
        return dungeon

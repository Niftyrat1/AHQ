"""
Dungeon view using tkinter with canvas for grid display.
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import List, Optional, Callable, Tuple
from hero import Hero
from monster import Monster
from dungeon import Dungeon, TileType


TILE_SIZE = 24


class DungeonViewTk:
    """Dungeon exploration view using tkinter canvas."""
    
    def __init__(self, root: tk.Tk, on_hero_move=None, on_hero_attack=None,
                 on_end_phase=None, on_exit_dungeon=None, on_stairs_down=None, on_get_hero_acted=None, on_get_hero_status=None, on_open_door=None):
        self.root = root
        self.on_hero_move = on_hero_move
        self.on_hero_attack = on_hero_attack
        self.on_end_phase = on_end_phase
        self.on_exit_dungeon = on_exit_dungeon
        self.on_stairs_down = on_stairs_down
        self.on_get_hero_acted = on_get_hero_acted
        self.on_get_hero_status = on_get_hero_status
        self.on_open_door = on_open_door
        self.on_get_monsters = None
        self.on_open_door = None
        
        self.dungeon: Optional[Dungeon] = None
        self.heroes: List[Hero] = []
        self.monsters: List[Monster] = []
        self.selected_hero: Optional[Hero] = None
        
        self.combat_mode = False
        self.current_phase = "EXPLORATION"
        self.hero_phase = True
        
        self.camera_x = 0
        self.camera_y = 0
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI layout."""
        self.root.title("Advanced HeroQuest - Dungeon")
        
        # Main frames
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.main_frame = tk.Frame(self.root, highlightthickness=0)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top info bar
        self.info_label = tk.Label(self.top_frame, text="Dungeon Level 1 | Exploration | Hero Phase",
                                   font=("Arial", 12, "bold"), bg="#333", fg="#ddd")
        self.info_label.pack(fill=tk.X)
        
        # Left sidebar - Party
        self.left_frame = tk.Frame(self.main_frame, width=200, bg="#2a2a35", highlightthickness=0)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(self.left_frame, text="Party", font=("Arial", 12, "bold"), bg="#2a2a35", fg="#ddd").pack(anchor=tk.W)
        
        self.party_text = tk.Text(self.left_frame, width=25, height=20, font=("Courier", 10),
                                  bg="#222", fg="#ddd", insertwidth=0, takefocus=0)
        self.party_text.pack(fill=tk.Y, expand=False)
        
        # End Phase button
        self.end_phase_btn = tk.Button(self.left_frame, text="End Hero Phase",
                                      command=self._on_end_phase, bg="#44a", fg="white")
        self.end_phase_btn.pack(fill=tk.X, pady=5)
        
        # Return to Tavern button
        self.return_btn = tk.Button(self.left_frame, text="Return to Tavern",
                                   command=self._on_return_to_tavern, bg="#666", fg="white")
        self.return_btn.pack(fill=tk.X, pady=5)
        
        # Center - Canvas for dungeon
        self.canvas_frame = tk.Frame(self.main_frame, bg="black", highlightthickness=0)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#111", highlightthickness=0)
        # print(f"[DEBUG] Canvas created, highlightthickness=0")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        # Right sidebar - Combat Log
        self.right_frame = tk.Frame(self.main_frame, width=250, bg="#2a2a35", highlightthickness=0)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(self.right_frame, text="Combat Log", font=("Arial", 12, "bold"), bg="#2a2a35", fg="#ddd").pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(self.right_frame, width=35, height=20,
                                                  font=("Courier", 9),
                                                  bg="#1a1a1a", fg="#ccc", insertwidth=0, takefocus=0)
        self.log_text.pack(fill=tk.Y, expand=False)
        
        # Message display (initially hidden)
        self.message_label = tk.Label(self.main_frame, text="", font=("Arial", 11),
                                     fg="#f55", bg="#111")
    
    def setup_dungeon(self, dungeon: Dungeon, heroes: List[Hero]):
        """Initialize dungeon view."""
        self.dungeon = dungeon
        self.heroes = heroes
        self.monsters = []
        self.selected_hero = heroes[0] if heroes else None
        
        # Initial exploration from hero starting position only
        if self.selected_hero:
            self.dungeon._explore_from(self.selected_hero.x, self.selected_hero.y)
        
        # Clear log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "The expedition enters the dungeon...\n")
        self.log_text.config(state=tk.DISABLED)
        
        self.root.update_idletasks()
        self._center_camera()
        self._update_display()
        # Schedule a second render after window is fully laid out
        self.root.after(100, self._initial_render)
    
    def _initial_render(self):
        # print(f"[DEBUG] Canvas winfo: x={self.canvas.winfo_x()}, y={self.canvas.winfo_y()}, w={self.canvas.winfo_width()}, h={self.canvas.winfo_height()}")
        # print(f"[DEBUG] party_text winfo: x={self.party_text.winfo_x()}, y={self.party_text.winfo_y()}, w={self.party_text.winfo_width()}, h={self.party_text.winfo_height()}")
        self._center_camera()
        self._update_display()

    def _center_camera(self):
        """Center camera on party."""
        if not self.heroes:
            return
        
        avg_x = sum(h.x for h in self.heroes if not h.is_dead) / max(1, len(self.heroes))
        avg_y = sum(h.y for h in self.heroes if not h.is_dead) / max(1, len(self.heroes))
        
        canvas_width = max(400, self.canvas.winfo_width())
        canvas_height = max(300, self.canvas.winfo_height())
        
        # Camera in grid coordinates (not pixels)
        calc_x = int(avg_x - canvas_width // 2 // TILE_SIZE)
        calc_y = int(avg_y - canvas_height // 2 // TILE_SIZE + 2)
        # print(f"[CAMERA] avg=({avg_x},{avg_y}), canvas={canvas_width}x{canvas_height}, calculated=({calc_x},{calc_y}), current=({self.camera_x},{self.camera_y})")
        self.camera_x = calc_x
        self.camera_y = calc_y
    
    def _grid_to_canvas(self, x: int, y: int) -> Tuple[int, int]:
        """Convert grid coordinates to canvas coordinates."""
        return ((x - self.camera_x) * TILE_SIZE, (y - self.camera_y) * TILE_SIZE)
    
    def _canvas_to_grid(self, cx: int, cy: int) -> Optional[Tuple[int, int]]:
        """Convert canvas coordinates to grid coordinates."""
        x = cx // TILE_SIZE + self.camera_x
        y = cy // TILE_SIZE + self.camera_y
        return (int(x), int(y))
    
    def _on_canvas_click(self, event):
        """Handle clicks on the dungeon canvas."""
        grid_pos = self._canvas_to_grid(event.x, event.y)
        if not grid_pos:
            return
        
        x, y = grid_pos
        
        # Check if clicked on a hero
        for hero in self.heroes:
            if hero.x == x and hero.y == y and not hero.is_dead:
                self.selected_hero = hero
                self._update_display()
                # Only show movement range if hero hasn't acted yet
                if self.on_get_hero_acted and not self.on_get_hero_acted(hero.id):
                    self._show_movement_range(hero)
                return
        
        if not self.selected_hero or self.selected_hero.is_dead:
            return
        
        if not self.hero_phase:
            self._show_message("GM Phase - wait for monsters")
            return
        
        # Check for monster at position
        monster = self._get_monster_at(x, y)
        if monster and not monster.is_dead:
            if self.dungeon.is_adjacent(self.selected_hero.x, self.selected_hero.y, x, y):
                if self.on_hero_attack:
                    self.on_hero_attack(self.selected_hero, monster)
                    self.add_log_message(f"{self.selected_hero.name} attacks {monster.name}")
            else:
                self._show_message("Not adjacent!")
            return
        
        # Check for door
        tile = self.dungeon.get_tile(x, y)
        if tile == TileType.DOOR_CLOSED:
            # Check if hero is adjacent to the door
            if not self.dungeon.is_adjacent(self.selected_hero.x, self.selected_hero.y, x, y):
                self._show_message("Not adjacent to door!")
                return
            if self.on_open_door and self.on_open_door(x, y):
                self.add_log_message(f"{self.selected_hero.name} opens a door")
                self._sync_from_game()
                self._update_display()
            return
        
        # Check for stairs down
        if tile == TileType.STAIRS_DOWN:
            from tkinter import messagebox
            if messagebox.askyesno("Stairs Down", f"Go down the stairs to the next level?"):
                if self.on_stairs_down:
                    self.on_stairs_down()
            return
        
        # Check for stairs out
        if tile == TileType.STAIRS_OUT:
            from tkinter import messagebox
            if messagebox.askyesno("Exit Dungeon", f"Exit the dungeon?"):
                if self.on_exit_dungeon:
                    self.on_exit_dungeon()
            return
        
        # Try to move
        dist = self.dungeon.get_distance(self.selected_hero.x, self.selected_hero.y, x, y)
        tile = self.dungeon.get_tile(x, y)
        walkable = self.dungeon.is_walkable(x, y)
        
        # Get remaining movement
        remaining_movement = self.selected_hero.speed
        if self.on_get_hero_status:
            remaining_movement, _ = self.on_get_hero_status(self.selected_hero.id)
        
        # print(f"[MOVE] Trying to move to ({x},{y}), tile: {tile.name}, walkable: {walkable}, dist: {dist}, remaining: {remaining_movement}")
        
        # Check path is clear - try both X-first and Y-first paths
        path_clear = True
        if dist > 0 and dist <= remaining_movement:
            hero_x, hero_y = self.selected_hero.x, self.selected_hero.y
            target_x, target_y = x, y
            
            # Path 1: X first, then Y
            curr_x, curr_y = hero_x, hero_y
            path1_clear = True
            while curr_x != target_x:
                curr_x += 1 if target_x > curr_x else -1
                if not self.dungeon.is_walkable(curr_x, curr_y):
                    path1_clear = False
                    break
            if path1_clear:
                while curr_y != target_y:
                    curr_y += 1 if target_y > curr_y else -1
                    if not self.dungeon.is_walkable(curr_x, curr_y):
                        path1_clear = False
                        break
            
            # Path 2: Y first, then X
            curr_x, curr_y = hero_x, hero_y
            path2_clear = True
            while curr_y != target_y:
                curr_y += 1 if target_y > curr_y else -1
                if not self.dungeon.is_walkable(curr_x, curr_y):
                    path2_clear = False
                    break
            if path2_clear:
                while curr_x != target_x:
                    curr_x += 1 if target_x > curr_x else -1
                    if not self.dungeon.is_walkable(curr_x, curr_y):
                        path2_clear = False
                        break
            
            path_clear = path1_clear or path2_clear
        
        if dist <= remaining_movement and walkable and path_clear:
            # Check not occupied
            occupied = False
            for h in self.heroes:
                if h != self.selected_hero and not h.is_dead and h.x == x and h.y == y:
                    occupied = True
                    break
            for m in self.monsters:
                if not m.is_dead and m.x == x and m.y == y:
                    occupied = True
                    break
            
            if not occupied:
                moved = False
                if self.on_hero_move:
                    moved = self.on_hero_move(self.selected_hero, x, y)
                if moved:
                    self.selected_hero.x = x
                    self.selected_hero.y = y
                    self.dungeon._explore_from(x, y)
                    self._clear_movement_range()
                    self._update_display()
            else:
                self._show_message("Square occupied!")
        else:
            if dist > self.selected_hero.speed:
                self._show_message("Too far!")
    
    def _get_monster_at(self, x: int, y: int) -> Optional[Monster]:
        """Get monster at position."""
        for m in self.monsters:
            if m.x == x and m.y == y and not m.is_dead:
                return m
        return None
    
    def _on_end_phase(self):
        """End hero phase button."""
        if self.on_end_phase:
            self.on_end_phase()
    
    def _on_return_to_tavern(self):
        """Return to tavern button."""
        if self.on_exit_dungeon:
            self.on_exit_dungeon()
    
    def _show_message(self, text: str):
        """Show temporary message."""
        self.message_label.config(text=text)
        self.message_label.place(relx=0.5, rely=0.1, anchor=tk.CENTER)
        self.root.after(2000, lambda: self.message_label.place_forget())
    
    def _update_display(self):
        """Redraw the canvas."""
        self.canvas.delete("all")
        
        if not self.dungeon:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Calculate visible range (camera is in grid coordinates)
        start_x = self.camera_x - 1
        start_y = self.camera_y - 1
        end_x = start_x + canvas_width // TILE_SIZE + 2
        end_y = start_y + canvas_height // TILE_SIZE + 2
        
        # Draw tiles
        for x in range(start_x, end_x):
            for y in range(start_y, end_y):
                cx, cy = self._grid_to_canvas(x, y)
                
                if cx < -TILE_SIZE or cy < -TILE_SIZE or cx > canvas_width or cy > canvas_height:
                    continue
                
                tile = self.dungeon.get_tile(x, y)
                explored = self.dungeon.is_explored(x, y)
                
                if not explored:
                    # Fog of war
                    self.canvas.create_rectangle(cx, cy, cx+TILE_SIZE, cy+TILE_SIZE,
                                                fill="#0a0a0f", outline="")
                else:
                    # Tile colors
                    if tile == TileType.FLOOR:
                        color = "#4a4a55"
                        outline = "#3a3a45"
                    elif tile == TileType.WALL:
                        color = "#1a1a2a"    # Dark navy — clearly different from floor
                        outline = "#2a2a3a"
                    elif tile == TileType.PASSAGE_END:
                        color = "#4a3728"    # Dark brown - dead end cap (walkable but looks like wall)
                        outline = "#5a4738"
                    elif tile == TileType.DOOR_CLOSED:
                        color = "#8b5a2b"
                        outline = "#6b4a1b"
                    elif tile == TileType.DOOR_OPEN:
                        color = "#bb8a5b"  # Lighter shade of closed door brown
                        outline = "#9b6a3b"
                    elif tile == TileType.STAIRS_OUT:
                        color = "#c8b896"
                        outline = "#a89876"
                    elif tile == TileType.STAIRS_DOWN:
                        # Check if this is the starting stairs at (0,0)
                        if (x, y) == (0, 0):
                            color = "#32CD32"  # Green for starting stairs
                            outline = "#228B22"
                        else:
                            color = "#FFD700"  # Gold/yellow for stairs down
                            outline = "#B8860B"
                    else:
                        color = "#3a3a45"
                        outline = "#2a2a35"
                    
                    self.canvas.create_rectangle(cx, cy, cx+TILE_SIZE, cy+TILE_SIZE,
                                                fill=color, outline=outline)
                    
                    # Draw door symbol
                    if tile == TileType.DOOR_CLOSED:
                        self.canvas.create_line(cx+4, cy+TILE_SIZE//2, cx+TILE_SIZE-4, cy+TILE_SIZE//2,
                                               fill="#4a2a0b", width=2)
                    elif tile == TileType.STAIRS_OUT:
                        self.canvas.create_text(cx+TILE_SIZE//2, cy+TILE_SIZE//2,
                                               text="OUT", fill="#222", font=("Arial", 8))
                    elif tile == TileType.STAIRS_DOWN:
                        # Check if this is the starting stairs at (0,0)
                        if (x, y) == (0, 0):
                            self.canvas.create_text(cx+TILE_SIZE//2, cy+TILE_SIZE//2,
                                                   text="START", fill="#222", font=("Arial", 7))
                        else:
                            self.canvas.create_text(cx+TILE_SIZE//2, cy+TILE_SIZE//2,
                                                   text="DOWN", fill="#222", font=("Arial", 7))
        
        # Draw monsters
        for m in self.monsters:
            if not m.is_dead:
                cx, cy = self._grid_to_canvas(m.x, m.y)
                if -TILE_SIZE < cx < canvas_width and -TILE_SIZE < cy < canvas_height:
                    # Monster circle
                    self.canvas.create_oval(cx+4, cy+4, cx+TILE_SIZE-4, cy+TILE_SIZE-4,
                                           fill="#c44", outline="#822")
                    # Monster letter
                    self.canvas.create_text(cx+TILE_SIZE//2, cy+TILE_SIZE//2,
                                           text=m.name[0], fill="white", font=("Arial", 10, "bold"))
        
        # Draw heroes
        for h in self.heroes:
            if not h.is_dead:
                cx, cy = self._grid_to_canvas(h.x, h.y)
                if -TILE_SIZE < cx < canvas_width and -TILE_SIZE < cy < canvas_height:
                    # Highlight selected
                    if h == self.selected_hero:
                        self.canvas.create_rectangle(cx-2, cy-2, cx+TILE_SIZE+2, cy+TILE_SIZE+2,
                                                    outline="#ff0", width=2)
                    
                    # Hero color by class
                    color = "#68c" if h.class_type == "Warrior" else "#a6c"
                    if h.is_ko:
                        color = "#666"
                    
                    self.canvas.create_oval(cx+4, cy+4, cx+TILE_SIZE-4, cy+TILE_SIZE-4,
                                          fill=color, outline="#468" if h.class_type == "Warrior" else "#86a")
                    # Hero letter
                    self.canvas.create_text(cx+TILE_SIZE//2, cy+TILE_SIZE//2,
                                           text=h.name[0], fill="white", font=("Arial", 10, "bold"))
        
        # Update party panel
        self._update_party_panel()
    
    def _update_party_panel(self):
        """Update party status panel."""
        self.party_text.config(state=tk.NORMAL)
        self.party_text.delete(1.0, tk.END)
        
        for hero in self.heroes:
            if hero.is_dead:
                status = "DEAD"
                color_tag = "dead"
            elif hero.is_ko:
                status = "KO"
                color_tag = "ko"
            elif hero == self.selected_hero:
                status = "ACTIVE"
                color_tag = "active"
            else:
                status = "OK"
                color_tag = "ok"
            
            wound_color = "#f55" if hero.current_wounds <= hero.max_wounds // 2 else "#ddd"
            
            # Get hero status if callback available
            movement_remaining = hero.speed
            has_attacked = False
            if self.on_get_hero_status:
                movement_remaining, has_attacked = self.on_get_hero_status(hero.id)
            
            attack_status = " A" if has_attacked else ""
            
            line = f"{hero.name:12} {status:6}\n"
            line += f"  W:{hero.current_wounds:2}/{hero.max_wounds:2} F:{hero.current_fate} M:{movement_remaining}{attack_status}\n\n"
            
            self.party_text.insert(tk.END, line)
        
        self.party_text.config(state=tk.DISABLED)
    
    def update_state(self):
        """Update display from game state."""
        # Sync monsters from game state
        if self.on_get_monsters:
            self.monsters = self.on_get_monsters()
        self._center_camera()
        self._update_display()
        
        # Update info bar
        phase_text = f"Dungeon Level 1 | {self.current_phase} | {'Hero' if self.hero_phase else 'GM'} Phase"
        self.info_label.config(text=phase_text)
        
        # Update button
        if self.hero_phase:
            self.end_phase_btn.config(text="End Hero Phase", state=tk.NORMAL)
        else:
            self.end_phase_btn.config(text="GM Phase...", state=tk.DISABLED)
    
    def _show_movement_range(self, hero):
        """Highlight tiles the hero can move to."""
        # print(f"[DEBUG] _show_movement_range called for {hero.name} at ({hero.x},{hero.y})")
        self._clear_movement_range()
        self.movement_highlights = []
        
        # Get remaining movement from callback
        movement_remaining = hero.speed
        if self.on_get_hero_status:
            movement_remaining, _ = self.on_get_hero_status(hero.id)
        
        # Get hero color by class (same as rendering)
        base_color = "#68c" if hero.class_type == "Warrior" else "#a6c"
        # Lighten the color for the highlight
        highlight_color = self._lighten_color(base_color, 0.3)
        # print(f"[DEBUG] Hero class: {hero.class_type}, base_color: {base_color}, remaining_movement: {movement_remaining}")
        
        # Find all tiles within remaining movement range
        # print(f"[DEBUG] Checking tiles within remaining {movement_remaining}, canvas size: {self.canvas.winfo_width()}x{self.canvas.winfo_height()}")
        count_checked = 0
        count_walkable = 0
        count_onscreen = 0
        count_drawn = 0
        for dx in range(-movement_remaining, movement_remaining + 1):
            for dy in range(-movement_remaining, movement_remaining + 1):
                if abs(dx) + abs(dy) > movement_remaining or (dx == 0 and dy == 0):
                    continue
                
                tx, ty = hero.x + dx, hero.y + dy
                count_checked += 1
                
                # Check if walkable, visible (explored), and not occupied
                if not self.dungeon.is_walkable(tx, ty):
                    continue
                if (tx, ty) not in self.dungeon.explored:
                    continue
                # Check path is clear - natural movement (any x/y combination)
                path_clear = True
                dist = abs(dx) + abs(dy)
                if dist > 0:
                    # Try path 1: X first, then Y
                    curr_x, curr_y = hero.x, hero.y
                    path1_tiles = []
                    while curr_x != tx:
                        curr_x += 1 if tx > curr_x else -1
                        path1_tiles.append((curr_x, curr_y))
                    while curr_y != ty:
                        curr_y += 1 if ty > curr_y else -1
                        path1_tiles.append((curr_x, curr_y))
                    
                    path1_clear = True
                    for path_tile in path1_tiles[:-1] if path1_tiles else []:
                        if not self.dungeon.is_walkable(path_tile[0], path_tile[1]):
                            path1_clear = False
                            break
                    
                    # Try path 2: Y first, then X
                    curr_x, curr_y = hero.x, hero.y
                    path2_tiles = []
                    while curr_y != ty:
                        curr_y += 1 if ty > curr_y else -1
                        path2_tiles.append((curr_x, curr_y))
                    while curr_x != tx:
                        curr_x += 1 if tx > curr_x else -1
                        path2_tiles.append((curr_x, curr_y))
                    
                    path2_clear = True
                    for path_tile in path2_tiles[:-1] if path2_tiles else []:
                        if not self.dungeon.is_walkable(path_tile[0], path_tile[1]):
                            path2_clear = False
                            break
                    
                    path_clear = path1_clear or path2_clear
                
                if not path_clear:
                    continue
                
                count_walkable += 1
                
                occupied = False
                for h in self.heroes:
                    if not h.is_dead and h.x == tx and h.y == ty:
                        occupied = True
                        break
                for m in self.monsters:
                    if not m.is_dead and m.x == tx and m.y == ty:
                        occupied = True
                        break
                
                if occupied:
                    continue
                
                # Draw highlight circle
                px = (tx - self.camera_x) * TILE_SIZE + TILE_SIZE // 2
                py = (ty - self.camera_y) * TILE_SIZE + TILE_SIZE // 2
                
                # Only draw if on screen (skip check if canvas not ready)
                canvas_w = self.canvas.winfo_width()
                canvas_h = self.canvas.winfo_height()
                # If canvas size is 1 (not ready), assume on screen
                on_screen = (canvas_w <= 1) or (0 <= px < canvas_w and 0 <= py < canvas_h)
                # Log first few walkable tiles
                # if count_walkable <= 5 and not occupied:
                #     print(f"[DEBUG] Walkable tile ({tx},{ty}) -> pixel ({px},{py}), camera ({self.camera_x},{self.camera_y}), canvas {canvas_w}x{canvas_h}, onscreen={on_screen}")
                if on_screen:
                    count_onscreen += 1
                    # Draw a larger filled circle with border
                    circle = self.canvas.create_oval(
                        px - 10, py - 10, px + 10, py + 10,
                        fill=highlight_color, outline=base_color, width=3,
                        tags="movement_range"
                    )
                    self.canvas.tag_raise(circle)  # Ensure circle is on top
                    self.movement_highlights.append(circle)
                    count_drawn += 1
        # print(f"[DEBUG] Tiles: checked={count_checked}, walkable={count_walkable}, onscreen={count_onscreen}, drawn={count_drawn}")
    
    def _clear_movement_range(self):
        """Clear movement range highlights."""
        if hasattr(self, 'movement_highlights'):
            for item in self.movement_highlights:
                self.canvas.delete(item)
        self.movement_highlights = []
    
    def _lighten_color(self, color, factor):
        """Lighten a hex color by a factor."""
        # Remove # if present
        color = color.lstrip('#')
        # Convert 3-char hex to 6-char (e.g., #68c -> #6688cc)
        if len(color) == 3:
            color = color[0] + color[0] + color[1] + color[1] + color[2] + color[2]
        # Convert to RGB
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        # Lighten
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def add_log_message(self, message: str):
        """Add message to combat log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def show(self):
        """Show the dungeon view."""
        # Clear and repack
        for widget in self.root.winfo_children():
            widget.destroy()
        self._setup_ui()
    
    def refresh(self):
        """Force refresh of display."""
        self._update_display()

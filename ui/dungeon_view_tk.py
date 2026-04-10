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
                 on_end_phase=None, on_exit_dungeon=None):
        self.root = root
        self.on_hero_move = on_hero_move
        self.on_hero_attack = on_hero_attack
        self.on_end_phase = on_end_phase
        self.on_exit_dungeon = on_exit_dungeon
        
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
        
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top info bar
        self.info_label = tk.Label(self.top_frame, text="Dungeon Level 1 | Exploration | Hero Phase",
                                   font=("Arial", 12, "bold"), bg="#333", fg="#ddd")
        self.info_label.pack(fill=tk.X)
        
        # Left sidebar - Party
        self.left_frame = tk.Frame(self.main_frame, width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(self.left_frame, text="Party", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        self.party_text = tk.Text(self.left_frame, width=25, height=20, font=("Courier", 10),
                                  bg="#222", fg="#ddd")
        self.party_text.pack(fill=tk.BOTH, expand=True)
        self.party_text.config(state=tk.DISABLED)
        
        # End Phase button
        self.end_phase_btn = tk.Button(self.left_frame, text="End Hero Phase",
                                      command=self._on_end_phase, bg="#44a", fg="white")
        self.end_phase_btn.pack(fill=tk.X, pady=5)
        
        # Return to Tavern button
        self.return_btn = tk.Button(self.left_frame, text="Return to Tavern",
                                   command=self._on_return_to_tavern, bg="#666", fg="white")
        self.return_btn.pack(fill=tk.X, pady=5)
        
        # Center - Canvas for dungeon
        self.canvas_frame = tk.Frame(self.main_frame, bg="black")
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        
        # Right sidebar - Combat Log
        self.right_frame = tk.Frame(self.main_frame, width=250)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(self.right_frame, text="Combat Log", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(self.right_frame, width=35, height=20,
                                                  font=("Courier", 9),
                                                  bg="#1a1a1a", fg="#ccc")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # Message display
        self.message_label = tk.Label(self.main_frame, text="", font=("Arial", 11),
                                     fg="#f55", bg="#111")
        self.message_label.place(relx=0.5, rely=0.1, anchor=tk.CENTER)
    
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
        """Second render pass once canvas has real dimensions."""
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
        
        self.camera_x = int(avg_x * TILE_SIZE - canvas_width // 2)
        # Shift down by 2 tiles to show North wall above hero
        self.camera_y = int(avg_y * TILE_SIZE - canvas_height // 2 + TILE_SIZE * 2)
    
    def _grid_to_canvas(self, x: int, y: int) -> Tuple[int, int]:
        """Convert grid coordinates to canvas coordinates."""
        return (x * TILE_SIZE - self.camera_x, y * TILE_SIZE - self.camera_y)
    
    def _canvas_to_grid(self, cx: int, cy: int) -> Optional[Tuple[int, int]]:
        """Convert canvas coordinates to grid coordinates."""
        x = (cx + self.camera_x) // TILE_SIZE
        y = (cy + self.camera_y) // TILE_SIZE
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
            if self.dungeon.open_door(x, y):
                self.add_log_message(f"{self.selected_hero.name} opens a door")
                self._update_display()
            return
        
        # Check for stairs out
        if tile == TileType.STAIRS_OUT:
            if self.on_exit_dungeon:
                self.on_exit_dungeon()
            return
        
        # Try to move
        dist = self.dungeon.get_distance(self.selected_hero.x, self.selected_hero.y, x, y)
        if dist <= self.selected_hero.speed and self.dungeon.is_walkable(x, y):
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
        self.root.after(2000, lambda: self.message_label.config(text=""))
    
    def _update_display(self):
        """Redraw the canvas."""
        self.canvas.delete("all")
        
        if not self.dungeon:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Calculate visible range
        # Remove the max(0,...) clamps — dungeon coords can be negative
        start_x = self.camera_x // TILE_SIZE - 1
        start_y = self.camera_y // TILE_SIZE - 1
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
                    elif tile == TileType.DOOR_CLOSED:
                        color = "#8b5a2b"
                        outline = "#6b4a1b"
                    elif tile == TileType.DOOR_OPEN:
                        color = "#4a4a55"
                        outline = "#8b5a2b"
                    elif tile == TileType.STAIRS_DOWN:
                        color = "#4a4a55"
                        outline = "#aaa"
                    elif tile == TileType.STAIRS_OUT:
                        color = "#c8b896"
                        outline = "#a89876"
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
            
            line = f"{hero.name:12} {status:6}\n"
            line += f"  W:{hero.current_wounds:2}/{hero.max_wounds:2} F:{hero.current_fate} \n\n"
            
            self.party_text.insert(tk.END, line)
        
        self.party_text.config(state=tk.DISABLED)
    
    def update_state(self):
        """Update display from game state."""
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

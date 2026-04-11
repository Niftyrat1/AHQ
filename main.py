"""
Entry point for Advanced HeroQuest digital adaptation.
Uses tkinter for UI (built into Python).
"""

import sys
import tkinter as tk
from tkinter import messagebox

from game import GameState
from ui.tavern_tk import TavernScreenTk
from ui.dungeon_view_tk import DungeonViewTk


# Window settings
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60


def main():
    """Main entry point using tkinter."""
    # Initialize game state
    game = GameState()
    
    # Check for save game
    has_save = game.has_save_game()
    
    # Ask to continue if save exists
    if has_save:
        root = tk.Tk()
        root.withdraw()
        if messagebox.askyesno("Continue Game", "Save game found. Continue where you left off?"):
            if game.load_game():
                pass  # Continue with loaded game
            else:
                game.mode = "TAVERN"
        root.destroy()
    
    # Create main window
    root = tk.Tk()
    root.title("Advanced HeroQuest")
    root.geometry("1100x700")
    root.configure(bg="#222")
    
    # Create screens
    tavern = TavernScreenTk(root)
    dungeon_view = None
    
    # Current screen tracking
    current_screen = "tavern"
    
    # Set up callbacks
    def on_begin_quest(party):
        game.start_quest(party)
        switch_to_dungeon()
    
    def on_hero_move(hero, x, y):
        if game.move_hero(hero, x, y):
            dungeon_view.add_log_message(f"{hero.name} moves to ({x}, {y})")
            return True
        return False
    
    def on_hero_attack(hero, monster):
        if game.hero_attack(hero, monster):
            dungeon_view.monsters = game.monsters
            dungeon_view.add_log_message(f"{hero.name} attacks {monster.name}")
            if monster.is_dead:
                dungeon_view.add_log_message(f"{monster.name} is killed! (+{monster.pv} PV)")
    
    def on_end_phase():
        dungeon_view.add_log_message("--- Ending Hero Phase ---")
        game.end_hero_phase()
        dungeon_view.hero_phase = game.hero_phase_active
        dungeon_view.current_phase = game.current_phase
        dungeon_view.monsters = game.monsters
        dungeon_view.update_state()
        
        # Add GM phase results to log
        for msg in game.combat_log[-5:]:
            dungeon_view.add_log_message(msg)
    
    def on_exit_dungeon():
        game._exit_dungeon()
        switch_to_tavern()
    
    def on_stairs_down():
        # Generate new dungeon level
        from dungeon import Dungeon
        game.dungeon_debug_log.clear()
        game.dungeon = Dungeon(level=game.dungeon.level + 1, debug_log=game.dungeon_debug_log)
        game.monsters = []
        # Reset hero positions to stairs
        for hero in game.party:
            hero.x, hero.y = game.dungeon.hero_start
        dungeon_view.setup_dungeon(game.dungeon, game.party)
        dungeon_view.update_state()
        dungeon_view.add_log_message(f"Descended to dungeon level {game.dungeon.level}!")
    
    def on_get_hero_acted(hero_id):
        # Hero has "acted" if no movement remaining AND has already attacked
        remaining = game.hero_movement_remaining.get(hero_id, 0)
        has_attacked = hero_id in game.hero_has_attacked
        return remaining <= 0 and has_attacked
    
    def on_get_hero_status(hero_id):
        # Return (movement_remaining, has_attacked)
        remaining = game.hero_movement_remaining.get(hero_id, 0)
        has_attacked = hero_id in game.hero_has_attacked
        return (remaining, has_attacked)
    
    tavern.on_begin_quest = on_begin_quest
    
    def switch_to_dungeon():
        nonlocal current_screen, dungeon_view
        current_screen = "dungeon"
        for widget in root.winfo_children():
            widget.destroy()
        dungeon_view = DungeonViewTk(root)
        dungeon_view.on_hero_move = on_hero_move
        dungeon_view.on_hero_attack = on_hero_attack
        dungeon_view.on_end_phase = on_end_phase
        dungeon_view.on_exit_dungeon = on_exit_dungeon
        dungeon_view.on_stairs_down = on_stairs_down
        dungeon_view.on_get_hero_acted = on_get_hero_acted
        dungeon_view.setup_dungeon(game.dungeon, game.party)
        dungeon_view.update_state()
    
    def switch_to_tavern():
        nonlocal current_screen, tavern
        current_screen = "tavern"
        # Reset dungeon view
        for widget in root.winfo_children():
            widget.destroy()
        # Recreate tavern
        tavern = TavernScreenTk(root, on_begin_quest)
        tavern.refresh_hero_list()
        tavern.on_begin_quest = on_begin_quest
    
    def on_closing():
        """Handle window close."""
        if game.mode in ("DUNGEON", "COMBAT"):
            game.save_game()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # If game loaded into dungeon mode, switch to it
    if game.mode in ("DUNGEON", "COMBAT"):
        switch_to_dungeon()
    
    # Run
    root.mainloop()


if __name__ == "__main__":
    main()

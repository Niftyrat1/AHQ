"""
Core game loop and state machine for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import List, Optional

from hero import Hero, HeroManager
from monster import Monster, MonsterLibrary, roll_lair_encounter, roll_quest_room_encounter
from dungeon import Dungeon
from combat import (
    resolve_melee_attack, resolve_monster_attack,
    do_surprise_roll, find_target_hero
)
from gm import run_gm_phase, check_dungeon_counter


class GameState:
    """Manages the overall game state."""
    
    SAVE_FILE = Path(__file__).parent / "data" / "save_game.json"
    
    def __init__(self):
        self.mode = "TAVERN"  # TAVERN, DUNGEON, COMBAT, GAME_OVER
        self.dungeon: Optional[Dungeon] = None
        self.party: List[Hero] = []
        self.monsters: List[Monster] = []
        self.monster_library = MonsterLibrary()
        self.hero_manager = HeroManager()
        
        self.current_phase = "EXPLORATION"  # EXPLORATION or COMBAT
        self.hero_phase_active = True
        self.turn_count = 0
        
        self.heroes_acted_this_phase: set = set()  # Track which heroes have moved/attacked
        
        self.combat_log: List[str] = []
        self.experience_gained = 0
        self.gold_found = 0
        self.dungeon_debug_log: List[str] = []  # For tracking dungeon generation
    
    def start_quest(self, party: List[Hero]):
        """Begin a new dungeon expedition."""
        self.party = party
        self.monsters = []
        self.dungeon_debug_log = []
        self.dungeon = Dungeon(debug_log=self.dungeon_debug_log)
        self.mode = "DUNGEON"
        self.current_phase = "EXPLORATION"
        self.hero_phase_active = True
        self.turn_count = 0
        self.combat_log = ["The expedition enters the dungeon..."]
        self.experience_gained = 0
        self.gold_found = 0
        
        # Place heroes
        start_x, start_y = self.dungeon.hero_start
        for i, hero in enumerate(self.party):
            hero.x = start_x + (i % 2)
            hero.y = start_y + (i // 2)
            hero.is_ko = False
            hero.current_wounds = hero.max_wounds
        
        self.save_game()
    
    def move_hero(self, hero: Hero, x: int, y: int):
        """Move a hero to a new position."""
        if hero.is_dead or hero.is_ko:
            self.combat_log.append(f"{hero.name} is dead/KO!")
            return False
        
        # Check if hero already acted this phase
        if hero.id in self.heroes_acted_this_phase:
            self.combat_log.append(f"{hero.name} has already acted this phase!")
            return False
        
        # Check distance
        dist = abs(hero.x - x) + abs(hero.y - y)
        if dist > hero.speed:
            self.combat_log.append(f"Too far! Distance {dist} > speed {hero.speed}")
            return False
        
        # Check if walkable
        tile = self.dungeon.get_tile(x, y)
        if not self.dungeon.is_walkable(x, y):
            self.combat_log.append(f"Cannot move to ({x},{y}): tile is {tile.name}")
            return False
        
        # Check for monsters blocking
        for m in self.monsters:
            if not m.is_dead and m.x == x and m.y == y:
                return False
        
        # Check for other heroes
        for h in self.party:
            if h != hero and not h.is_dead and h.x == x and h.y == y:
                return False
        
        # Move
        hero.x, hero.y = x, y
        
        # Mark as having acted this phase
        self.heroes_acted_this_phase.add(hero.id)
        
        # Check for junctions (this will explore new passages if it's a pending junction)
        self.dungeon.check_and_generate_junction(x, y)
        
        # Check for encounter triggers
        self._check_triggers(x, y)
        
        return True
    
    def _check_triggers(self, x: int, y: int):
        """Check for triggered events at position."""
        tile = self.dungeon.get_tile(x, y)
        
        if tile.value == 10:  # STAIRS_OUT
            self._exit_dungeon()
    
    def hero_attack(self, hero: Hero, monster: Monster) -> bool:
        """Hero attacks a monster."""
        if hero.is_dead or hero.is_ko or monster.is_dead:
            return False
        
        # Check if hero already acted this phase
        if hero.id in self.heroes_acted_this_phase:
            self.combat_log.append(f"{hero.name} has already acted this phase!")
            return False
        
        # Must be adjacent
        if not self.dungeon.is_adjacent(hero.x, hero.y, monster.x, monster.y):
            return False
        
        # Resolve attack
        hit, damage, result = resolve_melee_attack(hero, monster, self.combat_log)
        
        # Mark as having acted this phase
        self.heroes_acted_this_phase.add(hero.id)
        
        if monster.is_dead:
            self.experience_gained += monster.pv
            self.monsters = [m for m in self.monsters if not m.is_dead]
            
            # Check if combat ends
            if not any(not m.is_dead for m in self.monsters):
                self._end_combat()
        
        self.save_game()
        return True
    
    def end_hero_phase(self):
        """End hero phase and start GM phase."""
        self.hero_phase_active = False
        
        if self.current_phase == "EXPLORATION":
            self._run_exploration_gm_phase()
        else:  # COMBAT
            self._run_combat_gm_phase()
        
        self.hero_phase_active = True
        self.heroes_acted_this_phase.clear()  # Reset for next hero phase
        self.turn_count += 1
        
        # Check for dead party
        if all(h.is_dead for h in self.party):
            self._game_over()
        
        self.save_game()
    
    def _run_exploration_gm_phase(self):
        """Run GM phase during exploration."""
        # Check for dungeon counter
        counter = check_dungeon_counter()
        if counter:
            self.combat_log.append(f"Dungeon Counter: {counter}")
        
        self.combat_log.append("GM Phase complete.")
    
    def _run_combat_gm_phase(self):
        """Run GM phase during combat."""
        self.monsters, self.combat_log = run_gm_phase(
            self.monsters, self.party, self.dungeon, self.combat_log
        )
        
        # Remove dead monsters from list
        self.monsters = [m for m in self.monsters if not m.is_dead]
        
        # Check if combat ends
        if not self.monsters:
            self._end_combat()
        
        # Check for dead heroes
        for hero in self.party:
            if hero.is_ko and not hero.is_dead:
                hero.current_wounds = 1
                hero.is_ko = False
    
    def _start_combat(self, monster_ids: List[str]):
        """Start combat with spawned monsters."""
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        
        # Reset hero actions for new combat round
        self.heroes_acted_this_phase.clear()
        
        # Create monsters
        spawn_positions = self._get_spawn_positions(len(monster_ids))
        
        for i, monster_id in enumerate(monster_ids):
            monster = self.monster_library.create_monster(monster_id)
            if monster and i < len(spawn_positions):
                monster.x, monster.y = spawn_positions[i]
                self.monsters.append(monster)
        
        # Surprise roll
        has_elf = any(h.race == "Elf" for h in self.party)
        has_sentry = any(m.is_sentry for m in self.monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")
        
        if winner == "gm":
            self.combat_log.append("GM wins surprise! Monsters attack first.")
            self.hero_phase_active = False
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        else:
            self.combat_log.append("Heroes win surprise!")
        
        self.save_game()
    
    def _get_spawn_positions(self, count: int) -> List[tuple]:
        """Get positions to spawn monsters."""
        positions = []
        # Spawn at edges of explored area, away from heroes
        explored = list(self.dungeon.explored)
        
        for _ in range(count):
            # Find a position that's walkable and not occupied
            attempts = 0
            while attempts < 50:
                pos = random.choice(explored)
                if self.dungeon.is_walkable(pos[0], pos[1]):
                    # Check not too close to heroes
                    min_dist = min(
                        self.dungeon.get_distance(pos[0], pos[1], h.x, h.y)
                        for h in self.party if not h.is_dead
                    )
                    if min_dist >= 3 and min_dist <= 8:
                        positions.append(pos)
                        break
                attempts += 1
            
            if len(positions) < _ + 1:
                # Fallback: random explored position
                positions.append(random.choice(explored))
        
        return positions
    
    def _end_combat(self):
        """End combat and return to exploration."""
        self.current_phase = "EXPLORATION"
        self.mode = "DUNGEON"
        self.combat_log.append("Combat ended. Monsters defeated!")
        self.monsters = []
        self.heroes_acted_this_phase.clear()  # Reset for exploration phase
    
    def open_door(self, x: int, y: int) -> bool:
        """Open a door and possibly trigger combat."""
        if not self.dungeon.open_door(x, y):
            return False
        
        self.combat_log.append(f"Door opened at ({x}, {y})")
        
        # Check if room has monsters placed by dungeon generation
        if self.dungeon.monsters:
            monster_ids = list(self.dungeon.monsters.values())
            self.dungeon.monsters.clear()  # Clear from dungeon, will spawn in game
            if monster_ids:
                self._start_combat(monster_ids)
        
        # Check for wandering monsters on door open
        elif random.randint(1, 12) <= 2:
            self.combat_log.append("Wandering monsters appear!")
            monster_ids = roll_lair_encounter()
            self._start_combat(monster_ids)
        
        self.save_game()
        return True
    
    def _exit_dungeon(self):
        """Exit the dungeon and return to tavern."""
        self.mode = "TAVERN"
        self.combat_log.append("Party exits the dungeon!")
        
        # Award experience
        for hero in self.party:
            if not hero.is_dead:
                hero.total_pv += self.experience_gained
        
        # Delete save
        if self.SAVE_FILE.exists():
            self.SAVE_FILE.unlink()
        
        # Save hero updates
        for hero in self.party:
            self.hero_manager.update_hero(hero)
    
    def _game_over(self):
        """Handle game over."""
        self.mode = "GAME_OVER"
        self.combat_log.append("GAME OVER - All heroes have fallen!")
        
        # Delete save
        if self.SAVE_FILE.exists():
            self.SAVE_FILE.unlink()
    
    def save_game(self):
        """Save current game state."""
        data = {
            "mode": self.mode,
            "dungeon": self.dungeon.to_dict() if self.dungeon else None,
            "party_ids": [h.id for h in self.party],
            "monsters": [
                {
                    "id": m.id,
                    "instance_id": m.instance_id,
                    "x": m.x,
                    "y": m.y,
                    "current_wounds": m.current_wounds,
                    "is_dead": m.is_dead
                }
                for m in self.monsters
            ],
            "current_phase": self.current_phase,
            "hero_phase_active": self.hero_phase_active,
            "heroes_acted_this_phase": list(self.heroes_acted_this_phase),
            "turn_count": self.turn_count,
            "combat_log": self.combat_log[-50:],  # Last 50 messages
            "experience_gained": self.experience_gained,
            "gold_found": self.gold_found
        }
        
        self.SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.SAVE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_game(self) -> bool:
        """Load game state if save exists."""
        if not self.SAVE_FILE.exists():
            return False
        
        try:
            with open(self.SAVE_FILE, "r") as f:
                data = json.load(f)
            
            self.mode = data.get("mode", "TAVERN")
            
            if data.get("dungeon"):
                self.dungeon = Dungeon.from_dict(data["dungeon"])
            
            # Restore party
            party_ids = data.get("party_ids", [])
            self.party = []
            for hero_id in party_ids:
                hero = self.hero_manager.get_hero(hero_id)
                if hero:
                    self.party.append(hero)
            
            # Restore monsters
            self.monsters = []
            for m_data in data.get("monsters", []):
                monster = self.monster_library.create_monster(m_data["id"])
                if monster:
                    monster.instance_id = m_data["instance_id"]
                    monster.x = m_data["x"]
                    monster.y = m_data["y"]
                    monster.current_wounds = m_data["current_wounds"]
                    monster.is_dead = m_data["is_dead"]
                    self.monsters.append(monster)
            
            self.current_phase = data.get("current_phase", "EXPLORATION")
            self.hero_phase_active = data.get("hero_phase_active", True)
            self.heroes_acted_this_phase = set(data.get("heroes_acted_this_phase", []))
            self.turn_count = data.get("turn_count", 0)
            self.combat_log = data.get("combat_log", [])
            self.experience_gained = data.get("experience_gained", 0)
            self.gold_found = data.get("gold_found", 0)
            
            return True
        except Exception as e:
            print(f"Error loading save: {e}")
            return False
    
    def has_save_game(self) -> bool:
        """Check if a save game exists."""
        return self.SAVE_FILE.exists()

"""
Core game loop and state machine for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import List, Optional, Tuple

from hero import Hero, HeroManager
from monster import Monster, MonsterLibrary, roll_lair_encounter, roll_quest_room_encounter
from dungeon import Dungeon
from combat import (
    resolve_melee_attack, resolve_monster_attack, apply_damage_to_hero,
    do_surprise_roll, find_target_hero
)
from gm import run_gm_phase, check_dungeon_counter, find_path_bfs, create_dungeon_counter_pool
from hazards import describe_hazard, get_hazard_anchor, resolve_hazard_reveal, resolve_magic_circle_entry
from monster_placement import place_monsters_whq_rules, surprise_move_monster
from traps import get_trap_marker, resolve_pit_leap, resolve_trap_event


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
        
        self.hero_movement_remaining: dict = {}  # hero_id -> remaining move points
        self.hero_has_attacked: set = set()       # track who has attacked this phase
        
        self.combat_log: List[str] = []
        self.experience_gained = 0
        self.gold_found = 0
        self.dungeon_debug_log: List[str] = []  # For tracking dungeon generation
        self.dungeon_counter_pool: List[str] = []
        self.held_dungeon_counters: List[str] = []
        self.expedition_followers = {
            "maiden": False,
            "man_at_arms": False,
            "rogue": False,
        }

    def _get_movement_allowance_for_phase(self, hero: Hero, phase: Optional[str] = None) -> int:
        """Return a hero's movement allowance for the current phase."""
        active_phase = phase or self.current_phase
        if active_phase == "COMBAT":
            return hero.get_movement_allowance("combat")
        return hero.get_movement_allowance("exploration")
    
    def start_quest(self, party: List[Hero]):
        """Begin a new dungeon expedition."""
        self.party = party
        self.monsters = []
        self.dungeon_debug_log = []
        self.dungeon = Dungeon(level=1, debug_log=self.dungeon_debug_log, 
                               monster_library=self.monster_library)
        # Wire up monster placement callback
        self.dungeon._on_monster_placed = lambda m: self.monsters.append(m)
        self.mode = "DUNGEON"
        self.current_phase = "EXPLORATION"
        self.hero_phase_active = True
        self.turn_count = 0
        self.combat_log = ["The expedition enters the dungeon..."]
        # Add any dungeon generation logs
        for msg in self.dungeon_debug_log:
            self.combat_log.append(f"[DUNGEON] {msg}")
        self.experience_gained = 0
        self.gold_found = 0
        self.dungeon_counter_pool = create_dungeon_counter_pool()
        self.held_dungeon_counters = []
        self.expedition_followers = {
            "maiden": False,
            "man_at_arms": False,
            "rogue": False,
        }
        
        # Initialize movement tracking
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "EXPLORATION")
            for h in self.party
        }
        self.hero_has_attacked.clear()
        
        # Place heroes
        start_x, start_y = self.dungeon.hero_start
        for i, hero in enumerate(self.party):
            hero.x = start_x + (i % 2)
            hero.y = start_y + (i // 2)
            hero.is_ko = False
            hero.ko_turns = 0
            hero.current_wounds = hero.max_wounds
            hero.temp_fate_bonus = 0
            hero.free_spell_cast = 0
            hero.status_effects = []
        
        self.save_game()

    def roll_wandering_monsters(self) -> List[str]:
        """Roll a wandering-monster group for the current expedition."""
        return roll_lair_encounter()

    def get_party_gold_total(self) -> int:
        """Return total gold currently carried by the party."""
        return sum(hero.gold for hero in self.party if not hero.is_dead)

    def adjust_party_gold(self, amount: int):
        """Distribute or remove gold across living heroes."""
        living = [hero for hero in self.party if not hero.is_dead]
        if not living or amount == 0:
            return

        if amount > 0:
            share, remainder = divmod(amount, len(living))
            for idx, hero in enumerate(living):
                hero.gold += share + (1 if idx < remainder else 0)
            return

        remaining = -amount
        for hero in sorted(living, key=lambda current: current.gold, reverse=True):
            if remaining <= 0:
                break
            taken = min(hero.gold, remaining)
            hero.gold -= taken
            remaining -= taken

    def _find_room_with_chest(self, x: int, y: int) -> Optional[dict]:
        """Return the room metadata for a chest tile."""
        if self.dungeon is None:
            return None
        for room in self.dungeon.rooms:
            chest_pos = room.get("chest_pos")
            if isinstance(chest_pos, list) and len(chest_pos) == 2 and (x, y) == (int(chest_pos[0]), int(chest_pos[1])):
                return room
        return None

    def _roll_room_chest_contents(self, room: dict) -> dict:
        """Resolve chest contents for a room if they have not been rolled yet."""
        existing = room.get("chest_loot")
        if isinstance(existing, dict):
            return existing

        room_kind = room.get("room_kind", "normal")
        if room_kind == "quest":
            loot = {"gold": random.randint(5, 12) * 10}
        elif room_kind == "lair":
            loot = {"gold": random.randint(3, 8) * 10}
        else:
            loot = {"gold": random.randint(1, 6) * 5}
        room["chest_loot"] = loot
        return loot

    def open_treasure_chest(self, hero: Hero, x: int, y: int) -> str:
        """Open a treasure chest, resolving any trap and loot."""
        if self.dungeon.get_tile(x, y) != self.dungeon.TileType.TREASURE_CLOSED:
            return "There is no closed chest there."

        room = self._find_room_with_chest(x, y)
        if room is None:
            return "This chest is not linked to a room."

        messages: List[str] = []
        if room.get("chest_trapped") and not room.get("chest_trap_resolved"):
            room["chest_trap_resolved"] = True
            resolve_trap_event(
                hero,
                self.dungeon,
                self.combat_log,
                lambda _: None,
                source="chest",
                can_spot=False,
                can_disarm=False,
            )
            messages.append("The chest is trapped!")

        if hero.is_dead:
            return " ".join(messages) if messages else f"{hero.name} is killed by the chest trap."

        loot = self._roll_room_chest_contents(room)
        gold = int(loot.get("gold", 0))
        if gold > 0:
            hero.gold += gold
            self.gold_found += gold
            messages.append(f"{hero.name} finds {gold} gold crowns in the chest.")
        else:
            messages.append("The chest is empty.")

        room["chest_opened"] = True
        self.dungeon.treasure[(x, y)] = True
        self.dungeon.grid[(x, y)] = self.dungeon.TileType.TREASURE_OPEN
        return " ".join(messages)

    def lift_portcullis(self, hero: Hero, x: int, y: int) -> str:
        """Attempt to lift a visible portcullis long enough for others to pass."""
        marker = get_trap_marker(self.dungeon, (x, y), "portcullis")
        if marker is None:
            return "There is no portcullis there."

        if not self.dungeon.is_adjacent(hero.x, hero.y, x, y) and (hero.x, hero.y) != (x, y):
            return "You must stand next to the portcullis to lift it."

        if self.current_phase != "EXPLORATION":
            return "A portcullis can only be lifted during exploration."

        participants: List[Hero] = []
        for candidate in self.party:
            if candidate.is_dead or candidate.is_ko or candidate.is_under_gm_control():
                continue
            if not self.dungeon.is_adjacent(candidate.x, candidate.y, x, y) and (candidate.x, candidate.y) != (x, y):
                continue
            remaining = self.hero_movement_remaining.get(
                candidate.id,
                self._get_movement_allowance_for_phase(candidate, "EXPLORATION"),
            )
            if remaining <= 0:
                continue
            participants.append(candidate)

        if hero not in participants:
            participants.append(hero)

        roll = random.randint(1, 12)
        total_strength = sum(current.get_effective_strength() for current in participants)
        total = roll + total_strength
        for participant in participants:
            self.hero_movement_remaining[participant.id] = 0

        names = ", ".join(current.name for current in participants)
        if total >= 20:
            marker["blocks_movement"] = False
            marker["temporary_open"] = True
            marker["opened_on_turn"] = self.turn_count
            marker["helpers"] = [current.id for current in participants]
            return (
                f"Portcullis lift: {names} heave together. Roll {roll} + Strength {total_strength} = {total}. "
                "The portcullis is lifted for the rest of this hero phase."
            )

        marker["blocks_movement"] = True
        marker.pop("temporary_open", None)
        return (
            f"Portcullis lift: {names} heave together. Roll {roll} + Strength {total_strength} = {total}. "
            "The portcullis does not budge."
        )

    def leap_pit_trap(self, hero: Hero, x: int, y: int) -> str:
        """Attempt to leap over a visible pit trap."""
        marker = get_trap_marker(self.dungeon, (x, y), "pit_trap")
        if marker is None and self.dungeon.get_tile(x, y) != self.dungeon.TileType.PIT_TRAP:
            return "There is no pit trap there."

        if not self.dungeon.is_adjacent(hero.x, hero.y, x, y):
            return "You must stand next to the pit to leap it."

        dx = x - hero.x
        dy = y - hero.y
        landing = (x + dx, y + dy)
        if not self.dungeon.is_walkable(*landing):
            return f"There is no clear landing square beyond the pit at {landing}."

        occupied = self._get_occupied_tiles_for_hero(hero)
        if landing in occupied:
            return f"The landing square at {landing} is occupied."

        start = (hero.x, hero.y)
        result_pos = resolve_pit_leap(hero, self.dungeon, self.combat_log, (x, y))
        if result_pos is None:
            hero.x, hero.y = start
            return "The leap cannot be attempted."

        self.hero_movement_remaining[hero.id] = 0
        self.dungeon._explore_from(hero.x, hero.y)
        if (hero.x, hero.y) == landing:
            return f"{hero.name} leaps the pit and lands at {landing}."
        return f"{hero.name} falls into the pit at ({x}, {y})."
    
    def move_hero(self, hero: Hero, x: int, y: int):
        """Move a hero to a new position."""
        can_move, message, dist = self.can_move_hero_to(hero, x, y)
        if not can_move:
            if message:
                self.combat_log.append(message)
            return False

        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))

        # Move
        hero.x, hero.y = x, y
        
        # Deduct movement points
        self.hero_movement_remaining[hero.id] = remaining - dist
        
        # Check for junctions (this will explore new passages if it's a pending junction)
        log_count_before = len(self.dungeon_debug_log)
        self.dungeon.check_and_generate_junction(x, y)
        # Add any new dungeon logs to combat log
        for msg in self.dungeon_debug_log[log_count_before:]:
            self.combat_log.append(f"[DUNGEON] {msg}")
        
        # Check for encounter triggers
        self._check_triggers(x, y)

        if self.current_phase == "EXPLORATION":
            self._enter_combat_if_monsters_visible()
        
        return True

    def _get_occupied_tiles_for_hero(self, hero: Hero) -> set:
        """Return occupied tiles that block hero movement."""
        occupied = set()
        for other in self.party:
            if other != hero and not other.is_dead and not other.is_ko:
                occupied.add((other.x, other.y))
        for monster in self.monsters:
            if not monster.is_dead:
                occupied.add((monster.x, monster.y))
        return occupied

    def _find_hero_path(self, hero: Hero, x: int, y: int) -> Optional[List[Tuple[int, int]]]:
        """Find a legal movement path for a hero using BFS."""
        occupied = self._get_occupied_tiles_for_hero(hero)
        return find_path_bfs(hero.x, hero.y, x, y, self.dungeon, occupied)

    def can_move_hero_to(self, hero: Hero, x: int, y: int) -> Tuple[bool, str, int]:
        """Check whether a hero can legally move to a tile."""
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} is dead/KO!", 0

        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control!", 0
        
        # Check remaining movement
        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))
        if remaining <= 0:
            return False, f"{hero.name} has no movement left!", 0
        
        # Check if walkable
        tile = self.dungeon.get_tile(x, y)
        if not self.dungeon.is_walkable(x, y):
            return False, f"Cannot move to ({x},{y}): tile is {tile.name}", 0

        if (x, y) in self._get_occupied_tiles_for_hero(hero):
            return False, "Square occupied!", 0

        path = self._find_hero_path(hero, x, y)
        if path is None:
            return False, f"Cannot move to ({x},{y}): path is blocked", 0

        dist = max(0, len(path) - 1)
        if dist > remaining:
            return False, f"Too far! Distance {dist} > remaining movement {remaining}", dist

        return True, "", dist
    
    def _check_triggers(self, x: int, y: int):
        """Check for triggered events at position."""
        tile = self.dungeon.get_tile(x, y)

        room = self.dungeon.find_room_for_tile(x, y)
        if room is not None and room.get("room_kind") == "hazard":
            hazard = room.get("hazard")
            if hazard and not hazard.get("revealed", False):
                hazard["revealed"] = True
                self.combat_log.append(f"Hazard room revealed: {describe_hazard(hazard)}.")
                reveal_result = resolve_hazard_reveal(room, self)
                if reveal_result:
                    self.combat_log.append(reveal_result)
                if self.current_phase == "COMBAT":
                    return
            if hazard and hazard.get("type") == "magic_circle":
                anchor = get_hazard_anchor(room)
                if anchor == (x, y):
                    hero_at_tile = next((h for h in self.party if h.x == x and h.y == y and not h.is_dead), None)
                    result = None
                    if hero_at_tile is not None:
                        result = resolve_magic_circle_entry(hero=hero_at_tile, room=room, game=self)
                    if result:
                        self.combat_log.append(result)
        
        if tile == self.dungeon.TileType.STAIRS_OUT:
            self._exit_dungeon()
        
        # Check for wandering monsters in passages
        if (x, y) in self.dungeon.wandering_monsters:
            self.dungeon.wandering_monsters.remove((x, y))  # Remove so it only triggers once
            self.combat_log.append("Wandering monsters appear!")
            # Debug: Check what tiles are explored around this position
            explored_nearby = [pos for pos in self.dungeon.explored if abs(pos[0]-x) + abs(pos[1]-y) <= 3]
            self.combat_log.append(f"  Explored tiles within 3 squares: {explored_nearby}")
            monster_ids = roll_lair_encounter()
            self._start_combat_random(monster_ids, trigger_tile=(x, y))

        # Check for pre-placed monsters in passages/rooms (now stored in self.monsters)
        triggered = []
        to_check = set()
        for monster in self.monsters:
            if not monster.is_dead and abs(monster.x - x) + abs(monster.y - y) <= 1:
                to_check.add((monster.x, monster.y))

        checked = set()
        while to_check:
            p = to_check.pop()
            if p in checked:
                continue
            checked.add(p)
            # Find monster at this position
            for monster in self.monsters:
                if not monster.is_dead and monster.x == p[0] and monster.y == p[1]:
                    if monster not in triggered:
                        triggered.append(monster)
                    for dp in [(0,1),(0,-1),(1,0),(-1,0)]:
                        neighbour = (p[0]+dp[0], p[1]+dp[1])
                        if neighbour not in checked:
                            to_check.add(neighbour)

        if triggered:
            self.combat_log.append("Monsters encountered!")
            self._start_combat_with_monsters(triggered)
            return

    def _get_visible_monsters(self) -> List[Monster]:
        """Return monsters currently visible to any active hero."""
        visible = []
        active_heroes = [hero for hero in self.party if not hero.is_dead and not hero.is_ko]
        for monster in self.monsters:
            if monster.is_dead:
                continue
            for hero in active_heroes:
                if self.dungeon._has_los(hero.x, hero.y, monster.x, monster.y):
                    visible.append(monster)
                    break
        return visible

    def _describe_monster_location(self, monster: Monster) -> str:
        """Return a short location label for a visible monster."""
        room = self.dungeon.find_room_for_tile(monster.x, monster.y)
        if room is not None:
            return f"room@({monster.x},{monster.y})"
        return f"passage@({monster.x},{monster.y})"

    def _enter_combat_if_monsters_visible(self) -> bool:
        """Switch to combat if monsters are visible during exploration."""
        if self.current_phase != "EXPLORATION":
            return False

        visible_monsters = self._get_visible_monsters()
        if not visible_monsters:
            return False

        monster_names = ", ".join(
            f"{monster.name} {self._describe_monster_location(monster)}"
            for monster in visible_monsters[:6]
        )
        if len(visible_monsters) > 6:
            monster_names += ", ..."
        self.combat_log.append(
            f"Visible monsters force combat: {len(visible_monsters)} monster(s) in sight: {monster_names}."
        )
        self._start_combat_with_monsters(visible_monsters)
        return True

    def hero_attack(self, hero: Hero, monster: Monster) -> bool:
        """Hero attacks a monster."""
        if hero.is_dead or hero.is_ko or monster.is_dead:
            return False

        if hero.is_under_gm_control():
            self.combat_log.append(f"{hero.name} is under GM control and cannot be directed by the player.")
            return False
        
        # Check if hero already attacked this phase
        if hero.id in self.hero_has_attacked:
            self.combat_log.append(f"{hero.name} has already attacked this phase!")
            return False
        
        # Must be adjacent
        if not self.dungeon.is_adjacent(hero.x, hero.y, monster.x, monster.y):
            return False
        
        # Resolve attack
        hit, damage, result = resolve_melee_attack(hero, monster, self.combat_log)
        
        # Mark as having attacked this phase
        self.hero_has_attacked.add(hero.id)
        
        if monster.is_dead:
            self.experience_gained += monster.pv
            self.monsters = [m for m in self.monsters if not m.is_dead]
            self._refresh_special_monster_states()
            
            # Check if combat ends
            if not any(not m.is_dead for m in self.monsters):
                self._end_combat()
        
        self.save_game()
        return True
    
    def end_hero_phase(self):
        """End hero phase and start GM phase."""
        self.hero_phase_active = False
        self._close_temporary_traps()
        
        if self.current_phase == "EXPLORATION":
            self._run_exploration_gm_phase()
        else:  # COMBAT
            self._run_combat_gm_phase()
        
        self.hero_phase_active = True
        # Reset movement and attack tracking for next hero phase
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h)
            for h in self.party
        }
        self.hero_has_attacked.clear()
        self.turn_count += 1
        self._advance_ko_timers()
        self._advance_status_effects()
        
        # Check for dead party
        if all(h.is_dead for h in self.party):
            self._game_over()
        
        self.save_game()

    def _close_temporary_traps(self):
        """Close any trap states that only stay open for the hero phase."""
        if self.dungeon is None:
            return
        for pos, marker in self.dungeon.trap_markers.items():
            if marker.get("type") == "portcullis" and marker.get("temporary_open"):
                marker["blocks_movement"] = True
                marker.pop("temporary_open", None)
                self.combat_log.append(f"The portcullis at {pos} crashes shut again.")

    def _advance_ko_timers(self):
        """Reduce temporary KO timers and wake heroes when they expire."""
        for hero in self.party:
            if hero.ko_turns > 0:
                hero.ko_turns -= 1
                if hero.ko_turns == 0 and hero.is_ko and not hero.is_dead:
                    hero.is_ko = False
                    if hero.current_wounds <= 0:
                        hero.current_wounds = 1
                    self.combat_log.append(f"{hero.name} recovers from a temporary KO.")

    def _advance_status_effects(self):
        """Advance timed hero status effects."""
        expiry_messages = {
            "madness": "returns to their senses.",
            "mild_poison": "can move again.",
        }
        for hero in self.party:
            for expired in hero.tick_status_effects():
                suffix = expiry_messages.get(expired, "is no longer affected.")
                self.combat_log.append(f"{hero.name} {suffix}")
    
    def _run_exploration_gm_phase(self):
        """Run GM phase during exploration."""
        if self._enter_combat_if_monsters_visible():
            return

        # Check for dungeon counter
        counter = check_dungeon_counter(self.dungeon_counter_pool)
        if counter:
            self.combat_log.append(f"Dungeon Counter drawn: {counter}")
            self._resolve_dungeon_counter(counter)
        
        self.combat_log.append("GM Phase complete.")

    def _get_active_heroes(self) -> List[Hero]:
        """Return heroes who can currently be affected by dungeon events."""
        return [hero for hero in self.party if not hero.is_dead and not hero.is_ko]

    def _resolve_dungeon_counter(self, counter: str):
        """Apply a drawn dungeon counter."""
        if counter == "wandering":
            self._resolve_wandering_counter()
        elif counter == "ambush":
            if self.current_phase == "COMBAT":
                self._resolve_ambush_counter()
            else:
                self.held_dungeon_counters.append(counter)
                self.combat_log.append("  Ambush counter held until the start of a combat turn.")
        elif counter == "character":
            self._resolve_character_counter()
        elif counter == "fate":
            self._resolve_fate_counter()
        elif counter == "trap":
            self._resolve_trap_counter()
        elif counter == "escape":
            self._resolve_escape_counter()
        else:
            self.combat_log.append(f"  No handler for counter '{counter}'.")

    def _choose_counter_target_hero(self) -> Optional[Hero]:
        """Pick an active hero for a dungeon counter effect."""
        active_heroes = self._get_active_heroes()
        if not active_heroes:
            return None
        return random.choice(active_heroes)

    def _resolve_wandering_counter(self):
        """Resolve a wandering-monster dungeon counter."""
        hero = self._choose_counter_target_hero()
        if hero is None:
            self.combat_log.append("  No active hero available for wandering monsters.")
            return

        self.combat_log.append(f"  Wandering monsters close on {hero.name}.")
        monster_ids = roll_lair_encounter()
        self._start_combat_random(monster_ids, trigger_tile=(hero.x, hero.y))

    def _resolve_ambush_counter(self):
        """Resolve an ambush dungeon counter."""
        if self.current_phase != "COMBAT":
            self.combat_log.append("  Ambush counter cannot be played outside combat.")
            return

        hero = self._choose_counter_target_hero()
        if hero is None:
            self.combat_log.append("  No active hero available for an ambush.")
            return

        self.combat_log.append(f"  Ambush! Monsters spring out near {hero.name}.")
        monster_ids = roll_lair_encounter()
        self._spawn_reinforcements(monster_ids, trigger_tile=(hero.x, hero.y), reason="Ambush")
        self.combat_log.append("  Ambush counter adds reinforcements to the current fight.")

    def _resolve_character_counter(self):
        """Resolve a character-monster dungeon counter."""
        hero = self._choose_counter_target_hero()
        if hero is None:
            self.combat_log.append("  No active hero available for a character encounter.")
            return

        character_ids = [
            monster_id
            for monster_id, data in self.monster_library.templates.items()
            if data.get("is_character")
        ]
        if not character_ids:
            self.combat_log.append("  Character counter drawn, but no character monsters are configured.")
            return

        monster_id = random.choice(character_ids)
        monster_name = self.monster_library.templates[monster_id].get("name", monster_id)
        self.combat_log.append(f"  Character monster encountered: {monster_name}.")
        self._start_combat_random([monster_id], trigger_tile=(hero.x, hero.y))

    def _resolve_fate_counter(self):
        """Resolve a fate dungeon counter."""
        candidates = [hero for hero in self.party if not hero.is_dead and hero.current_fate < hero.max_fate]
        if not candidates:
            self.combat_log.append("  Fate smiles on the party, but no hero has spent any Fate yet.")
            return

        hero = min(candidates, key=lambda h: (h.current_fate, h.name))
        hero.current_fate += 1
        self.combat_log.append(f"  {hero.name} regains 1 Fate Point.")

    def _resolve_trap_counter(self):
        """Resolve a trap dungeon counter."""
        hero = self._choose_counter_target_hero()
        if hero is None:
            self.combat_log.append("  No active hero available to trigger a trap.")
            return

        self.combat_log.append(f"  Trap! {hero.name} triggers a trap.")
        resolve_trap_event(
            hero=hero,
            dungeon=self.dungeon,
            log=self.combat_log,
            start_wandering_combat=lambda trigger_tile: self._start_combat_random(
                roll_lair_encounter(), trigger_tile=trigger_tile
            ),
            source="room_or_passage",
        )

    def _resolve_escape_counter(self):
        """Resolve an escape dungeon counter."""
        if self.dungeon and self.dungeon.wandering_monsters:
            escaped_marker = random.choice(list(self.dungeon.wandering_monsters))
            self.dungeon.wandering_monsters.remove(escaped_marker)
            self.combat_log.append(f"  Something slips away in the dark near {escaped_marker}.")
            return

        self.combat_log.append("  Escape counter drawn, but there is nothing currently marked to escape.")
    
    def _run_combat_gm_phase(self):
        """Run GM phase during combat."""
        self._refresh_special_monster_states()
        self._resolve_hazard_npc_rounds()
        self.monsters, self.combat_log = run_gm_phase(
            self.monsters, self.party, self.dungeon, self.combat_log
        )
        
        # Remove dead monsters from list
        self.monsters = [m for m in self.monsters if not m.is_dead]
        self._refresh_special_monster_states()
        
        # Check if combat ends
        if not self.monsters:
            self._end_combat()
        
        # Check for dead heroes
        if not any(not hero.is_dead and not hero.is_ko for hero in self.party):
            self._game_over()
    
    def _start_combat_with_positions(self, monster_data: List[Tuple[Tuple[int, int], str]]):
        """Start combat with monsters placed according to WHQ rules in the room."""
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self.hero_has_attacked.clear()
        
        # Extract monster IDs
        monster_ids = [mid for _, mid in monster_data]
        
        # Find the room containing these monsters - use ALL room tiles for placement
        first_monster_pos = monster_data[0][0] if monster_data else None
        room_tiles = []
        if first_monster_pos:
            room = self.dungeon.find_room_for_tile(*first_monster_pos)
            if room is not None:
                room_tiles = list(self.dungeon.get_room_interior_tiles(room))
        
        # Fallback: use monster positions if room not found
        if not room_tiles:
            room_tiles = [(x, y) for (x, y), _ in monster_data]
        
        # Filter to only walkable tiles (not on walls/entrances)
        valid_tiles = [(x, y) for (x, y) in room_tiles if self.dungeon.is_walkable(x, y)]
        
        # Place using WHQ rules
        self.monsters = place_monsters_whq_rules(
            monster_ids, valid_tiles, self.dungeon, self.party,
            self.monster_library, self.combat_log
        )
        self._play_held_combat_counters()
        
        # Surprise roll
        has_elf = any(h.race == "Elf" for h in self.party)
        has_sentry = any(m.is_sentry for m in self.monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")
        
        if winner == "gm":
            self.combat_log.append("Monsters win surprise!")
            # Move monsters up to 1 square (towards heroes or for attack)
            for monster in self.monsters:
                moved = surprise_move_monster(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  {monster.name} moves to ({monster.x}, {monster.y})")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        
        self.save_game()
    
    def _start_combat_with_monsters(self, monsters: List[Monster]):
        """Start combat with already-instantiated monsters (from dungeon generation)."""
        self._start_combat_with_monsters_configured(monsters)

    def _start_combat_with_monsters_configured(
        self,
        monsters: List[Monster],
        hero_surprise_bonus: int = 0,
        gm_surprise_bonus: int = 0,
        ignore_elf_surprise_bonus: bool = False,
        force_gm_surprise: bool = False,
        summary_prefix: str = "Combat started with",
    ):
        """Start combat with pre-placed monsters and optional surprise modifiers."""
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self.hero_has_attacked.clear()
        
        # Use the provided monsters (already placed during dungeon generation)
        # Filter to only include monsters that aren't already in combat
        existing_ids = {m.instance_id for m in self.monsters}
        new_monsters = [m for m in monsters if m.instance_id not in existing_ids]
        self.monsters.extend(new_monsters)
        encountered_monsters = [m for m in monsters if not m.is_dead]
        monster_summary = ", ".join(f"{m.name}@({m.x},{m.y})" for m in encountered_monsters[:8])
        if len(encountered_monsters) > 8:
            monster_summary += ", ..."
        self.combat_log.append(
            f"{summary_prefix} {len(encountered_monsters)} visible monsters: {monster_summary}"
        )
        self._play_held_combat_counters()
        
        # Surprise roll
        has_elf = any(h.race == "Elf" for h in self.party) and not ignore_elf_surprise_bonus
        has_sentry = any(m.is_sentry for m in self.monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        hero_roll = min(12, hero_roll + hero_surprise_bonus)
        gm_roll = min(12, gm_roll + gm_surprise_bonus)
        if force_gm_surprise:
            winner = "gm"
        elif hero_roll >= gm_roll:
            winner = "heroes"
        else:
            winner = "gm"
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")
        
        if winner == "gm":
            self.combat_log.append("Monsters surprise the heroes!")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        
        self.save_game()

    def _start_room_hazard_combat(
        self,
        room: dict,
        monster_ids: List[str],
        reason: str,
        prisoners: bool = False,
        throne: bool = False,
        hero_surprise_bonus: int = 0,
        ignore_elf_surprise_bonus: bool = False,
    ) -> List[Monster]:
        """Start a room-based hazard combat using the room interior for placement."""
        room_tiles = [
            (x, y)
            for (x, y) in self.dungeon.get_room_interior_tiles(room)
            if self.dungeon.is_walkable(x, y)
        ]
        monsters = place_monsters_whq_rules(
            monster_ids,
            room_tiles,
            self.dungeon,
            self.party,
            self.monster_library,
            self.combat_log,
        )
        if prisoners:
            for monster in monsters:
                monster.weapons = [dict(weapon, damage_dice=1) for weapon in monster.weapons]
                monster.is_sentry = False
        if throne:
            self._apply_throne_aura(room, monsters)
        self._start_combat_with_monsters_configured(
            monsters,
            hero_surprise_bonus=hero_surprise_bonus,
            ignore_elf_surprise_bonus=ignore_elf_surprise_bonus,
            summary_prefix=f"{reason}:",
        )
        return monsters

    def create_hazard_npc(self, npc_type: str) -> Monster:
        """Create a hazard-room NPC or NPC-like opponent."""
        if npc_type == "witch":
            witch = Monster(
                monster_id="hazard_witch",
                name="Witch",
                ws=6,
                bs=7,
                strength=3,
                toughness=4,
                speed=5,
                bravery=7,
                intelligence=8,
                wounds=2,
                pv=4,
                weapons=[{"name": "Staff", "damage_dice": 1, "critical": 12, "fumble": 1}],
                ranged={"name": "Hex Bolt", "range": 6, "damage_dice": 1},
                is_sentry=False,
                is_character=True,
            )
            setattr(witch, "witch_escape_pending", True)
            setattr(witch, "witch_rounds_remaining", 2)
            return witch
        raise ValueError(f"Unsupported hazard NPC type: {npc_type}")

    def place_hazard_chest(self, room: dict) -> Optional[Tuple[int, int]]:
        """Place a visible chest for hazards such as the chasm room."""
        anchor = get_hazard_anchor(room)
        if anchor is None:
            return None

        interior_tiles = [
            pos for pos in self.dungeon.get_room_interior_tiles(room)
            if pos != anchor and self.dungeon.get_tile(*pos) == self.dungeon.TileType.FLOOR
        ]
        if not interior_tiles:
            return None

        chest_pos = max(
            interior_tiles,
            key=lambda pos: (abs(pos[0] - anchor[0]) + abs(pos[1] - anchor[1]), pos[1], pos[0]),
        )
        self.dungeon.grid[chest_pos] = self.dungeon.TileType.TREASURE_CLOSED
        self.dungeon.treasure[chest_pos] = False
        room["chest_pos"] = list(chest_pos)
        room["chest_loot"] = {"gold": random.randint(1, 5) * 25}
        room["chest_trapped"] = True
        room["chest_opened"] = False
        room["chest_trap_resolved"] = False
        return chest_pos

    def _apply_throne_aura(self, room: dict, monsters: List[Monster]):
        """Mark the throne occupant and buff the rest of the room's monsters."""
        anchor = get_hazard_anchor(room)
        if not monsters or anchor is None:
            return

        leader = min(monsters, key=lambda monster: abs(monster.x - anchor[0]) + abs(monster.y - anchor[1]))
        leader.x, leader.y = anchor
        setattr(leader, "throne_leader", True)
        setattr(leader, "throne_room_id", room.get("id"))

        for monster in monsters:
            if monster is leader:
                continue
            setattr(monster, "throne_guardian", True)
            setattr(monster, "throne_room_id", room.get("id"))
            setattr(monster, "throne_original_toughness", monster.toughness)
            monster.toughness += 1
            if monster.weapons:
                original_weapons = [dict(weapon) for weapon in monster.weapons]
                setattr(monster, "throne_original_weapons", original_weapons)
                monster.weapons = [
                    dict(weapon, damage_dice=weapon.get("damage_dice", 1) + 1)
                    for weapon in monster.weapons
                ]
        self.combat_log.append("  Throne aura: one monster commands the throne and empowers the others.")

    def _refresh_special_monster_states(self):
        """Refresh transient monster states such as throne auras."""
        throne_leaders = [
            monster for monster in self.monsters
            if getattr(monster, "throne_leader", False) and not monster.is_dead
        ]
        active_rooms = {getattr(monster, "throne_room_id", None) for monster in throne_leaders}
        for monster in self.monsters:
            room_id = getattr(monster, "throne_room_id", None)
            if not getattr(monster, "throne_guardian", False):
                continue
            if room_id in active_rooms:
                continue
            if hasattr(monster, "throne_original_toughness"):
                monster.toughness = getattr(monster, "throne_original_toughness")
                delattr(monster, "throne_original_toughness")
            if hasattr(monster, "throne_original_weapons"):
                monster.weapons = getattr(monster, "throne_original_weapons")
                delattr(monster, "throne_original_weapons")
            if hasattr(monster, "throne_guardian"):
                delattr(monster, "throne_guardian")
            if hasattr(monster, "throne_room_id"):
                delattr(monster, "throne_room_id")
            self.combat_log.append(f"The throne aura fades from {monster.name}.")

    def _find_room_by_id(self, room_id) -> Optional[dict]:
        """Return a dungeon room by its stored ID."""
        if self.dungeon is None:
            return None
        for room in self.dungeon.rooms:
            if room.get("id") == room_id:
                return room
        return None

    def _resolve_hazard_npc_rounds(self):
        """Advance timed hazard NPC behaviors such as witches escaping."""
        escaped_monsters: List[Monster] = []
        for monster in self.monsters:
            if monster.is_dead or not getattr(monster, "witch_escape_pending", False):
                continue

            rounds_remaining = int(getattr(monster, "witch_rounds_remaining", 1)) - 1
            setattr(monster, "witch_rounds_remaining", rounds_remaining)
            if rounds_remaining > 0:
                self.combat_log.append(
                    f"{monster.name} chants and prepares to flee the room."
                )
                continue

            escaped_monsters.append(monster)

        for monster in escaped_monsters:
            room_id = getattr(monster, "witch_room_id", None)
            room = self._find_room_by_id(room_id)
            if room is not None:
                hazard = room.get("hazard") or {}
                hazard["witch_escaped"] = True
                hazard["resolved"] = True
            stolen = self.get_party_gold_total() // 2
            if stolen > 0:
                self.adjust_party_gold(-stolen)
                self.gold_found = max(0, self.gold_found - stolen)
                self.combat_log.append(
                    f"The Witch teleports away, stealing {stolen} gold crowns from the party."
                )
            else:
                self.combat_log.append("The Witch teleports away before the party can stop her.")
            monster.is_dead = True

    def _is_witch_sealed_away(self, room_id) -> bool:
        """Whether the witch from a room has already escaped or been removed."""
        room = self._find_room_by_id(room_id)
        if room is None:
            return False
        hazard = room.get("hazard") or {}
        return bool(hazard.get("witch_escaped"))
    
    def _start_combat_random(self, monster_ids: List[str], trigger_tile: Optional[Tuple[int, int]] = None):
        """Start combat with monsters at positions following WHQ placement rules."""
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self.hero_has_attacked.clear()
        
        # Get valid spawn tiles
        if trigger_tile:
            # For wandering monsters, spawn near the trigger tile (adjacent to hero)
            valid_tiles = []
            for dx, dy in [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0), (0, 2), (0, -2), (2, 0), (-2, 0)]:
                tx, ty = trigger_tile[0] + dx, trigger_tile[1] + dy
                if self.dungeon.is_walkable(tx, ty):
                    valid_tiles.append((tx, ty))
            self.combat_log.append(f"  Wandering monsters spawning near {trigger_tile}, {len(valid_tiles)} valid tiles")
        else:
            # Get valid spawn tiles (explored walkable area)
            explored = list(self.dungeon.explored)
            valid_tiles = [pos for pos in explored if self.dungeon.is_walkable(pos[0], pos[1])]
        
        # Place monsters using WHQ rules
        self.monsters = place_monsters_whq_rules(
            monster_ids, valid_tiles, self.dungeon, self.party,
            self.monster_library, self.combat_log
        )
        self.combat_log.append(f"  Placed {len(self.monsters)} monsters: {[(m.name, m.x, m.y) for m in self.monsters]}")
        self._play_held_combat_counters()
        
        # Surprise roll
        has_elf = any(h.race == "Elf" for h in self.party)
        has_sentry = any(m.is_sentry for m in self.monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")
        
        if winner == "gm":
            self.combat_log.append("Monsters win surprise!")
            # Move monsters up to 1 square (towards heroes or for attack)
            for monster in self.monsters:
                moved = surprise_move_monster(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  {monster.name} moves to ({monster.x}, {monster.y})")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
            # Heroes get first turn, monsters don't move
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        
        self.save_game()

    def _get_reinforcement_tiles(self, trigger_tile: Optional[Tuple[int, int]] = None) -> List[Tuple[int, int]]:
        """Find valid tiles for reinforcement placement without replacing existing monsters."""
        occupied = {
            (monster.x, monster.y)
            for monster in self.monsters
            if not monster.is_dead
        }
        occupied.update(
            (hero.x, hero.y)
            for hero in self.party
            if not hero.is_dead and not hero.is_ko
        )

        valid_tiles: List[Tuple[int, int]] = []
        if trigger_tile:
            for dx, dy in [
                (0, 0), (0, 1), (0, -1), (1, 0), (-1, 0),
                (0, 2), (0, -2), (2, 0), (-2, 0), (1, 1),
                (1, -1), (-1, 1), (-1, -1)
            ]:
                tx, ty = trigger_tile[0] + dx, trigger_tile[1] + dy
                if self.dungeon.is_walkable(tx, ty) and (tx, ty) not in occupied:
                    valid_tiles.append((tx, ty))
        else:
            explored = list(self.dungeon.explored)
            valid_tiles = [
                pos for pos in explored
                if self.dungeon.is_walkable(pos[0], pos[1]) and pos not in occupied
            ]
        return valid_tiles

    def _spawn_reinforcements(
        self,
        monster_ids: List[str],
        trigger_tile: Optional[Tuple[int, int]] = None,
        reason: str = "Reinforcements",
    ) -> List[Monster]:
        """Add monsters to an existing combat without replacing current monsters."""
        valid_tiles = self._get_reinforcement_tiles(trigger_tile)
        if not valid_tiles:
            self.combat_log.append(f"  {reason}: no valid reinforcement positions.")
            return []

        new_monsters = place_monsters_whq_rules(
            monster_ids, valid_tiles, self.dungeon, self.party,
            self.monster_library, self.combat_log
        )
        self.monsters.extend(new_monsters)
        self.combat_log.append(
            f"  {reason}: placed {len(new_monsters)} monster(s): "
            f"{[(m.name, m.x, m.y) for m in new_monsters]}"
        )
        return new_monsters

    def _play_held_combat_counters(self):
        """Play any counters that are only legal at the start of combat."""
        if self.current_phase != "COMBAT" or not self.held_dungeon_counters:
            return

        remaining_counters: List[str] = []
        for counter in self.held_dungeon_counters:
            if counter == "ambush":
                self.combat_log.append("Held ambush counter played as combat begins.")
                self._resolve_ambush_counter()
            else:
                remaining_counters.append(counter)
        self.held_dungeon_counters = remaining_counters
    
    def _get_spawn_positions(self, count: int) -> List[tuple]:
        """Get positions to spawn monsters."""
        positions = []
        # Spawn in explored walkable area, away from heroes
        explored = list(self.dungeon.explored)
        
        # Filter to only walkable tiles
        walkable_explored = [pos for pos in explored if self.dungeon.is_walkable(pos[0], pos[1])]
        
        if not walkable_explored:
            # No walkable tiles, return empty (shouldn't happen)
            return positions
        
        for _ in range(count):
            # Find a position that's walkable and not too close to heroes
            attempts = 0
            while attempts < 100:
                pos = random.choice(walkable_explored)
                # Check not too close to heroes (3-8 tiles away)
                min_dist = min(
                    self.dungeon.get_distance(pos[0], pos[1], h.x, h.y)
                    for h in self.party if not h.is_dead
                )
                if min_dist >= 3 and min_dist <= 10:
                    positions.append(pos)
                    break
                attempts += 1
            
            if len(positions) < _ + 1:
                # Fallback: any walkable position away from heroes (at least 3 tiles)
                for pos in walkable_explored:
                    min_dist = min(
                        self.dungeon.get_distance(pos[0], pos[1], h.x, h.y)
                        for h in self.party if not h.is_dead
                    )
                    if min_dist >= 3:
                        positions.append(pos)
                        break
                else:
                    # Last resort: any walkable position
                    positions.append(random.choice(walkable_explored))
        
        return positions
    
    def _end_combat(self):
        """End combat and return to exploration."""
        self.current_phase = "EXPLORATION"
        self.mode = "DUNGEON"
        self.combat_log.append("Combat ended. Monsters defeated!")
        self.monsters = []
        for hero in self.party:
            hero.clear_status_effects("combat")
            hero.clear_status_effects("next_combat")
            if hero.is_ko and not hero.is_dead:
                hero.current_wounds = 1
                hero.is_ko = False
                self.combat_log.append(f"{hero.name} regains consciousness with 1 wound.")
        # Reset for exploration phase
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "EXPLORATION")
            for h in self.party
        }
        self.hero_has_attacked.clear()
    
    def open_door(self, x: int, y: int) -> bool:
        """Open a door and possibly trigger combat."""
        if not self.dungeon.open_door(x, y):
            return False
        
        self.combat_log.append(f"Door opened at ({x}, {y})")
        
        # Check if room has monsters placed by dungeon generation
        # Monsters are now stored directly in self.monsters with positions set during generation
        nearby_monsters = [m for m in self.monsters if not m.is_dead and 
                          abs(m.x - x) + abs(m.y - y) <= 3]
        if nearby_monsters:
            self.combat_log.append(f"  Found {len(nearby_monsters)} monsters nearby!")
            self._start_combat_with_monsters(nearby_monsters)

        elif self._enter_combat_if_monsters_visible():
            self.save_game()
            return True
        
        # Check for wandering monsters on door open
        elif random.randint(1, 12) <= 2:
            self.combat_log.append("Wandering monsters appear!")
            monster_ids = roll_lair_encounter()
            self._start_combat_random(monster_ids)

        self.save_game()
        return True
    
    def _exit_dungeon(self):
        """Exit the dungeon and return to tavern."""
        self.mode = "TAVERN"
        self.combat_log.append("Party exits the dungeon!")

        if self.expedition_followers.get("maiden"):
            self.adjust_party_gold(100)
            self.gold_found += 100
            self.combat_log.append("The Maiden is returned safely and her family rewards the party with 100 gold crowns.")

        if self.expedition_followers.get("rogue"):
            betrayal_roll = random.randint(1, 12)
            if betrayal_roll >= 7:
                stolen = self.get_party_gold_total() // 2
                if stolen > 0:
                    self.adjust_party_gold(-stolen)
                    self.gold_found = max(0, self.gold_found - stolen)
                    self.combat_log.append(
                        f"Rogue betrayal roll: {betrayal_roll}. The Rogue slips away with {stolen} gold crowns."
                    )
                else:
                    self.combat_log.append(
                        f"Rogue betrayal roll: {betrayal_roll}. The Rogue deserts the party but finds no gold to steal."
                    )
            else:
                self.combat_log.append(
                    f"Rogue betrayal roll: {betrayal_roll}. The Rogue keeps his bargain and leaves peacefully."
                )

        if self.expedition_followers.get("man_at_arms"):
            self.combat_log.append(
                "The rescued Man-at-Arms survives the expedition and is available as a henchman after the delve."
            )

        for hero in self.party:
            if hero.current_fate > hero.max_fate:
                hero.current_fate = hero.max_fate
            hero.temp_fate_bonus = 0
            hero.free_spell_cast = 0
            hero.ko_turns = 0
            hero.clear_status_effects()
        
        # Award experience
        for hero in self.party:
            if not hero.is_dead:
                hero.total_pv += self.experience_gained
        
        # Delete save
        if self.SAVE_FILE.exists():
            try:
                self.SAVE_FILE.unlink()
            except OSError:
                self.combat_log.append("Could not remove the expedition save file immediately.")
        
        # Save hero updates
        for hero in self.party:
            self.hero_manager.update_hero(hero)
    
    def _game_over(self):
        """Handle game over."""
        self.mode = "GAME_OVER"
        self.combat_log.append("GAME OVER - All heroes have fallen!")
        
        # Delete save
        if self.SAVE_FILE.exists():
            try:
                self.SAVE_FILE.unlink()
            except OSError:
                pass
    
    def save_game(self):
        """Save current game state."""
        party_data = []
        for hero in self.party:
            hero_data = hero.to_dict()
            hero_data["x"] = hero.x
            hero_data["y"] = hero.y
            party_data.append(hero_data)

        data = {
            "mode": self.mode,
            "dungeon": self.dungeon.to_dict() if self.dungeon else None,
            "party_ids": [h.id for h in self.party],
            "party": party_data,
            "monsters": [
                {
                    "id": m.id,
                    "name": m.name,
                    "instance_id": m.instance_id,
                    "x": m.x,
                    "y": m.y,
                    "ws": m.ws,
                    "bs": m.bs,
                    "strength": m.strength,
                    "toughness": m.toughness,
                    "speed": m.speed,
                    "bravery": m.bravery,
                    "intelligence": m.intelligence,
                    "max_wounds": m.max_wounds,
                    "current_wounds": m.current_wounds,
                    "pv": m.pv,
                    "weapons": m.weapons,
                    "ranged": m.ranged,
                    "is_sentry": m.is_sentry,
                    "is_character": m.is_character,
                    "is_dead": m.is_dead,
                    "special_state": {
                        "throne_leader": getattr(m, "throne_leader", False),
                        "throne_guardian": getattr(m, "throne_guardian", False),
                        "throne_room_id": getattr(m, "throne_room_id", None),
                        "throne_original_toughness": getattr(m, "throne_original_toughness", None),
                        "throne_original_weapons": getattr(m, "throne_original_weapons", None),
                        "witch_escape_pending": getattr(m, "witch_escape_pending", False),
                        "witch_rounds_remaining": getattr(m, "witch_rounds_remaining", None),
                        "witch_room_id": getattr(m, "witch_room_id", None),
                    },
                }
                for m in self.monsters
            ],
            "current_phase": self.current_phase,
            "hero_phase_active": self.hero_phase_active,
            "hero_movement_remaining": self.hero_movement_remaining,
            "hero_has_attacked": list(self.hero_has_attacked),
            "turn_count": self.turn_count,
            "combat_log": self.combat_log[-50:],  # Last 50 messages
            "experience_gained": self.experience_gained,
            "gold_found": self.gold_found,
            "dungeon_counter_pool": self.dungeon_counter_pool,
            "held_dungeon_counters": self.held_dungeon_counters,
            "expedition_followers": self.expedition_followers,
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
                self.dungeon._on_monster_placed = lambda m: self.monsters.append(m)
            
            # Restore party
            self.party = []
            party_data = data.get("party", [])
            if party_data:
                for hero_data in party_data:
                    hero = Hero.from_dict(hero_data)
                    hero.x = hero_data.get("x", 0)
                    hero.y = hero_data.get("y", 0)
                    self.party.append(hero)
            else:
                party_ids = data.get("party_ids", [])
                for hero_id in party_ids:
                    hero = self.hero_manager.get_hero(hero_id)
                    if hero:
                        self.party.append(hero)
            
            # Restore monsters
            self.monsters = []
            for m_data in data.get("monsters", []):
                monster = self.monster_library.create_monster(m_data["id"])
                if not monster:
                    monster = Monster(
                        monster_id=m_data["id"],
                        name=m_data.get("name", m_data["id"]),
                        ws=m_data.get("ws", 1),
                        bs=m_data.get("bs", 0),
                        strength=m_data.get("strength", 1),
                        toughness=m_data.get("toughness", 1),
                        speed=m_data.get("speed", 1),
                        bravery=m_data.get("bravery", 1),
                        intelligence=m_data.get("intelligence", 1),
                        wounds=m_data.get("max_wounds", 1),
                        pv=m_data.get("pv", 1),
                        weapons=m_data.get("weapons", []),
                        ranged=m_data.get("ranged"),
                        is_sentry=m_data.get("is_sentry", False),
                        is_character=m_data.get("is_character", False),
                    )
                monster.instance_id = m_data["instance_id"]
                monster.x = m_data["x"]
                monster.y = m_data["y"]
                monster.ws = m_data.get("ws", monster.ws)
                monster.bs = m_data.get("bs", monster.bs)
                monster.strength = m_data.get("strength", monster.strength)
                monster.toughness = m_data.get("toughness", monster.toughness)
                monster.speed = m_data.get("speed", monster.speed)
                monster.bravery = m_data.get("bravery", monster.bravery)
                monster.intelligence = m_data.get("intelligence", monster.intelligence)
                monster.max_wounds = m_data.get("max_wounds", monster.max_wounds)
                monster.current_wounds = m_data["current_wounds"]
                monster.pv = m_data.get("pv", monster.pv)
                monster.weapons = m_data.get("weapons", monster.weapons)
                monster.ranged = m_data.get("ranged", monster.ranged)
                monster.is_sentry = m_data.get("is_sentry", monster.is_sentry)
                monster.is_character = m_data.get("is_character", monster.is_character)
                monster.is_dead = m_data["is_dead"]
                for key, value in m_data.get("special_state", {}).items():
                    if value is not None:
                        setattr(monster, key, value)
                self.monsters.append(monster)
            
            self.current_phase = data.get("current_phase", "EXPLORATION")
            self.hero_phase_active = data.get("hero_phase_active", True)
            self.hero_movement_remaining = data.get("hero_movement_remaining", {h["id"]: h["speed"] for h in data.get("party", [])})
            self.hero_has_attacked = set(data.get("hero_has_attacked", []))
            self.turn_count = data.get("turn_count", 0)
            self.combat_log = data.get("combat_log", [])
            self.experience_gained = data.get("experience_gained", 0)
            self.gold_found = data.get("gold_found", 0)
            self.dungeon_counter_pool = data.get("dungeon_counter_pool", create_dungeon_counter_pool())
            self.held_dungeon_counters = data.get("held_dungeon_counters", [])
            self.expedition_followers = data.get(
                "expedition_followers",
                {"maiden": False, "man_at_arms": False, "rogue": False},
            )
            
            return True
        except Exception as e:
            print(f"Error loading save: {e}")
            return False
    
    def get_game_state(self) -> dict:
        """Get current game state for UI sync."""
        return {
            'phase': self.current_phase,
            'mode': self.mode,
            'hero_phase': self.hero_phase_active,
            'monsters': self.monsters
        }
    
    def has_save_game(self) -> bool:
        """Check if a save game exists."""
        return self.SAVE_FILE.exists()

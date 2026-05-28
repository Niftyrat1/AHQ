"""
Core game loop and state machine for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import List, Optional, Tuple

from hero import Hero, HeroManager, create_henchman
from monster import Monster, MonsterLibrary, roll_lair_encounter, roll_quest_room_encounter
from dungeon import Dungeon
from combat import (
    resolve_melee_attack, resolve_monster_attack, resolve_hero_ranged_attack, apply_damage_to_hero,
    resolve_spell_damage, resolve_hero_vs_hero_attack,
    do_surprise_roll, find_target_hero, get_fireball_template_area, get_ranged_los_state_for_models
)
from gm import run_gm_phase, check_dungeon_counter, find_path_bfs, create_dungeon_counter_pool
from hazards import (
    describe_hazard,
    find_lower_room_for_tile,
    get_hazard_anchor,
    get_lower_room_for_hero,
    get_lower_room_tiles,
    lower_room_entry_available,
    lower_room_exit_available,
    resolve_enter_lower_room,
    resolve_hazard_reveal,
    resolve_leave_lower_room,
    resolve_magic_circle_entry,
)
from magic import (
    format_spell_source_label,
    get_spell_definition,
    normalize_spell_name,
    spell_component_count,
)
from monster_placement import (
    place_monsters_ahq_section,
    place_monsters_far_los,
    surprise_move_monster,
    move_monster_one_square_away,
)
from traps import attempt_disarm_trap, get_trap_marker, resolve_pit_leap, resolve_trap_event
from dungeon.rooms import choose_room_chest_position
from magic_treasure import generate_magic_treasure
from fate import (
    get_pending_fate_hero as fate_get_pending_fate_hero,
    has_pending_fate_decision as fate_has_pending_fate_decision,
    resolve_pending_fate as fate_resolve_pending_fate,
)
from between_expeditions import (
    train_hero_stat,
    increase_hero_fate,
    buy_equipment as buy_between_expedition_equipment,
    buy_supply as buy_between_expedition_supply,
    buy_ammo_bundle,
    buy_spell,
    buy_spell_component,
    use_healer_service,
)


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
        self.hero_ran_this_phase: set = set()     # track who has chosen to run this phase
        self.hero_turn_start_positions: dict = {}  # hero_id -> start-of-phase (x, y)
        self.entered_tiles: set = set()           # all tiles heroes have entered this expedition
        self.ambush_counter_played_this_combat_turn = False
        self.combat_escape_pending_closed_door = False
        self.combat_pursuit_active = False
        self.combat_escape_closed_doors: List[Tuple[int, int]] = []
        
        self.combat_log: List[str] = []
        self.experience_gained = 0
        self.gold_found = 0
        self.dungeon_debug_log: List[str] = []  # For tracking dungeon generation
        self.dungeon_counter_pool: List[str] = []
        self.held_dungeon_counters: List[str] = []
        self.escaped_character_monsters: List[dict] = []
        self.section_spell_effects: List[dict] = []
        self.expedition_followers = {
            "maiden": False,
            "man_at_arms": False,
            "rogue": False,
        }
        self.last_expedition_summary: Optional[dict] = None
        self.pending_board_action: Optional[dict] = None
        self.left_behind_treasure: List[dict] = []
        self.pending_henchman_rewards: List[dict] = []
        self.active_fireball_traps: List[dict] = []
        self.next_portcullis_placement: Optional[List[Tuple[int, int]]] = None
        self.next_fireball_trap_directions: List[Tuple[int, int]] = []
        self.party_stash_gold = 0
        self.quest_id: Optional[str] = None
        self.quest_specific_stairs_down = False
        self.heroquest_maze_available = True
        self.pending_sub_level_entry: Optional[dict] = None
        self.active_sub_level: Optional[dict] = None

    def _living_true_heroes(self) -> List[Hero]:
        """Return living non-henchman heroes."""
        return [hero for hero in self.party if hero.is_true_hero() and not hero.is_dead]

    def _all_true_heroes_dead(self) -> bool:
        """Whether all actual heroes have fallen."""
        heroes = [hero for hero in self.party if hero.is_true_hero()]
        return bool(heroes) and all(hero.is_dead for hero in heroes)

    def _get_movement_allowance_for_phase(self, hero: Hero, phase: Optional[str] = None) -> int:
        """Return a hero's movement allowance for the current phase."""
        active_phase = phase or self.current_phase
        if active_phase == "COMBAT":
            return hero.get_movement_allowance("combat")
        return hero.get_movement_allowance("exploration")
    
    def start_quest(
        self,
        party: List[Hero],
        quest_id: Optional[str] = None,
        *,
        quest_specific_stairs_down: Optional[bool] = None,
        heroquest_maze_available: Optional[bool] = None,
    ):
        """Begin a new dungeon expedition."""
        self.party = party
        self.monsters = []
        self.dungeon_debug_log = []
        self.quest_id = quest_id
        if quest_specific_stairs_down is None:
            self.quest_specific_stairs_down = self._quest_uses_specific_stairs_down(quest_id)
        else:
            self.quest_specific_stairs_down = bool(quest_specific_stairs_down)
        if heroquest_maze_available is not None:
            self.heroquest_maze_available = bool(heroquest_maze_available)
        self.pending_sub_level_entry = None
        self.active_sub_level = None
        self.dungeon = Dungeon(level=1, debug_log=self.dungeon_debug_log, 
                               monster_library=self.monster_library)
        self.dungeon.game_state = self
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
        self.section_spell_effects = []
        self.expedition_followers = {
            "maiden": False,
            "man_at_arms": False,
            "rogue": False,
        }
        self.last_expedition_summary = None
        self.pending_board_action = None
        self.ambush_counter_played_this_combat_turn = False
        self.combat_escape_pending_closed_door = False
        self.combat_pursuit_active = False
        self.combat_escape_closed_doors = []
        self.left_behind_treasure = []
        self.active_fireball_traps = []
        
        # Initialize movement tracking
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "EXPLORATION")
            for h in self.party
        }
        self.hero_has_attacked.clear()
        self.hero_ran_this_phase.clear()
        self._capture_hero_turn_start_positions()
        
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
            hero.death_turn = None
            hero.pending_fate_decision = None

        self.entered_tiles = {(hero.x, hero.y) for hero in self.party}
        self._capture_hero_turn_start_positions()
        self._snapshot_party_turn_state()
        
        self.save_game()

    @staticmethod
    def _quest_uses_specific_stairs_down(quest_id: Optional[str]) -> bool:
        """Whether a quest overrides random stairs-down results."""
        if not quest_id:
            return False
        normalized = str(quest_id).lower().replace(" ", "_").replace("-", "_")
        return normalized in {"shattered_amulet", "quest_for_the_shattered_amulet"}

    def register_heroquest_maze_entry(self, room: dict, anchor: Optional[Tuple[int, int]]) -> dict:
        """Record a trapdoor entrance to a Heroquest maze sub-level."""
        entry = {
            "type": "heroquest_maze",
            "source": "trapdoor",
            "room_id": room.get("id"),
            "origin_level": self.dungeon.level if self.dungeon else None,
            "origin_anchor": [anchor[0], anchor[1]] if anchor is not None else None,
        }
        self.pending_sub_level_entry = dict(entry)
        return entry

    def enter_heroquest_maze_sub_level(self, hero: Hero, room: dict) -> str:
        """Move the expedition onto the Heroquest maze sub-level opened by a trapdoor."""
        from hazards import get_hazard_anchor, is_adjacent_or_same

        if self.dungeon is None:
            return "There is no dungeon to descend from."
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "trapdoor" or hazard.get("opened_result") != "maze":
            return "There is no maze sub-level entrance here."
        if not hazard.get("maze_sub_level_available"):
            return "The trapdoor does not lead to a usable maze sub-level."
        if hazard.get("maze_sub_level_entered"):
            return "The party has already entered this maze sub-level."
        anchor = get_hazard_anchor(room)
        if not is_adjacent_or_same(hero, anchor, self.dungeon):
            return "Move next to the trapdoor before entering the maze sub-level."

        old_level = self.dungeon.level
        entry = dict(hazard.get("maze_sub_level_entry") or self.pending_sub_level_entry or {})
        if not entry:
            entry = self.register_heroquest_maze_entry(room, anchor)

        self.dungeon_debug_log = []
        self.monsters = []
        self.dungeon = Dungeon(
            level=old_level + 1,
            debug_log=self.dungeon_debug_log,
            monster_library=self.monster_library,
        )
        self.dungeon.game_state = self
        self.dungeon._on_monster_placed = lambda m: self.monsters.append(m)
        start_x, start_y = self.dungeon.hero_start
        for index, party_hero in enumerate(self.party):
            party_hero.x = start_x + (index % 2)
            party_hero.y = start_y + (index // 2)
        self.mode = "DUNGEON"
        self.current_phase = "EXPLORATION"
        self.hero_phase_active = True
        self.hero_movement_remaining = {
            party_hero.id: self._get_movement_allowance_for_phase(party_hero, "EXPLORATION")
            for party_hero in self.party
        }
        self.hero_has_attacked.clear()
        self.hero_ran_this_phase.clear()
        self.entered_tiles = {(party_hero.x, party_hero.y) for party_hero in self.party}
        self._capture_hero_turn_start_positions()
        self._snapshot_party_turn_state()

        hazard["maze_sub_level_entered"] = True
        self.pending_sub_level_entry = None
        self.active_sub_level = {
            "type": "heroquest_maze",
            "source": "trapdoor",
            "origin_level": entry.get("origin_level", old_level),
            "origin_anchor": entry.get("origin_anchor"),
            "dungeon_level": self.dungeon.level,
        }
        self.combat_log.append(f"The party descends into a Heroquest maze sub-level below dungeon level {old_level}.")
        self.save_game()
        return f"Entered Heroquest maze sub-level below dungeon level {old_level}."

    def _capture_hero_turn_start_positions(self):
        """Remember where each hero started the current hero phase."""
        self.hero_turn_start_positions = {
            hero.id: (hero.x, hero.y)
            for hero in self.party
            if not hero.is_dead
        }

    def _snapshot_party_turn_state(self):
        """Record turn-start wound state for Fate handling."""
        for hero in self.party:
            if not hero.is_dead:
                hero.start_turn_snapshot()

    def _draw_dungeon_counter(self, reason: str) -> Optional[str]:
        """Draw and resolve a dungeon counter outside the GM-phase roll."""
        if not self.dungeon_counter_pool:
            self.dungeon_counter_pool.extend(create_dungeon_counter_pool())
        counter = self.dungeon_counter_pool.pop()
        self.combat_log.append(f"{reason} Dungeon Counter drawn: {counter}")
        self._resolve_dungeon_counter(counter)
        return counter

    def _play_held_trap_counter(
        self,
        hero: Hero,
        source: str,
        trap_pos: Optional[Tuple[int, int]] = None,
        previous_pos: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """Play one held trap counter when its trigger condition is met."""
        try:
            index = self.held_dungeon_counters.index("trap")
        except ValueError:
            return False

        del self.held_dungeon_counters[index]
        source_label = "opening a chest" if source == "chest" else "stepping onto an unentered square"
        self.combat_log.append(f"Held trap counter played on {hero.name} after {source_label}.")
        resolve_trap_event(
            hero=hero,
            dungeon=self.dungeon,
            log=self.combat_log,
            start_wandering_combat=lambda trigger_tile, placement_mode="section": self._start_combat_random(
                roll_lair_encounter(), trigger_tile=trigger_tile, placement_mode=placement_mode
            ),
            resolve_magic_spell=lambda trapped_hero, spell_name, trap_origin=None: self._resolve_magic_trap_spell(
                trapped_hero, spell_name, trap_origin
            ),
            source="chest" if source == "chest" else "room_or_passage",
            trap_pos=trap_pos,
            affected_heroes=self.party,
        )
        if source == "movement" and trap_pos is not None and previous_pos is not None:
            marker = self.dungeon.trap_markers.get(trap_pos)
            if marker and marker.get("type") == "visible_trap_zone":
                hero.x, hero.y = previous_pos
                self.combat_log.append(f"{hero.name} pulls back before entering the armed trap area.")
        return True

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

    def award_party_gold(self, amount: int, source: str, note_pos: Optional[Tuple[int, int]] = None) -> tuple[int, int]:
        """Distribute expedition gold up to the party carry cap and return awarded/left behind."""
        living = [hero for hero in self.party if not hero.is_dead]
        if amount <= 0 or not living:
            return 0, 0

        awarded = self._distribute_party_gold_without_recording(amount)
        left = amount - awarded
        if left > 0:
            entry = {"source": source, "gold": left}
            if note_pos is not None:
                entry["pos"] = [note_pos[0], note_pos[1]]
            self.left_behind_treasure.append(entry)
            self.combat_log.append(f"{left} gold crowns are left behind at {note_pos or source} due to carry limits.")
        if awarded > 0:
            self.gold_found += awarded
        return awarded, left

    def _distribute_party_gold_without_recording(self, amount: int) -> int:
        """Distribute gold to living heroes without creating a left-behind note."""
        living = [hero for hero in self.party if not hero.is_dead]
        if amount <= 0 or not living:
            return 0

        awarded = 0
        for hero in sorted(living, key=lambda current: current.gold):
            _, capacity = hero.can_carry_gold(amount - awarded)
            if capacity <= 0:
                continue
            carried = min(capacity, amount - awarded)
            hero.gold += carried
            awarded += carried
            if awarded >= amount:
                break
        return awarded

    def _record_left_behind_treasure(
        self,
        source: str,
        note_pos: Optional[Tuple[int, int]] = None,
        *,
        gold: int = 0,
        item: Optional[dict] = None,
        supply_key: Optional[str] = None,
        ammo_type: Optional[str] = None,
        ammo_count: int = 0,
        spellbook_spells: Optional[List[str]] = None,
        spell_components: Optional[dict] = None,
    ) -> dict:
        """Record treasure or items that must be left on the expedition map."""
        entry = {"source": source}
        if note_pos is not None:
            entry["pos"] = [int(note_pos[0]), int(note_pos[1])]
        if gold > 0:
            entry["gold"] = int(gold)
        if item is not None:
            entry["item"] = dict(item)
            entry["description"] = str(item.get("name", "item"))
        if supply_key:
            entry["supply_key"] = str(supply_key)
            entry["description"] = str(supply_key).replace("_", " ")
        if ammo_type and ammo_count > 0:
            entry["ammo_type"] = str(ammo_type)
            entry["ammo_count"] = int(ammo_count)
            entry["description"] = f"{ammo_count} {ammo_type}"
        if spellbook_spells:
            spells = [str(spell) for spell in spellbook_spells if str(spell).strip()]
            if spells:
                entry["spellbook_spells"] = spells
                entry["description"] = "Spell Book"
        if spell_components:
            components = {
                str(spell): int(count)
                for spell, count in dict(spell_components).items()
                if int(count) > 0
            }
            if components:
                entry["spell_components"] = components
                if "description" not in entry:
                    entry["description"] = "Spell Components"
        self.left_behind_treasure.append(entry)
        return entry

    def get_left_behind_treasure_at(self, pos: Tuple[int, int]) -> List[dict]:
        """Return all left-behind treasure entries recorded at a tile."""
        px, py = int(pos[0]), int(pos[1])
        return [
            entry for entry in self.left_behind_treasure
            if isinstance(entry.get("pos"), list)
            and len(entry["pos"]) == 2
            and int(entry["pos"][0]) == px
            and int(entry["pos"][1]) == py
        ]

    def collect_left_behind_treasure_at(self, hero: Hero, pos: Tuple[int, int]) -> str:
        """Collect any recorded left-behind treasure from a mapped location."""
        entries = list(self.get_left_behind_treasure_at(pos))
        if not entries:
            return "There is no recorded treasure left here."

        messages: List[str] = []
        remaining_entries: List[dict] = []
        for entry in entries:
            leftover = dict(entry)
            collected_any = False

            gold = int(leftover.get("gold", 0))
            if gold > 0:
                awarded = self._distribute_party_gold_without_recording(gold)
                still_left = gold - awarded
                if awarded > 0:
                    self.gold_found += awarded
                if awarded > 0:
                    messages.append(f"The party recovers {awarded} gold crowns.")
                    collected_any = True
                if still_left > 0:
                    leftover["gold"] = still_left
                else:
                    leftover.pop("gold", None)

            item = leftover.get("item")
            if isinstance(item, dict):
                can_carry, _reason = hero.can_carry_equipment_item(item)
                if can_carry:
                    hero.equipment.append(dict(item))
                    self.hero_manager.update_hero(hero)
                    messages.append(f"{hero.name} takes {item.get('name', 'an item')}.")
                    collected_any = True
                    leftover.pop("item", None)
                else:
                    messages.append(f"{hero.name} still cannot carry {item.get('name', 'that item')}.")

            supply_key = leftover.get("supply_key")
            if isinstance(supply_key, str):
                can_carry, _reason = hero.can_carry_supply_item(supply_key)
                if can_carry:
                    hero.add_inventory_item(supply_key, 1)
                    self.hero_manager.update_hero(hero)
                    messages.append(f"{hero.name} takes {supply_key.replace('_', ' ')}.")
                    collected_any = True
                    leftover.pop("supply_key", None)
                else:
                    messages.append(f"{hero.name} still cannot carry {supply_key.replace('_', ' ')}.")

            ammo_type = leftover.get("ammo_type")
            ammo_count = int(leftover.get("ammo_count", 0))
            if isinstance(ammo_type, str) and ammo_count > 0:
                hero.add_ammo(ammo_type, ammo_count)
                self.hero_manager.update_hero(hero)
                messages.append(f"{hero.name} recovers {ammo_count} {ammo_type}.")
                collected_any = True
                leftover.pop("ammo_type", None)
                leftover.pop("ammo_count", None)

            spellbook_spells = leftover.get("spellbook_spells")
            if isinstance(spellbook_spells, list):
                if hero.is_wizard():
                    learned: List[str] = []
                    for spell in spellbook_spells:
                        spell_name = str(spell).strip()
                        if spell_name and not hero.knows_spell(spell_name):
                            hero.known_spells.append(spell_name)
                            hero.spell_components.setdefault(spell_name, 0)
                            learned.append(spell_name)
                    if learned:
                        self.hero_manager.update_hero(hero)
                        messages.append(f"{hero.name} copies {'; '.join(learned)} from the spell book.")
                        collected_any = True
                        leftover.pop("spellbook_spells", None)
                    else:
                        messages.append(f"{hero.name} finds no new spells in that spell book.")
                else:
                    messages.append(f"{hero.name} cannot use the spell book.")

            spell_components = leftover.get("spell_components")
            if isinstance(spell_components, dict):
                if hero.is_wizard():
                    for spell_name, count in spell_components.items():
                        clean_name = str(spell_name).strip()
                        if clean_name:
                            hero.spell_components[clean_name] = int(hero.spell_components.get(clean_name, 0)) + int(count)
                    self.hero_manager.update_hero(hero)
                    messages.append(f"{hero.name} takes the spell components.")
                    collected_any = True
                    leftover.pop("spell_components", None)
                else:
                    messages.append(f"{hero.name} cannot make use of the spell components.")

            if any(key in leftover for key in ("gold", "item", "supply_key", "ammo_type", "spellbook_spells", "spell_components")):
                remaining_entries.append(leftover)
            elif not collected_any:
                remaining_entries.append(leftover)

        self.left_behind_treasure = [
            entry for entry in self.left_behind_treasure
            if entry not in entries
        ] + remaining_entries

        if not messages:
            return "The party cannot carry anything left here."
        return " ".join(messages)

    def tavern_train_hero(self, hero: Hero, stat_key: str) -> str:
        """Apply a between-expedition training action and persist the hero."""
        if hero.is_henchman:
            return f"{hero.name} is a henchman and cannot train like a hero."
        result = train_hero_stat(hero, stat_key)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_increase_fate(self, hero: Hero) -> str:
        """Increase Fate between expeditions and persist the hero."""
        if hero.is_henchman:
            return f"{hero.name} is a henchman and cannot gain Fate this way."
        result = increase_hero_fate(hero)
        if "increases Fate by 1" in result:
            self._grant_attracted_henchman(hero)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_buy_equipment(self, hero: Hero, item_key: str) -> str:
        """Buy equipment between expeditions and persist the hero."""
        result = buy_between_expedition_equipment(hero, item_key)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_buy_supply(self, hero: Hero, item_key: str) -> str:
        """Buy expedition supplies between expeditions and persist the hero."""
        result = buy_between_expedition_supply(hero, item_key)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_buy_ammo(self, hero: Hero, ammo_key: str) -> str:
        """Buy ammunition bundles between expeditions and persist the hero."""
        result = buy_ammo_bundle(hero, ammo_key)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_buy_spell(self, hero: Hero, spell_key: str) -> str:
        """Buy a wizard spell between expeditions and persist the hero."""
        if hero.is_henchman:
            return f"{hero.name} is a henchman and cannot study wizard spells."
        result = buy_spell(hero, spell_key)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_buy_spell_component(self, hero: Hero, spell_name: str) -> str:
        """Buy one spell component between expeditions and persist the hero."""
        if hero.is_henchman:
            return f"{hero.name} is a henchman and cannot buy spell components."
        result = buy_spell_component(hero, spell_name)
        self.hero_manager.update_hero(hero)
        return result

    def tavern_deposit_gold(self, hero: Hero, amount: Optional[int] = None) -> str:
        """Deposit carried gold into the shared expedition stash."""
        if amount is None:
            amount = int(hero.gold)
        amount = max(0, min(int(amount), int(hero.gold)))
        if amount <= 0:
            return f"{hero.name} has no gold to deposit."
        hero.gold -= amount
        self.party_stash_gold += amount
        self.hero_manager.update_hero(hero)
        return f"{hero.name} deposits {amount} gold crowns into the stash."

    def tavern_withdraw_gold(self, hero: Hero, amount: int = 250) -> str:
        """Withdraw gold from the shared stash up to the hero's carry limit."""
        carry_space = max(0, 250 - int(hero.gold))
        if carry_space <= 0:
            return f"{hero.name} cannot carry any more gold."
        amount = max(0, min(int(amount), int(self.party_stash_gold), carry_space))
        if amount <= 0:
            return "There is no stash gold available to withdraw."
        hero.gold += amount
        self.party_stash_gold -= amount
        self.hero_manager.update_hero(hero)
        return f"{hero.name} withdraws {amount} gold crowns from the stash."

    def tavern_hire_henchman(self, employer: Hero, henchman_type: str) -> str:
        """Hire a henchman between expeditions."""
        if employer.is_henchman:
            return "Henchmen cannot hire followers of their own."
        kind = str(henchman_type).strip().lower()
        cost = 50 if kind == "man_at_arms" else 100 if kind == "sergeant" else None
        if cost is None:
            return "Unknown henchman type."
        if employer.gold < cost:
            return f"{employer.name} needs {cost} gold crowns."
        employer.gold -= cost
        henchman = create_henchman(kind, employer_id=employer.id, attracted=False)
        self.hero_manager.update_hero(employer)
        self.hero_manager.update_hero(henchman)
        return f"{employer.name} hires {henchman.name} for {cost} gold crowns."

    def tavern_swap_henchmen_for_sergeant(self, employer: Hero) -> str:
        """Swap two Men-at-Arms owned by a hero for one Sergeant."""
        if employer.is_henchman:
            return "Henchmen cannot command other henchmen."
        owned = [
            hero for hero in self.hero_manager.get_all_heroes()
            if hero.is_henchman and hero.employer_id == employer.id and hero.henchman_type == "man_at_arms"
        ]
        if len(owned) < 2:
            return f"{employer.name} needs two Men-at-Arms to make the swap."
        first, second = owned[:2]
        self.hero_manager.delete_hero(first.id)
        self.hero_manager.delete_hero(second.id)
        sergeant = create_henchman("sergeant", employer_id=employer.id, attracted=False)
        self.hero_manager.update_hero(sergeant)
        return f"{employer.name} swaps two Men-at-Arms for a Sergeant."

    def _grant_attracted_henchman(self, employer: Hero):
        """Grant a free attracted Man-at-Arms when a hero gains Fate."""
        henchman = create_henchman("man_at_arms", employer_id=employer.id, attracted=True)
        self.hero_manager.update_hero(henchman)

    def _apply_henchman_upkeep(self) -> List[str]:
        """Pay henchmen between expeditions or dismiss those who cannot be maintained."""
        messages: List[str] = []
        roster = list(self.hero_manager.get_all_heroes())
        for henchman in [hero for hero in roster if hero.is_henchman]:
            employer = self.hero_manager.get_hero(str(henchman.employer_id)) if henchman.employer_id else None
            if employer is None or employer.is_dead:
                self.hero_manager.delete_hero(henchman.id)
                messages.append(f"{henchman.name} leaves because their employer is gone.")
                continue
            upkeep = int(henchman.upkeep_cost)
            if employer.gold >= upkeep:
                employer.gold -= upkeep
                self.hero_manager.update_hero(employer)
                messages.append(f"{employer.name} pays {upkeep} gold crowns to maintain {henchman.name}.")
            else:
                self.hero_manager.delete_hero(henchman.id)
                messages.append(f"{henchman.name} leaves because {employer.name} cannot pay {upkeep} gold crowns.")
        return messages

    def finalize_between_expeditions(self) -> List[str]:
        """Apply automatic between-expedition bookkeeping once per returned expedition."""
        if not self.last_expedition_summary or self.last_expedition_summary.get("between_expeditions_processed"):
            return []
        messages: List[str] = []
        for hero in self.party:
            if hero.is_dead:
                continue
            if hero.gold > 250:
                excess = int(hero.gold) - 250
                hero.gold = 250
                self.party_stash_gold += excess
                self.hero_manager.update_hero(hero)
                messages.append(f"{hero.name} deposits {excess} excess gold crowns into the stash.")
        if self.expedition_followers.get("man_at_arms"):
            leader = next((hero for hero in self.party if hero.is_true_hero() and not hero.is_dead), None)
            if leader is not None:
                henchman = create_henchman("man_at_arms", employer_id=leader.id, attracted=True)
                self.hero_manager.update_hero(henchman)
                messages.append(f"{henchman.name} joins {leader.name} as a henchman.")
        if self.expedition_followers.get("rogue"):
            leader = next((hero for hero in self.party if hero.is_true_hero() and not hero.is_dead), None)
            if leader is not None and not any("leaves peacefully" in msg.lower() or "slips away" in msg.lower() for msg in self.last_expedition_summary.get("messages", [])):
                rogue = create_henchman("rogue", employer_id=leader.id, attracted=True, name="Rogue")
                self.hero_manager.update_hero(rogue)
                messages.append(f"The Rogue remains with {leader.name} as a Sergeant henchman.")
        messages.extend(self._apply_henchman_upkeep())
        self.last_expedition_summary["between_expeditions_processed"] = True
        self.last_expedition_summary.setdefault("messages", []).extend(messages)
        return messages

    def tavern_use_healer(self, hero: Hero, service_key: str) -> str:
        """Use a healer service between expeditions and persist the hero."""
        result = use_healer_service(hero, service_key)
        self.hero_manager.update_hero(hero)
        return result

    def get_last_expedition_summary(self) -> Optional[dict]:
        """Return the most recent expedition summary, if any."""
        return dict(self.last_expedition_summary) if isinstance(self.last_expedition_summary, dict) else None

    def get_pending_fate_hero(self) -> Optional[Hero]:
        """Return the hero currently awaiting a Fate decision, if any."""
        return fate_get_pending_fate_hero(self.party)

    def has_pending_fate_decision(self) -> bool:
        """Whether any hero is awaiting a Fate decision."""
        return fate_has_pending_fate_decision(self.party)

    def resolve_pending_fate(self, use_fate: bool) -> str:
        """Resolve the current pending Fate decision."""
        return fate_resolve_pending_fate(self, use_fate)

    def _build_equipment_item_from_key(self, item_key: str, *, equipped: bool = False) -> Optional[dict]:
        """Construct an equipment item dict from the tables entry."""
        tables_path = Path(__file__).parent / "data" / "tables.json"
        if not tables_path.exists():
            return None
        with open(tables_path, "r", encoding="utf-8") as handle:
            tables = json.load(handle)
        data = dict(tables.get("equipment", {}).get(item_key, {}))
        if not data:
            return None
        item = {
            "key": item_key,
            "name": data.get("display_name", item_key.replace("_", " ").title()),
            "type": data.get("type", "weapon"),
            "equipped": equipped,
        }
        for field in (
            "damage_dice",
            "strength_damage",
            "two_handed",
            "critical",
            "fumble",
            "long_reach",
            "max_range",
            "move_and_fire",
            "min_strength",
            "requires_reload",
            "starts_loaded",
            "armour_value",
            "bs_modifier",
            "speed_modifier",
            "notes",
            "wizard_usable",
            "toughness_bonus",
            "strength_bonus",
            "ws_bonus",
            "bs_bonus",
            "speed_bonus",
        ):
            if field in data:
                item[field] = data[field]
        if item.get("requires_reload"):
            item["loaded"] = bool(data.get("starts_loaded", True))
        return item

    def _award_equipment_item(
        self,
        hero: Hero,
        item: dict,
        source: str,
        *,
        note_pos: Optional[Tuple[int, int]] = None,
    ) -> str:
        """Give a non-stackable item to a hero if they can carry it."""
        can_carry, reason = hero.can_carry_equipment_item(item)
        if not can_carry:
            self._record_left_behind_treasure(source, note_pos, item=item)
            self.combat_log.append(
                f"{hero.name} cannot carry {item.get('name', 'the item')}: {reason} It is left behind on the map."
            )
            return f"{reason} It is left behind."
        hero.equipment.append(dict(item))
        self.hero_manager.update_hero(hero)
        item_name = str(item.get("name", "item"))
        self.combat_log.append(f"{hero.name} gains {item_name} from {source}.")
        return f"{hero.name} gains {item_name}."

    def _award_supply_item(
        self,
        hero: Hero,
        item_key: str,
        source: str,
        *,
        note_pos: Optional[Tuple[int, int]] = None,
    ) -> str:
        """Give a stackable supply item to a hero if legal."""
        can_carry, reason = hero.can_carry_supply_item(item_key)
        if not can_carry:
            self._record_left_behind_treasure(source, note_pos, supply_key=item_key)
            self.combat_log.append(
                f"{hero.name} cannot carry {item_key.replace('_', ' ')}: {reason} It is left behind on the map."
            )
            return f"{reason} It is left behind."
        hero.add_inventory_item(item_key, 1)
        self.hero_manager.update_hero(hero)
        self.combat_log.append(f"{hero.name} gains {item_key.replace('_', ' ')} from {source}.")
        return f"{hero.name} gains {item_key.replace('_', ' ')}."

    def _award_spellbook_loot(
        self,
        hero: Hero,
        spells: List[str],
        source: str,
        *,
        note_pos: Optional[Tuple[int, int]] = None,
    ) -> str:
        """Award monster-carried spellbook knowledge to a wizard, or leave it behind."""
        clean_spells = [str(spell).strip() for spell in spells if str(spell).strip()]
        if not clean_spells:
            return ""
        if not hero.is_wizard():
            self._record_left_behind_treasure(source, note_pos, spellbook_spells=clean_spells)
            self.combat_log.append(f"{hero.name} cannot use the spell book from {source}. It is left behind on the map.")
            return "The spell book is left behind."
        learned: List[str] = []
        for spell_name in clean_spells:
            if not hero.knows_spell(spell_name):
                hero.known_spells.append(spell_name)
                hero.spell_components.setdefault(spell_name, 0)
                learned.append(spell_name)
        if learned:
            self.hero_manager.update_hero(hero)
            self.combat_log.append(f"{hero.name} copies {'; '.join(learned)} from {source}'s spell book.")
            return f"{hero.name} copies {'; '.join(learned)}."
        self._record_left_behind_treasure(source, note_pos, spellbook_spells=clean_spells)
        self.combat_log.append(f"{hero.name} finds no new spells in {source}'s spell book.")
        self.combat_log.append("The spell book is left behind so another wizard can study it later.")
        return f"{hero.name} finds no new spells. The spell book is left behind."

    def _award_spell_components_loot(
        self,
        hero: Hero,
        components: dict,
        source: str,
        *,
        note_pos: Optional[Tuple[int, int]] = None,
    ) -> str:
        """Award monster-carried spell components, or leave them behind for later."""
        clean_components = {
            str(spell): int(count)
            for spell, count in dict(components).items()
            if str(spell).strip() and int(count) > 0
        }
        if not clean_components:
            return ""
        if not hero.is_wizard():
            self._record_left_behind_treasure(source, note_pos, spell_components=clean_components)
            self.combat_log.append(f"{hero.name} cannot use the spell components from {source}. They are left behind on the map.")
            return "The spell components are left behind."
        for spell_name, count in clean_components.items():
            hero.spell_components[spell_name] = int(hero.spell_components.get(spell_name, 0)) + int(count)
        self.hero_manager.update_hero(hero)
        self.combat_log.append(f"{hero.name} recovers spell components from {source}.")
        return f"{hero.name} recovers spell components."

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
            bonus_roll = random.randint(1, 12)
            if bonus_roll >= 10:
                loot["magic"] = True
            elif bonus_roll >= 7:
                loot["item"] = "healing_potion"
        elif room_kind == "lair":
            loot = {"gold": random.randint(3, 8) * 10}
            bonus_roll = random.randint(1, 12)
            if bonus_roll >= 11:
                loot["magic"] = True
            elif bonus_roll >= 8:
                loot["item"] = random.choice(["healing_potion", "rope_10ft", "iron_spikes_10"])
        else:
            loot = {"gold": random.randint(1, 6) * 5}
            bonus_roll = random.randint(1, 12)
            if bonus_roll == 12:
                loot["magic"] = True
            elif bonus_roll >= 10:
                loot["item"] = "healing_potion"
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
        self._play_held_trap_counter(hero, source="chest", trap_pos=(x, y))
        chest_marker = self.dungeon.trap_markers.get((x, y))
        if chest_marker and chest_marker.get("type") == "visible_trap_zone":
            return "A spotted trap blocks the chest. It must be disarmed before the chest can be opened."
        if room.get("chest_trapped") and not room.get("chest_trap_resolved"):
            room["chest_trap_resolved"] = True
            resolve_trap_event(
                hero,
                self.dungeon,
                self.combat_log,
                lambda *_: None,
                resolve_magic_spell=lambda trapped_hero, spell_name, trap_origin=None: self._resolve_magic_trap_spell(
                    trapped_hero, spell_name, trap_origin
                ),
                source="chest",
                can_spot=False,
                can_disarm=False,
                trap_pos=(x, y),
                affected_heroes=self.party,
            )
            messages.append("The chest is trapped!")

        if hero.is_dead:
            return " ".join(messages) if messages else f"{hero.name} is killed by the chest trap."

        loot = self._roll_room_chest_contents(room)
        gold = int(loot.get("gold", 0))
        if gold > 0:
            awarded, left = self.award_party_gold(gold, "chest", note_pos=(x, y))
            if awarded > 0:
                messages.append(f"The party recovers {awarded} gold crowns from the chest.")
            if left > 0:
                room["left_behind_gold"] = int(room.get("left_behind_gold", 0)) + left
                messages.append(f"{left} gold crowns must be left behind here.")
        if loot.get("magic"):
            treasure_log: List[str] = []
            item = generate_magic_treasure(hero, treasure_log, game=self, source="opened chest", note_pos=(x, y))
            for entry in treasure_log:
                self.combat_log.append(entry)
            messages.append(f"The chest also contains magical treasure: {item.get('name', 'Unknown')}.")
        item_key = loot.get("item")
        if item_key == "healing_potion":
            potion = {
                "name": "Healing Potion",
                "type": "potion",
                "potion_effect": "healing",
                "equipped": False,
            }
            self._award_equipment_item(hero, potion, "the opened chest", note_pos=(x, y))
            messages.append(f"{hero.name} also finds a Healing Potion.")
        elif isinstance(item_key, str):
            self._award_supply_item(hero, item_key, "the opened chest", note_pos=(x, y))
            messages.append(f"{hero.name} also finds {item_key.replace('_', ' ')}.")

        if gold <= 0 and not loot.get("magic") and not item_key:
            messages.append("The chest is empty.")

        room["chest_opened"] = True
        self.dungeon.treasure[(x, y)] = True
        self.dungeon.grid[(x, y)] = self.dungeon.TileType.TREASURE_OPEN
        return " ".join(messages)

    def set_next_portcullis_placement(self, positions: List[Tuple[int, int]]) -> str:
        """Queue the GM's chosen portcullis line for the next portcullis trap."""
        self.next_portcullis_placement = [(int(x), int(y)) for x, y in positions]
        return "Next portcullis placement queued."

    def consume_next_portcullis_placement(
        self,
        trap_location: Tuple[int, int],
        options: List[List[Tuple[int, int]]],
    ) -> Optional[List[Tuple[int, int]]]:
        """Consume a queued GM portcullis line if it is legal for this trap."""
        selected = self.next_portcullis_placement
        self.next_portcullis_placement = None
        if not selected:
            return None
        selected_set = set(selected)
        for option in options:
            if selected_set == set(option):
                self.combat_log.append(f"  GM places the portcullis across {selected}.")
                return selected
        self.combat_log.append(
            f"  Queued portcullis line {selected} is not legal from {trap_location}; using engine placement."
        )
        return None

    def lift_portcullis(self, hero: Hero, x: int, y: int) -> str:
        """Attempt to lift a visible portcullis long enough for others to pass."""
        marker = get_trap_marker(self.dungeon, (x, y), "portcullis")
        if marker is None:
            return "There is no portcullis there."
        zone_data = marker.get("trap_zone", [])
        zone_positions = [
            (int(pos[0]), int(pos[1]))
            for pos in zone_data
            if isinstance(pos, list) and len(pos) == 2
        ] or [(x, y)]

        if not any(
            self.dungeon.is_adjacent(hero.x, hero.y, px, py) or (hero.x, hero.y) == (px, py)
            for px, py in zone_positions
        ):
            return "You must stand next to the portcullis to lift it."

        if self.current_phase != "EXPLORATION":
            return "A portcullis can only be lifted during exploration."
        if hero.is_dead or hero.is_ko or hero.is_under_gm_control() or hero.is_restrained_by_mindstealer():
            return f"{hero.name} cannot help lift the portcullis."

        hero_allowance = self._get_movement_allowance_for_phase(hero, "EXPLORATION")
        hero_remaining = self.hero_movement_remaining.get(hero.id, hero_allowance)
        if hero_remaining != hero_allowance:
            return "Lifting a portcullis takes a full exploration turn; helpers must not have acted or moved."

        participants: List[Hero] = []
        for candidate in self.party:
            if candidate.is_dead or candidate.is_ko or candidate.is_under_gm_control():
                continue
            if not any(
                self.dungeon.is_adjacent(candidate.x, candidate.y, px, py) or (candidate.x, candidate.y) == (px, py)
                for px, py in zone_positions
            ):
                continue
            remaining = self.hero_movement_remaining.get(
                candidate.id,
                self._get_movement_allowance_for_phase(candidate, "EXPLORATION"),
            )
            allowance = self._get_movement_allowance_for_phase(candidate, "EXPLORATION")
            if remaining != allowance:
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
            for pos in zone_positions:
                current_marker = self.dungeon.trap_markers.get(pos)
                if current_marker is None:
                    continue
                current_marker["blocks_movement"] = False
                current_marker["temporary_open"] = True
                current_marker["opened_on_turn"] = self.turn_count
                current_marker["helpers"] = [current.id for current in participants]
            return (
                f"Portcullis lift: {names} heave together. Roll {roll} + Strength {total_strength} = {total}. "
                "The portcullis is lifted for the rest of this hero phase."
            )

        for pos in zone_positions:
            current_marker = self.dungeon.trap_markers.get(pos)
            if current_marker is None:
                continue
            current_marker["blocks_movement"] = True
            current_marker.pop("temporary_open", None)
        if hero.has_fate_available():
            hero.queue_failed_roll_fate_decision(
                "portcullis_lift",
                zone_positions=[[pos[0], pos[1]] for pos in zone_positions],
                lift_roll=roll,
                total_strength=total_strength,
            )
            return (
                f"Portcullis lift: {names} heave together. Roll {roll} + Strength {total_strength} = {total}. "
                f"{hero.name} may spend Fate to force it open."
            )
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
        if hero.has_pending_fate_decision():
            return f"{hero.name} fails the pit leap and must decide whether to spend Fate."
        self.dungeon._explore_from(hero.x, hero.y)
        if (hero.x, hero.y) == landing:
            return f"{hero.name} leaps the pit and lands at {landing}."
        return f"{hero.name} falls into the pit at ({x}, {y})."
    
    def move_hero(self, hero: Hero, x: int, y: int):
        """Move a hero to a new position."""
        if self.has_pending_fate_decision():
            self.combat_log.append("Resolve the pending Fate decision before moving any hero.")
            return False
        self.ensure_phase_consistency()
        can_move, message, dist = self.can_move_hero_to(hero, x, y)
        if not can_move:
            if message:
                self.combat_log.append(message)
            return False

        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))
        lower_room_transition = self._get_lower_room_transition(hero, x, y)
        if lower_room_transition is not None:
            previous_pos = (hero.x, hero.y)
            room = lower_room_transition["room"]
            if lower_room_transition["direction"] == "enter":
                result = resolve_enter_lower_room(hero, room, self, landing=(x, y))
            else:
                result = resolve_leave_lower_room(hero, room, self, landing=(x, y))
            if (hero.x, hero.y) == previous_pos:
                if result:
                    self.combat_log.append(result)
                return False

            self.hero_movement_remaining[hero.id] = remaining - dist
            self.entered_tiles.add((hero.x, hero.y))
            self.combat_log.append(result)
            if lower_room_transition["direction"] == "leave":
                self._check_triggers(hero.x, hero.y)
            elif self.current_phase == "EXPLORATION":
                self._enter_combat_if_monsters_visible()
            self.save_game()
            return True

        path = self._find_hero_path(hero, x, y) or [(hero.x, hero.y), (x, y)]

        # Move
        previous_pos = (hero.x, hero.y)
        hero.x, hero.y = x, y
        first_entry = (x, y) not in self.entered_tiles
        self.entered_tiles.add((x, y))
        
        # Deduct movement points
        self.hero_movement_remaining[hero.id] = remaining - dist

        for step in path[1:]:
            if self._resolve_poisoned_wind_cloud(hero, step):
                self.save_game()
                return True

        if self.current_phase == "EXPLORATION" and first_entry:
            self._play_held_trap_counter(hero, source="movement", trap_pos=(x, y), previous_pos=previous_pos)
            if hero.is_dead or hero.is_ko:
                self.save_game()
                return True
        
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

    def _resolve_poisoned_wind_cloud(self, hero: Hero, pos: Tuple[int, int]) -> bool:
        """Resolve lingering poisoned-wind fumes on entry or movement through a cloud tile."""
        marker = self.dungeon.trap_markers.get(pos)
        if not marker or marker.get("type") != "poisoned_wind_cloud":
            return False
        roll = random.randint(1, 12)
        if roll > hero.intelligence:
            self.combat_log.append(
                f"{hero.name} chokes in poisoned wind at {pos} and fails the breath test ({roll} vs Int {hero.intelligence})!"
            )
            if hero.has_fate_available():
                hero.queue_failed_roll_fate_decision(
                    "poisoned_wind_breath",
                    position=[pos[0], pos[1]],
                    roll=roll,
                )
                self.combat_log.append(f"{hero.name} may spend Fate to turn the failed breath test into a success.")
                return True
            from combat import apply_damage_to_hero
            apply_damage_to_hero(hero, hero.current_wounds, self.combat_log, source="Poisoned Wind")
            return True
        self.combat_log.append(
            f"{hero.name} holds their breath through the poisoned wind at {pos} ({roll} vs Int {hero.intelligence})."
        )
        return False

    def _get_occupied_tiles_for_hero(self, hero: Hero) -> set:
        """Return occupied tiles that block hero movement."""
        occupied = set()
        for other in self.party:
            if other != hero and not other.is_dead and not other.is_ko:
                occupied.add((other.x, other.y))
        for monster in self.monsters:
            if not monster.is_dead:
                occupied.update(monster.get_occupied_tiles())
        return occupied

    def _get_lower_room_exit_candidates(self, room: dict) -> List[Tuple[int, int]]:
        anchor = get_hazard_anchor(room)
        if anchor is None:
            return []
        candidates = [anchor]
        room_tiles = self.dungeon.get_room_interior_tiles(room)
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            pos = (anchor[0] + dx, anchor[1] + dy)
            if pos in room_tiles:
                candidates.append(pos)
        return candidates

    def _get_lower_room_transition(self, hero: Hero, x: int, y: int) -> Optional[dict]:
        """Return lower-room enter/leave transition data for a move target."""
        target = (int(x), int(y))
        current_lower_room = get_lower_room_for_hero(hero, self.dungeon)
        target_lower_room = find_lower_room_for_tile(self.dungeon, x, y)

        if current_lower_room is not None:
            if target_lower_room is current_lower_room:
                return None
            if target not in self._get_lower_room_exit_candidates(current_lower_room):
                return None
            return {"direction": "leave", "room": current_lower_room}

        if target_lower_room is None:
            return None
        return {"direction": "enter", "room": target_lower_room}

    def _can_use_lower_room_transition(self, hero: Hero, x: int, y: int) -> Tuple[bool, str, int]:
        transition = self._get_lower_room_transition(hero, x, y)
        if transition is None:
            return False, "", 0

        target = (int(x), int(y))
        room = transition["room"]
        if transition["direction"] == "enter":
            allowed, message = lower_room_entry_available(hero, room, self)
            if not allowed:
                return False, message, 0
            if target not in get_lower_room_tiles(room):
                return False, "Choose a square in the lower room.", 0
        else:
            allowed, message = lower_room_exit_available(hero, room, self)
            if not allowed:
                return False, message, 0
            if target not in self._get_lower_room_exit_candidates(room):
                return False, "Choose the grate or trapdoor opening to climb out.", 0

        if not self.dungeon.is_walkable(*target):
            tile = self.dungeon.get_tile(*target)
            return False, f"Cannot move to ({target[0]},{target[1]}): tile is {tile.name}", 0
        if target in self._get_occupied_tiles_for_hero(hero):
            return False, "Square occupied!", 0
        return True, "", 1

    def _monster_can_make_melee_attack_from(self, monster: Monster, x: int, y: int) -> bool:
        """Whether a monster at its current tile threatens another tile in melee."""
        return (x, y) in monster.get_death_zone_tiles()

    def _tile_in_enemy_death_zone_for_hero(self, hero: Hero, x: int, y: int) -> bool:
        """Whether the tile is threatened by any living monster."""
        return any(
            not monster.is_dead and self._monster_can_make_melee_attack_from(monster, x, y)
            for monster in self.monsters
        )

    def _path_respects_enemy_death_zones(self, hero: Hero, path: List[Tuple[int, int]]) -> bool:
        """Combat movement must stop when entering an enemy death zone."""
        if self.current_phase != "COMBAT" or len(path) <= 1:
            return True
        currently_in_zone = self._tile_in_enemy_death_zone_for_hero(hero, hero.x, hero.y)
        for index, step in enumerate(path[1:], start=1):
            in_zone = self._tile_in_enemy_death_zone_for_hero(hero, step[0], step[1])
            if in_zone and not currently_in_zone and index != len(path) - 1:
                return False
            currently_in_zone = in_zone
        return True

    def _find_hero_path(self, hero: Hero, x: int, y: int) -> Optional[List[Tuple[int, int]]]:
        """Find a legal movement path for a hero using BFS."""
        occupied = self._get_occupied_tiles_for_hero(hero)
        return find_path_bfs(hero.x, hero.y, x, y, self.dungeon, occupied)

    def get_path_movement_cost(self, path: Optional[List[Tuple[int, int]]]) -> int:
        """Return the exploration/combat movement cost for a path."""
        if not path or len(path) <= 1:
            return 0
        cost = 0
        for step in path[1:]:
            marker = self.dungeon.trap_markers.get(step)
            if marker and marker.get("careful_movement_only"):
                cost += 2
            else:
                cost += 1
        return cost

    def disarm_visible_trap(self, hero: Hero, x: int, y: int) -> str:
        """Attempt to disarm a visible trap marker."""
        if self.current_phase != "EXPLORATION":
            return "Traps may only be disarmed during exploration."
        if not self.dungeon.is_adjacent(hero.x, hero.y, x, y) and (hero.x, hero.y) != (x, y):
            return "You must stand next to the trap to disarm it."
        success = attempt_disarm_trap(hero, self.dungeon, self.combat_log, (x, y))
        self.hero_movement_remaining[hero.id] = 0
        return "Trap disarmed." if success else "Disarm attempt resolved."

    def can_move_hero_to(self, hero: Hero, x: int, y: int) -> Tuple[bool, str, int]:
        """Check whether a hero can legally move to a tile."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first.", 0
        self.ensure_phase_consistency()
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} is dead/KO!", 0

        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control!", 0
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained and cannot move!", 0
        if hero.has_pending_fate_decision():
            return False, f"{hero.name} must resolve their Fate decision first!", 0
        if self.current_phase == "COMBAT" and hero.has_status_effect("cowering"):
            return False, f"{hero.name} is cowering before a fearsome monster and cannot move normally!", 0
        
        # Check remaining movement
        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))
        if remaining <= 0:
            return False, f"{hero.name} has no movement left!", 0

        can_transition, transition_message, transition_dist = self._can_use_lower_room_transition(hero, x, y)
        if transition_message:
            return False, transition_message, transition_dist
        if can_transition:
            if transition_dist > remaining:
                return False, f"Too far! Distance {transition_dist} > remaining movement {remaining}", transition_dist
            return True, "", transition_dist
        
        # Check if walkable
        tile = self.dungeon.get_tile(x, y)
        if not self.dungeon.is_walkable(x, y):
            return False, f"Cannot move to ({x},{y}): tile is {tile.name}", 0

        if (x, y) in self._get_occupied_tiles_for_hero(hero):
            return False, "Square occupied!", 0

        path = self._find_hero_path(hero, x, y)
        if path is None:
            return False, f"Cannot move to ({x},{y}): path is blocked", 0
        if not self._path_respects_enemy_death_zones(hero, path):
            return False, "Movement must stop on entering an enemy death zone.", 0

        dist = self.get_path_movement_cost(path)
        if dist > remaining:
            return False, f"Too far! Distance {dist} > remaining movement {remaining}", dist

        return True, "", dist

    def get_adjacent_ko_allies(self, hero: Hero) -> List[Hero]:
        """Return KO allies adjacent to the hero."""
        return [
            ally for ally in self.party
            if ally.id != hero.id
            and ally.is_ko
            and not ally.is_dead
            and self.dungeon.is_adjacent(hero.x, hero.y, ally.x, ally.y)
        ]

    def can_prepare_ko_move(self, hero: Hero) -> Tuple[bool, str]:
        """Whether the hero may start a KO carry or drag action."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot move anyone right now."
        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control."
        if not self.get_adjacent_ko_allies(hero):
            return False, "No adjacent KO ally to move."
        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))
        if remaining <= 0:
            return False, f"{hero.name} has no movement left."
        if self.current_phase == "COMBAT":
            if hero.id in self.hero_has_attacked:
                return False, f"{hero.name} has already used their combat action."
            if hero.id in self.hero_ran_this_phase:
                return False, f"{hero.name} ran this phase."
        return True, ""

    def can_administer_healing_potion(self, hero: Hero) -> Tuple[bool, str]:
        """Whether the hero can give a Healing Potion to an adjacent KO ally."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot administer a potion."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained."
        if not hero.has_usable_healing_potion():
            return False, f"{hero.name} has no Healing Potion."
        adjacent_ko = self.get_adjacent_ko_allies(hero)
        if not adjacent_ko:
            return False, "No adjacent KO hero needs a potion."
        if self.current_phase == "COMBAT":
            if hero.id in self.hero_has_attacked:
                return False, f"{hero.name} has already used their combat action."
            if hero.id in self.hero_ran_this_phase:
                return False, f"{hero.name} ran this phase."
        if self._tile_in_enemy_death_zone_for_hero(hero, hero.x, hero.y):
            return False, f"{hero.name} is in an enemy death zone."
        for ally in adjacent_ko:
            if self._tile_in_enemy_death_zone_for_hero(ally, ally.x, ally.y):
                return False, f"{ally.name} is in an enemy death zone."
        return True, ""

    def get_adjacent_mad_allies(self, hero: Hero) -> List[Hero]:
        """Return adjacent allies currently under Mindstealer control."""
        return [
            ally for ally in self.party
            if ally.id != hero.id
            and not ally.is_dead
            and ally.has_status_effect("madness")
            and not ally.has_status_effect("madness_restrained")
            and self.dungeon.is_adjacent(hero.x, hero.y, ally.x, ally.y)
        ]

    def can_restrain_mad_hero(self, hero: Hero) -> Tuple[bool, str]:
        """Whether the hero can attempt to restrain an adjacent maddened ally."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot restrain anyone right now."
        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is already helping restrain someone."
        if not self.get_adjacent_mad_allies(hero):
            return False, "No adjacent mad hero can be restrained."
        if self.current_phase == "COMBAT":
            if hero.id in self.hero_has_attacked:
                return False, f"{hero.name} has already used their combat action."
            if hero.id in self.hero_ran_this_phase:
                return False, f"{hero.name} ran this phase."
        elif self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero)) <= 0:
            return False, f"{hero.name} has no actions left this phase."
        return True, ""

    def restrain_mad_hero(self, hero: Hero) -> str:
        """Attempt to restrain an adjacent hero affected by Mindstealer madness."""
        allowed, message = self.can_restrain_mad_hero(hero)
        if not allowed:
            return message
        targets = self.get_adjacent_mad_allies(hero)
        if len(targets) != 1:
            return "Exactly one adjacent mad hero must be available to restrain."
        target = targets[0]
        helpers = [
            ally for ally in self.party
            if not ally.is_dead
            and not ally.is_ko
            and not ally.is_under_gm_control()
            and self.dungeon.is_adjacent(ally.x, ally.y, target.x, target.y)
        ]
        combined_strength = sum(current.get_effective_strength() for current in helpers)
        required_strength = target.get_effective_strength() * 3
        if self.current_phase == "COMBAT":
            self.hero_has_attacked.add(hero.id)
        self.hero_movement_remaining[hero.id] = 0
        if combined_strength < required_strength:
            self.combat_log.append(
                f"{hero.name} tries to restrain {target.name}, but the adjacent allies only total Strength "
                f"{combined_strength} against the required {required_strength}."
            )
            self.save_game()
            return f"The party cannot yet restrain {target.name}."

        madness = target.get_status_effect("madness") or {}
        turns = int(madness.get("turns", 1))
        target.add_status_effect(
            "madness_restrained",
            turns=turns,
            scope=madness.get("scope", "expedition"),
            cannot_move=True,
        )
        self.combat_log.append(
            f"{hero.name} and the nearby allies restrain {target.name} "
            f"(Strength {combined_strength} vs requirement {required_strength})."
        )
        self.hero_manager.update_hero(hero)
        self.hero_manager.update_hero(target)
        self.save_game()
        return f"{target.name} is restrained."

    def prepare_ko_move(self, hero: Hero) -> Tuple[bool, str]:
        """Prepare a board-targeted KO carry/drag action."""
        allowed, message = self.can_prepare_ko_move(hero)
        if not allowed:
            return False, message
        candidates = self.get_adjacent_ko_allies(hero)
        if len(candidates) != 1:
            return False, "Exactly one adjacent KO hero must be available to move them."
        action_type = "drag_ko_hero" if self.current_phase == "COMBAT" else "carry_ko_hero"
        self.pending_board_action = {"type": action_type, "hero_id": hero.id, "target_id": candidates[0].id}
        return True, f"Choose a destination for {candidates[0].name}."

    def _execute_ko_move(self, hero: Hero, target: Hero, x: int, y: int) -> str:
        """Carry or drag a KO ally to a destination."""
        allowed, message = self.can_prepare_ko_move(hero)
        if not allowed:
            return message
        if target.id not in {current.id for current in self.get_adjacent_ko_allies(hero)}:
            return f"{target.name} must stay adjacent to {hero.name}."

        path = self._find_hero_path(hero, x, y)
        if path is None:
            return f"{hero.name} cannot reach that destination while moving {target.name}."
        if not self._path_respects_enemy_death_zones(hero, path):
            return "Movement must stop on entering an enemy death zone."
        distance = self.get_path_movement_cost(path)
        max_distance = 3 if self.current_phase == "COMBAT" else 6
        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero))
        if distance > remaining:
            return f"{hero.name} lacks the movement to get there."
        if distance > max_distance:
            return (
                f"{hero.name} may only drag {target.name} up to 3 squares in combat."
                if self.current_phase == "COMBAT"
                else f"{hero.name} may only carry {target.name} up to 6 squares in exploration."
            )
        if len(path) < 2:
            return "Choose a different destination."

        previous_step = path[-2]
        hero.x, hero.y = x, y
        target.x, target.y = previous_step
        self.hero_movement_remaining[hero.id] = remaining - distance
        if self.current_phase == "COMBAT":
            self.hero_movement_remaining[hero.id] = 0
            action_label = "drags"
        else:
            self.hero_movement_remaining[hero.id] = 0
            action_label = "carries"
        self.pending_board_action = None
        self.dungeon._explore_from(hero.x, hero.y)
        self.combat_log.append(f"{hero.name} {action_label} {target.name} to ({hero.x}, {hero.y}).")
        self.save_game()
        return f"{hero.name} {action_label} {target.name}."

    def give_healing_potion_to_ko(self, hero: Hero) -> str:
        """Administer a Healing Potion to a single adjacent KO ally."""
        allowed, message = self.can_administer_healing_potion(hero)
        if not allowed:
            return message
        targets = self.get_adjacent_ko_allies(hero)
        if len(targets) != 1:
            return "Exactly one adjacent KO hero must be available to administer a potion."
        target = targets[0]
        if target.has_pending_healing_potion():
            return f"{target.name} is already waiting for a Healing Potion to take effect."
        if not hero.consume_healing_potion():
            return f"{hero.name} has no Healing Potion."
        target.queue_healing_potion_recovery()
        if self.current_phase == "COMBAT":
            self.hero_has_attacked.add(hero.id)
        self.hero_movement_remaining[hero.id] = 0
        self.hero_manager.update_hero(hero)
        self.hero_manager.update_hero(target)
        self.save_game()
        return f"{hero.name} gives a Healing Potion to {target.name}. It will take effect at the start of the next turn."

    def resolve_pending_board_action(self, hero: Hero, x: int, y: int) -> str:
        """Resolve the currently prepared board-targeted action."""
        action = self.pending_board_action or {}
        if not action:
            return "No targeted action is pending."
        if action.get("hero_id") != hero.id:
            return f"{hero.name} is not the selected hero for that action."
        action_type = action.get("type")
        if action_type == "secret_door_search":
            from actions.dungeon_actions import resolve_pending_secret_search

            return resolve_pending_secret_search(hero, self.dungeon, self, (x, y))
        if action_type not in {"carry_ko_hero", "drag_ko_hero"}:
            return "That targeted action is not implemented."
        target = next((current for current in self.party if current.id == action.get("target_id")), None)
        if target is None:
            self.pending_board_action = None
            return "The KO hero is no longer available."
        return self._execute_ko_move(hero, target, x, y)

    def drink_healing_potion(self, hero: Hero) -> str:
        """Drink a healing potion in exploration or combat."""
        if self.has_pending_fate_decision():
            return "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return f"{hero.name} cannot drink a potion."
        if hero.is_restrained_by_mindstealer():
            return f"{hero.name} is being restrained."
        if self.current_phase == "COMBAT":
            if hero.id in self.hero_has_attacked:
                return f"{hero.name} has already used their combat action."
            if hero.id in self.hero_ran_this_phase:
                return f"{hero.name} ran this phase."
        elif self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero)) <= 0:
            return f"{hero.name} has no actions left this phase."
        if not hero.has_usable_healing_potion():
            return f"{hero.name} has no Healing Potion."
        if hero.current_wounds >= hero.max_wounds:
            return f"{hero.name} does not need a Healing Potion right now."
        if hero.has_pending_healing_potion():
            return f"{hero.name} already has a Healing Potion taking effect next turn."
        if not hero.consume_healing_potion():
            return f"{hero.name} has no Healing Potion."
        hero.queue_healing_potion_recovery()
        if self.current_phase == "COMBAT":
            self.hero_has_attacked.add(hero.id)
        self.hero_movement_remaining[hero.id] = 0
        self.hero_manager.update_hero(hero)
        self.save_game()
        return f"{hero.name} drinks a Healing Potion. It will take effect at the start of the next turn."

    def can_drink_strength_potion(self, hero: Hero) -> Tuple[bool, str]:
        """Whether a hero may drink a Strength Potion at the start of this turn."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot drink a potion."
        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained."
        if hero.has_status_effect("strength_potion"):
            return False, f"{hero.name} is already under a Strength Potion."
        if not any(
            item.get("type") == "potion" and item.get("potion_effect") == "strength"
            for item in hero.equipment
        ):
            return False, f"{hero.name} has no Strength Potion."
        if self.current_phase == "COMBAT":
            if hero.id in self.hero_has_attacked:
                return False, f"{hero.name} has already used their combat action."
            if hero.id in self.hero_ran_this_phase:
                return False, f"{hero.name} ran this phase."
        allowance = self._get_movement_allowance_for_phase(hero)
        remaining = self.hero_movement_remaining.get(hero.id, allowance)
        if remaining < allowance:
            return False, "Strength Potions may only be drunk at the start of a turn."
        return True, ""

    def drink_strength_potion(self, hero: Hero) -> str:
        """Drink a Strength Potion and apply its three-turn melee bonus."""
        allowed, message = self.can_drink_strength_potion(hero)
        if not allowed:
            return message
        for index, item in enumerate(hero.equipment):
            if item.get("type") == "potion" and item.get("potion_effect") == "strength":
                del hero.equipment[index]
                hero.add_status_effect(
                    "strength_potion",
                    turns=3,
                    scope="turn",
                    strength_delta=2,
                    bonus_melee_damage_dice=2,
                )
                self.hero_manager.update_hero(hero)
                self.save_game()
                return f"{hero.name} drinks a Strength Potion. Strength and hand-to-hand damage dice are increased for 3 turns."
        return f"{hero.name} has no Strength Potion."
    
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
                if any(self.dungeon._has_los(hero.x, hero.y, mx, my) for mx, my in monster.get_occupied_tiles()):
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

    def ensure_phase_consistency(self) -> bool:
        """Keep phase state aligned with visible monsters and surviving combatants."""
        if self.dungeon is None or self.mode in {"TAVERN", "GAME_OVER"}:
            return False
        if self.current_phase == "EXPLORATION":
            return self._enter_combat_if_monsters_visible()
        if self.current_phase == "COMBAT" and not any(not monster.is_dead for monster in self.monsters):
            self._end_combat()
            return True
        return False

    def hero_attack(self, hero: Hero, monster: Monster) -> bool:
        """Hero attacks a monster."""
        if self.has_pending_fate_decision():
            self.combat_log.append("Resolve the pending Fate decision before acting.")
            return False
        if hero.is_dead or hero.is_ko or monster.is_dead:
            return False

        if hero.is_under_gm_control():
            self.combat_log.append(f"{hero.name} is under GM control and cannot be directed by the player.")
            return False
        if hero.is_restrained_by_mindstealer():
            self.combat_log.append(f"{hero.name} is being restrained and cannot fight.")
            return False
        if hero.has_status_effect("cowering"):
            self.combat_log.append(f"{hero.name} cowers before the fearsome foe and cannot attack this phase.")
            return False
        
        # Check if hero already attacked this phase
        if hero.id in self.hero_has_attacked:
            self.combat_log.append(f"{hero.name} has already attacked this phase!")
            return False

        if self._hero_can_make_melee_attack(hero, monster):
            return self._hero_melee_attack(hero, monster)
        return self._hero_ranged_attack(hero, monster)

    def _hero_melee_attack(self, hero: Hero, monster: Monster) -> bool:
        """Resolve a melee attack and update combat state."""
        resolve_melee_attack(hero, monster, self.combat_log)
        self.hero_has_attacked.add(hero.id)
        self._handle_monster_defeat(monster, killer=hero)
        self.save_game()
        return True

    def _hero_ranged_attack(self, hero: Hero, monster: Monster) -> bool:
        """Resolve a ranged attack and update combat state."""
        can_attack, reason = self.can_hero_make_ranged_attack(hero, monster)
        if not can_attack:
            if reason:
                self.combat_log.append(reason)
            return False
        if not hero.consume_ranged_ammo():
            self.combat_log.append(f"{hero.name} has no ammunition left.")
            return False
        magic_ammo_effect = getattr(hero, "last_ranged_ammo_effect", None)
        if magic_ammo_effect:
            self.combat_log.append(
                f"{hero.name} uses magical ammunition: {str(magic_ammo_effect).replace('_', ' ').title()}."
            )

        los_state, _, _ = get_ranged_los_state_for_models(
            self.dungeon,
            hero,
            monster,
            friendly_models=self.party,
            hostile_models=self.monsters,
        )
        fumble_target = self._get_ranged_fumble_target(monster)
        resolve_hero_ranged_attack(
            hero,
            monster,
            self.combat_log,
            partial_obscured=(los_state == "partial"),
            fumble_target=fumble_target,
            magic_ammo_effect=magic_ammo_effect,
        )
        hero.mark_ranged_weapon_fired()
        self.hero_has_attacked.add(hero.id)
        self._handle_monster_defeat(monster, killer=hero)
        if fumble_target is not None and fumble_target.is_dead:
            self.combat_log.append(f"{fumble_target.name} is downed by friendly fire.")
        self.save_game()
        return True

    def _get_ranged_los_state(
        self,
        attacker_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        *,
        friendly_is_heroes: bool,
    ) -> str:
        """Return `clear`, `partial`, or `blocked` for a ranged line of sight."""
        if friendly_is_heroes:
            friendly_positions = {
                (hero.x, hero.y)
                for hero in self.party
                if not hero.is_dead and (hero.x, hero.y) != attacker_pos and (hero.x, hero.y) != target_pos
            }
            hostile_positions = set()
            for monster in self.monsters:
                if monster.is_dead:
                    continue
                hostile_positions.update(
                    pos for pos in monster.get_occupied_tiles()
                    if pos != attacker_pos and pos != target_pos
                )
        else:
            friendly_positions = set()
            for monster in self.monsters:
                if monster.is_dead:
                    continue
                friendly_positions.update(
                    pos for pos in monster.get_occupied_tiles()
                    if pos != attacker_pos and pos != target_pos
                )
            hostile_positions = {
                (hero.x, hero.y)
                for hero in self.party
                if not hero.is_dead and not hero.is_ko and (hero.x, hero.y) != attacker_pos and (hero.x, hero.y) != target_pos
            }

        adjacent_friendly = {
            pos for pos in friendly_positions
            if abs(pos[0] - attacker_pos[0]) + abs(pos[1] - attacker_pos[1]) == 1
        }
        return self.dungeon.get_los_state(
            attacker_pos[0],
            attacker_pos[1],
            target_pos[0],
            target_pos[1],
            model_blockers=friendly_positions | hostile_positions,
            adjacent_friendly_blockers=adjacent_friendly,
        )

    def _get_ranged_fumble_target(self, target: Monster) -> Optional[Monster]:
        """Pick a model friendly to the original target within two squares of it."""
        candidates = [
            monster for monster in self.monsters
            if monster is not target
            and not monster.is_dead
            and min(
                abs(tx - ox) + abs(ty - oy)
                for tx, ty in target.get_occupied_tiles()
                for ox, oy in monster.get_occupied_tiles()
            ) <= 2
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda monster: (
                min(
                    abs(tx - ox) + abs(ty - oy)
                    for tx, ty in target.get_occupied_tiles()
                    for ox, oy in monster.get_occupied_tiles()
                ),
                monster.name,
            ),
        )

    def can_hero_make_ranged_attack(self, hero: Hero, monster: Monster) -> Tuple[bool, str]:
        """Check whether a hero can make a ranged attack against a monster."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if not hero.has_ranged_weapon():
            return False, f"{hero.name} has no ranged weapon equipped."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained."
        weapon = hero.get_equipped_ranged_weapon() or {}
        weapon_name = str(weapon.get("name", "ranged weapon"))
        if hero.get_effective_strength() < hero.get_ranged_min_strength():
            return False, f"{hero.name} is not strong enough to use {weapon_name}."
        if not hero.is_ranged_weapon_loaded():
            return False, f"{weapon_name} is unloaded. Spend a turn without moving or attacking to reload it."
        ammo_type = hero.get_ranged_ammo_type()
        if ammo_type is not None and not hero.has_ammo_for_ranged_weapon():
            return False, f"{hero.name} has no {ammo_type} left for {weapon_name}."
        los_state, _, target_tile = get_ranged_los_state_for_models(
            self.dungeon,
            hero,
            monster,
            friendly_models=self.party,
            hostile_models=self.monsters,
        )
        if los_state == "blocked":
            return False, f"{hero.name} has no line of sight to {monster.name}."
        if any(self.dungeon.is_adjacent(hero.x, hero.y, mx, my) for mx, my in monster.get_occupied_tiles()):
            return False, f"{hero.name} must use melee against an adjacent monster."
        if self._hero_is_adjacent_to_any_monster(hero):
            return False, f"{hero.name} is engaged in melee and cannot fire."
        if self._monster_is_in_any_enemy_death_zone(monster):
            return False, f"{monster.name} is in melee and cannot be targeted by ranged fire."

        range_distance = abs(hero.x - target_tile[0]) + abs(hero.y - target_tile[1])
        if los_state == "partial":
            range_distance += 4
        if range_distance > hero.get_ranged_max_range():
            return False, f"{monster.name} is out of range for {weapon_name}."

        allowance = self._get_movement_allowance_for_phase(hero)
        remaining = self.hero_movement_remaining.get(hero.id, allowance)
        if not hero.can_move_and_fire_ranged_weapon() and remaining < allowance:
            return False, f"{hero.name} must stand still to fire {weapon_name}."
        return True, ""

    def get_available_spell_options(self, hero: Hero) -> List[dict]:
        """Return spellbook and magic-item casts available to the hero."""
        if hero.is_dead or hero.is_ko or hero.is_under_gm_control():
            return []
        if hero.is_restrained_by_mindstealer():
            return []

        options: List[dict] = []
        seen: set[tuple] = set()

        if hero.can_cast_spells():
            for spell_name in hero.known_spells:
                definition = get_spell_definition(spell_name)
                if definition is None:
                    continue
                key = ("spellbook", normalize_spell_name(spell_name), None, None)
                if key in seen:
                    continue
                seen.add(key)
                options.append({
                    "label": format_spell_source_label(definition["name"], "spellbook"),
                    "spell_name": definition["name"],
                    "source_kind": "spellbook",
                    "item_index": None,
                    "scroll_spell_index": None,
                    "target_mode": definition.get("target_mode", "none"),
                })

        for item_index, item in enumerate(hero.equipment):
            item_type = item.get("type")
            if item_type == "wand" and int(item.get("charges", 0)) > 0:
                spell_name = str(item.get("spell", "")).strip()
                definition = get_spell_definition(spell_name)
                if definition is None:
                    continue
                key = ("wand", normalize_spell_name(spell_name), item_index, None)
                if key in seen:
                    continue
                seen.add(key)
                options.append({
                    "label": format_spell_source_label(definition["name"], "wand", item),
                    "spell_name": definition["name"],
                    "source_kind": "wand",
                    "item_index": item_index,
                    "scroll_spell_index": None,
                    "target_mode": definition.get("target_mode", "none"),
                })
            elif item_type == "scroll":
                for spell_index, spell_name in enumerate(list(item.get("spells", []))):
                    definition = get_spell_definition(str(spell_name))
                    if definition is None:
                        continue
                    key = ("scroll", normalize_spell_name(definition["name"]), item_index, spell_index)
                    if key in seen:
                        continue
                    seen.add(key)
                    options.append({
                        "label": format_spell_source_label(definition["name"], "scroll", item),
                        "spell_name": definition["name"],
                        "source_kind": "scroll",
                        "item_index": item_index,
                        "scroll_spell_index": spell_index,
                        "target_mode": definition.get("target_mode", "none"),
                    })

        return options

    def can_hero_cast_spell(
        self,
        hero: Hero,
        spell_name: str,
        source_kind: str = "spellbook",
        item_index: Optional[int] = None,
        scroll_spell_index: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Check whether a hero can currently cast a specific spell."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot cast while dead or KO."
        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained."
        if hero.id in self.hero_has_attacked:
            return False, f"{hero.name} has already acted this turn."

        definition = get_spell_definition(spell_name)
        if definition is None:
            return False, f"{spell_name} is not implemented."
        if (
            definition.get("blocked_by_enemy_death_zone")
            and self.current_phase == "COMBAT"
            and self._tile_in_enemy_death_zone_for_hero(hero, hero.x, hero.y)
        ):
            return False, f"{hero.name} is in an enemy death zone and cannot cast {definition['name']}."

        if source_kind == "spellbook":
            if not hero.is_wizard():
                return False, f"{hero.name} is not a Wizard."
            if not hero.can_cast_spells():
                return False, f"{hero.name} cannot cast while carrying forbidden weapons or armour."
            if not hero.knows_spell(spell_name):
                return False, f"{hero.name} does not know {spell_name}."
            if hero.free_spell_cast <= 0 and not hero.has_spell_components(spell_name):
                return False, f"{hero.name} has no component left for {spell_name}."
        else:
            if item_index is None or item_index < 0 or item_index >= len(hero.equipment):
                return False, "That magical item is no longer available."
            item = hero.equipment[item_index]
            if item.get("wizard_only") and not hero.is_wizard():
                return False, f"{hero.name} cannot use {item.get('name', 'that item')}."
            if hero.is_wizard() and not hero.can_cast_spells():
                return False, f"{hero.name} cannot use magic while carrying forbidden weapons or armour."
            if source_kind == "wand":
                if int(item.get("charges", 0)) <= 0:
                    return False, f"{item.get('name', 'The wand')} has no charges left."
            elif source_kind == "scroll":
                spells = list(item.get("spells", []))
                if scroll_spell_index is None or scroll_spell_index < 0 or scroll_spell_index >= len(spells):
                    return False, "That scroll spell has already been used."

        required_components = spell_component_count(spell_name)
        if hero.has_status_effect("lost_hand") and required_components >= 2:
            return False, f"{hero.name} cannot cast {spell_name} after losing a hand."
        allowance = self._get_movement_allowance_for_phase(hero)
        remaining = self.hero_movement_remaining.get(hero.id, allowance)
        if required_components >= 2 and remaining < allowance:
            return False, f"{hero.name} must stand still to cast {spell_name}."

        return True, ""

    def cast_spell(
        self,
        hero: Hero,
        spell_name: str,
        target: Optional[Tuple[int, int]] = None,
        source_kind: str = "spellbook",
        item_index: Optional[int] = None,
        scroll_spell_index: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Resolve a spell cast from a spellbook, wand, or scroll."""
        can_cast, message = self.can_hero_cast_spell(hero, spell_name, source_kind, item_index, scroll_spell_index)
        if not can_cast:
            if message:
                self.combat_log.append(message)
            return False, message
        if hero.has_status_effect("cowering"):
            self.combat_log.append(f"{hero.name} cowers before the fearsome foe and cannot cast this phase.")
            return False, f"{hero.name} is cowering."

        definition = get_spell_definition(spell_name)
        if definition is None:
            return False, f"{spell_name} is not implemented."

        success, result = self._resolve_spell_effect(hero, definition, target)
        if not success:
            if result:
                self.combat_log.append(result)
            return False, result

        self._consume_spell_source(hero, definition["name"], source_kind, item_index, scroll_spell_index)
        if spell_component_count(definition["name"]) >= 2:
            self.hero_movement_remaining[hero.id] = 0
        self.hero_has_attacked.add(hero.id)
        self._refresh_hero_death_turns()
        self.hero_manager.update_hero(hero)
        self.save_game()
        self.combat_log.append(result)
        return True, result

    def _consume_spell_source(
        self,
        hero: Hero,
        spell_name: str,
        source_kind: str,
        item_index: Optional[int],
        scroll_spell_index: Optional[int],
    ):
        """Spend the resource used to cast a spell."""
        if source_kind == "spellbook":
            if hero.free_spell_cast > 0:
                hero.free_spell_cast -= 1
            else:
                hero.spend_spell_components(spell_name)
            return

        if item_index is None or item_index < 0 or item_index >= len(hero.equipment):
            return
        item = hero.equipment[item_index]
        if source_kind == "wand":
            item["charges"] = max(0, int(item.get("charges", 0)) - 1)
            return
        if source_kind == "scroll":
            spells = list(item.get("spells", []))
            if scroll_spell_index is None or scroll_spell_index < 0 or scroll_spell_index >= len(spells):
                return
            del spells[scroll_spell_index]
            item["spells"] = spells
            if not spells:
                del hero.equipment[item_index]

    def _get_hero_at(self, x: int, y: int) -> Optional[Hero]:
        """Return the living or fallen hero occupying a tile."""
        for hero in self.party:
            if (hero.x, hero.y) == (x, y):
                return hero
        return None

    def _get_monster_at(self, x: int, y: int) -> Optional[Monster]:
        """Return a living monster occupying a tile."""
        for monster in self.monsters:
            if not monster.is_dead and (x, y) in monster.get_occupied_tiles():
                return monster
        return None

    def collect_left_behind_chest_gold(self, hero: Hero, x: int, y: int) -> str:
        """Collect previously left-behind chest gold from a room."""
        room = self._find_room_with_chest(x, y)
        if room is None:
            return "There is no recorded chest treasure here."
        left = int(room.get("left_behind_gold", 0))
        if left <= 0:
            return "There is no treasure left here."
        awarded = self._distribute_party_gold_without_recording(left)
        remaining = left - awarded
        if awarded > 0:
            self.gold_found += awarded
        room["left_behind_gold"] = remaining
        updated_entries: List[dict] = []
        adjusted = False
        for entry in self.left_behind_treasure:
            if (
                not adjusted
                and entry.get("source") == "chest"
                and isinstance(entry.get("pos"), list)
                and len(entry["pos"]) == 2
                and int(entry["pos"][0]) == x
                and int(entry["pos"][1]) == y
                and int(entry.get("gold", 0)) > 0
            ):
                adjusted = True
                if remaining > 0:
                    revised = dict(entry)
                    revised["gold"] = remaining
                    updated_entries.append(revised)
                continue
            updated_entries.append(entry)
        self.left_behind_treasure = updated_entries
        if awarded <= 0:
            return "The party cannot carry any more gold."
        if remaining > 0:
            return f"The party recovers {awarded} gold crowns, but {remaining} still remain behind."
        return f"The party recovers the remaining {awarded} gold crowns."

    def _get_any_model_at(self, x: int, y: int):
        """Return any model at a tile."""
        hero = self._get_hero_at(x, y)
        if hero is not None:
            return hero
        return self._get_monster_at(x, y)

    def _hero_resists_spell(self, hero: Hero, spell_name: str, caster_name: str) -> bool:
        """Resolve carried-item spell protection against a spell."""
        for item in hero.equipment:
            if not item.get("equipped"):
                continue
            protection = item.get("spell_protection")
            if not isinstance(protection, dict):
                continue
            mode = protection.get("mode")
            item_name = str(item.get("name", "magical protection"))
            if mode == "threshold":
                target = int(protection.get("target", 13))
                roll = random.randint(1, 12)
                if roll >= target:
                    self.combat_log.append(
                        f"{hero.name}'s {item_name} wards off {spell_name} from {caster_name} ({roll} vs {target}+)."
                    )
                    return True
            elif mode == "intelligence":
                roll = random.randint(1, 12)
                if roll <= hero.intelligence:
                    self.combat_log.append(
                        f"{hero.name}'s {item_name} wards off {spell_name} from {caster_name} ({roll} vs Int {hero.intelligence})."
                    )
                    return True
        return False

    def _apply_choke_to_hero(self, hero: Hero, caster_ref: str, caster_name: str) -> bool:
        """Apply the Skaven Choke effect to a hero."""
        if self._hero_resists_spell(hero, "Choke", caster_name):
            return False
        hero.add_status_effect(
            "choke",
            turns=3,
            exploration_move_cap=1,
            combat_move_cap=1,
            choke_caster_ref=caster_ref,
            choke_caster_name=caster_name,
        )
        self.combat_log.append(
            f"{caster_name} casts Choke on {hero.name}. {hero.name} may only stagger 1 square per turn for 3 turns."
        )
        return True

    def _resolve_magic_trap_spell(
        self,
        hero: Hero,
        spell_name: str,
        trap_origin: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Resolve a magic-trap spell through the shared spell engine."""
        definition = get_spell_definition(spell_name)
        if definition is None:
            self.combat_log.append(f"  Magic trap: {spell_name} is not implemented.")
            return

        norm = normalize_spell_name(spell_name)
        origin = trap_origin if trap_origin is not None else (hero.x, hero.y)
        label = f"Magic trap ({definition['name']})"
        self.combat_log.append(f"  {label} goes off at {origin}.")

        if norm in {"fireball", "flames of death", "inferno of doom"}:
            damage_dice = int(definition.get("damage_dice", 5))
            self._apply_spell_damage(self._get_fireball_area(origin[0], origin[1]), damage_dice, label)
            if norm == "fireball":
                self._queue_fireball_trap(origin)
                self.combat_log.append("  The Fireball trap will move for the next three later GM phases.")
            return

        if norm == "lightning bolt":
            if self._hero_resists_spell(hero, definition["name"], "the magic trap"):
                return
            self._apply_spell_damage([(hero.x, hero.y)], int(definition.get("damage_dice", 6)), label)
            return

        if norm == "choke":
            self._apply_choke_to_hero(hero, "trap", "the magic trap")
            return

        self.combat_log.append(f"  {label} has no trap resolver yet.")

    def _monster_cast_spell(self, monster: Monster) -> bool:
        """Let a monster resolve a spell instead of taking a normal action."""
        if not monster.has_spellcasting():
            return False

        mode = str(monster.spellcasting.get("mode", "wizard")).lower()
        if mode == "warpscroll":
            if int(monster.spellcasting.get("charges", {}).get("Warpscroll", 0)) <= 0:
                return False
            if monster.spellcasting.get("charging_spell") == "Warpscroll":
                roll = random.randint(1, 12)
                monster.spellcasting["charging_spell"] = None
                monster.spellcasting["charge_turns"] = 0
                if roll > monster.intelligence:
                    if self.current_phase == "COMBAT" and self._pop_held_fate_counter():
                        self.combat_log.append(
                            f"  GM spends a Fate counter for {monster.name}: failed Warpscroll Intelligence test "
                            f"({roll} vs Int {monster.intelligence}) becomes a success."
                        )
                    else:
                        self.combat_log.append(
                            f"{monster.name} fails the Warpscroll Intelligence test ({roll} vs Int {monster.intelligence})."
                        )
                        return True
                monster.consume_spell_charge("Warpscroll")
                self.combat_log.append(f"{monster.name} completes the Warpscroll and ages the whole party!")
                for hero in self.party:
                    if hero.is_dead:
                        continue
                    resist_roll = random.randint(1, 12)
                    if resist_roll <= hero.intelligence:
                        self.combat_log.append(
                            f"  {hero.name} resists the Warpscroll ({resist_roll} vs Int {hero.intelligence})."
                        )
                        continue
                    if hero.has_fate_available():
                        hero.queue_failed_roll_fate_decision("warpscroll", roll=resist_roll)
                        self.combat_log.append(
                            f"  {hero.name} fails the Warpscroll test ({resist_roll}) and must decide whether to spend Fate."
                        )
                    else:
                        hero.is_dead = True
                        hero.is_ko = True
                        hero.current_wounds = 0
                        hero.death_turn = self.turn_count
                        self.combat_log.append(f"  {hero.name} fails the Warpscroll test ({resist_roll}) and dies.")
                return True

            if self._monster_is_in_any_enemy_death_zone(monster):
                return False
            monster.spellcasting["charging_spell"] = "Warpscroll"
            monster.spellcasting["charge_turns"] = int(monster.spellcasting.get("charge_turns", 0)) + 1
            self.combat_log.append(f"{monster.name} begins chanting from a Warpscroll.")
            return True

        available_spells = monster.get_available_spells()
        if not available_spells:
            return False

        living_heroes = [hero for hero in self.party if not hero.is_dead]
        visible_targets = [
            hero for hero in living_heroes
            if self.dungeon._has_los(monster.x, monster.y, hero.x, hero.y)
            and self.dungeon.get_distance(monster.x, monster.y, hero.x, hero.y) <= 12
        ]

        if "Flaming Skull of Terror" in available_spells and not monster.has_status_effect("flaming_skull_of_terror"):
            monster.consume_spell_charge("Flaming Skull of Terror")
            monster.add_status_effect(
                "flaming_skull_of_terror",
                scope="next_exploration",
                ws_delta=1,
                toughness_delta=1,
            )
            self.combat_log.append(f"{monster.name} casts Flaming Skull of Terror on itself.")
            return True

        if "Fireball" in available_spells and visible_targets:
            target_hero = min(
                visible_targets,
                key=lambda hero: self.dungeon.get_distance(monster.x, monster.y, hero.x, hero.y),
            )
            monster.consume_spell_charge("Fireball")
            self.combat_log.append(f"{monster.name} casts Fireball at {target_hero.name}.")
            self._apply_spell_damage(self._get_fireball_area(target_hero.x, target_hero.y), 5, f"{monster.name}'s Fireball")
            return True

        if "Choke" in available_spells and visible_targets:
            target_hero = min(
                visible_targets,
                key=lambda hero: self.dungeon.get_distance(monster.x, monster.y, hero.x, hero.y),
            )
            monster.consume_spell_charge("Choke")
            self._apply_choke_to_hero(target_hero, monster.instance_id, monster.name)
            return True

        return False

    def _apply_spell_damage(self, positions: List[Tuple[int, int]], damage_dice: int, label: str):
        """Apply spell damage to any models in the affected squares."""
        hit_models = set()
        for pos in positions:
            model = self._get_any_model_at(pos[0], pos[1])
            if model is None or model in hit_models:
                continue
            hit_models.add(model)
            if isinstance(model, Hero):
                damage, rolls = resolve_spell_damage(damage_dice, model.get_effective_toughness())
                self.combat_log.append(f"  {label} hits {model.name}: {rolls} vs T{model.get_effective_toughness()} = {damage} wounds.")
                if damage:
                    apply_damage_to_hero(model, damage, self.combat_log)
                    if model.is_dead and model.death_turn is None:
                        model.death_turn = self.turn_count
            else:
                damage, rolls = resolve_spell_damage(damage_dice, model.toughness)
                self.combat_log.append(f"  {label} hits {model.name}: {rolls} vs T{model.toughness} = {damage} wounds.")
                if damage:
                    model.take_damage(damage)
                    self._handle_monster_defeat(model)

    def _get_fireball_area(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Return the AHQ fireball template area."""
        return get_fireball_template_area(x, y)

    def _get_section_tiles(self, x: int, y: int) -> set[Tuple[int, int]]:
        """Return the room or passage section containing a tile."""
        room = self.dungeon.find_room_for_tile(x, y)
        if room is not None:
            return set(self.dungeon.get_room_interior_tiles(room))

        if not self.dungeon.is_walkable(x, y):
            return set()

        section = set()
        queue = [(x, y)]
        while queue:
            cx, cy = queue.pop()
            if (cx, cy) in section:
                continue
            tile = self.dungeon.get_tile(cx, cy)
            if tile not in (
                self.dungeon.TileType.FLOOR,
                self.dungeon.TileType.PASSAGE_END,
                self.dungeon.TileType.DOOR_OPEN,
                self.dungeon.TileType.STAIRS_DOWN,
                self.dungeon.TileType.STAIRS_OUT,
            ):
                continue
            if self.dungeon.find_room_for_tile(cx, cy) is not None and (cx, cy) != (x, y):
                continue
            section.add((cx, cy))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                queue.append((cx + dx, cy + dy))
        return section

    def _get_visible_section_tiles_for_monsters(self, monsters: List[Monster]) -> List[Tuple[int, int]]:
        """Return the discovered section tiles for an encountered monster group."""
        if not monsters:
            return []
        section: set[Tuple[int, int]] = set()
        for monster in monsters:
            if monster.is_dead:
                continue
            section.update(self._get_section_tiles(monster.x, monster.y))
        return [pos for pos in section if self.dungeon.is_walkable(pos[0], pos[1])]

    def _is_other_model_in_death_zone(self, caster: Hero, exempt: Optional[Hero] = None) -> bool:
        """Whether another model occupies the caster's death zone."""
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            model = self._get_any_model_at(caster.x + dx, caster.y + dy)
            if model is None or model == exempt:
                continue
            return True
        return False

    def _resolve_spell_effect(self, hero: Hero, definition: dict, target: Optional[Tuple[int, int]]) -> Tuple[bool, str]:
        """Apply the actual effect of a spell."""
        spell_name = definition["name"]
        norm = normalize_spell_name(spell_name)

        if definition.get("target_mode") != "none" and target is None:
            return False, f"{spell_name} needs a target."

        if norm in {"dragon armour", "courage", "flames of the phoenix", "power of the phoenix"}:
            target_hero = self._get_hero_at(target[0], target[1]) if target is not None else hero
            if target_hero is None:
                return False, f"{spell_name} must target a hero."
            if definition.get("adjacent_only") and not (
                (target_hero.x, target_hero.y) == (hero.x, hero.y)
                or self.dungeon.is_adjacent(hero.x, hero.y, target_hero.x, target_hero.y)
            ):
                return False, f"{spell_name} must target a model in the wizard's death zone."

            if norm == "dragon armour":
                target_hero.add_status_effect("dragon_armour", scope="next_exploration", toughness_delta=1)
                return True, f"{hero.name} casts Dragon Armour on {target_hero.name}."
            if norm == "courage":
                target_hero.add_status_effect("courage", scope="next_exploration", bravery_override=12)
                return True, f"{hero.name} casts Courage on {target_hero.name}."
            if norm == "flames of the phoenix":
                if self._is_other_model_in_death_zone(hero, exempt=target_hero):
                    return False, "Flames of the Phoenix cannot be cast while other models are in the wizard's death zone."
                target_hero.restore_to_full()
                return True, f"{hero.name} casts Flames of the Phoenix on {target_hero.name}, restoring them to full strength."
            if target_hero.death_turn != self.turn_count - 1:
                return False, "Power of the Phoenix may only be cast on a character killed in the previous turn."
            roll = random.randint(1, 12)
            if roll > hero.intelligence:
                if hero.has_fate_available():
                    hero.queue_failed_roll_fate_decision(
                        "power_of_the_phoenix",
                        roll=roll,
                        target_hero_id=target_hero.id,
                    )
                    return True, (
                        f"{hero.name} fails the Intelligence test for Power of the Phoenix "
                        f"({roll} vs Int {hero.intelligence}) and may spend Fate to turn it into a success."
                    )
                target_hero.is_dead = True
                target_hero.is_ko = True
                return True, f"{hero.name} fails the Intelligence test for Power of the Phoenix ({roll} vs Int {hero.intelligence})."
            target_hero.restore_to_full()
            return True, f"{hero.name} casts Power of the Phoenix on {target_hero.name} (roll {roll}), returning them to life at full strength."

        if norm == "flaming hand of destruction":
            hero.add_status_effect("flaming_hand_of_destruction", scope="next_exploration")
            return True, f"{hero.name}'s hands blaze with magical fire."

        if norm == "swift wind":
            roll = random.randint(1, 12)
            moved_characters = (roll + 1) // 2
            hero.add_status_effect("swift_wind", turns=1, scope="hero_phase", exploration_move_cap=18, speed_delta=hero.get_effective_speed(self.current_phase.lower()))
            self.hero_movement_remaining[hero.id] = max(self.hero_movement_remaining.get(hero.id, 0), hero.get_movement_allowance(self.current_phase.lower()))
            return True, f"{hero.name} casts Swift Wind (roll {roll}), enough power for {moved_characters} characters. The current implementation empowers {hero.name} for this turn."

        if norm in {"flames of death", "fireball", "inferno of doom"}:
            if not self.dungeon._has_los(hero.x, hero.y, target[0], target[1]):
                return False, f"{hero.name} has no line of sight for {spell_name}."
            max_range = int(definition.get("max_range", 12))
            if self.dungeon.get_distance(hero.x, hero.y, target[0], target[1]) > max_range:
                return False, f"{spell_name} is out of range."
            damage_dice = int(definition.get("damage_dice", 5))
            if norm == "inferno of doom":
                roll = random.randint(1, 12)
                if roll > hero.intelligence:
                    failed_damage = int(definition.get("damage_dice_on_failed_test", 5))
                    if hero.has_fate_available():
                        area = self._get_fireball_area(target[0], target[1])
                        hero.queue_failed_roll_fate_decision(
                            "inferno_of_doom",
                            roll=roll,
                            area=[[pos[0], pos[1]] for pos in area],
                            success_damage_dice=damage_dice,
                            failed_damage_dice=failed_damage,
                            spell_name=spell_name,
                        )
                        return True, (
                            f"{hero.name} fails the Inferno of Doom Intelligence test "
                            f"({roll} vs Int {hero.intelligence}) and may spend Fate to unleash the full spell."
                        )
                    damage_dice = failed_damage
                    self.combat_log.append(f"{hero.name} fails the Inferno of Doom Intelligence test ({roll} vs Int {hero.intelligence}).")
                else:
                    self.combat_log.append(f"{hero.name} passes the Inferno of Doom Intelligence test ({roll} vs Int {hero.intelligence}).")
            area = self._get_fireball_area(target[0], target[1])
            self._apply_spell_damage(area, damage_dice, spell_name)
            return True, f"{hero.name} casts {spell_name} at {target}."

        if norm == "still air":
            if not self.dungeon._has_los(hero.x, hero.y, target[0], target[1]):
                return False, "Still Air needs line of sight to the selected dungeon section."
            section_tiles = self._get_section_tiles(target[0], target[1])
            affected = 0
            for monster in self.monsters:
                if not monster.is_dead and (monster.x, monster.y) in section_tiles:
                    monster.add_status_effect("still_air", turns=1, cannot_move=True, cannot_attack=True)
                    affected += 1
            return True, f"{hero.name} casts Still Air. {affected} monster(s) in that section are frozen for the turn."

        if norm == "open window":
            tile = self.dungeon.get_tile(target[0], target[1])
            if tile != self.dungeon.TileType.DOOR_CLOSED:
                return False, "Open Window currently targets a closed door."
            log_count_before = len(self.dungeon_debug_log)
            if not self.dungeon.open_door(target[0], target[1]):
                return False, "The spell reveals only solid resistance beyond that doorway."
            self.dungeon.grid[target] = self.dungeon.TileType.DOOR_CLOSED
            if target in self.dungeon.doors:
                self.dungeon.doors[target]["is_open"] = False
            for msg in self.dungeon_debug_log[log_count_before:]:
                self.combat_log.append(f"[DUNGEON] {msg}")
            return True, f"{hero.name} casts Open Window beyond the door at {target}."

        if norm == "the bright key":
            tile = self.dungeon.get_tile(target[0], target[1])
            if tile != self.dungeon.TileType.WALL:
                return False, "The Bright Key must target a wall."
            current_section = self._get_section_tiles(hero.x, hero.y)
            if not any(self.dungeon.is_adjacent(target[0], target[1], sx, sy) for sx, sy in current_section):
                return False, "That wall is not part of the wizard's current dungeon section."
            rock_roll = random.randint(1, 12)
            self.dungeon.grid[target] = self.dungeon.TileType.DOOR_CLOSED
            self.dungeon.doors[target] = {"is_open": False, "from_room": self.dungeon.find_room_for_tile(hero.x, hero.y) is not None, "bright_key_roll": rock_roll}
            self.dungeon.explored.add(target)
            return True, f"{hero.name} casts The Bright Key, creating a door in the wall at {target}."

        if norm == "flight":
            target_model = self._get_any_model_at(target[0], target[1])
            if target_model is None:
                return False, "Flight must target a model."
            if not self.dungeon._has_los(hero.x, hero.y, target_model.x, target_model.y):
                return False, "Flight requires line of sight to the target."
            dx = 1 if target_model.x > hero.x else -1 if target_model.x < hero.x else 0
            dy = 1 if target_model.y > hero.y else -1 if target_model.y < hero.y else 0
            max_steps = 18 if self.current_phase == "EXPLORATION" else max(1, getattr(target_model, "speed", 6) * 2)
            moved = 0
            while moved < max_steps:
                nx, ny = target_model.x + dx, target_model.y + dy
                if not self.dungeon.is_walkable(nx, ny):
                    break
                if self._get_any_model_at(nx, ny) is not None:
                    break
                target_model.x, target_model.y = nx, ny
                moved += 1
            return True, f"{hero.name} casts Flight on {target_model.name}, hurling them {moved} square(s)."

        if norm in {"choke", "lightning bolt"}:
            target_monster = self._get_monster_at(target[0], target[1])
            if target_monster is None:
                return False, f"{spell_name} currently targets a visible monster."
            if not self.dungeon._has_los(hero.x, hero.y, target_monster.x, target_monster.y):
                return False, f"{spell_name} requires line of sight."
            if norm == "choke":
                target_monster.add_status_effect("choke", turns=3, choke_caster_id=hero.id)
                return True, f"{hero.name} casts Choke on {target_monster.name}."
            self._apply_spell_damage([(target_monster.x, target_monster.y)], int(definition.get("damage_dice", 6)), spell_name)
            return True, f"{hero.name} casts Lightning Bolt on {target_monster.name}."

        if norm == "flaming skull of terror":
            hero.add_status_effect("flaming_skull_of_terror", scope="next_exploration", ws_delta=1, toughness_delta=1)
            return True, f"{hero.name} becomes a fearsome monster until the next exploration turn."

        return False, f"{spell_name} is not implemented."

    def _hero_is_adjacent_to_any_monster(self, hero: Hero) -> bool:
        """Check whether a hero is engaged with any living monster."""
        return any(
            not monster.is_dead and self.dungeon.is_adjacent(hero.x, hero.y, monster.x, monster.y)
            for monster in self.monsters
        )

    def _reset_combat_turn_flags(self):
        """Reset per-phase combat action state for heroes."""
        self.hero_has_attacked.clear()
        self.hero_ran_this_phase.clear()
        self.ambush_counter_played_this_combat_turn = False
        self._snapshot_party_turn_state()

    def hero_run(self, hero: Hero) -> str:
        """Run during combat instead of attacking."""
        if self.has_pending_fate_decision():
            return "Resolve the pending Fate decision first."
        if self.current_phase != "COMBAT":
            return "Running is only used during combat."
        if hero.is_dead or hero.is_ko:
            return f"{hero.name} cannot run."
        if hero.is_under_gm_control():
            return f"{hero.name} is under GM control."
        if hero.is_restrained_by_mindstealer():
            return f"{hero.name} is being restrained."
        if hero.id in self.hero_has_attacked:
            return f"{hero.name} has already used their attack and cannot run."
        remaining = self.hero_movement_remaining.get(hero.id, self._get_movement_allowance_for_phase(hero, "COMBAT"))
        if remaining <= 0:
            return f"{hero.name} has no movement left."

        roll = random.randint(1, 12)
        bonus = roll if roll >= 2 else 0
        self.hero_has_attacked.add(hero.id)
        self.hero_ran_this_phase.add(hero.id)
        self.hero_movement_remaining[hero.id] = remaining + bonus
        if roll == 1:
            self.save_game()
            return f"{hero.name} runs but stumbles on a 1 and gains no extra movement."
        self.save_game()
        return f"{hero.name} runs and gains {bonus} extra movement."

    def _hero_can_use_door_in_combat(self, hero: Hero) -> Tuple[bool, str]:
        """Check combat legality for opening or closing a door."""
        if self.has_pending_fate_decision():
            return False, "Resolve the pending Fate decision first."
        if self.current_phase != "COMBAT":
            return False, "This door action is only for combat turns."
        if hero.is_dead or hero.is_ko:
            return False, f"{hero.name} cannot use a door right now."
        if hero.is_under_gm_control():
            return False, f"{hero.name} is under GM control."
        if hero.is_restrained_by_mindstealer():
            return False, f"{hero.name} is being restrained."
        if hero.id in self.hero_has_attacked:
            return False, f"{hero.name} has already used their attack this phase."
        if hero.id in self.hero_ran_this_phase:
            return False, f"{hero.name} ran this phase and cannot operate a door."
        if self._hero_is_adjacent_to_any_monster(hero):
            return False, f"{hero.name} is in an enemy death zone and cannot operate a door."
        return True, ""

    def combat_open_door(self, hero: Hero, x: int, y: int) -> str:
        """Open a door during combat, replacing the hero's attack."""
        allowed, message = self._hero_can_use_door_in_combat(hero)
        if not allowed:
            return message
        if not self.dungeon.is_adjacent(hero.x, hero.y, x, y):
            return "Stand beside the door first."
        if self.dungeon.get_tile(x, y) != self.dungeon.TileType.DOOR_CLOSED:
            return "That door is not closed."
        if not self.open_door(x, y):
            return "Failed to open the door."
        self.hero_has_attacked.add(hero.id)
        self.save_game()
        return f"{hero.name} opens the door."

    def combat_close_door(self, hero: Hero, x: int, y: int) -> str:
        """Close a door during combat, replacing the hero's attack."""
        allowed, message = self._hero_can_use_door_in_combat(hero)
        if not allowed:
            return message
        if not self.dungeon.is_adjacent(hero.x, hero.y, x, y):
            return "Stand beside the door first."
        if self.dungeon.get_tile(x, y) != self.dungeon.TileType.DOOR_OPEN:
            return "That door is not open."
        self.dungeon.grid[(x, y)] = self.dungeon.TileType.DOOR_CLOSED
        if (x, y) in self.dungeon.doors:
            self.dungeon.doors[(x, y)]["is_open"] = False
        self.hero_has_attacked.add(hero.id)
        self.combat_escape_pending_closed_door = True
        if (x, y) not in self.combat_escape_closed_doors:
            self.combat_escape_closed_doors.append((x, y))
        self.combat_log.append(f"{hero.name} closes the door at ({x}, {y}).")
        self.save_game()
        return f"{hero.name} closes the door."

    def _hero_can_make_melee_attack(self, hero: Hero, monster: Monster) -> bool:
        """Check whether the monster is within melee reach."""
        dx = abs(hero.x - monster.x)
        dy = abs(hero.y - monster.y)
        if hero.has_long_reach_weapon():
            return max(dx, dy) == 1 and (dx != 0 or dy != 0)
        return (dx + dy == 1)

    def _roll_monster_loot(self, monster: Monster) -> List[dict]:
        """Generate loot carried by a defeated monster."""
        loot: List[dict] = []
        weapon_names = [str(weapon.get("name", "")) for weapon in monster.weapons]
        joined_names = " ".join(weapon_names).lower()
        special_rules = {str(rule).lower() for rule in getattr(monster, "special_rules", [])}
        spellcasting = dict(getattr(monster, "spellcasting", {}))

        if "ring_of_magic_protection" in special_rules:
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Ring of Magic Protection",
                    "type": "ring",
                    "equipped": False,
                    "toughness_bonus": 1,
                },
            })
        if "runesword" in joined_names:
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Runesword",
                    "type": "weapon",
                    "equipped": False,
                    "damage_dice": 7,
                    "critical": 12,
                    "fumble": 1,
                },
            })
        elif "chaos sword" in joined_names:
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Chaos Sword",
                    "type": "weapon",
                    "equipped": False,
                    "damage_dice": 6,
                    "critical": 12,
                    "fumble": 0,
                },
            })
        elif "magic halberd" in joined_names:
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Magic Halberd",
                    "type": "weapon",
                    "equipped": False,
                    "damage_dice": 6,
                    "critical": 12,
                    "fumble": 1,
                    "long_reach": True,
                    "two_handed": True,
                },
            })

        if int(spellcasting.get("charges", {}).get("Warpscroll", 0)) > 0 or str(spellcasting.get("mode", "")).lower() == "warpscroll":
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Warpscroll",
                    "type": "scroll",
                    "equipped": False,
                    "spells": ["Inferno of Doom"],
                },
            })
        elif monster.has_spellcasting():
            loot.append({
                "type": "equipment",
                "item": {
                    "name": "Spell Scroll",
                    "type": "scroll",
                    "equipped": False,
                    "spells": list(spellcasting.get("charges", {}).keys())[:1] or ["Fireball"],
                },
            })
        if str(spellcasting.get("mode", "")).lower() == "wizard":
            known_spells = [str(spell) for spell in spellcasting.get("charges", {}).keys() if str(spell).strip()]
            if known_spells:
                loot.append({"type": "spellbook", "spells": known_spells})
                loot.append({
                    "type": "spell_components",
                    "components": {spell: int(spellcasting.get("charges", {}).get(spell, 0)) for spell in known_spells},
                })

        if "poisoned_weapon" in special_rules:
            loot.append({"type": "supply", "item_key": "rat_poison"})

        if monster.has_ranged():
            ranged_name = str((monster.ranged or {}).get("name", "")).lower()
            if "crossbow" in ranged_name:
                loot.append({"type": "ammo", "ammo_type": "bolts", "count": 6})
            elif "bow" in ranged_name:
                loot.append({"type": "ammo", "ammo_type": "arrows", "count": 6})

        return loot

    def _award_monster_loot(self, hero: Optional[Hero], monster: Monster):
        """Award any generated monster-carried loot."""
        recipient = hero or next((current for current in self.party if not current.is_dead), None)
        if recipient is None:
            return
        note_pos = (monster.x, monster.y)
        for entry in self._roll_monster_loot(monster):
            entry_type = entry.get("type")
            if entry_type == "equipment":
                self._award_equipment_item(recipient, dict(entry.get("item", {})), monster.name, note_pos=note_pos)
            elif entry_type == "supply":
                self._award_supply_item(recipient, str(entry.get("item_key", "")), monster.name, note_pos=note_pos)
            elif entry_type == "ammo":
                ammo_type = str(entry.get("ammo_type", "arrows"))
                count = int(entry.get("count", 0))
                recipient.add_ammo(ammo_type, count)
                self.hero_manager.update_hero(recipient)
                self.combat_log.append(f"{recipient.name} recovers {count} {ammo_type} from {monster.name}.")
            elif entry_type == "spellbook":
                self._award_spellbook_loot(recipient, list(entry.get("spells", [])), monster.name, note_pos=note_pos)
            elif entry_type == "spell_components":
                self._award_spell_components_loot(recipient, dict(entry.get("components", {})), monster.name, note_pos=note_pos)

    def _monster_is_in_any_enemy_death_zone(self, monster: Monster) -> bool:
        """Check whether a monster is in any hero melee death zone."""
        return any(
            not hero.is_dead and not hero.is_ko and self._hero_can_make_melee_attack(hero, monster)
            for hero in self.party
        )

    def _handle_monster_defeat(self, monster: Monster, killer: Optional[Hero] = None):
        """Apply shared post-attack cleanup for a defeated monster."""
        if not monster.is_dead:
            return

        if self._try_spend_monster_fate_counter(monster):
            return

        self.experience_gained += monster.pv
        if not getattr(monster, "loot_awarded", False):
            self._award_monster_loot(killer, monster)
            monster.loot_awarded = True
        self.monsters = [current for current in self.monsters if not current.is_dead]
        self._refresh_special_monster_states()

        if not any(not current.is_dead for current in self.monsters):
            self._end_combat()

    def _try_spend_monster_fate_counter(self, monster: Monster) -> bool:
        """Use a held Fate counter to keep a monster in the fight after a killing blow."""
        if self.current_phase != "COMBAT":
            return False
        if not self._pop_held_fate_counter():
            return False

        monster.is_dead = False
        monster.current_wounds = 1
        self.combat_log.append(f"  GM spends a Fate counter for {monster.name}; the killing blow is negated.")
        return True

    def _pop_held_fate_counter(self) -> bool:
        """Remove one held GM Fate counter if available."""
        try:
            index = self.held_dungeon_counters.index("fate")
        except ValueError:
            return False
        del self.held_dungeon_counters[index]
        return True

    def _try_spend_monster_fate_for_failed_roll(
        self,
        monster: Monster,
        roll_label: str,
        roll: int,
        needed: int,
    ) -> bool:
        """Use a held Fate counter to turn a failed monster dice roll into a success."""
        if self.current_phase != "COMBAT" or monster.is_dead:
            return False
        if not self._pop_held_fate_counter():
            return False
        self.combat_log.append(
            f"  GM spends a Fate counter for {monster.name}: failed {roll_label} "
            f"({roll}, needed {needed}+) becomes a success."
        )
        return True

    def _hero_is_in_monster_death_zone(self, hero: Hero, monster: Monster) -> bool:
        """Whether a hero begins the phase inside a monster's death zone."""
        return self._monster_can_make_melee_attack_from(monster, hero.x, hero.y)

    def _apply_fearsome_checks(self, phase_label: str):
        """Apply fear checks at the start of a combat phase."""
        if self.current_phase != "COMBAT":
            return
        fearsome_monsters = [monster for monster in self.monsters if not monster.is_dead and monster.is_fearsome()]
        if not fearsome_monsters:
            for hero in self.party:
                hero.remove_status_effect("cowering")
            return
        for hero in self.party:
            hero.remove_status_effect("cowering")
            if hero.is_dead or hero.is_ko:
                continue
            if any(self._hero_is_in_monster_death_zone(hero, monster) for monster in fearsome_monsters):
                roll = random.randint(1, 12)
                if roll > hero.bravery:
                    if hero.has_fate_available():
                        hero.queue_failed_roll_fate_decision("fearsome_bravery", roll=roll, phase_label=phase_label)
                        self.combat_log.append(
                            f"{phase_label}: {hero.name} fails a Bravery test ({roll} vs Br {hero.bravery}) "
                            "and may spend Fate to stand firm."
                        )
                    else:
                        hero.add_status_effect("cowering", scope="phase")
                        self.combat_log.append(
                            f"{phase_label}: {hero.name} fails a Bravery test ({roll} vs Br {hero.bravery}) and cowers."
                        )
                else:
                    self.combat_log.append(
                        f"{phase_label}: {hero.name} stands firm against fear ({roll} vs Br {hero.bravery})."
                    )
    
    def end_hero_phase(self):
        """End hero phase and start GM phase."""
        if self.has_pending_fate_decision():
            self.combat_log.append("A Fate decision is pending and the phase cannot end yet.")
            return
        self.ensure_phase_consistency()
        self.hero_phase_active = False
        self._close_temporary_traps()
        
        if self.current_phase == "EXPLORATION":
            self._run_exploration_gm_phase()
        else:  # COMBAT
            self._apply_fearsome_checks("Start of GM phase")
            self._run_combat_gm_phase()
        self._advance_gm_phase_markers()

        self.hero_phase_active = True
        if self.current_phase == "EXPLORATION":
            self._clear_next_exploration_magic_effects()
        self._reload_ranged_weapons()
        # Reset movement and attack tracking for next hero phase
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h)
            for h in self.party
        }
        self._reset_combat_turn_flags()
        if self.current_phase == "COMBAT":
            self._play_held_combat_counters()
        self.turn_count += 1
        self._advance_ko_timers()
        self._advance_status_effects()
        self._advance_monster_status_effects()
        self._capture_hero_turn_start_positions()
        self._snapshot_party_turn_state()
        if self.current_phase == "COMBAT":
            self._apply_fearsome_checks("Start of Hero phase")
        
        # Check for dead party
        if self._all_true_heroes_dead():
            self._game_over()
        
        self.save_game()

    def _reload_ranged_weapons(self):
        """Reload crossbows for heroes who spent the whole turn reloading."""
        phase_name = self.current_phase
        for hero in self.party:
            if hero.is_dead or hero.is_ko:
                continue
            if not hero.ranged_weapon_requires_reload():
                continue
            allowance = self._get_movement_allowance_for_phase(hero, phase_name)
            remaining = self.hero_movement_remaining.get(hero.id, allowance)
            if remaining != allowance:
                continue
            if hero.id in self.hero_has_attacked:
                continue
            weapon_name = hero.reload_ranged_weapon()
            if weapon_name:
                self.combat_log.append(f"{hero.name} reloads {weapon_name}.")

    def _close_temporary_traps(self):
        """Close any trap states that only stay open for the hero phase."""
        if self.dungeon is None:
            return
        for pos, marker in self.dungeon.trap_markers.items():
            if marker.get("type") == "portcullis" and marker.get("temporary_open"):
                marker["blocks_movement"] = True
                marker.pop("temporary_open", None)
                self.combat_log.append(f"The portcullis at {pos} crashes shut again.")

    def _advance_gm_phase_markers(self):
        """Advance board markers that expire at the end of GM phases."""
        if self.dungeon is None:
            return
        self._advance_fireball_traps()
        expired: List[Tuple[int, int]] = []
        for pos, marker in self.dungeon.trap_markers.items():
            phases = marker.get("gm_phases_remaining")
            if phases is None:
                continue
            marker["gm_phases_remaining"] = int(phases) - 1
            if marker["gm_phases_remaining"] <= 0:
                expired.append(pos)
        for pos in expired:
            marker = self.dungeon.trap_markers.pop(pos, None)
            if marker and marker.get("type") == "poisoned_wind_cloud":
                self.combat_log.append(f"The poisoned wind cloud at {pos} disperses.")

    def queue_fireball_trap_directions(self, directions: List[Tuple[int, int]]) -> str:
        """Queue GM-chosen 8-square Fireball movement directions for the next Fireball trap."""
        normalized = []
        for dx, dy in directions:
            direction = (int(dx), int(dy))
            if direction not in {
                (-1, -1), (0, -1), (1, -1),
                (-1, 0),           (1, 0),
                (-1, 1),  (0, 1),  (1, 1),
            }:
                return "Fireball directions must be one-square non-zero directions."
            normalized.append(direction)
        self.next_fireball_trap_directions = normalized
        return "Fireball trap directions queued."

    def set_active_fireball_trap_directions(self, trap_index: int, directions: List[Tuple[int, int]]) -> str:
        """Set GM-chosen directions for an already-active Fireball trap."""
        if trap_index < 0 or trap_index >= len(self.active_fireball_traps):
            return "No active Fireball trap at that index."
        message = self.queue_fireball_trap_directions(directions)
        if "queued" not in message:
            return message
        self.active_fireball_traps[trap_index]["direction_queue"] = [
            [dx, dy] for dx, dy in self.next_fireball_trap_directions
        ]
        self.next_fireball_trap_directions = []
        return "Active Fireball trap directions set."

    def _queue_fireball_trap(self, origin: Tuple[int, int]):
        """Create a persistent fireball trap that activates over later GM phases."""
        entry = {
            "x": int(origin[0]),
            "y": int(origin[1]),
            "delay_phases": 1,
            "remaining_moves": 3,
            "direction_queue": [[dx, dy] for dx, dy in self.next_fireball_trap_directions],
        }
        self.next_fireball_trap_directions = []
        self.active_fireball_traps.append(entry)
        self.dungeon.trap_markers[(entry["x"], entry["y"])] = {
            "type": "fireball_trap",
            "symbol": "FB",
        }

    def _choose_fireball_trap_direction(self, trap: dict, current_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Return a queued GM Fireball direction, or the deterministic engine fallback."""
        direction_queue = trap.get("direction_queue")
        if isinstance(direction_queue, list) and direction_queue:
            raw_direction = direction_queue.pop(0)
            if isinstance(raw_direction, (list, tuple)) and len(raw_direction) == 2:
                direction = (int(raw_direction[0]), int(raw_direction[1]))
                if direction in {
                    (-1, -1), (0, -1), (1, -1),
                    (-1, 0),           (1, 0),
                    (-1, 1),  (0, 1),  (1, 1),
                }:
                    return direction

        targets = [hero for hero in self.party if not hero.is_dead]
        if not targets:
            return (0, 0)
        target = min(targets, key=lambda hero: self.dungeon.get_distance(current_pos[0], current_pos[1], hero.x, hero.y))
        directions = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),           (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
        ]
        best_dir = (0, 0)
        best_score = self.dungeon.get_distance(current_pos[0], current_pos[1], target.x, target.y)
        for dx, dy in directions:
            probe_x = current_pos[0] + dx * 8
            probe_y = current_pos[1] + dy * 8
            score = self.dungeon.get_distance(probe_x, probe_y, target.x, target.y)
            if score < best_score:
                best_score = score
                best_dir = (dx, dy)
        return best_dir

    def _advance_fireball_traps(self):
        """Advance persistent fireball traps after GM phases."""
        if self.dungeon is None or not self.active_fireball_traps:
            return
        updated: List[dict] = []
        for trap in self.active_fireball_traps:
            current_pos = (int(trap["x"]), int(trap["y"]))
            if int(trap.get("delay_phases", 0)) > 0:
                trap["delay_phases"] = int(trap.get("delay_phases", 0)) - 1
                updated.append(trap)
                continue

            self.dungeon.trap_markers.pop(current_pos, None)
            dx, dy = self._choose_fireball_trap_direction(trap, current_pos)
            next_x = current_pos[0] + dx * 8
            next_y = current_pos[1] + dy * 8
            trap["x"], trap["y"] = next_x, next_y
            self.dungeon.trap_markers[(next_x, next_y)] = {
                "type": "fireball_trap",
                "symbol": "FB",
            }
            self.combat_log.append(f"The trapped Fireball streaks to ({next_x}, {next_y}).")
            self._apply_spell_damage(self._get_fireball_area(next_x, next_y), 5, "Fireball trap")
            trap["remaining_moves"] = int(trap.get("remaining_moves", 0)) - 1
            if trap["remaining_moves"] > 0:
                updated.append(trap)
            else:
                self.dungeon.trap_markers.pop((next_x, next_y), None)
                self.combat_log.append("The trapped Fireball gutters out.")
        self.active_fireball_traps = updated

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
            "madness_restrained": "is no longer being restrained.",
            "mild_poison": "can move again.",
        }
        for hero in self.party:
            choke = hero.get_status_effect("choke")
            choke_caster_dead = False
            choke_caster_name = str(choke.get("choke_caster_name", "the caster")) if choke is not None else ""
            healing_pending = hero.has_pending_healing_potion()
            if choke is not None:
                caster_ref = choke.get("choke_caster_ref")
                if caster_ref == "trap":
                    choke_caster_dead = False
                elif caster_ref is not None:
                    caster = next((monster for monster in self.monsters if monster.instance_id == caster_ref), None)
                    choke_caster_dead = caster is None or caster.is_dead
            for expired in hero.tick_status_effects():
                if expired == "choke":
                    if choke_caster_dead:
                        self.combat_log.append(f"{hero.name} survives as Choke collapses with {choke_caster_name}.")
                    elif hero.has_fate_available():
                        hero.queue_failed_roll_fate_decision("choke")
                        self.combat_log.append(f"{hero.name} suffocates as Choke runs its course and must decide whether to spend Fate.")
                    else:
                        hero.is_dead = True
                        hero.is_ko = True
                        hero.current_wounds = 0
                        hero.death_turn = self.turn_count
                        self.combat_log.append(f"{hero.name} suffocates as Choke runs its course.")
                    continue
                if expired == "healing_potion_pending" and healing_pending:
                    hero.restore_to_full()
                    self.combat_log.append(f"{hero.name}'s Healing Potion takes effect and restores them to full strength.")
                    continue
                suffix = expiry_messages.get(expired, "is no longer affected.")
                self.combat_log.append(f"{hero.name} {suffix}")

    def _advance_monster_status_effects(self):
        """Advance timed monster effects from spells."""
        for monster in list(self.monsters):
            caster_dead = False
            choke = monster.get_status_effect("choke")
            if choke is not None:
                caster_id = choke.get("choke_caster_id")
                caster = next((hero for hero in self.party if hero.id == caster_id), None)
                caster_dead = caster is None or caster.is_dead
            for expired in monster.tick_status_effects():
                if expired == "choke":
                    if caster_dead:
                        self.combat_log.append(f"{monster.name} survives as the Choke spell collapses with its caster.")
                    else:
                        monster.is_dead = True
                        self.combat_log.append(f"{monster.name} suffocates as Choke runs its course.")
                        self._handle_monster_defeat(monster)
                else:
                    self.combat_log.append(f"{monster.name} is no longer affected by {expired}.")

    def _clear_next_exploration_magic_effects(self):
        """Clear effects that expire when play returns to exploration turns."""
        for hero in self.party:
            hero.clear_status_effects("next_exploration")
        for monster in self.monsters:
            monster.status_effects = [
                effect for effect in monster.status_effects
                if effect.get("scope") != "next_exploration"
            ]

    def _refresh_hero_death_turns(self):
        """Backfill death-turn tracking for resurrection spells."""
        for hero in self.party:
            if hero.is_dead and hero.death_turn is None:
                hero.death_turn = self.turn_count
            elif not hero.is_dead:
                hero.death_turn = None
    
    def _run_exploration_gm_phase(self):
        """Run GM phase during exploration."""
        self._run_mad_hero_phase()
        if self._enter_combat_if_monsters_visible():
            return

        # Check for dungeon counter
        counter = check_dungeon_counter(self.dungeon_counter_pool)
        if counter:
            self.combat_log.append(f"Dungeon Counter drawn: {counter}")
            self._resolve_dungeon_counter(counter, allow_wandering=True)
            if self.current_phase == "COMBAT":
                return

        self._play_held_exploration_counters()
        if self.current_phase == "COMBAT":
            return

        self.combat_log.append("GM Phase complete.")

    def _get_active_heroes(self) -> List[Hero]:
        """Return heroes who can currently be affected by dungeon events."""
        return [hero for hero in self.party if not hero.is_dead and not hero.is_ko]

    def _resolve_dungeon_counter(self, counter: str, *, allow_wandering: bool = False):
        """Apply a drawn dungeon counter."""
        if counter == "wandering":
            if allow_wandering:
                self._resolve_wandering_counter()
            else:
                self.held_dungeon_counters.append(counter)
                self.combat_log.append("  Wandering Monster counter held until the end of an exploration phase.")
        elif counter == "ambush":
            if self.current_phase == "COMBAT":
                if not self._resolve_ambush_counter():
                    self.held_dungeon_counters.append(counter)
            else:
                self.held_dungeon_counters.append(counter)
                self.combat_log.append("  Ambush counter held until the start of a combat turn.")
        elif counter == "character":
            self._resolve_character_counter()
        elif counter == "fate":
            self._resolve_fate_counter()
        elif counter == "trap":
            self.held_dungeon_counters.append(counter)
            self.combat_log.append("  Trap counter held until a hero opens a chest or enters an unentered square.")
        elif counter == "escape":
            self._resolve_escape_counter()
        else:
            self.combat_log.append(f"  No handler for counter '{counter}'.")

    def _play_held_exploration_counters(self):
        """Play held counters that are legal at the end of an exploration phase."""
        if self.current_phase != "EXPLORATION" or not self.held_dungeon_counters:
            return

        remaining_counters: List[str] = []
        for counter in self.held_dungeon_counters:
            if counter == "wandering" and self.current_phase == "EXPLORATION":
                self.combat_log.append("Held Wandering Monster counter played at the end of exploration.")
                self._resolve_wandering_counter()
                if self.current_phase == "COMBAT":
                    continue
            else:
                remaining_counters.append(counter)
        self.held_dungeon_counters = remaining_counters

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
        self._start_combat_random(monster_ids, trigger_tile=(hero.x, hero.y), placement_mode="far_los")

    def _resolve_ambush_counter(self, *, first_turn: bool = False) -> bool:
        """Resolve an ambush dungeon counter."""
        if self.current_phase != "COMBAT":
            self.combat_log.append("  Ambush counter cannot be played outside combat.")
            return False

        if self.ambush_counter_played_this_combat_turn:
            self.combat_log.append("  Ambush counter held; only one Ambush may be played per combat turn.")
            return False

        hero = self._choose_counter_target_hero()
        if hero is None:
            self.combat_log.append("  No active hero available for an ambush.")
            return False

        self.ambush_counter_played_this_combat_turn = True
        self.combat_log.append(f"  Ambush! Monsters spring out near {hero.name}.")
        monster_ids = roll_lair_encounter()
        if first_turn:
            self._spawn_reinforcements(
                monster_ids,
                trigger_tile=(hero.x, hero.y),
                reason="Ambush",
                placement_mode="section",
            )
        else:
            self._spawn_reinforcements(
                monster_ids,
                trigger_tile=(hero.x, hero.y),
                reason="Ambush",
                placement_mode="far_los",
            )
        self.combat_log.append("  Ambush counter adds reinforcements to the current fight.")
        return True

    def _resolve_character_counter(self):
        """Resolve a character-monster dungeon counter."""
        self.held_dungeon_counters.append("character")
        self.combat_log.append("  Character counter held until monsters are next placed.")

    def _get_next_character_monster_id(self) -> Optional[str]:
        """Return the next configured character monster not already active or escaped."""
        active_ids = {
            str(monster.id)
            for monster in self.monsters
            if monster.is_character and not monster.is_dead
        }
        escaped_ids = {
            str(data.get("id", ""))
            for data in self.escaped_character_monsters
            if isinstance(data, dict)
        }
        character_ids = [
            monster_id
            for monster_id, data in self.monster_library.templates.items()
            if data.get("is_character") and monster_id not in active_ids and monster_id not in escaped_ids
        ]
        if character_ids:
            return character_ids[0]
        for monster_id, data in self.monster_library.templates.items():
            if data.get("is_character"):
                return monster_id
        return None

    def _play_held_character_counters(
        self,
        trigger_tile: Optional[Tuple[int, int]],
        placement_mode: str = "section",
    ):
        """Add held character counters to the monsters being placed."""
        if self.current_phase != "COMBAT" or not self.held_dungeon_counters:
            return

        remaining_counters: List[str] = []
        for counter in self.held_dungeon_counters:
            if counter != "character":
                remaining_counters.append(counter)
                continue

            if self.escaped_character_monsters:
                monster_data = self.escaped_character_monsters.pop(0)
                monster = self._restore_escaped_character_monster(monster_data)
                if monster is None:
                    self.combat_log.append("  An escaped character counter was drawn, but the monster could not be restored.")
                    continue
                self._place_returning_character_monster(monster, trigger_tile or (monster.x, monster.y))
                self.monsters.append(monster)
                self.combat_log.append(f"  Escaped character monster returns: {monster.name}.")
                continue

            monster_id = self._get_next_character_monster_id()
            if monster_id is None:
                self.combat_log.append("  Character counter drawn, but no character monsters are configured.")
                continue

            monster_name = self.monster_library.templates[monster_id].get("name", monster_id)
            self.combat_log.append(f"  Character monster encountered: {monster_name}.")
            self._spawn_reinforcements(
                [monster_id],
                trigger_tile=trigger_tile,
                reason="Character counter",
                placement_mode=placement_mode,
                play_character_counters=False,
            )

        self.held_dungeon_counters = remaining_counters

    def _resolve_fate_counter(self):
        """Resolve a fate dungeon counter."""
        self.held_dungeon_counters.append("fate")
        if self.current_phase == "COMBAT":
            self.combat_log.append("  Fate counter held for a monster's combat Fate Point.")
        else:
            self.combat_log.append("  Fate counter held until it can be used during combat.")

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
            start_wandering_combat=lambda trigger_tile, placement_mode="section": self._start_combat_random(
                roll_lair_encounter(), trigger_tile=trigger_tile, placement_mode=placement_mode
            ),
            resolve_magic_spell=lambda trapped_hero, spell_name, trap_origin=None: self._resolve_magic_trap_spell(
                trapped_hero, spell_name, trap_origin
            ),
            source="room_or_passage",
            affected_heroes=self.party,
        )

    def _resolve_escape_counter(self):
        """Resolve an escape dungeon counter."""
        if self.current_phase == "COMBAT":
            candidates = [
                monster for monster in self.monsters
                if monster.is_character and not monster.is_dead
            ]
            if candidates:
                monster = random.choice(candidates)
                self.escaped_character_monsters.append(self._serialize_escaped_character_monster(monster))
                self.monsters = [current for current in self.monsters if current is not monster]
                self.combat_log.append(
                    f"  Escape counter: {monster.name} escapes and can return through a later Character counter."
                )
                if not any(not current.is_dead for current in self.monsters):
                    self._end_combat()
                return

        if self.dungeon and self.dungeon.wandering_monsters:
            escaped_marker = random.choice(list(self.dungeon.wandering_monsters))
            self.dungeon.wandering_monsters.remove(escaped_marker)
            self.combat_log.append(f"  Something slips away in the dark near {escaped_marker}.")
            return

        self.combat_log.append("  Escape counter drawn, but there is no live character monster available to escape.")

    def _serialize_escaped_character_monster(self, monster: Monster) -> dict:
        """Capture enough state for an escaped character monster to return later."""
        return {
            "id": monster.id,
            "name": monster.name,
            "ws": monster.ws,
            "bs": monster.bs,
            "strength": monster.strength,
            "toughness": monster.toughness,
            "speed": monster.speed,
            "bravery": monster.bravery,
            "intelligence": monster.intelligence,
            "max_wounds": monster.max_wounds,
            "current_wounds": monster.current_wounds,
            "pv": monster.pv,
            "weapons": monster.weapons,
            "ranged": monster.ranged,
            "spellcasting": dict(getattr(monster, "spellcasting", {})),
            "special_rules": list(getattr(monster, "special_rules", [])),
            "is_sentry": monster.is_sentry,
            "is_character": True,
            "status_effects": list(getattr(monster, "status_effects", [])),
        }

    def _restore_escaped_character_monster(self, data: dict) -> Optional[Monster]:
        """Recreate an escaped character monster from saved counter state."""
        monster = self.monster_library.create_monster(str(data.get("id", "")))
        if monster is None:
            monster = Monster(
                monster_id=str(data.get("id", "escaped_character")),
                name=str(data.get("name", "Escaped Character")),
                ws=int(data.get("ws", 1)),
                bs=int(data.get("bs", 0)),
                strength=int(data.get("strength", 1)),
                toughness=int(data.get("toughness", 1)),
                speed=int(data.get("speed", 1)),
                bravery=int(data.get("bravery", 1)),
                intelligence=int(data.get("intelligence", 1)),
                wounds=int(data.get("max_wounds", 1)),
                pv=int(data.get("pv", 1)),
                weapons=list(data.get("weapons", [])),
                ranged=data.get("ranged"),
                spellcasting=dict(data.get("spellcasting", {})),
                special_rules=list(data.get("special_rules", [])),
                is_sentry=bool(data.get("is_sentry", False)),
                is_character=True,
            )
        monster.current_wounds = max(1, int(data.get("current_wounds", monster.current_wounds)))
        monster.spellcasting = dict(data.get("spellcasting", getattr(monster, "spellcasting", {})))
        monster.status_effects = list(data.get("status_effects", []))
        monster.is_dead = False
        monster.is_character = True
        return monster

    def _place_returning_character_monster(self, monster: Monster, trigger_tile: Tuple[int, int]):
        """Place a returning character in a legal reinforcement square near the trigger."""
        valid_tiles = self._get_reinforcement_tiles(trigger_tile)
        if valid_tiles:
            pos = valid_tiles[0]
        else:
            pos = trigger_tile
        monster.x, monster.y = pos
    
    def _run_combat_gm_phase(self):
        """Run GM phase during combat."""
        self._run_mad_hero_phase()
        self._refresh_special_monster_states()
        self._resolve_hazard_npc_rounds()
        self.monsters, self.combat_log = run_gm_phase(
            self.monsters,
            self.party,
            self.dungeon,
            self.combat_log,
            monster_spell_action=self._monster_cast_spell,
            pursuit_mode=self.combat_pursuit_active,
            monster_fate_roll=self._try_spend_monster_fate_for_failed_roll,
        )
        self._refresh_hero_death_turns()
        
        # Remove dead monsters from list
        self.monsters = [m for m in self.monsters if not m.is_dead]
        self._refresh_special_monster_states()
        
        # Check if combat ends
        if not self.monsters:
            self._end_combat()
            return

        self._evaluate_escape_after_gm_phase()
        
        # Check for dead heroes
        if not any(not hero.is_dead and not hero.is_ko for hero in self.party):
            self._game_over()

    def _get_reachable_tiles_for_mad_hero(self, hero: Hero, allowance: int) -> List[Tuple[int, int]]:
        """Return reachable tiles for a hero acting under GM control."""
        occupied = self._get_occupied_tiles_for_hero(hero)
        frontier: List[Tuple[int, int, int]] = [(hero.x, hero.y, 0)]
        seen = {(hero.x, hero.y)}
        reachable = [(hero.x, hero.y)]
        while frontier:
            x, y, dist = frontier.pop(0)
            if dist >= allowance:
                continue
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen or (nx, ny) in occupied:
                    continue
                if not self.dungeon.is_walkable(nx, ny):
                    continue
                seen.add((nx, ny))
                reachable.append((nx, ny))
                frontier.append((nx, ny, dist + 1))
        return reachable

    def _move_mad_hero_toward_target(self, hero: Hero, target: Hero, allowance: int) -> bool:
        """Move a maddened hero toward the nearest square adjacent to a target."""
        occupied = self._get_occupied_tiles_for_hero(hero)
        candidate_paths: List[List[Tuple[int, int]]] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = target.x + dx, target.y + dy
            if (tx, ty) in occupied:
                continue
            if not self.dungeon.is_walkable(tx, ty):
                continue
            path = find_path_bfs(hero.x, hero.y, tx, ty, self.dungeon, occupied)
            if path is not None:
                candidate_paths.append(path)
        if not candidate_paths:
            return False
        path = min(candidate_paths, key=len)
        if len(path) <= 1:
            return False
        steps = min(allowance, len(path) - 1)
        dest = path[steps]
        hero.x, hero.y = dest
        self.dungeon._explore_from(hero.x, hero.y)
        self.combat_log.append(f"{hero.name} staggers under GM control to ({hero.x}, {hero.y}).")
        return True

    def _move_mad_hero_away(self, hero: Hero, allowance: int) -> bool:
        """Move a non-hostile maddened hero in a disruptive random direction."""
        reachable = self._get_reachable_tiles_for_mad_hero(hero, allowance)
        if len(reachable) <= 1:
            return False
        others = [ally for ally in self.party if ally.id != hero.id and not ally.is_dead]
        if not others:
            return False
        def score(pos: Tuple[int, int]) -> Tuple[int, int, int]:
            nearest = min(abs(pos[0] - other.x) + abs(pos[1] - other.y) for other in others)
            return (nearest, pos[1], pos[0])
        dest = max(reachable, key=score)
        if dest == (hero.x, hero.y):
            return False
        hero.x, hero.y = dest
        self.dungeon._explore_from(hero.x, hero.y)
        self.combat_log.append(f"{hero.name} wanders under madness to ({hero.x}, {hero.y}).")
        return True

    def queue_madness_move(self, hero: Hero, x: int, y: int) -> str:
        """Queue the GM's chosen movement for a Gas Madness controlled hero."""
        madness = hero.get_status_effect("madness")
        if madness is None:
            return f"{hero.name} is not under madness."
        orders = madness.setdefault("gm_orders", [])
        orders.append({"destination": [int(x), int(y)]})
        return f"GM movement queued for {hero.name}."

    def queue_mindstealer_action(
        self,
        hero: Hero,
        x: int,
        y: int,
        attack_target: Optional[Hero] = None,
    ) -> str:
        """Queue the GM's chosen move and optional ally attack for a Mindstealer victim."""
        madness = hero.get_status_effect("madness")
        if madness is None:
            return f"{hero.name} is not under Mindstealer control."
        if not bool(madness.get("madness_attack_allies", False)):
            return f"{hero.name} cannot be ordered to attack allies."
        order = {"destination": [int(x), int(y)]}
        if attack_target is not None:
            order["attack_target_id"] = attack_target.id
        orders = madness.setdefault("gm_orders", [])
        orders.append(order)
        return f"GM Mindstealer action queued for {hero.name}."

    def _apply_queued_madness_order(
        self,
        hero: Hero,
        madness: dict,
        allowance: int,
        attack_allies: bool,
    ) -> bool:
        """Apply one queued GM order for a hero under madness."""
        orders = madness.get("gm_orders")
        if not isinstance(orders, list) or not orders:
            return False
        order = orders.pop(0)
        destination = order.get("destination") if isinstance(order, dict) else None
        if not isinstance(destination, list) or len(destination) != 2:
            self.combat_log.append(f"{hero.name}'s queued GM order is invalid; engine policy takes over.")
            return False

        dest = (int(destination[0]), int(destination[1]))
        occupied = self._get_occupied_tiles_for_hero(hero)
        path = find_path_bfs(hero.x, hero.y, dest[0], dest[1], self.dungeon, occupied)
        if path is None or len(path) - 1 > allowance:
            self.combat_log.append(
                f"{hero.name}'s queued GM move to {dest} is not reachable; engine policy takes over."
            )
            return False
        hero.x, hero.y = dest
        self.dungeon._explore_from(hero.x, hero.y)
        self.combat_log.append(f"GM moves {hero.name} under madness to ({hero.x}, {hero.y}).")

        if attack_allies:
            target_id = order.get("attack_target_id") if isinstance(order, dict) else None
            target = next((ally for ally in self.party if ally.id == target_id and not ally.is_dead), None)
            if target is not None and self.dungeon.is_adjacent(hero.x, hero.y, target.x, target.y):
                resolve_hero_vs_hero_attack(hero, target, self.combat_log)
            elif target_id is not None:
                self.combat_log.append(f"{hero.name}'s queued Mindstealer attack has no adjacent target.")
        return True

    def _run_mad_hero_phase(self):
        """Let heroes under madness act during the GM phase."""
        phase_name = self.current_phase.lower()
        for hero in self.party:
            madness = hero.get_status_effect("madness")
            if madness is None or hero.is_dead or hero.is_ko:
                continue
            if hero.is_restrained_by_mindstealer():
                self.combat_log.append(f"{hero.name} struggles, but the party keeps them restrained.")
                continue
            allowance = hero.get_movement_allowance(phase_name)
            attack_allies = bool(madness.get("madness_attack_allies", False))
            if self._apply_queued_madness_order(hero, madness, allowance, attack_allies):
                continue
            others = [ally for ally in self.party if ally.id != hero.id and not ally.is_dead]
            if not others:
                continue
            target = min(others, key=lambda ally: abs(hero.x - ally.x) + abs(hero.y - ally.y))
            if attack_allies:
                self._move_mad_hero_toward_target(hero, target, allowance)
                adjacent_targets = [
                    ally for ally in others
                    if self.dungeon.is_adjacent(hero.x, hero.y, ally.x, ally.y)
                ]
                if adjacent_targets:
                    defender = min(adjacent_targets, key=lambda ally: (ally.current_wounds, ally.name))
                    resolve_hero_vs_hero_attack(hero, defender, self.combat_log)
            else:
                self._move_mad_hero_away(hero, allowance)
    
    def _start_combat_with_positions(self, monster_data: List[Tuple[Tuple[int, int], str]]):
        """Start combat for monsters already discovered in an encountered room section."""
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        self.combat_escape_pending_closed_door = False
        self.combat_pursuit_active = False
        self.combat_escape_closed_doors = []
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self._reset_combat_turn_flags()
        
        # Extract monster IDs
        monster_ids = [mid for _, mid in monster_data]
        
        # Find the room containing these monsters - use the encountered room section
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
        
        # Surprise roll before placement
        has_elf = any(h.race == "Elf" for h in self.party)
        preview_monsters = [self.monster_library.create_monster(mid) for mid in monster_ids]
        has_sentry = any(monster and monster.is_sentry for monster in preview_monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")

        favor_side = "heroes" if winner == "heroes" else "gm"
        self.monsters = place_monsters_ahq_section(
            monster_ids,
            valid_tiles,
            self.dungeon,
            self.party,
            self.monster_library,
            self.combat_log,
            favor_side=favor_side,
        )
        self._play_held_character_counters(first_monster_pos, "section")
        self._play_held_combat_counters()
        
        if winner == "gm":
            self.combat_log.append("Monsters surprise the heroes!")
            # Heroes may reposition each monster by up to one square.
            for monster in self.monsters:
                moved = move_monster_one_square_away(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  Heroes reposition {monster.name} to ({monster.x}, {monster.y})")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
            for monster in self.monsters:
                moved = surprise_move_monster(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  GM moves {monster.name} to ({monster.x}, {monster.y})")
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        if self.current_phase == "COMBAT" and self.hero_phase_active:
            self._apply_fearsome_checks("Start of Hero phase")
        
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
        preserve_placed_monsters: bool = False,
        summary_prefix: str = "Combat started with",
    ):
        """Start combat with pre-placed monsters and optional surprise modifiers."""
        if self.current_phase == "COMBAT" and any(not monster.is_dead for monster in self.monsters):
            existing_ids = {m.instance_id for m in self.monsters}
            new_monsters = [m for m in monsters if not m.is_dead and m.instance_id not in existing_ids]
            if new_monsters:
                self.monsters.extend(new_monsters)
                monster_summary = ", ".join(f"{m.name}@({m.x},{m.y})" for m in new_monsters[:8])
                if len(new_monsters) > 8:
                    monster_summary += ", ..."
                self.combat_log.append(
                    f"Additional monsters join the current combat: {len(new_monsters)} monster(s): {monster_summary}"
                )
                first_pos = (new_monsters[0].x, new_monsters[0].y)
                self._play_held_character_counters(first_pos, "section")
                self.save_game()
            return
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        self.combat_escape_pending_closed_door = False
        self.combat_pursuit_active = False
        self.combat_escape_closed_doors = []
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self._reset_combat_turn_flags()
        
        encountered_monsters = [m for m in monsters if not m.is_dead]
        section_tiles = self._get_visible_section_tiles_for_monsters(encountered_monsters)

        monster_summary = ", ".join(f"{m.name}@({m.x},{m.y})" for m in encountered_monsters[:8])
        if len(encountered_monsters) > 8:
            monster_summary += ", ..."
        self.combat_log.append(
            f"{summary_prefix} {len(encountered_monsters)} visible monsters: {monster_summary}"
        )

        # Surprise roll
        has_elf = any(h.race == "Elf" for h in self.party) and not ignore_elf_surprise_bonus
        has_sentry = any(m.is_sentry for m in encountered_monsters)
        
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

        if section_tiles and not preserve_placed_monsters:
            monster_ids = [m.id for m in encountered_monsters]
            favor_side = "heroes" if winner == "heroes" else "gm"
            placed = place_monsters_ahq_section(
                monster_ids,
                section_tiles,
                self.dungeon,
                self.party,
                self.monster_library,
                self.combat_log,
                favor_side=favor_side,
            )
            existing_ids = {m.instance_id for m in self.monsters}
            self.monsters = [m for m in self.monsters if m.instance_id in existing_ids and m not in encountered_monsters]
            self.monsters.extend(placed)
            encountered_monsters = placed
        elif preserve_placed_monsters:
            existing_ids = {m.instance_id for m in self.monsters}
            self.monsters.extend(
                monster
                for monster in encountered_monsters
                if monster.instance_id not in existing_ids
            )

        trigger_tile = (encountered_monsters[0].x, encountered_monsters[0].y) if encountered_monsters else None
        self._play_held_character_counters(trigger_tile, "section")
        self._play_held_combat_counters()
        
        if winner == "gm":
            self.combat_log.append("Monsters surprise the heroes!")
            for monster in encountered_monsters:
                moved = move_monster_one_square_away(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  Heroes reposition {monster.name} to ({monster.x}, {monster.y})")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
            for monster in encountered_monsters:
                moved = surprise_move_monster(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  GM moves {monster.name} to ({monster.x}, {monster.y})")
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        if self.current_phase == "COMBAT" and self.hero_phase_active:
            self._apply_fearsome_checks("Start of Hero phase")
        
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
        placement_tiles: Optional[List[Tuple[int, int]]] = None,
        preserve_placed_monsters: bool = False,
    ) -> List[Monster]:
        """Start a room-based hazard combat using the room interior for placement."""
        source_tiles = placement_tiles if placement_tiles is not None else self.dungeon.get_room_interior_tiles(room)
        room_tiles = [(x, y) for (x, y) in source_tiles if self.dungeon.is_walkable(x, y)]
        if not room_tiles and placement_tiles is not None:
            room_tiles = [
                (x, y)
                for (x, y) in self.dungeon.get_room_interior_tiles(room)
                if self.dungeon.is_walkable(x, y)
            ]
        monsters = place_monsters_ahq_section(
            monster_ids,
            room_tiles,
            self.dungeon,
            self.party,
            self.monster_library,
            self.combat_log,
            favor_side="gm",
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
            preserve_placed_monsters=preserve_placed_monsters,
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
            setattr(witch, "witch_rounds_remaining", 1)
            return witch
        raise ValueError(f"Unsupported hazard NPC type: {npc_type}")

    def place_hazard_chest(
        self,
        room: dict,
        candidate_tiles: Optional[List[Tuple[int, int]]] = None,
    ) -> Optional[Tuple[int, int]]:
        """Place a visible chest for hazards such as the chasm room."""
        anchor = get_hazard_anchor(room)
        if anchor is None:
            return None

        occupied = {
            (hero.x, hero.y)
            for hero in self.party
            if not hero.is_dead
        }
        occupied.update(
            (monster.x, monster.y)
            for monster in self.monsters
            if not monster.is_dead
        )
        source_tiles = candidate_tiles if candidate_tiles is not None else self.dungeon.get_room_interior_tiles(room)
        interior_tiles = [
            pos for pos in source_tiles
            if pos != anchor and pos not in occupied and self.dungeon.get_tile(*pos) == self.dungeon.TileType.FLOOR
        ]
        if not interior_tiles and candidate_tiles is not None:
            interior_tiles = [
                pos for pos in self.dungeon.get_room_interior_tiles(room)
                if pos != anchor and pos not in occupied and self.dungeon.get_tile(*pos) == self.dungeon.TileType.FLOOR
            ]
        if not interior_tiles:
            return None

        chest_pos = choose_room_chest_position(self.dungeon, room, interior_tiles)
        if chest_pos is None:
            return None
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

            room_id = getattr(monster, "witch_room_id", None)
            room = self._find_room_by_id(room_id)
            entrance = tuple(room.get("entrance", [])) if room else None
            if entrance and len(entrance) == 2 and self.dungeon.get_tile(*entrance) == self.dungeon.TileType.DOOR_CLOSED:
                if room is not None:
                    hazard = room.get("hazard") or {}
                    hazard["resolved"] = True
                self.combat_log.append(f"The Witch is sealed away behind the closed door and cannot escape.")
                monster.is_dead = True
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
    
    def _start_combat_random(
        self,
        monster_ids: List[str],
        trigger_tile: Optional[Tuple[int, int]] = None,
        placement_mode: str = "section",
    ):
        """Start combat with freshly generated monsters using AHQ section placement."""
        if self.current_phase == "COMBAT" and any(not monster.is_dead for monster in self.monsters):
            self._spawn_reinforcements(
                monster_ids,
                trigger_tile=trigger_tile,
                reason="Additional monsters",
                placement_mode=("far_los" if placement_mode == "far_los" else "section"),
            )
            self.save_game()
            return
        self.current_phase = "COMBAT"
        self.mode = "COMBAT"
        self.combat_escape_pending_closed_door = False
        self.combat_pursuit_active = False
        self.combat_escape_closed_doors = []
        
        # Reset hero actions for new combat round
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "COMBAT")
            for h in self.party
        }
        self._reset_combat_turn_flags()
        
        # Get valid spawn tiles
        if trigger_tile and placement_mode == "far_los":
            valid_tiles = self._get_far_los_reinforcement_tiles()
            self.combat_log.append(f"  Wandering monsters seek far line-of-sight positions, {len(valid_tiles)} valid tiles")
        elif trigger_tile:
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
        
        # Surprise roll before placement
        has_elf = any(h.race == "Elf" for h in self.party)
        preview_monsters = [self.monster_library.create_monster(mid) for mid in monster_ids]
        has_sentry = any(monster and monster.is_sentry for monster in preview_monsters)
        
        winner, hero_roll, gm_roll = do_surprise_roll(has_elf, has_sentry)
        
        self.combat_log.append(f"Surprise roll! Heroes: {hero_roll}, GM: {gm_roll}")

        if trigger_tile and placement_mode == "section":
            section_tiles = [
                pos for pos in self._get_section_tiles(trigger_tile[0], trigger_tile[1])
                if self.dungeon.is_walkable(pos[0], pos[1])
            ]
        elif trigger_tile and placement_mode == "far_los":
            section_tiles = valid_tiles
        else:
            section_tiles = valid_tiles
        if not section_tiles:
            section_tiles = valid_tiles

        favor_side = "heroes" if winner == "heroes" else "gm"
        if placement_mode == "far_los":
            self.monsters = place_monsters_far_los(
                monster_ids,
                section_tiles,
                self.dungeon,
                self.party,
                self.monster_library,
                self.combat_log,
            )
        else:
            self.monsters = place_monsters_ahq_section(
                monster_ids,
                section_tiles,
                self.dungeon,
                self.party,
                self.monster_library,
                self.combat_log,
                favor_side=favor_side,
            )
        self.combat_log.append(f"  Placed {len(self.monsters)} monsters: {[(m.name, m.x, m.y) for m in self.monsters]}")
        self._play_held_character_counters(trigger_tile, placement_mode)
        self._play_held_combat_counters()
        
        if winner == "gm":
            self.combat_log.append("Monsters surprise the heroes!")
            for monster in self.monsters:
                moved = move_monster_one_square_away(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  Heroes reposition {monster.name} to ({monster.x}, {monster.y})")
            self.combat_log.append("Heroes lose first turn!")
            self.hero_phase_active = False
        elif winner == "heroes":
            self.combat_log.append("Heroes win surprise!")
            for monster in self.monsters:
                moved = surprise_move_monster(monster, self.dungeon, self.party, self.monsters)
                if moved:
                    self.combat_log.append(f"  GM moves {monster.name} to ({monster.x}, {monster.y})")
        else:
            self.combat_log.append("Neither side surprised!")
        
        # If monsters won surprise, run GM phase first
        if winner == "gm":
            self._run_combat_gm_phase()
            self.hero_phase_active = True
        if self.current_phase == "COMBAT" and self.hero_phase_active:
            self._apply_fearsome_checks("Start of Hero phase")
        
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

    def _get_far_los_reinforcement_tiles(self) -> List[Tuple[int, int]]:
        """Find explored walkable tiles for far-line-of-sight counter placement."""
        occupied = {
            tile
            for monster in self.monsters
            if not monster.is_dead
            for tile in monster.get_occupied_tiles()
        }
        occupied.update(
            (hero.x, hero.y)
            for hero in self.party
            if not hero.is_dead and not hero.is_ko
        )
        return [
            pos for pos in self.dungeon.explored
            if self.dungeon.is_walkable(pos[0], pos[1]) and pos not in occupied
        ]

    def _spawn_reinforcements(
        self,
        monster_ids: List[str],
        trigger_tile: Optional[Tuple[int, int]] = None,
        reason: str = "Reinforcements",
        placement_mode: str = "far_los",
        play_character_counters: bool = True,
    ) -> List[Monster]:
        """Add monsters to an existing combat without replacing current monsters."""
        valid_tiles = (
            self._get_far_los_reinforcement_tiles()
            if placement_mode == "far_los"
            else self._get_reinforcement_tiles(trigger_tile)
        )
        if not valid_tiles:
            self.combat_log.append(f"  {reason}: no valid reinforcement positions.")
            return []

        if placement_mode == "section" and trigger_tile:
            section_tiles = [
                pos for pos in self._get_section_tiles(trigger_tile[0], trigger_tile[1])
                if pos in valid_tiles
            ]
            if section_tiles:
                new_monsters = place_monsters_ahq_section(
                    monster_ids,
                    section_tiles,
                    self.dungeon,
                    self.party,
                    self.monster_library,
                    self.combat_log,
                    favor_side="gm",
                )
            else:
                new_monsters = place_monsters_far_los(
                    monster_ids,
                    valid_tiles,
                    self.dungeon,
                    self.party,
                    self.monster_library,
                    self.combat_log,
                )
        else:
            new_monsters = place_monsters_far_los(
                monster_ids,
                valid_tiles,
                self.dungeon,
                self.party,
                self.monster_library,
                self.combat_log,
            )
        self.monsters.extend(new_monsters)
        self.combat_log.append(
            f"  {reason}: placed {len(new_monsters)} monster(s): "
            f"{[(m.name, m.x, m.y) for m in new_monsters]}"
        )
        if play_character_counters:
            self._play_held_character_counters(trigger_tile, placement_mode)
        return new_monsters

    def _play_held_combat_counters(self):
        """Play any counters that are only legal at the start of combat."""
        if self.current_phase != "COMBAT" or not self.held_dungeon_counters:
            return

        remaining_counters: List[str] = []
        for counter in self.held_dungeon_counters:
            if counter == "ambush":
                if self.ambush_counter_played_this_combat_turn:
                    remaining_counters.append(counter)
                    continue
                self.combat_log.append("Held ambush counter played as combat begins.")
                if not self._resolve_ambush_counter(first_turn=True):
                    remaining_counters.append(counter)
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
    
    def _evaluate_escape_after_gm_phase(self):
        """Resolve escape and pursuit state after a combat GM phase."""
        self._resolve_pursuit_door_opening()
        visible_monsters = self._get_visible_monsters()
        if visible_monsters:
            if self.combat_pursuit_active:
                self.combat_log.append("Pursuit ends as the monsters catch sight of the heroes again.")
            self.combat_pursuit_active = False
            self.combat_escape_pending_closed_door = False
            self.combat_escape_closed_doors = []
            return

        if self.combat_pursuit_active:
            self.combat_log.append("The heroes stay out of sight and escape the pursuit.")
            self._end_combat(escaped=True)
            return

        if self.combat_escape_pending_closed_door:
            self.combat_escape_pending_closed_door = False
            self.combat_pursuit_active = True
            self.combat_log.append("The monsters are allowed one more turn of pursuit after the closed door.")
            return

        self.combat_log.append("The heroes slip out of sight and escape the combat.")
        self._end_combat(escaped=True)

    def _resolve_pursuit_door_opening(self):
        """Allow monsters in pursuit to reopen closed escape doors they reach."""
        if not self.combat_escape_closed_doors:
            return
        reopened: List[Tuple[int, int]] = []
        for door_pos in list(self.combat_escape_closed_doors):
            if self.dungeon.get_tile(*door_pos) != self.dungeon.TileType.DOOR_CLOSED:
                reopened.append(door_pos)
                continue
            opener = next(
                (
                    monster for monster in self.monsters
                    if not monster.is_dead and any(
                        self.dungeon.is_adjacent(mx, my, door_pos[0], door_pos[1])
                        for mx, my in monster.get_occupied_tiles()
                    )
                ),
                None,
            )
            if opener is None:
                continue
            self.dungeon.grid[door_pos] = self.dungeon.TileType.DOOR_OPEN
            if door_pos in self.dungeon.doors:
                self.dungeon.doors[door_pos]["is_open"] = True
            self.dungeon.explored.add(door_pos)
            if self.dungeon.get_tile(*door_pos) == self.dungeon.TileType.DOOR_OPEN:
                self.combat_log.append(f"{opener.name} forces the door at {door_pos} open during the pursuit.")
                reopened.append(door_pos)
        if reopened:
            self.combat_escape_closed_doors = [
                pos for pos in self.combat_escape_closed_doors if pos not in reopened
            ]

    def _end_combat(self, escaped: bool = False):
        """End combat and return to exploration."""
        self.current_phase = "EXPLORATION"
        self.mode = "DUNGEON"
        self.pending_board_action = None
        self.combat_pursuit_active = False
        self.combat_escape_pending_closed_door = False
        self.combat_escape_closed_doors = []
        self.combat_log.append("Combat ended. The heroes escape!" if escaped else "Combat ended. Monsters defeated!")
        recovered_totals = {"arrows": 0, "bolts": 0}
        if not escaped:
            for hero in self.party:
                recovered = hero.recover_spent_ammo()
                for ammo_type, amount in recovered.items():
                    recovered_totals[ammo_type] += int(amount)
        self.monsters = []
        for hero in self.party:
            hero.clear_status_effects("combat")
            hero.clear_status_effects("next_combat")
            if hero.is_ko and not hero.is_dead:
                hero.current_wounds = 1
                hero.is_ko = False
                self.combat_log.append(f"{hero.name} regains consciousness with 1 wound.")
        if recovered_totals["arrows"] or recovered_totals["bolts"]:
            parts = []
            if recovered_totals["arrows"]:
                parts.append(f"{recovered_totals['arrows']} arrows")
            if recovered_totals["bolts"]:
                parts.append(f"{recovered_totals['bolts']} bolts")
            self.combat_log.append(f"Recovered spent missiles after the fight: {', '.join(parts)}.")
        self._clear_next_exploration_magic_effects()
        # Reset for exploration phase
        self.hero_movement_remaining = {
            h.id: self._get_movement_allowance_for_phase(h, "EXPLORATION")
            for h in self.party
        }
        self._reset_combat_turn_flags()
    
    def open_door(self, x: int, y: int) -> bool:
        """Open a door and possibly trigger combat."""
        self.ensure_phase_consistency()
        if not self.dungeon.open_door(x, y):
            return False
        
        self.combat_log.append(f"Door opened at ({x}, {y})")

        if self.ensure_phase_consistency():
            self.save_game()
            return True
        
        self.save_game()
        return True
    
    def _exit_dungeon(self):
        """Exit the dungeon and return to tavern."""
        self.mode = "TAVERN"
        self.pending_board_action = None
        self.combat_log.append("Party exits the dungeon!")
        summary_messages: List[str] = ["Party exits the dungeon!"]
        followers_summary: List[str] = []
        rogue_stolen = 0

        if self.expedition_followers.get("maiden"):
            self.adjust_party_gold(100)
            self.gold_found += 100
            maiden_msg = "The Maiden is returned safely and her family rewards the party with 100 gold crowns."
            self.combat_log.append(maiden_msg)
            summary_messages.append(maiden_msg)
            followers_summary.append("Maiden rescued")

        if self.expedition_followers.get("rogue"):
            betrayal_roll = random.randint(1, 12)
            if betrayal_roll >= 7:
                stolen = self.get_party_gold_total() // 2
                rogue_stolen = stolen
                if stolen > 0:
                    self.adjust_party_gold(-stolen)
                    self.gold_found = max(0, self.gold_found - stolen)
                    rogue_msg = f"Rogue betrayal roll: {betrayal_roll}. The Rogue slips away with {stolen} gold crowns."
                    self.combat_log.append(rogue_msg)
                    summary_messages.append(rogue_msg)
                else:
                    rogue_msg = (
                        f"Rogue betrayal roll: {betrayal_roll}. "
                        "The Rogue deserts the party but finds no gold to steal."
                    )
                    self.combat_log.append(rogue_msg)
                    summary_messages.append(rogue_msg)
            else:
                rogue_msg = f"Rogue betrayal roll: {betrayal_roll}. The Rogue keeps his bargain and leaves peacefully."
                self.combat_log.append(rogue_msg)
                summary_messages.append(rogue_msg)
            followers_summary.append("Rogue encountered")

        if self.expedition_followers.get("man_at_arms"):
            man_msg = "The rescued Man-at-Arms survives the expedition and is available as a henchman after the delve."
            self.combat_log.append(man_msg)
            summary_messages.append(man_msg)
            followers_summary.append("Man-at-Arms rescued")

        survivors = [hero.name for hero in self.party if not hero.is_dead]
        fallen = [hero.name for hero in self.party if hero.is_dead]
        ammo_state = {
            hero.name: {
                "arrows": hero.get_ammo_count("arrows"),
                "bolts": hero.get_ammo_count("bolts"),
            }
            for hero in self.party
        }

        for hero in self.party:
            if not hero.is_dead:
                hero.expeditions_completed += 1
                hero.paid_spells_learned = 0
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

        self.last_expedition_summary = {
            "gold_found": int(self.gold_found),
            "experience_gained": int(self.experience_gained),
            "survivors": survivors,
            "fallen": fallen,
            "followers": followers_summary,
            "rogue_stolen": int(rogue_stolen),
            "ammo": ammo_state,
            "left_behind_treasure": list(self.left_behind_treasure),
            "messages": summary_messages,
        }
    
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
            "party_stash_gold": int(self.party_stash_gold),
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
                    "special_rules": list(getattr(m, "special_rules", [])),
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
                        "status_effects": list(getattr(m, "status_effects", [])),
                        "spellcasting": dict(getattr(m, "spellcasting", {})),
                    },
                }
                for m in self.monsters
            ],
            "current_phase": self.current_phase,
            "hero_phase_active": self.hero_phase_active,
            "hero_movement_remaining": self.hero_movement_remaining,
            "hero_has_attacked": list(self.hero_has_attacked),
            "hero_ran_this_phase": list(self.hero_ran_this_phase),
            "hero_turn_start_positions": {
                hero_id: [pos[0], pos[1]]
                for hero_id, pos in self.hero_turn_start_positions.items()
            },
            "entered_tiles": [[pos[0], pos[1]] for pos in sorted(self.entered_tiles)],
            "turn_count": self.turn_count,
            "ambush_counter_played_this_combat_turn": self.ambush_counter_played_this_combat_turn,
            "combat_escape_pending_closed_door": self.combat_escape_pending_closed_door,
            "combat_pursuit_active": self.combat_pursuit_active,
            "combat_escape_closed_doors": [[pos[0], pos[1]] for pos in self.combat_escape_closed_doors],
            "combat_log": self.combat_log[-50:],  # Last 50 messages
            "experience_gained": self.experience_gained,
            "gold_found": self.gold_found,
            "dungeon_counter_pool": self.dungeon_counter_pool,
            "held_dungeon_counters": self.held_dungeon_counters,
            "escaped_character_monsters": self.escaped_character_monsters,
            "section_spell_effects": self.section_spell_effects,
            "expedition_followers": self.expedition_followers,
            "pending_board_action": self.pending_board_action,
            "left_behind_treasure": self.left_behind_treasure,
            "active_fireball_traps": self.active_fireball_traps,
            "quest_id": self.quest_id,
            "quest_specific_stairs_down": self.quest_specific_stairs_down,
            "heroquest_maze_available": self.heroquest_maze_available,
            "pending_sub_level_entry": self.pending_sub_level_entry,
            "active_sub_level": self.active_sub_level,
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
                self.dungeon.game_state = self
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
                        special_rules=m_data.get("special_rules", []),
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
                monster.special_rules = list(m_data.get("special_rules", getattr(monster, "special_rules", [])))
                monster.is_sentry = m_data.get("is_sentry", monster.is_sentry)
                monster.is_character = m_data.get("is_character", monster.is_character)
                monster.is_dead = m_data["is_dead"]
                for key, value in m_data.get("special_state", {}).items():
                    if key == "status_effects":
                        monster.status_effects = list(value or [])
                        continue
                    if key == "spellcasting":
                        monster.spellcasting = dict(value or {})
                        continue
                    if value is not None:
                        setattr(monster, key, value)
                self.monsters.append(monster)
            
            self.current_phase = data.get("current_phase", "EXPLORATION")
            self.hero_phase_active = data.get("hero_phase_active", True)
            self.hero_movement_remaining = data.get("hero_movement_remaining", {h["id"]: h["speed"] for h in data.get("party", [])})
            self.hero_has_attacked = set(data.get("hero_has_attacked", []))
            self.hero_ran_this_phase = set(data.get("hero_ran_this_phase", []))
            self.hero_turn_start_positions = {
                hero_id: (int(pos[0]), int(pos[1]))
                for hero_id, pos in data.get("hero_turn_start_positions", {}).items()
                if isinstance(pos, list) and len(pos) == 2
            }
            self.entered_tiles = {
                (int(pos[0]), int(pos[1]))
                for pos in data.get("entered_tiles", [])
                if isinstance(pos, list) and len(pos) == 2
            }
            if not self.entered_tiles:
                self.entered_tiles = {(hero.x, hero.y) for hero in self.party}
            if not self.hero_turn_start_positions:
                self._capture_hero_turn_start_positions()
            self.turn_count = data.get("turn_count", 0)
            self.ambush_counter_played_this_combat_turn = bool(
                data.get("ambush_counter_played_this_combat_turn", False)
            )
            self.combat_escape_pending_closed_door = data.get("combat_escape_pending_closed_door", False)
            self.combat_pursuit_active = data.get("combat_pursuit_active", False)
            self.combat_escape_closed_doors = [
                (int(pos[0]), int(pos[1]))
                for pos in data.get("combat_escape_closed_doors", [])
                if isinstance(pos, list) and len(pos) == 2
            ]
            self.combat_log = data.get("combat_log", [])
            self.experience_gained = data.get("experience_gained", 0)
            self.gold_found = data.get("gold_found", 0)
            self.party_stash_gold = int(data.get("party_stash_gold", 0))
            self.dungeon_counter_pool = data.get("dungeon_counter_pool", create_dungeon_counter_pool())
            self.held_dungeon_counters = data.get("held_dungeon_counters", [])
            self.escaped_character_monsters = list(data.get("escaped_character_monsters", []))
            self.section_spell_effects = data.get("section_spell_effects", [])
            self.expedition_followers = data.get(
                "expedition_followers",
                {"maiden": False, "man_at_arms": False, "rogue": False},
            )
            pending_board_action = data.get("pending_board_action")
            self.pending_board_action = dict(pending_board_action) if isinstance(pending_board_action, dict) else None
            self.left_behind_treasure = list(data.get("left_behind_treasure", []))
            self.active_fireball_traps = list(data.get("active_fireball_traps", []))
            self.quest_id = data.get("quest_id")
            self.quest_specific_stairs_down = bool(data.get("quest_specific_stairs_down", False))
            self.heroquest_maze_available = bool(data.get("heroquest_maze_available", True))
            pending_sub_level_entry = data.get("pending_sub_level_entry")
            self.pending_sub_level_entry = (
                dict(pending_sub_level_entry) if isinstance(pending_sub_level_entry, dict) else None
            )
            active_sub_level = data.get("active_sub_level")
            self.active_sub_level = dict(active_sub_level) if isinstance(active_sub_level, dict) else None
            self.ensure_phase_consistency()
            
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

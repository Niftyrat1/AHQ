"""
Hero data model and creation for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import Optional, List, Dict, Any

from magic import get_default_known_spells, get_default_spell_components, normalize_spell_name


TABLES_PATH = Path(__file__).parent / "data" / "tables.json"
if TABLES_PATH.exists():
    with open(TABLES_PATH, "r", encoding="utf-8") as _tables_handle:
        _TABLES = json.load(_tables_handle)
else:
    _TABLES = {}

_DEFAULT_FISTS_PROFILE = {
    "display_name": "Fists",
    "type": "weapon",
    "strength_damage": {"1-2": 0, "3-4": 1, "5": 1, "6": 1, "7": 2, "8": 3, "9": 4, "10": 5, "11": 6, "12": 7},
    "fumble": None,
    "critical": None,
}

_ONE_PER_HERO_SUPPLIES = {"rope_10ft", "iron_spikes_10", "rat_poison", "screetch_bug"}
_STACKABLE_SUPPLIES = {"greek_fire_flask"}


def _strength_band_key(strength: int) -> str:
    """Map a strength value to the AHQ weapon-table band key."""
    if strength <= 2:
        return "1-2"
    if strength <= 4:
        return "3-4"
    return str(min(12, strength))


def _get_equipment_profile(item_key: Optional[str]) -> Dict[str, Any]:
    """Return the equipment table profile for an item key if known."""
    if not item_key:
        return {}
    return _TABLES.get("equipment", {}).get(item_key, {})


def _infer_equipment_key(item: Dict[str, Any]) -> Optional[str]:
    """Infer an equipment key from a saved item's explicit key or display name."""
    item_key = item.get("key")
    if item_key:
        return str(item_key)
    item_name = str(item.get("name", "")).strip().lower().replace("-", " ")
    for key, data in _TABLES.get("equipment", {}).items():
        display = str(data.get("display_name", key)).strip().lower().replace("-", " ")
        if item_name == display or item_name == key.replace("_", " "):
            return key
    return None


class Hero:
    """Represents a hero in the game."""
    
    def __init__(
        self,
        name: str,
        race: str,
        class_type: str,
        ws: int,
        bs: int,
        strength: int,
        toughness: int,
        speed: int,
        bravery: int,
        intelligence: int,
        wounds: int,
        fate: int,
        gold: int = 0,
        equipment: Optional[List[Dict]] = None,
        id: Optional[str] = None,
        known_spells: Optional[List[str]] = None,
        spell_components: Optional[Dict[str, int]] = None,
        inventory: Optional[Dict[str, int]] = None,
        ammo: Optional[Dict[str, int]] = None,
        expeditions_completed: int = 0,
        is_henchman: bool = False,
        henchman_type: Optional[str] = None,
        employer_id: Optional[str] = None,
        upkeep_cost: int = 0,
        hire_cost: int = 0,
        attracted_henchman: bool = False,
        paid_spells_learned: int = 0,
    ):
        self.id = id or f"{name.lower().replace(' ', '_')}_{random.randint(1000, 9999)}"
        self.name = name
        self.race = race
        self.class_type = class_type  # "Warrior" or "Wizard"
        
        # Characteristics
        self.ws = ws  # Weapon Skill
        self.bs = bs  # Ballistic Skill
        self.strength = strength
        self.toughness = toughness
        self.speed = speed
        self.bravery = bravery
        self.intelligence = intelligence
        self.max_wounds = wounds
        self.current_wounds = wounds
        self.max_fate = fate
        self.current_fate = fate
        
        # Resources
        self.gold = gold
        self.experience = 0
        self.total_pv = 0  # Proven Value (accumulated XP)
        
        # Equipment
        self.equipment = equipment or [{"name": "Dagger", "key": "dagger", "type": "weapon", "equipped": True}]
        self.known_spells = list(known_spells) if known_spells is not None else get_default_known_spells(class_type)
        self.spell_components = dict(spell_components) if spell_components is not None else get_default_spell_components(class_type)
        self.inventory = dict(inventory) if inventory is not None else {}
        self.ammo = dict(ammo) if ammo is not None else {"arrows": 0, "bolts": 0}
        self.ammo_spent = {"arrows": 0, "bolts": 0}
        self.last_ranged_ammo_effect: Optional[str] = None
        self.expeditions_completed = int(expeditions_completed)
        self.is_henchman = bool(is_henchman)
        self.henchman_type = str(henchman_type) if henchman_type else None
        self.employer_id = employer_id
        self.upkeep_cost = int(upkeep_cost)
        self.hire_cost = int(hire_cost)
        self.attracted_henchman = bool(attracted_henchman)
        self.paid_spells_learned = int(paid_spells_learned)
        
        # State
        self.is_dead = False
        self.is_ko = False
        self.trap_disarm_bonus = 0
        self.ko_turns = 0
        self.temp_fate_bonus = 0
        self.free_spell_cast = 0
        self.status_effects: List[Dict[str, Any]] = []
        self.death_turn: Optional[int] = None
        self.pending_fate_decision: Optional[Dict[str, Any]] = None
        self.turn_wounds_snapshot = wounds
        self.damage_taken_this_turn = 0
        
        # Position in dungeon (set when placed)
        self.x = 0
        self.y = 0
        self.is_selected = False
    
    def get_damage_dice(self) -> int:
        """Get number of damage dice for equipped weapon."""
        weapon = self.get_equipped_melee_weapon()
        if weapon is None:
            profile = _DEFAULT_FISTS_PROFILE
        else:
            profile = weapon
        strength_damage = profile.get("strength_damage")
        if isinstance(strength_damage, dict):
            band = _strength_band_key(self.get_effective_strength())
            return int(strength_damage.get(band, 0))
        return int(profile.get("damage_dice", 1))

    def get_equipped_melee_weapon(self) -> Optional[Dict[str, Any]]:
        """Return the equipped melee weapon, if any."""
        for item in self.equipment:
            if item.get("equipped") and item.get("type") == "weapon":
                item_name = str(item.get("name", "")).lower()
                if self.is_wizard() and not item.get("wizard_usable", False) and "rune sword" not in item_name and "dagger" not in item_name:
                    continue
                return item
        return None

    def _get_item_profile(self, item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Return a read-only merged equipment profile with table fallbacks."""
        if item is None:
            return {}
        profile = dict(_get_equipment_profile(_infer_equipment_key(item)))
        profile.update(item)
        return profile

    def get_equipped_ranged_weapon(self) -> Optional[Dict[str, Any]]:
        """Return the equipped ranged weapon, if any."""
        for item in self.equipment:
            if item.get("equipped") and item.get("type") == "ranged_weapon":
                return item
        return None

    def has_ranged_weapon(self) -> bool:
        """Check whether the hero has an equipped ranged weapon."""
        return self.get_equipped_ranged_weapon() is not None

    def get_ranged_damage_dice(self) -> int:
        """Get damage dice for the equipped ranged weapon."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return 0
        profile = self._get_item_profile(weapon)
        return int(profile.get("damage_dice", 1))

    def get_ranged_max_range(self) -> int:
        """Get the maximum range of the equipped ranged weapon."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return 0
        profile = self._get_item_profile(weapon)
        return int(profile.get("max_range", 0))

    def get_ranged_ammo_type(self) -> Optional[str]:
        """Return the ammunition type used by the equipped ranged weapon, if any."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return None
        profile = self._get_item_profile(weapon)
        weapon_key = str(profile.get("key", "")).strip().lower()
        weapon_name = str(profile.get("name", "")).strip().lower()
        if "crossbow" in weapon_key or "crossbow" in weapon_name:
            return "bolts"
        if any(token in weapon_key for token in ("bow",)) or any(token in weapon_name for token in ("bow",)):
            return "arrows"
        return None

    def ranged_weapon_consumes_ammo(self) -> bool:
        """Whether the equipped ranged weapon uses arrows or bolts."""
        return self.get_ranged_ammo_type() is not None

    def has_ammo_for_ranged_weapon(self) -> bool:
        """Whether the equipped ranged weapon has consumable ammo available."""
        ammo_type = self.get_ranged_ammo_type()
        if ammo_type is None:
            return True
        return self.get_ammo_count(ammo_type) > 0 or self._get_magic_ammo_item(ammo_type) is not None

    def consume_ranged_ammo(self) -> bool:
        """Spend one shot of ammunition for the equipped ranged weapon."""
        ammo_type = self.get_ranged_ammo_type()
        self.last_ranged_ammo_effect = None
        if ammo_type is None:
            return True
        magic_ammo = self._get_magic_ammo_item(ammo_type)
        if magic_ammo is not None:
            magic_ammo["quantity"] = int(magic_ammo.get("quantity", 0)) - 1
            self.last_ranged_ammo_effect = str(magic_ammo.get("ammo_effect", "")).strip().lower() or None
            if int(magic_ammo.get("quantity", 0)) <= 0:
                self.equipment.remove(magic_ammo)
            return True
        current = self.get_ammo_count(ammo_type)
        if current <= 0:
            return False
        self.ammo[ammo_type] = current - 1
        self.ammo_spent[ammo_type] = int(self.ammo_spent.get(ammo_type, 0)) + 1
        return True

    def _get_magic_ammo_item(self, ammo_type: str) -> Optional[Dict[str, Any]]:
        """Return the first compatible magic arrow/bolt bundle with shots left."""
        wanted = "arrow" if ammo_type == "arrows" else "bolt" if ammo_type == "bolts" else ammo_type
        for item in self.equipment:
            if item.get("type") != "ammo":
                continue
            if str(item.get("ammo_type", "")).strip().lower() != wanted:
                continue
            if int(item.get("quantity", 0)) > 0:
                return item
        return None

    def recover_spent_ammo(self) -> Dict[str, int]:
        """Recover spent ammunition after a victorious combat using AHQ rolls."""
        recovered: Dict[str, int] = {}
        for ammo_type in ("arrows", "bolts"):
            spent = int(self.ammo_spent.get(ammo_type, 0))
            if spent <= 0:
                continue
            threshold = 10 if ammo_type == "arrows" else 7
            returned = 0
            for _ in range(spent):
                if random.randint(1, 12) >= threshold:
                    returned += 1
            if returned > 0:
                self.ammo[ammo_type] = int(self.ammo.get(ammo_type, 0)) + returned
                recovered[ammo_type] = returned
            self.ammo_spent[ammo_type] = 0
        return recovered

    def can_move_and_fire_ranged_weapon(self) -> bool:
        """Whether the equipped ranged weapon can be used after moving."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return False
        profile = self._get_item_profile(weapon)
        return bool(profile.get("move_and_fire", False))

    def get_ranged_min_strength(self) -> int:
        """Return any minimum Strength requirement for the equipped ranged weapon."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return 0
        profile = self._get_item_profile(weapon)
        return int(profile.get("min_strength", 0))

    def ranged_weapon_requires_reload(self) -> bool:
        """Whether the equipped ranged weapon needs reload turns."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return False
        profile = self._get_item_profile(weapon)
        return bool(profile.get("requires_reload", False))

    def is_ranged_weapon_loaded(self) -> bool:
        """Whether the equipped ranged weapon is currently loaded."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return False
        if not self.ranged_weapon_requires_reload():
            return True
        profile = self._get_item_profile(weapon)
        return bool(weapon.get("loaded", profile.get("starts_loaded", True)))

    def mark_ranged_weapon_fired(self):
        """Mark the equipped ranged weapon as fired."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return
        if self.ranged_weapon_requires_reload():
            weapon["loaded"] = False

    def reload_ranged_weapon(self) -> Optional[str]:
        """Reload the equipped ranged weapon if needed."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None or not self.ranged_weapon_requires_reload():
            return None
        if self.is_ranged_weapon_loaded():
            return None
        weapon["loaded"] = True
        return str(weapon.get("name", "Ranged weapon"))

    def get_ranged_critical(self) -> int:
        """Get critical threshold for the equipped ranged weapon."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return 12
        profile = self._get_item_profile(weapon)
        value = profile.get("critical", 12)
        if isinstance(value, str) and "-" in value:
            try:
                return int(value.split("-", 1)[0])
            except ValueError:
                return 12
        return int(value)

    def get_ranged_fumble(self) -> int:
        """Get fumble threshold for the equipped ranged weapon."""
        weapon = self.get_equipped_ranged_weapon()
        if weapon is None:
            return 1
        profile = self._get_item_profile(weapon)
        value = profile.get("fumble", 1)
        if isinstance(value, str) and "-" in value:
            try:
                return int(value.split("-", 1)[-1])
            except ValueError:
                return 1
        return int(value)
    
    def get_weapon_critical(self) -> int:
        """Get critical threshold for equipped weapon."""
        weapon = self.get_equipped_melee_weapon()
        if weapon is not None:
            profile = self._get_item_profile(weapon)
            if profile.get("critical") is not None:
                return int(profile["critical"])
            if profile.get("two_handed"):
                return 11
            return 12
        value = _DEFAULT_FISTS_PROFILE.get("critical")
        return int(value) if value is not None else 13
    
    def get_weapon_fumble(self) -> int:
        """Get fumble threshold for equipped weapon."""
        weapon = self.get_equipped_melee_weapon()
        if weapon is not None:
            profile = self._get_item_profile(weapon)
            if profile.get("fumble") is not None:
                return int(profile["fumble"])
            if profile.get("two_handed"):
                return 2
            return 1
        value = _DEFAULT_FISTS_PROFILE.get("fumble")
        return int(value) if value is not None else 0

    def get_equipped_armour(self) -> List[Dict[str, Any]]:
        """Return the currently equipped armour items."""
        return [
            item for item in self.equipment
            if item.get("equipped") and item.get("type") in {"armour", "armor", "helm"}
        ]

    def get_armour_value(self) -> int:
        """Return total armour value from equipped armour."""
        return sum(int(item.get("armour_value", 0)) for item in self.get_equipped_armour())

    def has_equipped_shield(self) -> bool:
        """Check whether the hero has an equipped shield."""
        return any(
            item.get("equipped") and item.get("type") == "shield"
            for item in self.equipment
        )

    def get_armour_skill_modifiers(self) -> Dict[str, int]:
        """Return combined armour modifiers from equipped gear."""
        modifiers = {"bs": 0, "toughness": 0, "speed": 0}
        for item in self.equipment:
            if not item.get("equipped"):
                continue
            item_type = item.get("type")
            if item_type not in {"armour", "armor", "shield", "helm"}:
                continue
            modifiers["bs"] += int(item.get("bs_modifier", 0))
            modifiers["toughness"] += int(item.get("armour_value", 0))
            modifiers["speed"] += int(item.get("speed_modifier", 0))
        return modifiers

    def _get_equipped_magic_bonus(self, field: str) -> int:
        """Return a total passive bonus from equipped non-armour items."""
        total = 0
        for item in self.equipment:
            if not item.get("equipped"):
                continue
            total += int(item.get(field, 0))
        return total

    def get_effective_toughness(self) -> int:
        """Get Toughness after armour and active effects."""
        toughness = self.toughness + self.get_armour_skill_modifiers()["toughness"] + self._get_equipped_magic_bonus("toughness_bonus")
        for effect in self.status_effects:
            toughness += int(effect.get("toughness_delta", 0))
        return max(1, toughness)

    def get_melee_reach(self) -> int:
        """Get melee reach of the equipped weapon."""
        weapon = self.get_equipped_melee_weapon()
        if weapon is None:
            return 1
        return 1

    def has_long_reach_weapon(self) -> bool:
        """Whether the equipped melee weapon allows diagonal attacks."""
        weapon = self.get_equipped_melee_weapon()
        if weapon is None:
            return False
        profile = self._get_item_profile(weapon)
        if profile.get("long_reach") is not None:
            return bool(profile.get("long_reach"))
        return str(profile.get("name", "")).lower() in {"spear", "halberd", "double-handed sword", "double handed sword"}
    
    def is_wizard(self) -> bool:
        """Check if hero is a wizard."""
        return self.class_type == "Wizard"

    def is_true_hero(self) -> bool:
        """Whether this character is one of the core heroes rather than a henchman."""
        return not self.is_henchman
    
    def can_wear_armour(self) -> bool:
        """Wizards cannot wear armour."""
        return not self.is_wizard()

    def can_cast_spells(self) -> bool:
        """Whether the hero can currently draw on magic."""
        if not self.is_wizard():
            return False
        for item in self.equipment:
            if not item.get("equipped"):
                continue
            item_type = item.get("type")
            if item_type in {"armour", "armor", "shield", "helm", "ranged_weapon"}:
                return False
            if item_type == "weapon":
                item_name = str(item.get("name", "")).lower()
                if "dagger" not in item_name and "rune sword" not in item_name and not item.get("wizard_usable", False):
                    return False
        return True

    def knows_spell(self, spell_name: str) -> bool:
        """Whether the hero knows the named spell."""
        target = normalize_spell_name(spell_name)
        return any(normalize_spell_name(current) == target for current in self.known_spells)

    def get_spell_component_count(self, spell_name: str) -> int:
        """Return how many uses worth of components the hero has for a spell."""
        target = normalize_spell_name(spell_name)
        for current, count in self.spell_components.items():
            if normalize_spell_name(current) == target:
                return int(count)
        return 0

    def has_spell_components(self, spell_name: str, count: int = 1) -> bool:
        """Whether the hero has at least `count` components for the spell."""
        return self.get_spell_component_count(spell_name) >= count

    def spend_spell_components(self, spell_name: str, count: int = 1) -> bool:
        """Spend a spell's components if available."""
        target = normalize_spell_name(spell_name)
        for current in list(self.spell_components.keys()):
            if normalize_spell_name(current) != target:
                continue
            if int(self.spell_components[current]) < count:
                return False
            self.spell_components[current] = int(self.spell_components[current]) - count
            if self.spell_components[current] <= 0:
                del self.spell_components[current]
            return True
        return False
    
    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to hero. Returns True if hero is KO'd or killed.
        """
        remaining_wounds = self.current_wounds - damage
        self.current_wounds = max(0, remaining_wounds)
        if self.is_henchman and remaining_wounds <= 0:
            self.is_dead = True
            self.is_ko = True
            return True
        if remaining_wounds <= 0:
            self.is_ko = True
            if remaining_wounds < 0:
                self.is_dead = True
                return True
            return True
        return False

    def start_turn_snapshot(self):
        """Record the start-of-turn wound state for Fate handling."""
        self.turn_wounds_snapshot = int(self.current_wounds)
        self.damage_taken_this_turn = 0
        pending = self.pending_fate_decision
        if isinstance(pending, dict) and pending.get("type") == "damage":
            self.pending_fate_decision = None

    def record_turn_damage(self, damage: int):
        """Track damage suffered in the current turn."""
        self.damage_taken_this_turn = int(self.damage_taken_this_turn) + int(max(0, damage))
    
    def spend_fate(self) -> bool:
        """Spend a Fate Point against the currently pending event."""
        if not self._spend_fate_point():
            return False
        pending = dict(self.pending_fate_decision or {})
        if str(pending.get("type", "damage")) == "damage":
            self.current_wounds = max(1, int(self.turn_wounds_snapshot))
        else:
            self.current_wounds = max(1, self.current_wounds)
        self.is_ko = False
        self.is_dead = False
        self.pending_fate_decision = None
        self.damage_taken_this_turn = 0
        return True

    def get_stored_fate_points(self) -> int:
        """Return non-regenerating Fate Points stored in carried Dawnstones."""
        total = 0
        for item in self.equipment:
            if str(item.get("name", "")).strip().lower() != "dawnstone":
                continue
            total += int(item.get("fate_points", 0))
        return max(0, total)

    def has_fate_available(self) -> bool:
        """Whether the hero can spend either normal Fate or Dawnstone Fate."""
        return self.current_fate > 0 or self.get_stored_fate_points() > 0

    def _spend_fate_point(self) -> bool:
        """Spend normal Fate first, then non-regenerating Dawnstone Fate."""
        if self.current_fate > 0:
            self.current_fate -= 1
            return True
        for item in self.equipment:
            if str(item.get("name", "")).strip().lower() != "dawnstone":
                continue
            stored = int(item.get("fate_points", 0))
            if stored <= 0:
                continue
            item["fate_points"] = stored - 1
            return True
        return False

    def queue_fate_decision(self, damage: int, source: Optional[str] = None):
        """Record a pending choice to spend Fate against turn damage."""
        self.pending_fate_decision = {
            "type": "damage",
            "damage": int(max(0, damage)),
            "source": source or "attack",
        }

    def queue_failed_roll_fate_decision(self, source: str, **context: Any):
        """Record a pending choice to convert a failed roll into a success."""
        self.pending_fate_decision = {
            "type": "failed_roll",
            "source": source,
            **context,
        }

    def has_pending_fate_decision(self) -> bool:
        """Whether the hero is awaiting a Fate decision."""
        return isinstance(self.pending_fate_decision, dict)
    
    def heal(self, amount: int):
        """Heal wounds up to max."""
        self.current_wounds = min(self.max_wounds, self.current_wounds + amount)

    def restore_to_full(self):
        """Restore the hero to full fighting strength."""
        self.current_wounds = self.max_wounds
        self.is_ko = False
        self.is_dead = False
        self.death_turn = None

    def get_status_effect(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a named status effect, if present."""
        for effect in self.status_effects:
            if effect.get("name") == name:
                return effect
        return None

    def has_status_effect(self, name: str) -> bool:
        """Check whether a named status effect is active."""
        return self.get_status_effect(name) is not None

    def add_status_effect(self, name: str, **data: Any):
        """Add or replace a named status effect."""
        effect = {"name": name, **data}
        existing = self.get_status_effect(name)
        if existing is not None:
            existing.clear()
            existing.update(effect)
            return
        self.status_effects.append(effect)

    def remove_status_effect(self, name: str):
        """Remove a named status effect if present."""
        self.status_effects = [effect for effect in self.status_effects if effect.get("name") != name]

    def clear_status_effects(self, scope: Optional[str] = None):
        """Clear all status effects, or only those in a scope."""
        if scope is None:
            self.status_effects = []
            return
        self.status_effects = [
            effect for effect in self.status_effects
            if effect.get("scope") != scope
        ]

    def tick_status_effects(self) -> List[str]:
        """Advance temporary effect timers and return expired effect names."""
        expired: List[str] = []
        remaining_effects: List[Dict[str, Any]] = []
        for effect in self.status_effects:
            turns = effect.get("turns")
            if turns is None:
                remaining_effects.append(effect)
                continue

            effect["turns"] = turns - 1
            if effect["turns"] <= 0:
                expired.append(str(effect.get("name", "effect")))
            else:
                remaining_effects.append(effect)

        self.status_effects = remaining_effects
        return expired

    def get_effective_ws(self) -> int:
        """Get Weapon Skill after active effects."""
        ws = self.ws + self._get_equipped_magic_bonus("ws_bonus")
        for effect in self.status_effects:
            ws += int(effect.get("ws_delta", 0))
            divisor = effect.get("ws_divisor")
            if divisor:
                ws = max(1, ws // int(divisor))
        return max(1, ws)

    def get_effective_bs(self) -> int:
        """Get Ballistic Skill after active effects."""
        bs = self.bs + self.get_armour_skill_modifiers()["bs"] + self._get_equipped_magic_bonus("bs_bonus")
        for effect in self.status_effects:
            bs += int(effect.get("bs_delta", 0))
            divisor = effect.get("bs_divisor")
            if divisor:
                bs = max(1, bs // int(divisor))
        return max(1, bs)

    def get_effective_strength(self) -> int:
        """Get Strength after active effects."""
        strength = self.strength + self._get_equipped_magic_bonus("strength_bonus")
        for effect in self.status_effects:
            strength += int(effect.get("strength_delta", 0))
        return max(1, strength)

    def get_effective_speed(self, phase: str = "exploration") -> int:
        """Get Speed after active effects."""
        speed = self.speed + self.get_armour_skill_modifiers()["speed"] + self._get_equipped_magic_bonus("speed_bonus")
        for effect in self.status_effects:
            speed += int(effect.get("speed_delta", 0))
            divisor = effect.get("speed_divisor_round_up")
            if divisor:
                div = int(divisor)
                speed = max(1, (speed + div - 1) // div)
            if phase == "combat" and effect.get("combat_speed_multiplier"):
                speed *= int(effect["combat_speed_multiplier"])
        return max(1, speed)

    def get_movement_allowance(self, phase: str = "exploration") -> int:
        """Get current movement allowance for the given phase."""
        if any(effect.get("cannot_move") for effect in self.status_effects):
            return 0

        if phase == "combat":
            allowance = self.get_effective_speed("combat")
            for effect in self.status_effects:
                cap = effect.get("combat_move_cap")
                if cap is not None:
                    allowance = min(allowance, int(cap))
                divisor = effect.get("combat_move_divisor")
                if divisor:
                    allowance = max(1, allowance // int(divisor))
            return max(0, allowance)

        allowance = self.get_effective_speed("exploration")
        for effect in self.status_effects:
            cap = effect.get("exploration_move_cap")
            if cap is not None:
                allowance = min(allowance, int(cap))
        return max(0, allowance)

    def get_bonus_melee_damage_dice(self) -> int:
        """Get any temporary bonus melee damage dice from effects."""
        return sum(int(effect.get("bonus_melee_damage_dice", 0)) for effect in self.status_effects)

    def has_usable_healing_potion(self) -> bool:
        """Whether the hero has a healing potion item available."""
        return any(
            item.get("type") == "potion" and item.get("potion_effect") == "healing"
            for item in self.equipment
        )

    def consume_healing_potion(self) -> bool:
        """Consume one healing potion if present."""
        for index, item in enumerate(self.equipment):
            if item.get("type") == "potion" and item.get("potion_effect") == "healing":
                del self.equipment[index]
                return True
        return False

    def add_inventory_item(self, item_key: str, count: int = 1):
        """Add a stackable between-expedition inventory item."""
        self.inventory[item_key] = int(self.inventory.get(item_key, 0)) + int(count)

    def remove_inventory_item(self, item_key: str, count: int = 1) -> bool:
        """Remove a stackable between-expedition inventory item if available."""
        current = int(self.inventory.get(item_key, 0))
        if current < count:
            return False
        remaining = current - int(count)
        if remaining > 0:
            self.inventory[item_key] = remaining
        else:
            self.inventory.pop(item_key, None)
        return True

    def get_inventory_count(self, item_key: str) -> int:
        """Return the count for a stackable between-expedition item."""
        return int(self.inventory.get(item_key, 0))

    def add_ammo(self, ammo_type: str, count: int):
        """Add purchased ammunition for future ammo tracking."""
        self.ammo[ammo_type] = int(self.ammo.get(ammo_type, 0)) + int(count)

    def get_ammo_count(self, ammo_type: str) -> int:
        """Return stored ammunition for the hero."""
        return int(self.ammo.get(ammo_type, 0))

    def get_total_carried_weapons(self) -> int:
        """Return the total carried melee and ranged weapons."""
        return sum(1 for item in self.equipment if item.get("type") in {"weapon", "ranged_weapon"})

    def can_carry_equipment_item(self, item: Dict[str, Any]) -> tuple[bool, str]:
        """Check whether the hero can legally carry a newly bought equipment item."""
        item_type = str(item.get("type", "")).lower()
        item_name = str(item.get("name", "item"))
        if self.has_status_effect("lost_hand") and item_type in {"ranged_weapon", "shield"}:
            return False, f"{self.name} cannot carry {item_name} after losing a hand."
        if self.has_status_effect("lost_hand") and item.get("two_handed"):
            return False, f"{self.name} cannot carry {item_name} after losing a hand."
        if self.has_status_effect("lost_leg") and (item_type == "shield" or item.get("two_handed")):
            return False, f"{self.name} cannot effectively use {item_name} after losing a leg."
        if item_type in {"weapon", "ranged_weapon"} and self.get_total_carried_weapons() >= 3:
            return False, f"{self.name} cannot carry more than three weapons."
        if item_type in {"armour", "armor"} and any(existing.get("type") in {"armour", "armor"} for existing in self.equipment):
            return False, f"{self.name} cannot carry another suit of armour."
        if item_type == "shield" and any(existing.get("type") == "shield" for existing in self.equipment):
            return False, f"{self.name} cannot carry another shield."
        if item_type == "helm" and any(existing.get("type") == "helm" for existing in self.equipment):
            return False, f"{self.name} cannot carry another helm."
        if item_type == "ring" and any(existing.get("type") == "ring" for existing in self.equipment):
            return False, f"{self.name} cannot carry another ring."
        if item_type == "amulet" and any(existing.get("type") == "amulet" for existing in self.equipment):
            return False, f"{self.name} cannot carry another amulet."
        return True, f"{self.name} can carry {item_name}."

    def can_carry_supply_item(self, item_key: str) -> tuple[bool, str]:
        """Check whether the hero can legally carry another expedition supply item."""
        current = self.get_inventory_count(item_key)
        if item_key in _ONE_PER_HERO_SUPPLIES and current > 0:
            return False, f"{self.name} is already carrying {item_key.replace('_', ' ')}."
        if item_key not in _ONE_PER_HERO_SUPPLIES and item_key not in _STACKABLE_SUPPLIES and current > 0:
            return False, f"{self.name} is already carrying {item_key.replace('_', ' ')}."
        return True, ""

    def can_carry_gold(self, amount: int, extra_carriers: int = 0) -> tuple[bool, int]:
        """Check whether the hero can carry the specified extra gold."""
        capacity = (250 * max(0, 1 + int(extra_carriers))) - int(self.gold)
        return capacity >= amount, max(0, capacity)

    def can_equip_item(self, item: Dict[str, Any]) -> tuple[bool, str]:
        """Check whether an item can be equipped without violating simple slot rules."""
        item_type = str(item.get("type", "")).lower()
        item_name = str(item.get("name", "item"))
        profile = self._get_item_profile(item)
        min_strength = int(profile.get("min_strength", 0))
        if self.has_status_effect("lost_hand") and (item_type == "shield" or item_type == "ranged_weapon" or item.get("two_handed")):
            return False, f"{self.name} cannot equip {item_name} after losing a hand."
        if self.has_status_effect("lost_leg") and (item_type == "shield" or item.get("two_handed")):
            return False, f"{self.name} cannot equip {item_name} after losing a leg."
        if item_type in {"weapon", "ranged_weapon"} and min_strength > 0 and self.get_effective_strength() < min_strength:
            return False, f"{self.name} needs Strength {min_strength} to equip {item_name}."
        if item_type in {"armour", "armor"}:
            if not self.can_wear_armour():
                return False, f"{self.name} cannot wear {item_name}."
            for existing in self.equipment:
                if existing is item:
                    continue
                if existing.get("equipped") and str(existing.get("type", "")).lower() in {"armour", "armor"}:
                    existing_name = str(existing.get("name", "other armour"))
                    return False, f"{self.name} is already wearing {existing_name}."
        if item_type == "shield":
            if not self.can_wear_armour():
                return False, f"{self.name} cannot use {item_name}."
            for existing in self.equipment:
                if existing is item:
                    continue
                if existing.get("equipped") and str(existing.get("type", "")).lower() == "shield":
                    existing_name = str(existing.get("name", "other shield"))
                    return False, f"{self.name} is already using {existing_name}."
        if item_type == "helm":
            for existing in self.equipment:
                if existing is item:
                    continue
                if existing.get("equipped") and str(existing.get("type", "")).lower() == "helm":
                    existing_name = str(existing.get("name", "other helm"))
                    return False, f"{self.name} is already wearing {existing_name}."
        if item_type == "weapon":
            for existing in self.equipment:
                if existing is item:
                    continue
                if existing.get("equipped") and str(existing.get("type", "")).lower() == "weapon":
                    existing["equipped"] = False
        if item_type == "ranged_weapon":
            for existing in self.equipment:
                if existing is item:
                    continue
                if existing.get("equipped") and str(existing.get("type", "")).lower() == "ranged_weapon":
                    existing["equipped"] = False
        return True, ""

    def is_under_gm_control(self) -> bool:
        """Whether the hero is currently not under player control."""
        return self.has_status_effect("madness") and not self.has_status_effect("madness_restrained")

    def is_restrained_by_mindstealer(self) -> bool:
        """Whether the hero is currently pinned to stop a Mindstealer frenzy."""
        return self.has_status_effect("madness_restrained")

    def has_pending_healing_potion(self) -> bool:
        """Whether a healing potion will restore the hero at the start of the next turn."""
        return self.has_status_effect("healing_potion_pending")

    def queue_healing_potion_recovery(self, source: str = "Healing Potion"):
        """Apply the delayed AHQ healing-potion recovery timing."""
        self.add_status_effect(
            "healing_potion_pending",
            turns=1,
            scope="turn",
            source=source,
            cannot_move=True,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert hero to dictionary for saving."""
        return {
            "id": self.id,
            "name": self.name,
            "race": self.race,
            "class_type": self.class_type,
            "ws": self.ws,
            "bs": self.bs,
            "strength": self.strength,
            "toughness": self.toughness,
            "speed": self.speed,
            "bravery": self.bravery,
            "intelligence": self.intelligence,
            "max_wounds": self.max_wounds,
            "current_wounds": self.current_wounds,
            "max_fate": self.max_fate,
            "current_fate": self.current_fate,
            "gold": self.gold,
            "experience": self.experience,
            "total_pv": self.total_pv,
            "equipment": self.equipment,
            "inventory": self.inventory,
            "ammo": self.ammo,
            "ammo_spent": self.ammo_spent,
            "expeditions_completed": self.expeditions_completed,
            "is_henchman": self.is_henchman,
            "henchman_type": self.henchman_type,
            "employer_id": self.employer_id,
            "upkeep_cost": self.upkeep_cost,
            "hire_cost": self.hire_cost,
            "attracted_henchman": self.attracted_henchman,
            "paid_spells_learned": self.paid_spells_learned,
            "is_dead": self.is_dead,
            "is_ko": self.is_ko,
            "trap_disarm_bonus": self.trap_disarm_bonus,
            "ko_turns": self.ko_turns,
            "temp_fate_bonus": self.temp_fate_bonus,
            "free_spell_cast": self.free_spell_cast,
            "status_effects": self.status_effects,
            "known_spells": self.known_spells,
            "spell_components": self.spell_components,
            "death_turn": self.death_turn,
            "pending_fate_decision": self.pending_fate_decision,
            "turn_wounds_snapshot": self.turn_wounds_snapshot,
            "damage_taken_this_turn": self.damage_taken_this_turn,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hero":
        """Create hero from dictionary."""
        hero = cls(
            name=data["name"],
            race=data["race"],
            class_type=data["class_type"],
            ws=data["ws"],
            bs=data["bs"],
            strength=data["strength"],
            toughness=data["toughness"],
            speed=data["speed"],
            bravery=data["bravery"],
            intelligence=data["intelligence"],
            wounds=data["max_wounds"],
            fate=data["max_fate"],
            gold=data.get("gold", 0),
            equipment=data.get("equipment", []),
            id=data.get("id"),
            known_spells=data.get("known_spells"),
            spell_components=data.get("spell_components"),
            inventory=data.get("inventory"),
            ammo=data.get("ammo"),
            expeditions_completed=data.get("expeditions_completed", 0),
            is_henchman=data.get("is_henchman", False),
            henchman_type=data.get("henchman_type"),
            employer_id=data.get("employer_id"),
            upkeep_cost=data.get("upkeep_cost", 0),
            hire_cost=data.get("hire_cost", 0),
            attracted_henchman=data.get("attracted_henchman", False),
            paid_spells_learned=data.get("paid_spells_learned", 0),
        )
        hero.current_wounds = data.get("current_wounds", hero.max_wounds)
        hero.current_fate = data.get("current_fate", hero.max_fate)
        hero.experience = data.get("experience", 0)
        hero.total_pv = data.get("total_pv", 0)
        hero.is_dead = data.get("is_dead", False)
        hero.is_ko = data.get("is_ko", False)
        hero.trap_disarm_bonus = data.get("trap_disarm_bonus", 0)
        hero.ko_turns = data.get("ko_turns", 0)
        hero.temp_fate_bonus = data.get("temp_fate_bonus", 0)
        hero.free_spell_cast = data.get("free_spell_cast", 0)
        hero.ammo_spent = dict(data.get("ammo_spent", {"arrows": 0, "bolts": 0}))
        hero.status_effects = list(data.get("status_effects", []))
        hero.death_turn = data.get("death_turn")
        pending_fate = data.get("pending_fate_decision")
        hero.pending_fate_decision = dict(pending_fate) if isinstance(pending_fate, dict) else None
        hero.turn_wounds_snapshot = int(data.get("turn_wounds_snapshot", hero.current_wounds))
        hero.damage_taken_this_turn = int(data.get("damage_taken_this_turn", 0))
        return hero
    
    def __repr__(self):
        return f"Hero({self.name}, {self.race} {self.class_type}, W:{self.current_wounds}/{self.max_wounds}, F:{self.current_fate})"


class HeroManager:
    """Manages the roster of heroes."""
    
    HEROES_FILE = Path(__file__).parent / "data" / "heroes.json"
    
    def __init__(self):
        self.heroes: Dict[str, Hero] = {}
        self._load_heroes()
    
    def _load_heroes(self):
        """Load heroes from JSON file."""
        if self.HEROES_FILE.exists():
            with open(self.HEROES_FILE, "r") as f:
                data = json.load(f)
                for hero_data in data.get("heroes", []):
                    hero = Hero.from_dict(hero_data)
                    self.heroes[hero.id] = hero
    
    def save_heroes(self):
        """Save heroes to JSON file."""
        data = {
            "heroes": [hero.to_dict() for hero in self.heroes.values() if not hero.is_dead]
        }
        self.HEROES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.HEROES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def create_hero(
        self,
        name: str,
        race: str,
        class_type: str,
        stats: Dict[str, int],
        gold: int,
        equipment: List[Dict]
    ) -> Hero:
        """Create a new hero and add to roster."""
        hero = Hero(
            name=name,
            race=race,
            class_type=class_type,
            ws=stats["WS"],
            bs=stats["BS"],
            strength=stats["S"],
            toughness=stats["T"],
            speed=stats["Sp"],
            bravery=stats["Br"],
            intelligence=stats["Int"],
            wounds=stats["W"],
            fate=stats["Fate"],
            gold=gold,
            equipment=equipment
        )
        self.heroes[hero.id] = hero
        self.save_heroes()
        return hero
    
    def get_all_heroes(self) -> List[Hero]:
        """Get all living heroes."""
        return [h for h in self.heroes.values() if not h.is_dead]
    
    def get_hero(self, hero_id: str) -> Optional[Hero]:
        """Get hero by ID."""
        return self.heroes.get(hero_id)
    
    def delete_hero(self, hero_id: str):
        """Delete a hero from the roster."""
        if hero_id in self.heroes:
            del self.heroes[hero_id]
            self.save_heroes()
    
    def update_hero(self, hero: Hero):
        """Update a hero in the roster."""
        self.heroes[hero.id] = hero
        self.save_heroes()


# Dice rolling functions for hero creation
def roll_d(sides: int) -> int:
    """Roll a die with given sides."""
    return random.randint(1, sides)


def roll_hero_race() -> str:
    """Roll for hero race."""
    roll = roll_d(12)
    if roll <= 6:
        return "Human"
    elif roll <= 9:
        return "Dwarf"
    else:
        return "Elf"


def create_henchman(henchman_type: str, employer_id: Optional[str] = None, attracted: bool = False, name: Optional[str] = None) -> Hero:
    """Create a rules-shaped henchman using final effective AHQ stats."""
    kind = str(henchman_type).strip().lower().replace("-", "_").replace(" ", "_")
    if kind == "man_at_arms":
        return Hero(
            name=name or "Man-at-Arms",
            race="Human",
            class_type="Warrior",
            ws=7,
            bs=6,
            strength=6,
            toughness=8,
            speed=8,
            bravery=7,
            intelligence=5,
            wounds=2,
            fate=0,
            gold=0,
            equipment=[
                {"name": "Sword", "key": "sword", "type": "weapon", "equipped": True},
                {"name": "Leather Armour", "key": "leather_armour", "type": "armour", "equipped": True, "armour_value": 1, "bs_modifier": -1, "speed_modifier": -1},
                {"name": "Shield", "key": "shield", "type": "shield", "equipped": True, "armour_value": 1, "bs_modifier": -1, "speed_modifier": 0},
            ],
            is_henchman=True,
            henchman_type="man_at_arms",
            employer_id=employer_id,
            upkeep_cost=35,
            hire_cost=0 if attracted else 50,
            attracted_henchman=attracted,
        )
    if kind in {"sergeant", "rogue"}:
        return Hero(
            name=name or ("Rogue" if kind == "rogue" else "Sergeant"),
            race="Human",
            class_type="Warrior",
            ws=8,
            bs=7,
            strength=6,
            toughness=10,
            speed=8,
            bravery=8,
            intelligence=6,
            wounds=2,
            fate=0,
            gold=0,
            equipment=[
                {"name": "Sword", "key": "sword", "type": "weapon", "equipped": True},
                {"name": "Chain Armour", "key": "chain_armour", "type": "armour", "equipped": True, "armour_value": 2, "bs_modifier": -1, "speed_modifier": -2},
                {"name": "Shield", "key": "shield", "type": "shield", "equipped": True, "armour_value": 1, "bs_modifier": -1, "speed_modifier": 0},
            ],
            is_henchman=True,
            henchman_type="rogue" if kind == "rogue" else "sergeant",
            employer_id=employer_id,
            upkeep_cost=75 if kind != "rogue" else 75,
            hire_cost=100 if kind != "rogue" else 0,
            attracted_henchman=attracted,
        )
    raise ValueError(f"Unknown henchman type: {henchman_type}")


def roll_hero_stats(race: str) -> Dict[str, int]:
    """Roll stats for a hero based on race."""
    if race == "Human":
        return {
            "WS": roll_d(6) + 4,
            "BS": roll_d(4) + 3,
            "S": roll_d(4) + 4,
            "T": roll_d(4) + 4,
            "Sp": roll_d(6) + 4,
            "Br": roll_d(8) + 3,
            "Int": roll_d(8) + 3,
            "W": roll_d(4) + 1,
            "Fate": 2
        }
    elif race == "Dwarf":
        return {
            "WS": roll_d(6) + 5,
            "BS": roll_d(4) + 3,
            "S": roll_d(4) + 4,
            "T": roll_d(4) + 4,
            "Sp": roll_d(6) + 3,
            "Br": roll_d(8) + 3,
            "Int": roll_d(8) + 3,
            "W": roll_d(4) + 1,
            "Fate": 2
        }
    else:  # Elf
        return {
            "WS": roll_d(6) + 4,
            "BS": roll_d(4) + 5,
            "S": roll_d(4) + 3,
            "T": roll_d(4) + 2,
            "Sp": roll_d(6) + 5,
            "Br": roll_d(8) + 3,
            "Int": roll_d(8) + 3,
            "W": roll_d(4) + 1,
            "Fate": 2
        }


def roll_starting_gold() -> int:
    """Roll starting gold."""
    return (roll_d(4) + 4) * 10

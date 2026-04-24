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
        
        # State
        self.is_dead = False
        self.is_ko = False
        self.trap_disarm_bonus = 0
        self.ko_turns = 0
        self.temp_fate_bonus = 0
        self.free_spell_cast = 0
        self.status_effects: List[Dict[str, Any]] = []
        self.death_turn: Optional[int] = None
        
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
        self.current_wounds -= damage
        if self.current_wounds <= 0:
            self.is_ko = True
            if self.current_fate <= 0:
                self.is_dead = True
                return True
        return False
    
    def spend_fate(self) -> bool:
        """Spend a fate point to negate damage. Returns True if spent."""
        if self.current_fate > 0:
            self.current_fate -= 1
            self.current_wounds = 1  # Keep at 1 wound
            self.is_ko = False
            return True
        return False
    
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

    def is_under_gm_control(self) -> bool:
        """Whether the hero is currently not under player control."""
        return self.has_status_effect("madness")
    
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
        hero.status_effects = list(data.get("status_effects", []))
        hero.death_turn = data.get("death_turn")
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

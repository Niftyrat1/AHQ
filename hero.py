"""
Hero data model and creation for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import Optional, List, Dict, Any


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
        id: Optional[str] = None
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
        self.equipment = equipment or [{"name": "Dagger", "type": "weapon", "equipped": True}]
        
        # State
        self.is_dead = False
        self.is_ko = False
        self.trap_disarm_bonus = 0
        
        # Position in dungeon (set when placed)
        self.x = 0
        self.y = 0
        self.is_selected = False
    
    def get_damage_dice(self) -> int:
        """Get number of damage dice for equipped weapon."""
        for item in self.equipment:
            if item.get("equipped") and item.get("type") == "weapon":
                return item.get("damage_dice", 1)
        return 1  # Default fist damage
    
    def get_weapon_critical(self) -> int:
        """Get critical threshold for equipped weapon."""
        for item in self.equipment:
            if item.get("equipped") and item.get("type") == "weapon":
                if item.get("two_handed"):
                    return 11
                return 12
        return 12
    
    def get_weapon_fumble(self) -> int:
        """Get fumble threshold for equipped weapon."""
        for item in self.equipment:
            if item.get("equipped") and item.get("type") == "weapon":
                if item.get("two_handed"):
                    return 2
                return 1
        return 1
    
    def is_wizard(self) -> bool:
        """Check if hero is a wizard."""
        return self.class_type == "Wizard"
    
    def can_wear_armour(self) -> bool:
        """Wizards cannot wear armour."""
        return not self.is_wizard()
    
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
            id=data.get("id")
        )
        hero.current_wounds = data.get("current_wounds", hero.max_wounds)
        hero.current_fate = data.get("current_fate", hero.max_fate)
        hero.experience = data.get("experience", 0)
        hero.total_pv = data.get("total_pv", 0)
        hero.is_dead = data.get("is_dead", False)
        hero.is_ko = data.get("is_ko", False)
        hero.trap_disarm_bonus = data.get("trap_disarm_bonus", 0)
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

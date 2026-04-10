"""
Monster data model for Advanced HeroQuest.
"""

import json
import random
from pathlib import Path
from typing import Dict, Any, Optional


class Monster:
    """Represents a monster in the dungeon."""
    
    def __init__(
        self,
        monster_id: str,
        name: str,
        ws: int,
        bs: int,
        strength: int,
        toughness: int,
        speed: int,
        bravery: int,
        intelligence: int,
        wounds: int,
        pv: int,
        weapons: list,
        ranged: Optional[Dict] = None,
        is_sentry: bool = False,
        is_character: bool = False
    ):
        self.id = monster_id
        self.instance_id = f"{monster_id}_{random.randint(10000, 99999)}"
        self.name = name
        
        # Characteristics
        self.ws = ws
        self.bs = bs
        self.strength = strength
        self.toughness = toughness
        self.speed = speed
        self.bravery = bravery
        self.intelligence = intelligence
        self.max_wounds = wounds
        self.current_wounds = wounds
        
        # Rewards
        self.pv = pv  # Proven Value (XP awarded when killed)
        
        # Combat
        self.weapons = weapons
        self.ranged = ranged
        
        # Flags
        self.is_sentry = is_sentry
        self.is_character = is_character
        
        # Position in dungeon
        self.x = 0
        self.y = 0
        
        # State
        self.is_dead = False
    
    def get_damage_dice(self) -> int:
        """Get number of damage dice."""
        if self.weapons:
            return self.weapons[0].get("damage_dice", 1)
        return 1
    
    def get_critical_threshold(self) -> int:
        """Get critical hit threshold."""
        if self.weapons:
            return self.weapons[0].get("critical", 12)
        return 12
    
    def get_fumble_threshold(self) -> int:
        """Get fumble threshold."""
        if self.weapons:
            return self.weapons[0].get("fumble", 1)
        return 1
    
    def has_ranged(self) -> bool:
        """Check if monster has ranged attack."""
        return self.ranged is not None
    
    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to monster.
        Returns True if monster died.
        """
        self.current_wounds -= damage
        if self.current_wounds <= 0:
            self.is_dead = True
            return True
        return False
    
    @classmethod
    def from_template(cls, monster_id: str, templates: Dict) -> "Monster":
        """Create a monster instance from template data."""
        data = templates.get(monster_id, {})
        return cls(
            monster_id=monster_id,
            name=data.get("name", "Unknown"),
            ws=data.get("WS", 3),
            bs=data.get("BS", 3),
            strength=data.get("S", 3),
            toughness=data.get("T", 3),
            speed=data.get("Sp", 4),
            bravery=data.get("Br", 5),
            intelligence=data.get("Int", 3),
            wounds=data.get("W", 1),
            pv=data.get("PV", 1),
            weapons=data.get("weapons", []),
            ranged=data.get("ranged"),
            is_sentry=data.get("is_sentry", False),
            is_character=data.get("is_character", False)
        )
    
    def __repr__(self):
        return f"Monster({self.name}, W:{self.current_wounds}/{self.max_wounds})"


class MonsterLibrary:
    """Loads and manages monster templates."""
    
    MONSTERS_FILE = Path(__file__).parent / "data" / "monsters.json"
    
    def __init__(self):
        self.templates: Dict[str, Dict] = {}
        self._load_monsters()
    
    def _load_monsters(self):
        """Load monster templates from JSON."""
        if self.MONSTERS_FILE.exists():
            with open(self.MONSTERS_FILE, "r") as f:
                self.templates = json.load(f)
    
    def create_monster(self, monster_id: str) -> Optional[Monster]:
        """Create a monster instance from template."""
        if monster_id in self.templates:
            return Monster.from_template(monster_id, self.templates)
        return None
    
    def get_random_monster(self, min_pv: int = 1, max_pv: int = 10) -> Optional[Monster]:
        """Get a random monster within PV range."""
        valid = [
            mid for mid, data in self.templates.items()
            if min_pv <= data.get("PV", 1) <= max_pv and not data.get("is_character", False)
        ]
        if valid:
            return self.create_monster(random.choice(valid))
        return None
    
    def get_all_ids(self) -> list:
        """Get all monster IDs."""
        return list(self.templates.keys())


# Predefined encounter tables for Phase 1
LAIR_ENCOUNTER_TABLE = {
    1: ["skaven_warrior", "skaven_warrior", "skaven_warrior"],
    2: ["skaven_warrior", "skaven_warrior", "skaven_champion"],
    3: ["skaven_warrior", "skaven_warrior", "skaven_warrior", "skaven_warrior"],
    4: ["skaven_warrior", "skaven_warrior", "giant_rat", "giant_rat"],
    5: ["skaven_champion", "skaven_warrior", "skaven_warrior"],
    6: ["rat_ogre", "skaven_warrior"],
    7: ["skaven_warrior", "skaven_warrior", "skaven_warrior", "skaven_warrior", "skaven_warrior"],
    8: ["skaven_champion", "skaven_champion"],
    9: ["skaven_warlord", "skaven_warrior", "skaven_warrior"],
    10: ["skaven_warrior", "skaven_warrior", "skaven_warrior", "giant_rat", "giant_rat", "giant_rat"],
    11: ["clan_eshin_assassin", "skaven_warrior", "skaven_warrior"],
    12: ["rat_ogre", "rat_ogre", "skaven_warrior"],
}

QUEST_ROOM_ENCOUNTER_TABLE = {
    1: ["skaven_warlord", "skaven_champion", "skaven_warrior", "skaven_warrior"],
    2: ["clan_pestilens_plague_monk", "skaven_warrior", "skaven_warrior", "skaven_warrior"],
    3: ["clan_skyre_warpweaver", "skaven_warrior", "skaven_warrior", "skaven_warrior"],
    4: ["skaven_warlord", "skaven_champion", "skaven_champion", "skaven_warrior"],
    5: ["clan_eshin_assassin", "clan_eshin_assassin", "skaven_warrior"],
    6: ["rat_ogre", "rat_ogre", "rat_ogre", "skaven_champion"],
    7: ["skaven_warlord", "skaven_warlord", "skaven_champion", "skaven_champion"],
    8: ["clan_pestilens_plague_monk", "clan_skyre_warpweaver", "skaven_champion", "skaven_warrior"],
    9: ["skaven_warlord", "clan_eshin_assassin", "skaven_champion", "skaven_warrior", "skaven_warrior"],
    10: ["rat_ogre", "rat_ogre", "rat_ogre", "skaven_warlord"],
    11: ["clan_pestilens_plague_monk", "clan_pestilens_plague_monk", "skaven_champion", "skaven_warrior", "skaven_warrior"],
    12: ["skaven_warlord", "skaven_warlord", "clan_skyre_warpweaver", "skaven_champion", "skaven_champion"],
}


def roll_lair_encounter() -> list:
    """Roll for a lair encounter. Returns list of monster IDs."""
    roll = random.randint(1, 12)
    return LAIR_ENCOUNTER_TABLE.get(roll, ["skaven_warrior"])


def roll_quest_room_encounter() -> list:
    """Roll for a quest room encounter. Returns list of monster IDs."""
    roll = random.randint(1, 12)
    return QUEST_ROOM_ENCOUNTER_TABLE.get(roll, ["skaven_warrior", "skaven_warrior"])

"""Central spell definitions and helpers for the AHQ magic system."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


DEFAULT_BRIGHT_SPELLS = [
    "Dragon Armour",
    "Open Window",
    "Flames of Death",
    "Flames of the Phoenix",
]


SPELL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "dragon armour": {
        "name": "Dragon Armour",
        "components": ["Red Dragon Dust"],
        "target_mode": "model",
        "adjacent_only": True,
    },
    "open window": {
        "name": "Open Window",
        "components": ["Silver Key"],
        "target_mode": "tile",
    },
    "the bright key": {
        "name": "The Bright Key",
        "components": ["Silver Key"],
        "target_mode": "tile",
    },
    "flaming hand of destruction": {
        "name": "Flaming Hand of Destruction",
        "components": ["Red Dragon Dust"],
        "target_mode": "none",
    },
    "flight": {
        "name": "Flight",
        "components": ["Red Dragon Dust"],
        "target_mode": "model",
        "requires_los": True,
    },
    "swift wind": {
        "name": "Swift Wind",
        "components": ["Fire Dust"],
        "target_mode": "none",
    },
    "flames of death": {
        "name": "Flames of Death",
        "components": ["Fire Dust"],
        "target_mode": "tile",
        "requires_los": True,
        "max_range": 12,
        "damage_dice": 5,
        "area": "fireball",
    },
    "flames of the phoenix": {
        "name": "Flames of the Phoenix",
        "components": ["Phoenix Feather"],
        "target_mode": "model",
        "adjacent_only": True,
        "friendly_only": True,
    },
    "power of the phoenix": {
        "name": "Power of the Phoenix",
        "components": ["Phoenix Feather", "Dragon Tooth"],
        "target_mode": "model",
        "friendly_only": True,
        "intelligence_test": True,
    },
    "still air": {
        "name": "Still Air",
        "components": ["Phoenix Feather"],
        "target_mode": "tile",
        "requires_los": True,
    },
    "inferno of doom": {
        "name": "Inferno of Doom",
        "components": ["Fire Dust", "Dragon Tooth"],
        "target_mode": "tile",
        "requires_los": True,
        "max_range": 12,
        "damage_dice": 7,
        "damage_dice_on_failed_test": 5,
        "area": "fireball",
        "intelligence_test": True,
    },
    "courage": {
        "name": "Courage",
        "components": ["Silver Key"],
        "target_mode": "model",
        "adjacent_only": True,
        "friendly_only": True,
    },
    "choke": {
        "name": "Choke",
        "components": ["Vial of Swamp Gas"],
        "target_mode": "model",
        "requires_los": True,
    },
    "fireball": {
        "name": "Fireball",
        "components": ["Pinch of Warpstone"],
        "target_mode": "tile",
        "requires_los": True,
        "max_range": 12,
        "damage_dice": 5,
        "area": "fireball",
    },
    "flaming skull of terror": {
        "name": "Flaming Skull of Terror",
        "components": ["Silver Daemon Statue"],
        "target_mode": "none",
    },
    "lightning bolt": {
        "name": "Lightning Bolt",
        "components": ["Silver Bolt"],
        "target_mode": "model",
        "requires_los": True,
        "max_range": 12,
        "damage_dice": 6,
    },
}


def normalize_spell_name(spell_name: str) -> str:
    """Convert a spell name to a stable lookup key."""
    return " ".join(str(spell_name).strip().lower().split())


def get_spell_definition(spell_name: str) -> Optional[Dict[str, Any]]:
    """Return the canonical spell definition for a spell name."""
    return SPELL_DEFINITIONS.get(normalize_spell_name(spell_name))


def get_default_known_spells(class_type: str) -> List[str]:
    """Return the default spellbook for a newly created caster."""
    if class_type == "Wizard":
        return list(DEFAULT_BRIGHT_SPELLS)
    return []


def get_default_spell_components(class_type: str) -> Dict[str, int]:
    """Return starting spell components for a newly created caster."""
    if class_type != "Wizard":
        return {}
    return {spell: 1 for spell in DEFAULT_BRIGHT_SPELLS}


def spell_component_count(spell_name: str) -> int:
    """Return how many components a spell consumes per cast."""
    definition = get_spell_definition(spell_name)
    if definition is None:
        return 0
    return len(definition.get("components", []))


def format_spell_source_label(spell_name: str, source_kind: str, item: Optional[Dict[str, Any]] = None) -> str:
    """Create a concise UI label for a spell source."""
    if source_kind == "wand" and item is not None:
        return f"Wand: {spell_name} ({int(item.get('charges', 0))})"
    if source_kind == "scroll" and item is not None:
        return f"Scroll: {spell_name}"
    return f"Spell: {spell_name}"

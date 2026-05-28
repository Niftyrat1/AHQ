"""Between-expedition training, healer, and shopping helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from hero import Hero


TABLES_PATH = Path(__file__).parent / "data" / "tables.json"
if TABLES_PATH.exists():
    with open(TABLES_PATH, "r", encoding="utf-8") as _tables_handle:
        _TABLES = json.load(_tables_handle)
else:
    _TABLES = {}


TRAINABLE_STATS = {
    "ws": ("Weapon Skill", "ws"),
    "bs": ("Ballistic Skill", "bs"),
    "strength": ("Strength", "strength"),
    "toughness": ("Toughness", "toughness"),
    "speed": ("Speed", "speed"),
    "bravery": ("Bravery", "bravery"),
    "intelligence": ("Intelligence", "intelligence"),
    "wounds": ("Wounds", "max_wounds"),
}

WIZARD_ARMOUR_KEYS = {"shield", "leather_armour", "chain_armour", "plate_armour", "mithril_armour"}


def _cost_entry(section: str, key: str) -> Dict[str, Any]:
    return dict(_TABLES.get("costs_table", {}).get(section, {}).get(key, {}))


def _equipment_entry(key: str) -> Dict[str, Any]:
    return dict(_TABLES.get("equipment", {}).get(key, {}))


def _build_equipment_item(item_key: str) -> Optional[Dict[str, Any]]:
    data = _equipment_entry(item_key)
    if not data:
        return None
    item: Dict[str, Any] = {
        "key": item_key,
        "name": data.get("display_name", item_key.replace("_", " ").title()),
        "type": data.get("type", "weapon"),
        "equipped": True,
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
    ):
        if field in data:
            item[field] = data[field]
    if item.get("requires_reload"):
        item["loaded"] = bool(data.get("starts_loaded", True))
    return item


def _deduct_gold(hero: Hero, cost: int) -> Tuple[bool, str]:
    if hero.gold < cost:
        return False, f"{hero.name} needs {cost} gold crowns."
    hero.gold -= cost
    return True, ""


def can_use_between_expedition_training(hero: Hero) -> bool:
    """Training and spell purchases are only legal after a completed expedition."""
    return hero.expeditions_completed > 0


def train_hero_stat(hero: Hero, stat_key: str) -> str:
    """Increase one hero characteristic using the costs table."""
    if not can_use_between_expedition_training(hero):
        return f"{hero.name} must complete an expedition before training."
    if stat_key not in TRAINABLE_STATS:
        return "Unknown characteristic."
    cost = int(_cost_entry("training", "increase_characteristic").get("cost", 200))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    label, attr = TRAINABLE_STATS[stat_key]
    if attr == "max_wounds":
        hero.max_wounds += 1
        hero.current_wounds += 1
    else:
        setattr(hero, attr, int(getattr(hero, attr)) + 1)
    return f"{hero.name} trains {label} for {cost} gold crowns."


def increase_hero_fate(hero: Hero) -> str:
    """Increase a hero's maximum Fate between expeditions."""
    if not can_use_between_expedition_training(hero):
        return f"{hero.name} must complete an expedition before training."
    cost = int(_cost_entry("training", "increase_fate").get("cost", 1000))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    hero.max_fate += 1
    hero.current_fate += 1
    return f"{hero.name} increases Fate by 1 for {cost} gold crowns."


def buy_equipment(hero: Hero, item_key: str) -> str:
    """Buy a weapon/armour item from the between-expedition shop."""
    profile = _equipment_entry(item_key)
    if not profile:
        return "Unknown equipment item."
    if hero.is_wizard() and item_key in WIZARD_ARMOUR_KEYS:
        return f"{hero.name} cannot wear that."
    cost = int(profile.get("cost", 0))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    item = _build_equipment_item(item_key)
    if item is None:
        hero.gold += cost
        return "That item could not be created."
    can_carry, carry_message = hero.can_carry_equipment_item(item)
    if not can_carry:
        hero.gold += cost
        return carry_message
    can_equip, equip_message = hero.can_equip_item(item)
    if not can_equip:
        item["equipped"] = False
    if item.get("type") == "weapon":
        for existing in hero.equipment:
            if existing.get("type") == "weapon":
                existing["equipped"] = False
    elif item.get("type") == "ranged_weapon":
        for existing in hero.equipment:
            if existing.get("type") == "ranged_weapon":
                existing["equipped"] = False
    elif item.get("type") in {"armour", "armor", "helm"}:
        for existing in hero.equipment:
            if existing.get("type") in {"armour", "armor", "helm"}:
                existing["equipped"] = False
    elif item.get("type") == "shield":
        for existing in hero.equipment:
            if existing.get("type") == "shield":
                existing["equipped"] = False
    hero.equipment.append(item)
    bonus_text = ""
    if item_key in {"short_bow", "bow", "long_bow"}:
        hero.add_ammo("arrows", 6)
        bonus_text = " and 6 arrows"
    elif item_key == "crossbow":
        hero.add_ammo("bolts", 6)
        bonus_text = " and 6 bolts"
    if not can_equip:
        return f"{hero.name} buys {item['name']}{bonus_text} for {cost} gold crowns. {equip_message}"
    return f"{hero.name} buys {item['name']}{bonus_text} for {cost} gold crowns."


def buy_supply(hero: Hero, item_key: str) -> str:
    """Buy a non-equipped expedition item."""
    entry = _cost_entry("equipment", item_key)
    if not entry:
        return "Unknown expedition item."
    can_carry, carry_message = hero.can_carry_supply_item(item_key)
    if not can_carry:
        return carry_message
    cost = int(entry.get("cost", 0))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    hero.add_inventory_item(item_key, 1)
    return f"{hero.name} buys {entry.get('display_name', item_key)} for {cost} gold crowns."


def buy_ammo_bundle(hero: Hero, ammo_key: str) -> str:
    """Buy an ammunition bundle for future ammo tracking."""
    ammo_map = {
        "arrows_bundle": ("arrows", 6),
        "crossbow_bolts_bundle": ("bolts", 6),
    }
    entry = _cost_entry("weapons", ammo_key)
    if not entry or ammo_key not in ammo_map:
        return "Unknown ammunition bundle."
    cost = int(entry.get("cost", 0))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    ammo_type, amount = ammo_map[ammo_key]
    hero.add_ammo(ammo_type, amount)
    return f"{hero.name} buys {amount} {ammo_type} for {cost} gold crowns."


def buy_spell(hero: Hero, spell_key: str) -> str:
    """Buy a wizard spell between expeditions."""
    if not hero.is_wizard():
        return f"{hero.name} is not a wizard."
    if not can_use_between_expedition_training(hero):
        return f"{hero.name} must complete an expedition before buying spells."
    entry = _cost_entry("spells", spell_key)
    if not entry:
        return "Unknown spell."
    display_name = str(entry.get("display_name", spell_key)).strip()
    if any(current.strip().lower() == display_name.lower() for current in hero.known_spells):
        return f"{hero.name} already knows {display_name}."
    if int(getattr(hero, "paid_spells_learned", 0)) >= int(hero.expeditions_completed):
        return f"{hero.name} may only learn one paid spell per completed expedition."
    cost = int(entry.get("cost", 0))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    hero.known_spells.append(display_name)
    hero.spell_components.setdefault(display_name, 0)
    hero.paid_spells_learned = int(getattr(hero, "paid_spells_learned", 0)) + 1
    return f"{hero.name} learns {display_name} for {cost} gold crowns."


def buy_spell_component(hero: Hero, spell_name: str) -> str:
    """Buy one spell component for a known spell."""
    if not hero.is_wizard():
        return f"{hero.name} is not a wizard."
    if not any(current.strip().lower() == spell_name.strip().lower() for current in hero.known_spells):
        return f"{hero.name} does not know {spell_name}."
    cost = int(_cost_entry("spells", "spell_component").get("cost", 25))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    for current in list(hero.spell_components.keys()):
        if current.strip().lower() == spell_name.strip().lower():
            hero.spell_components[current] = int(hero.spell_components.get(current, 0)) + 1
            return f"{hero.name} buys a spell component for {current}."
    hero.spell_components[spell_name] = 1
    return f"{hero.name} buys a spell component for {spell_name}."


def use_healer_service(hero: Hero, service_key: str) -> str:
    """Apply a between-expedition healer service."""
    entry = _cost_entry("healer", service_key)
    if not entry:
        return "Unknown healer service."
    cost = int(entry.get("cost", 0))
    ok, message = _deduct_gold(hero, cost)
    if not ok:
        return message
    display_name = str(entry.get("display_name", service_key))
    if service_key == "remove_disease":
        before = len(hero.status_effects)
        hero.status_effects = [
            effect for effect in hero.status_effects
            if "disease" not in str(effect.get("name", "")).lower()
            and "mould" not in str(effect.get("name", "")).lower()
        ]
        if len(hero.status_effects) == before:
            hero.gold += cost
            return f"{hero.name} has no disease to remove."
        return f"{hero.name} pays {cost} gold crowns for {display_name}."
    if service_key == "restore_lost_limb":
        before = len(hero.status_effects)
        hero.status_effects = [
            effect for effect in hero.status_effects
            if "limb" not in str(effect.get("name", "")).lower()
        ]
        if len(hero.status_effects) == before:
            hero.gold += cost
            return f"{hero.name} has no lost limb recorded."
        return f"{hero.name} pays {cost} gold crowns for {display_name}."
    if service_key == "resurrect_dead_hero":
        if not hero.is_dead:
            hero.gold += cost
            return f"{hero.name} is not dead."
        hero.restore_to_full()
        hero.current_fate = max(1, hero.current_fate)
        return f"{hero.name} is resurrected for {cost} gold crowns."
    if service_key == "healing_potion":
        hero.equipment.append({"name": "Healing Potion", "type": "potion", "potion_effect": "healing", "equipped": False})
        return f"{hero.name} buys a Healing Potion for {cost} gold crowns."
    hero.gold += cost
    return f"{display_name} is not implemented yet."

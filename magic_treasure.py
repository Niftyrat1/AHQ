"""Magic treasure generation for Advanced HeroQuest."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple


TOP_LEVEL_TABLE: List[Tuple[range, str]] = [
    (range(2, 3), "dawnstone"),
    (range(3, 5), "amulet"),
    (range(5, 7), "wand"),
    (range(7, 9), "ring"),
    (range(9, 11), "shield_or_helm"),
    (range(11, 12), "weapon"),
    (range(12, 14), "scroll"),
    (range(14, 17), "potion"),
    (range(17, 18), "arrows_or_bolts"),
    (range(18, 21), "bow"),
    (range(21, 22), "sword"),
    (range(22, 25), "armour"),
]

WAND_SPELL_TABLE: List[Tuple[range, str]] = [
    (range(2, 4), "Inferno of Doom"),
    (range(4, 5), "Power of the Phoenix"),
    (range(5, 6), "Swift Wind"),
    (range(6, 7), "Still Air"),
    (range(7, 9), "Lightning Bolt"),
    (range(9, 11), "Choke"),
    (range(11, 12), "Flames of Death"),
    (range(12, 13), "Flames of the Phoenix"),
    (range(13, 14), "Open Window"),
    (range(14, 15), "Dragon Armour"),
    (range(15, 16), "Flaming Skull of Terror"),
    (range(16, 18), "Fireball"),
    (range(18, 20), "Courage"),
    (range(20, 22), "Flight"),
    (range(22, 23), "Flaming Hand of Destruction"),
    (range(23, 25), "The Bright Key"),
]


def _roll_d12() -> int:
    return random.randint(1, 12)


def _roll_2d12() -> Tuple[int, int, int]:
    roll1 = _roll_d12()
    roll2 = _roll_d12()
    return roll1 + roll2, roll1, roll2


def _lookup_result(total: int, table: List[Tuple[range, str]]) -> str:
    for roll_range, result in table:
        if total in roll_range:
            return result
    raise ValueError(f"No table entry for roll {total}")


def _equip_conflicts(item: Dict[str, Any], existing: Dict[str, Any]) -> bool:
    item_type = item.get("type")
    existing_type = existing.get("type")
    if item_type != existing_type:
        return False
    if item_type in {"weapon", "ranged_weapon", "armour", "armor", "shield", "helm", "ring", "amulet"}:
        return True
    return False


def _add_item_to_hero(hero, item: Dict[str, Any], log: List[str]) -> None:
    item_type = item.get("type")
    if item_type in {"weapon", "ranged_weapon", "armour", "armor", "shield", "helm", "ring", "amulet"}:
        for existing in hero.equipment:
            if existing.get("equipped") and _equip_conflicts(item, existing):
                existing["equipped"] = False
                log.append(f"  {existing.get('name', 'Existing item')} is unequipped.")
    hero.equipment.append(item)


def _make_item(name: str, item_type: str, **fields: Any) -> Dict[str, Any]:
    item = {"name": name, "type": item_type, "equipped": True}
    item.update(fields)
    return item


def generate_magic_treasure(hero, log: List[str]) -> Dict[str, Any]:
    """Generate one magic treasure item and add it to the hero."""
    total, roll1, roll2 = _roll_2d12()
    category = _lookup_result(total, TOP_LEVEL_TABLE)
    log.append(f"Magic Treasure roll: {total} ({roll1}+{roll2}) -> {category.replace('_', ' ').title()}.")

    if category == "dawnstone":
        fate_points = _roll_d12()
        item = _make_item(
            "Dawnstone",
            "trinket",
            fate_points=fate_points,
            notes="Stored Fate Points do not regenerate.",
        )
    elif category == "amulet":
        if _roll_d12() % 2 == 0:
            item = _make_item(
                "Amulet of Iron",
                "amulet",
                spell_protection={"mode": "threshold", "target": 9},
                notes="On 9+ a spell has no effect on the wearer.",
            )
        else:
            item = _make_item("Amulet of Protection", "amulet", toughness_bonus=1)
    elif category == "wand":
        spell_total, _, _ = _roll_2d12()
        spell = _lookup_result(spell_total, WAND_SPELL_TABLE)
        charges = _roll_d12()
        item = _make_item(
            f"Wand of {spell}",
            "wand",
            spell=spell,
            charges=charges,
            wizard_only=True,
            notes="Casts without components; each use spends 1 charge.",
        )
    elif category == "ring":
        ring_roll = _roll_d12()
        if ring_roll <= 3:
            item = _make_item("Ring of Protection (Level 1)", "ring", toughness_bonus=1)
        elif ring_roll <= 5:
            item = _make_item("Ring of Protection (Level 2)", "ring", toughness_bonus=2)
        elif ring_roll == 6:
            item = _make_item("Ring of Protection (Level 3)", "ring", toughness_bonus=3)
        elif ring_roll <= 9:
            item = _make_item("Ring of Magic Protection (Level 1)", "ring", spell_protection={"mode": "threshold", "target": 11})
        elif ring_roll <= 11:
            item = _make_item("Ring of Magic Protection (Level 2)", "ring", spell_protection={"mode": "threshold", "target": 9})
        else:
            item = _make_item("Ring of Magic Protection (Level 3)", "ring", spell_protection={"mode": "intelligence"})
    elif category == "shield_or_helm":
        roll = _roll_d12()
        if roll <= 6:
            item = _make_item("Magical Shield", "shield", bs_modifier=-1, armour_value=1, speed_modifier=0)
        elif roll <= 8:
            item = _make_item("Magical Greatshield", "shield", bs_modifier=-2, armour_value=2, speed_modifier=-1)
        elif roll == 9:
            item = _make_item("Dwarven Shield", "shield", bs_modifier=-2, armour_value=2, speed_modifier=0)
        elif roll <= 11:
            item = _make_item("Magical Helm", "helm", bs_modifier=0, armour_value=1, speed_modifier=0)
        else:
            item = _make_item("Dwarven Helm", "helm", bs_modifier=-1, armour_value=2, speed_modifier=0)
    elif category == "weapon":
        roll = _roll_d12()
        if roll <= 3:
            item = _make_item("Magic Dagger", "weapon", strength_damage={"1-2": 1, "3-4": 1, "5": 2, "6": 3, "7": 4, "8": 5, "9": 6, "10": 7, "11": 8, "12": 9}, critical=12, fumble=1)
        elif roll <= 5:
            item = _make_item("Magic Spear", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, critical=12, fumble=1, long_reach=True)
        elif roll <= 8:
            item = _make_item("Magic Axe", "weapon", strength_damage={"3-4": 3, "5": 4, "6": 5, "7": 6, "8": 7, "9": 8, "10": 9, "11": 10, "12": 11}, critical=12, fumble=1)
        elif roll == 9:
            item = _make_item("Great Magic Axe", "weapon", strength_damage={"3-4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "11": 11, "12": 12}, critical=12, fumble=1)
        elif roll == 10:
            item = _make_item("Magic Halberd", "weapon", strength_damage={"3-4": 3, "5": 4, "6": 5, "7": 6, "8": 7, "9": 8, "10": 9, "11": 10, "12": 11}, critical=11, fumble=2, two_handed=True, long_reach=True)
        elif roll == 11:
            item = _make_item("Magic Double-Handed Sword", "weapon", strength_damage={"6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "11": 11, "12": 12}, critical=11, fumble=2, two_handed=True, long_reach=True)
        else:
            item = _make_item("Magic Double-Handed Axe", "weapon", strength_damage={"6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "11": 11, "12": 12}, critical=11, fumble=2, two_handed=True)
    elif category == "scroll":
        roll = _roll_d12()
        count = 1 if roll <= 6 else 2 if roll <= 9 else 3 if roll <= 11 else 4
        spells = []
        for _ in range(count):
            spell_total, _, _ = _roll_2d12()
            spells.append(_lookup_result(spell_total, WAND_SPELL_TABLE))
        item = _make_item("Magic Scroll", "scroll", spells=spells, wizard_only=True, notes="Each spell can be cast once without components.")
    elif category == "potion":
        if _roll_d12() % 2 == 0:
            item = _make_item("Strength Potion", "potion", potion_effect="strength", duration_turns=3)
        else:
            item = _make_item("Healing Potion", "potion", potion_effect="healing")
    elif category == "arrows_or_bolts":
        roll = _roll_d12()
        if roll <= 4:
            item = _make_item("Arrows of Death", "ammo", ammo_type="arrow", quantity=4, ammo_effect="death")
        elif roll == 5:
            item = _make_item("Bolts of Death", "ammo", ammo_type="bolt", quantity=2, ammo_effect="death")
        elif roll <= 7:
            item = _make_item("Arrows of True Flight", "ammo", ammo_type="arrow", quantity=2, ammo_effect="true_flight")
        elif roll == 8:
            item = _make_item("Bolts of True Flight", "ammo", ammo_type="bolt", quantity=1, ammo_effect="true_flight")
        elif roll <= 11:
            item = _make_item("Arrows of the Assassin", "ammo", ammo_type="arrow", quantity=4, ammo_effect="assassin")
        else:
            item = _make_item("Bolts of the Assassin", "ammo", ammo_type="bolt", quantity=2, ammo_effect="assassin")
    elif category == "bow":
        roll = _roll_d12()
        if roll <= 4:
            item = _make_item("Magic Short Bow", "ranged_weapon", max_range=28, damage_dice=4, critical=12, fumble=1)
        elif roll <= 7:
            item = _make_item("Magic Bow", "ranged_weapon", max_range=40, damage_dice=4, critical=12, fumble=1)
        elif roll <= 9:
            item = _make_item("Magic Long Bow", "ranged_weapon", max_range=48, damage_dice=5, min_strength=6, critical=12, fumble=1)
        elif roll <= 11:
            item = _make_item("Magic Crossbow", "ranged_weapon", max_range=48, damage_dice=5, requires_reload=True, starts_loaded=True, loaded=True, critical=12, fumble=1)
        else:
            item = _make_item("Elven Power Bow", "ranged_weapon", max_range=48, damage_dice=6, critical=12, fumble=1)
    elif category == "sword":
        roll = _roll_d12()
        if roll <= 3:
            item = _make_item("Magic Sword (+1 WS)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=1, critical=12, fumble=1)
        elif roll <= 6:
            item = _make_item("Magic Sword (+1 S)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, strength_bonus=1, critical=12, fumble=1)
        elif roll <= 8:
            item = _make_item("Magic Sword (+1 WS, +1 S)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=1, strength_bonus=1, critical=12, fumble=1)
        elif roll == 9:
            item = _make_item("Magic Sword (+2 WS, +1 S)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=2, strength_bonus=1, critical=12, fumble=1)
        elif roll == 10:
            item = _make_item("Magic Sword (+1 WS, +2 S)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=1, strength_bonus=2, critical=12, fumble=1)
        elif roll == 11:
            item = _make_item("Magic Sword (+2 WS, +2 S)", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=2, strength_bonus=2, critical=12, fumble=1)
        else:
            item = _make_item("Rune Sword", "weapon", strength_damage={"3-4": 2, "5": 3, "6": 4, "7": 5, "8": 6, "9": 7, "10": 8, "11": 9, "12": 10}, ws_bonus=2, strength_bonus=2, wizard_usable=True, critical=12, fumble=1)
    else:
        armour_total, _, _ = _roll_2d12()
        if armour_total <= 6:
            item = _make_item("Magic Leather Armour", "armour", speed_modifier=0, bs_modifier=-1, armour_value=1)
        elif armour_total <= 10:
            item = _make_item("Heavy Magic Leather Armour", "armour", speed_modifier=-1, bs_modifier=-1, armour_value=2)
        elif armour_total <= 13:
            item = _make_item("Magic Chain Armour", "armour", speed_modifier=-2, bs_modifier=-1, armour_value=3)
        elif armour_total <= 15:
            item = _make_item("Light Magic Chain Armour", "armour", speed_modifier=-1, bs_modifier=-1, armour_value=2)
        elif armour_total <= 17:
            item = _make_item("Fine Magic Chain Armour", "armour", speed_modifier=0, bs_modifier=0, armour_value=1)
        elif armour_total <= 19:
            item = _make_item("Magic Plate Armour", "armour", speed_modifier=-2, bs_modifier=-2, armour_value=4)
        elif armour_total == 20:
            item = _make_item("Mithril Armour", "armour", speed_modifier=0, bs_modifier=0, armour_value=3)
        elif armour_total == 21:
            item = _make_item("Enchanted Armour", "armour", speed_modifier=-2, bs_modifier=-2, armour_value=5)
        elif armour_total == 22:
            item = _make_item("Dwarven Armour", "armour", speed_modifier=0, bs_modifier=-2, armour_value=4)
        else:
            item = _make_item("Elven Armour", "armour", speed_modifier=-1, bs_modifier=0, armour_value=4)

    _add_item_to_hero(hero, item, log)
    log.append(f"{hero.name} receives {item['name']}.")
    return item


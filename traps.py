"""AHQ trap tables and trap resolution."""

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from combat import apply_damage_to_hero, roll_damage


@dataclass(frozen=True)
class TrapDefinition:
    """A trap entry from the AHQ traps table."""

    name: str
    spot_chance: int
    disarm_chance: Optional[int]


TRAP_TABLE_ROOM_OR_PASSAGE = (
    (1, 1, "Pit Trap"),
    (2, 2, "Crossfire"),
    (3, 3, "Portcullis"),
    (4, 4, "Poison Dart"),
    (5, 5, "Blocks"),
    (6, 6, "Gas"),
    (7, 7, "Mantrap"),
    (8, 8, "Spike"),
    (9, 12, "Shock"),
)

TRAP_TABLE_CHEST = (
    (1, 1, "Pit Trap"),
    (2, 2, "Portcullis"),
    (3, 3, "Poison Dart"),
    (4, 4, "Gas"),
    (5, 5, "Mantrap"),
    (6, 6, "Spike"),
    (7, 7, "Shock"),
    (8, 10, "Magic"),
    (11, 12, "Guillotine"),
)

TRAPS: Dict[str, TrapDefinition] = {
    "Pit Trap": TrapDefinition("Pit Trap", 5, None),
    "Crossfire": TrapDefinition("Crossfire", 8, 6),
    "Portcullis": TrapDefinition("Portcullis", 6, 11),
    "Poison Dart": TrapDefinition("Poison Dart", 9, 8),
    "Blocks": TrapDefinition("Blocks", 7, 11),
    "Gas": TrapDefinition("Gas", 10, 7),
    "Mantrap": TrapDefinition("Mantrap", 6, 6),
    "Spike": TrapDefinition("Spike", 8, 7),
    "Shock": TrapDefinition("Shock", 9, 11),
    "Magic": TrapDefinition("Magic", 8, 9),
    "Guillotine": TrapDefinition("Guillotine", 7, 7),
}

MAGIC_TRAP_SPELLS = (
    (1, 2, "Inferno of Doom"),
    (3, 4, "Lightning Bolt"),
    (5, 8, "Choke"),
    (9, 10, "Flames of Death"),
    (11, 12, "Fireball"),
)

GAS_EFFECTS = (
    (1, 6, "Mild Poison"),
    (7, 8, "Nausea"),
    (9, 10, "Madness"),
    (11, 11, "Strong Poison"),
    (12, 12, "Deadly Poison"),
)


def _roll_d12() -> int:
    return random.randint(1, 12)


def _lookup_table(roll: int, table) -> str:
    for low, high, result in table:
        if low <= roll <= high:
            return result
    raise ValueError(f"Roll {roll} did not match table")


def _is_dwarf(hero) -> bool:
    return getattr(hero, "race", "").lower() == "dwarf"


def _get_spot_bonus(hero) -> int:
    return 2 if _is_dwarf(hero) else 0


def _get_disarm_bonus(hero) -> int:
    bonus = getattr(hero, "trap_disarm_bonus", 0)
    if _is_dwarf(hero):
        bonus += 2
    return bonus


def _get_equipped_armour_names(hero) -> List[str]:
    armour_names: List[str] = []
    for item in getattr(hero, "equipment", []):
        if item.get("equipped") and item.get("type") in {"armour", "armor"}:
            armour_names.append(str(item.get("name", "")).lower())
    return armour_names


def _wears_metal_armour(hero) -> bool:
    armour_names = _get_equipped_armour_names(hero)
    metal_keywords = ("chain", "mail", "plate", "mithril", "metal", "heavy")
    return any(any(keyword in armour for keyword in metal_keywords) for armour in armour_names)


def roll_random_trap(source: str = "room_or_passage") -> TrapDefinition:
    """Roll a trap from the appropriate AHQ trap table."""
    roll = _roll_d12()
    table = TRAP_TABLE_CHEST if source == "chest" else TRAP_TABLE_ROOM_OR_PASSAGE
    return TRAPS[_lookup_table(roll, table)]


def mark_trap(dungeon, pos, trap_type: str, symbol: str, blocks_movement: bool = False):
    """Record a persistent visible trap marker in the dungeon state."""
    dungeon.trap_markers[pos] = {
        "type": trap_type,
        "symbol": symbol,
        "blocks_movement": blocks_movement,
    }


def resolve_trap_event(
    hero,
    dungeon,
    log: List[str],
    start_wandering_combat: Callable[[tuple], None],
    source: str = "room_or_passage",
    trap_name: Optional[str] = None,
    can_spot: bool = True,
    can_disarm: bool = True,
) -> TrapDefinition:
    """Resolve a trap using the AHQ tables and current engine defaults."""
    trap = TRAPS[trap_name] if trap_name is not None else roll_random_trap(source)
    spot_bonus = _get_spot_bonus(hero)
    disarm_bonus = _get_disarm_bonus(hero)
    spot_bonus_note = f" (+{spot_bonus} bonus)" if spot_bonus else ""
    disarm_bonus_note = f" (+{disarm_bonus} bonus)" if disarm_bonus else ""

    log.append(
        f"  Trap rolled: {trap.name}. Spot {trap.spot_chance}+"
        f"{', disarm ' + str(trap.disarm_chance) + '+' if trap.disarm_chance else ', cannot be disarmed'}."
    )

    spotted = False
    if can_spot:
        spot_roll = _roll_d12() + spot_bonus
        spotted = spot_roll >= trap.spot_chance
        log.append(f"  Spot roll: {spot_roll}{spot_bonus_note} -> {'spotted' if spotted else 'missed'}.")

    # Pit traps are explicitly spotted but not avoided.
    if trap.name == "Pit Trap" and spotted:
        log.append("  Pit trap spotted, but the victim still sets it off per the AHQ rules.")
    elif spotted and trap.disarm_chance and can_disarm:
        raw_disarm_roll = _roll_d12()
        disarm_roll = raw_disarm_roll + disarm_bonus
        log.append(f"  Disarm roll: {disarm_roll}{disarm_bonus_note}.")

        if raw_disarm_roll == 12:
            hero.trap_disarm_bonus = getattr(hero, "trap_disarm_bonus", 0) + 1
            log.append(f"  Perfect technique: {hero.name} gains +1 on future disarm attempts.")

        if disarm_roll >= trap.disarm_chance:
            log.append("  Trap disarmed.")
            return trap

        log.append("  Disarm failed. The trap goes off.")
        _apply_trap_effect(trap, hero, dungeon, log, start_wandering_combat)
        if raw_disarm_roll == 1:
            log.append("  Disarm blunder: 1 extra wound above the trap's normal effect.")
            apply_damage_to_hero(hero, 1, log)
        return trap
    elif spotted:
        if trap.disarm_chance is None:
            log.append("  This trap cannot be disarmed.")
        else:
            log.append("  Trap left active; the current engine resolves it immediately.")

    _apply_trap_effect(trap, hero, dungeon, log, start_wandering_combat)
    return trap


def _apply_trap_effect(trap: TrapDefinition, hero, dungeon, log: List[str], start_wandering_combat):
    if trap.name == "Pit Trap":
        dungeon.grid[(hero.x, hero.y)] = dungeon.TileType.PIT_TRAP
        mark_trap(dungeon, (hero.x, hero.y), "pit_trap", "PT", blocks_movement=True)
        fall_roll = _roll_d12()
        log.append(f"  Pit trap: fall roll {fall_roll}.")
        if fall_roll >= 9:
            apply_damage_to_hero(hero, 1, log)
        climb_roll = _roll_d12()
        if climb_roll <= hero.speed:
            log.append(f"  Climb-out roll {climb_roll} <= Speed {hero.speed}: {hero.name} scrambles clear.")
        else:
            log.append(
                f"  Climb-out roll {climb_roll} > Speed {hero.speed}: {hero.name} remains in the pit for now."
            )
        return

    if trap.name == "Crossfire":
        roll = _roll_d12()
        bolt_hits = (roll + 3) // 4
        log.append(f"  Crossfire: {roll} rolled, {bolt_hits} bolt(s) hit.")
        total_damage = 0
        for bolt_index in range(bolt_hits):
            damage, rolls = roll_damage(3, hero.toughness, False)
            total_damage += damage
            log.append(f"    Bolt {bolt_index + 1}: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if total_damage:
            apply_damage_to_hero(hero, total_damage, log)
        return

    if trap.name == "Portcullis":
        mark_trap(dungeon, (hero.x, hero.y), "portcullis", "PC", blocks_movement=True)
        log.append(
            "  A portcullis slams down. Lifting it should take a full exploration turn and Strength total 20+."
        )
        return

    if trap.name == "Poison Dart":
        damage, rolls = roll_damage(1, hero.toughness, False)
        log.append(f"  Poison dart: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage > 0:
            hero.current_wounds = 0
            hero.is_ko = True
            if hero.current_fate > 0:
                log.append(f"  {hero.name} is reduced to 0 wounds and spends Fate to survive the poison.")
                hero.spend_fate()
            else:
                log.append(f"  {hero.name} is reduced to 0 wounds and knocked out.")
        return

    if trap.name == "Blocks":
        mark_trap(dungeon, (hero.x, hero.y), "blocks", "BL", blocks_movement=True)
        dodge_roll = _roll_d12()
        damage_dice = 3 if dodge_roll <= hero.speed else 12
        damage, rolls = roll_damage(damage_dice, hero.toughness, False)
        log.append(
            f"  Blocks: dodge roll {dodge_roll} vs Speed {hero.speed} -> {damage_dice} damage dice, "
            f"{rolls} vs T{hero.toughness} = {damage} wounds."
        )
        if damage:
            apply_damage_to_hero(hero, damage, log)
        return

    if trap.name == "Gas":
        _apply_gas_trap(hero, log)
        return

    if trap.name == "Mantrap":
        damage, rolls = roll_damage(4, hero.toughness, False)
        log.append(f"  Mantrap: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log)
            log.append("  Limb-loss effects are noted for the rules pass but not yet modelled in equipment restrictions.")
        return

    if trap.name == "Spike":
        damage, rolls = roll_damage(3, hero.toughness, False)
        log.append(f"  Spike: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log)
        poison_roll = _roll_d12()
        if poison_roll >= 8:
            log.append(f"  Poison check {poison_roll}: poisoned like a poison dart.")
            poison_damage, poison_rolls = roll_damage(1, hero.toughness, False)
            log.append(f"  Poison follow-up: {poison_rolls} vs T{hero.toughness} = {poison_damage} wounds.")
            if poison_damage > 0:
                hero.current_wounds = 0
                hero.is_ko = True
                if hero.current_fate > 0:
                    log.append(f"  {hero.name} spends Fate to survive the poison.")
                    hero.spend_fate()
                else:
                    log.append(f"  {hero.name} is knocked out by the poison.")
        return

    if trap.name == "Shock":
        damage_dice = 10 if _wears_metal_armour(hero) else 5
        damage, rolls = roll_damage(damage_dice, hero.toughness, False)
        armour_note = " wearing metal armour" if damage_dice == 10 else ""
        log.append(
            f"  Shock{armour_note}: {rolls} vs T{hero.toughness} = {damage} wounds from {damage_dice} dice."
        )
        if damage:
            apply_damage_to_hero(hero, damage, log)
        return

    if trap.name == "Magic":
        spell_roll = _roll_d12()
        spell_name = _lookup_table(spell_roll, MAGIC_TRAP_SPELLS)
        log.append(f"  Magic trap: spell roll {spell_roll} -> {spell_name}.")
        if spell_name == "Fireball":
            damage, rolls = roll_damage(5, hero.toughness, False)
            log.append(f"  Fireball effect: {rolls} vs T{hero.toughness} = {damage} wounds.")
            if damage:
                apply_damage_to_hero(hero, damage, log)
        else:
            log.append("  Spell effect recorded; full spell implementation will share the future magic system.")
        return

    if trap.name == "Guillotine":
        damage, rolls = roll_damage(2, hero.toughness, False)
        log.append(f"  Guillotine: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log)
            log.append("  Hand-loss effects are noted for the rules pass but not yet modelled in equipment restrictions.")
        return

    log.append(f"  Trap {trap.name} has no resolver yet.")


def _apply_gas_trap(hero, log: List[str]):
    gas_roll = _roll_d12()
    gas_type = _lookup_table(gas_roll, GAS_EFFECTS)
    log.append(f"  Gas trap: effect roll {gas_roll} -> {gas_type}.")

    if gas_type == "Mild Poison":
        apply_damage_to_hero(hero, 1, log)
        log.append("  Mild poison: the movement restriction is noted but not yet enforced turn-by-turn.")
        return

    if gas_type == "Nausea":
        log.append("  Nausea: reduced move/WS/BS/Strength is noted for the follow-up status-effects pass.")
        return

    if gas_type == "Madness":
        log.append("  Madness: GM control for 6 turns is noted for the follow-up status-effects pass.")
        return

    if gas_type == "Strong Poison":
        damage, rolls = roll_damage(8, hero.toughness, False)
        log.append(f"  Strong poison: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log)
        return

    if gas_type == "Deadly Poison":
        if hero.current_fate > 0:
            log.append(f"  Deadly poison: {hero.name} spends Fate in lieu of the missing Healing Potion support.")
            hero.spend_fate()
        else:
            hero.is_dead = True
            hero.is_ko = True
            hero.current_wounds = 0
            log.append(f"  Deadly poison: {hero.name} dies without a Healing Potion.")
        return


__all__ = [
    "TrapDefinition",
    "TRAPS",
    "roll_random_trap",
    "resolve_trap_event",
]

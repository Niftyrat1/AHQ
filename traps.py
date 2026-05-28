"""AHQ trap tables and trap resolution."""

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

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
    (9, 9, "Shock"),
    (10, 10, "Magic"),
    (11, 11, "Fireball"),
    (12, 12, "Mindstealer"),
    (13, 13, "Guillotine"),
    (14, 15, "Alarm"),
)

TRAP_TABLE_CHEST = (
    (1, 1, "Pit Trap"),
    (2, 2, "Crossfire"),
    (3, 3, "Portcullis"),
    (4, 4, "Poison Dart"),
    (5, 5, "Blocks"),
    (6, 6, "Gas"),
    (7, 7, "Mantrap"),
    (8, 8, "Spike"),
    (9, 12, "Guillotine"),
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
    "Fireball": TrapDefinition("Fireball", 8, 9),
    "Mindstealer": TrapDefinition("Mindstealer", 6, 10),
    "Guillotine": TrapDefinition("Guillotine", 7, 7),
    "Alarm": TrapDefinition("Alarm", 7, 7),
}

TRAP_SYMBOLS = {
    "Pit Trap": "PT",
    "Crossfire": "CF",
    "Portcullis": "PC",
    "Poison Dart": "PD",
    "Blocks": "BL",
    "Gas": "GS",
    "Mantrap": "MT",
    "Spike": "SP",
    "Shock": "SH",
    "Magic": "MG",
    "Fireball": "FB",
    "Mindstealer": "MS",
    "Guillotine": "GU",
    "Alarm": "AL",
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


def _roll_d15() -> int:
    return random.randint(1, 15)


def _lookup_table(roll: int, table) -> str:
    for low, high, result in table:
        if low <= roll <= high:
            return result
    raise ValueError(f"Roll {roll} did not match table")


def _is_dwarf(hero) -> bool:
    return getattr(hero, "race", "").lower() == "dwarf"


def _get_spot_bonus(hero) -> int:
    bonus = 2 if _is_dwarf(hero) else 0
    for effect in getattr(hero, "status_effects", []):
        bonus += int(effect.get("trap_spot_delta", 0))
    return bonus


def _get_disarm_bonus(hero) -> int:
    bonus = getattr(hero, "trap_disarm_bonus", 0)
    if _is_dwarf(hero):
        bonus += 2
    for effect in getattr(hero, "status_effects", []):
        bonus += int(effect.get("trap_disarm_delta", 0))
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
    if source == "chest":
        roll = _roll_d12()
        table = TRAP_TABLE_CHEST
    else:
        roll = _roll_d15()
        table = TRAP_TABLE_ROOM_OR_PASSAGE
    return TRAPS[_lookup_table(roll, table)]


def mark_trap(dungeon, pos, trap_type: str, symbol: str, blocks_movement: bool = False, **extra):
    """Record a persistent visible trap marker in the dungeon state."""
    dungeon.trap_markers[pos] = {
        "type": trap_type,
        "symbol": symbol,
        "blocks_movement": blocks_movement,
        **extra,
    }


def _get_trap_zone_positions(pos: Tuple[int, int], source: str) -> List[Tuple[int, int]]:
    """Return the blocked zone for a visible undisbarmed trap."""
    if source == "chest":
        return [pos]
    x, y = pos
    return [
        (x, y),
        (x - 1, y),
        (x + 1, y),
        (x, y - 1),
        (x, y + 1),
    ]


def get_portcullis_placement_options(dungeon, pos: Tuple[int, int]) -> List[List[Tuple[int, int]]]:
    """Return legal doorway or non-diagonal room lines for a dropped portcullis."""
    if dungeon.get_tile(*pos) in {dungeon.TileType.DOOR_CLOSED, dungeon.TileType.DOOR_OPEN}:
        return [[pos]]

    room = dungeon.find_room_for_tile(*pos)
    if room is None:
        return [[pos]]

    interior = set(dungeon.get_room_interior_tiles(room))
    if pos not in interior:
        return [[pos]]

    options: List[List[Tuple[int, int]]] = []
    seen = set()
    for y in sorted({tile[1] for tile in interior}):
        line = tuple(sorted(tile for tile in interior if tile[1] == y))
        if line and line not in seen:
            seen.add(line)
            options.append(list(line))
    for x in sorted({tile[0] for tile in interior}):
        line = tuple(sorted(tile for tile in interior if tile[0] == x))
        if line and line not in seen:
            seen.add(line)
            options.append(list(line))
    return options or [[pos]]


def _coerce_selected_portcullis_line(
    options: List[List[Tuple[int, int]]],
    selected_positions: Optional[List[Tuple[int, int]]],
) -> Optional[List[Tuple[int, int]]]:
    """Return a selected line only if it exactly matches one legal placement."""
    if not selected_positions:
        return None
    selected = {(int(x), int(y)) for x, y in selected_positions}
    for option in options:
        if selected == set(option):
            return list(option)
    return None


def _get_portcullis_positions(
    dungeon,
    pos: Tuple[int, int],
    selected_positions: Optional[List[Tuple[int, int]]] = None,
) -> List[Tuple[int, int]]:
    """Return selected or deterministic board positions for a dropped portcullis."""
    options = get_portcullis_placement_options(dungeon, pos)
    selected = _coerce_selected_portcullis_line(options, selected_positions)
    if selected is not None:
        return selected

    if len(options) == 1:
        return options[0]

    room = dungeon.find_room_for_tile(*pos)
    if room is None:
        return options[0]

    interior = set(dungeon.get_room_interior_tiles(room))
    horizontal = sorted([tile for tile in interior if tile[1] == pos[1]])
    vertical = sorted([tile for tile in interior if tile[0] == pos[0]])
    if len(vertical) > len(horizontal):
        return vertical
    return horizontal or [pos]


def _apply_limb_loss(hero, lost: str, log: List[str]):
    """Apply the rules consequences for losing a hand or leg."""
    if lost == "lost_leg":
        if not hero.has_status_effect("lost_leg"):
            hero.add_status_effect(
                "lost_leg",
                scope="campaign",
                speed_divisor_round_up=2,
                exploration_move_cap=8,
            )
        for item in hero.equipment:
            if item.get("equipped") and (item.get("type") == "shield" or item.get("two_handed")):
                item["equipped"] = False
        log.append(
            f"  {hero.name} loses a leg. Speed is halved (round up), exploration move is capped at 8, "
            "and shields and two-handed weapons may not be used until healed between expeditions."
        )
        return

    if not hero.has_status_effect("lost_hand"):
        hero.add_status_effect("lost_hand", scope="campaign", ws_divisor=2)
    for item in hero.equipment:
        if item.get("equipped") and (
            item.get("type") in {"shield", "ranged_weapon"} or item.get("two_handed")
        ):
            item["equipped"] = False
    log.append(
        f"  {hero.name} loses a hand. Weapon Skill is halved, bows and two-handed weapons may not be used, "
        "and Wizards may not cast spells needing 2 or more components until healed between expeditions."
    )


def mark_visible_trap(dungeon, pos: Tuple[int, int], trap: TrapDefinition, source: str = "room_or_passage"):
    """Record a spotted trap that can later be disarmed."""
    zone = _get_trap_zone_positions(pos, source)
    for zone_pos in zone:
        symbol = TRAP_SYMBOLS.get(trap.name, "TR") if zone_pos == pos else ""
        mark_trap(
            dungeon,
            zone_pos,
            "visible_trap_zone",
            symbol,
            blocks_movement=(trap.name != "Blocks"),
            trap_name=trap.name,
            disarm_chance=trap.disarm_chance,
            trap_source=source,
            trap_center=[pos[0], pos[1]],
            trap_zone=[[item[0], item[1]] for item in zone],
            careful_movement_only=(trap.name == "Blocks"),
            zone_tile=(zone_pos != pos),
        )


def clear_visible_trap(dungeon, pos: Tuple[int, int]):
    """Remove a visible trap zone from the dungeon state."""
    marker = dungeon.trap_markers.get(pos)
    if marker is None:
        return
    center_data = marker.get("trap_center")
    if isinstance(center_data, list) and len(center_data) == 2:
        center = (int(center_data[0]), int(center_data[1]))
        marker = dungeon.trap_markers.get(center, marker)
    zone_data = marker.get("trap_zone", [])
    for zone_pos in zone_data:
        if isinstance(zone_pos, list) and len(zone_pos) == 2:
            dungeon.trap_markers.pop((int(zone_pos[0]), int(zone_pos[1])), None)


def get_trap_marker(dungeon, pos: Tuple[int, int], trap_type: Optional[str] = None) -> Optional[dict]:
    """Return trap marker metadata for a tile, optionally filtered by type."""
    marker = dungeon.trap_markers.get(pos)
    if marker is None:
        return None
    if trap_type is not None and marker.get("type") != trap_type:
        return None
    return marker


def get_pit_leap_destination(hero, dungeon) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Return a jumpable adjacent pit and the landing square beyond it."""
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        pit_pos = (hero.x + dx, hero.y + dy)
        if dungeon.get_tile(*pit_pos) != dungeon.TileType.PIT_TRAP:
            continue
        landing = (pit_pos[0] + dx, pit_pos[1] + dy)
        if dungeon.is_walkable(*landing):
            return pit_pos, landing
    return None


def resolve_trap_event(
    hero,
    dungeon,
    log: List[str],
    start_wandering_combat: Callable[[tuple], None],
    resolve_magic_spell: Optional[Callable[[object, str, Optional[Tuple[int, int]]], None]] = None,
    source: str = "room_or_passage",
    trap_name: Optional[str] = None,
    can_spot: bool = True,
    can_disarm: bool = True,
    trap_pos: Optional[Tuple[int, int]] = None,
    affected_heroes: Optional[List[object]] = None,
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
    trap_location = trap_pos if trap_pos is not None else (hero.x, hero.y)

    if trap.name == "Pit Trap" and spotted:
        log.append("  Pit trap spotted, but the victim still sets it off per the AHQ rules.")
    elif spotted and trap.disarm_chance and can_disarm:
        mark_visible_trap(dungeon, trap_location, trap, source)
        log.append("  Trap spotted before it takes effect. It remains armed until a hero disarms it.")
        return trap
    elif spotted:
        if trap.disarm_chance is None:
            log.append("  This trap cannot be disarmed.")
        else:
            log.append("  Trap left active; the current engine resolves it immediately.")

    _apply_trap_effect(
        trap,
        hero,
        dungeon,
        log,
        start_wandering_combat,
        trap_location,
        resolve_magic_spell,
        source,
        affected_heroes,
    )
    return trap


def attempt_disarm_trap(hero, dungeon, log: List[str], pos: Tuple[int, int]) -> bool:
    """Attempt to disarm a visible trap zone."""
    marker = dungeon.trap_markers.get(pos)
    if marker is None:
        log.append("  There is no visible trap there to disarm.")
        return False

    center_data = marker.get("trap_center")
    if isinstance(center_data, list) and len(center_data) == 2:
        center = (int(center_data[0]), int(center_data[1]))
    else:
        center = pos
    marker = dungeon.trap_markers.get(center, marker)

    trap_name = marker.get("trap_name")
    if trap_name not in TRAPS:
        log.append("  This trap cannot be disarmed here.")
        return False

    trap = TRAPS[trap_name]
    disarm_chance = trap.disarm_chance
    if disarm_chance is None:
        log.append(f"  {trap.name} cannot be disarmed.")
        return False

    disarm_bonus = _get_disarm_bonus(hero)
    disarm_bonus_note = f" (+{disarm_bonus} bonus)" if disarm_bonus else ""
    raw_disarm_roll = _roll_d12()
    disarm_roll = raw_disarm_roll + disarm_bonus
    log.append(f"  Disarm roll: {disarm_roll}{disarm_bonus_note}.")

    if raw_disarm_roll == 12:
        hero.trap_disarm_bonus = getattr(hero, "trap_disarm_bonus", 0) + 1
        log.append(f"  Perfect technique: {hero.name} gains +1 on future disarm attempts.")

    if disarm_roll >= disarm_chance:
        clear_visible_trap(dungeon, center)
        log.append("  Trap disarmed.")
        return True

    if hero.has_fate_available():
        hero.queue_failed_roll_fate_decision(
            "disarm_trap",
            trap_name=trap.name,
            trap_center=[center[0], center[1]],
            trap_source=str(marker.get("trap_source", "room_or_passage")),
            raw_disarm_roll=raw_disarm_roll,
        )
        log.append("  Disarm failed. The trap would go off, but Fate may still turn the failed roll into a success.")
        return False

    resolve_failed_disarm_outcome(hero, dungeon, log, center, raw_disarm_roll=raw_disarm_roll)
    return False


def resolve_failed_disarm_outcome(hero, dungeon, log: List[str], center: Tuple[int, int], *, raw_disarm_roll: Optional[int] = None):
    """Resolve the trap consequences from a failed disarm after Fate is refused or unavailable."""
    marker = dungeon.trap_markers.get(center)
    if marker is None:
        log.append("  The trap marker is no longer present.")
        return
    trap_name = marker.get("trap_name")
    if trap_name not in TRAPS:
        log.append("  The trap can no longer be identified.")
        return
    trap = TRAPS[trap_name]
    clear_visible_trap(dungeon, center)
    log.append("  Disarm failed. The trap goes off.")
    _apply_trap_effect(
        trap,
        hero,
        dungeon,
        log,
        lambda *_: None,
        center,
        None,
        str(marker.get("trap_source", "room_or_passage")),
    )
    if raw_disarm_roll == 1:
        log.append("  Disarm blunder: 1 extra wound above the trap's normal effect.")
        apply_damage_to_hero(hero, 1, log)


def _apply_trap_effect(
    trap: TrapDefinition,
    hero,
    dungeon,
    log: List[str],
    start_wandering_combat,
    trap_location: Tuple[int, int],
    resolve_magic_spell: Optional[Callable[[object, str, Optional[Tuple[int, int]]], None]],
    source: str,
    affected_heroes: Optional[List[object]] = None,
):
    if trap.name == "Pit Trap":
        dungeon.grid[trap_location] = dungeon.TileType.PIT_TRAP
        mark_trap(dungeon, trap_location, "pit_trap", "PT", blocks_movement=True)
        _resolve_pit_fall(hero, dungeon, log)
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
        options = get_portcullis_placement_options(dungeon, trap_location)
        selected_zone = None
        game_state = getattr(dungeon, "game_state", None)
        if game_state is not None and hasattr(game_state, "consume_next_portcullis_placement"):
            selected_zone = game_state.consume_next_portcullis_placement(trap_location, options)
        zone = _get_portcullis_positions(dungeon, trap_location, selected_zone)
        center = zone[0]
        for zone_pos in zone:
            mark_trap(
                dungeon,
                zone_pos,
                "portcullis",
                "PC" if zone_pos == center else "",
                blocks_movement=True,
                trap_center=[center[0], center[1]],
                trap_zone=[[item[0], item[1]] for item in zone],
                placement_options=[
                    [[item[0], item[1]] for item in option]
                    for option in options
                ],
            )
        log.append(
            "  A portcullis slams down. Lifting it should take a full exploration turn and Strength total 20+."
        )
        return

    if trap.name == "Poison Dart":
        damage, rolls = roll_damage(1, hero.toughness, False)
        log.append(f"  Poison dart: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage > 0:
            if hero.has_fate_available():
                hero.queue_fate_decision(hero.current_wounds, source="Poison Dart")
                log.append(f"  {hero.name} would be reduced to 0 wounds by the poison and must decide whether to spend Fate.")
            else:
                hero.current_wounds = 0
                hero.is_ko = True
                log.append(f"  {hero.name} is reduced to 0 wounds and knocked out.")
        return

    if trap.name == "Blocks":
        mark_trap(
            dungeon,
            trap_location,
            "blocks",
            "BL",
            blocks_movement=False,
            careful_movement_only=True,
        )
        dodge_roll = _roll_d12()
        effective_speed = hero.get_effective_speed("exploration")
        damage_dice = 3 if dodge_roll <= effective_speed else 12
        damage, rolls = roll_damage(damage_dice, hero.toughness, False)
        log.append(
            f"  Blocks: dodge roll {dodge_roll} vs Speed {effective_speed} -> {damage_dice} damage dice, "
            f"{rolls} vs T{hero.toughness} = {damage} wounds."
        )
        if damage:
            apply_damage_to_hero(hero, damage, log)
        log.append("  The section remains hazardous and should only be crossed carefully at half speed.")
        return

    if trap.name == "Gas":
        _apply_gas_trap(hero, dungeon, log, trap_location, affected_heroes)
        return

    if trap.name == "Mantrap":
        damage, rolls = roll_damage(4, hero.toughness, False)
        log.append(f"  Mantrap: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log, source="Mantrap")
            lost = "lost_hand" if source == "chest" else "lost_leg"
            _apply_limb_loss(hero, lost, log)
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
                if hero.has_fate_available():
                    hero.queue_fate_decision(hero.current_wounds, source="Spike Poison")
                    log.append(f"  {hero.name} must decide whether to spend Fate to survive the poison.")
                else:
                    hero.current_wounds = 0
                    hero.is_ko = True
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
        if resolve_magic_spell is not None:
            resolve_magic_spell(hero, spell_name, trap_location)
        elif spell_name == "Fireball":
            damage, rolls = roll_damage(5, hero.toughness, False)
            log.append(f"  Fireball effect: {rolls} vs T{hero.toughness} = {damage} wounds.")
            if damage:
                apply_damage_to_hero(hero, damage, log)
        else:
            log.append("  Spell effect recorded; full spell implementation will share the future magic system.")
        return

    if trap.name == "Fireball":
        log.append("  Fireball trap: an immediate fireball erupts, then the magical flames linger.")
        if resolve_magic_spell is not None:
            resolve_magic_spell(hero, "Fireball", trap_location)
        else:
            damage, rolls = roll_damage(5, hero.toughness, False)
            log.append(f"  Fireball effect: {rolls} vs T{hero.toughness} = {damage} wounds.")
            if damage:
                apply_damage_to_hero(hero, damage, log, source="Fireball")
        return

    if trap.name == "Mindstealer":
        hero.add_status_effect(
            "madness",
            turns=6,
            scope="expedition",
            madness_attack_allies=True,
            gm_control_policy="gm_selectable_hostile",
            gm_orders=[],
        )
        log.append(
            "  Mindstealer: the hero is driven mad for 6 turns and will be under hostile GM control unless restrained."
        )
        return

    if trap.name == "Guillotine":
        damage, rolls = roll_damage(2, hero.toughness, False)
        log.append(f"  Guillotine: {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log, source="Guillotine")
            _apply_limb_loss(hero, "lost_hand", log)
        return

    if trap.name == "Alarm":
        log.append("  Alarm: wandering monsters are alerted and close in from as far away as line of sight allows.")
        try:
            start_wandering_combat(trap_location, "far_los")
        except TypeError:
            start_wandering_combat(trap_location)
        return

    log.append(f"  Trap {trap.name} has no resolver yet.")


def _get_gas_area_targets(hero, trap_location: Tuple[int, int], affected_heroes: Optional[List[object]]) -> List[Tuple[object, int]]:
    """Return heroes inside the AHQ gas cloud with their distance ring."""
    candidates = affected_heroes or [hero]
    targets: List[Tuple[object, int]] = []
    seen = set()
    for candidate in candidates:
        if getattr(candidate, "is_dead", False):
            continue
        candidate_id = getattr(candidate, "id", id(candidate))
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        distance = max(abs(int(candidate.x) - trap_location[0]), abs(int(candidate.y) - trap_location[1]))
        if distance <= 2:
            targets.append((candidate, distance))
    return targets


def _apply_gas_effect(hero, gas_type: str, log: List[str]):
    """Apply a resolved AHQ gas subtype to one affected hero."""
    if gas_type == "Mild Poison":
        apply_damage_to_hero(hero, 1, log, source="Gas")
        hero.add_status_effect(
            "mild_poison",
            turns=3,
            scope="expedition",
            cannot_move=True,
        )
        log.append(f"  {hero.name}: mild poison causes 1 wound and no movement for 3 turns.")
        return

    if gas_type == "Nausea":
        hero.add_status_effect(
            "nausea",
            scope="expedition",
            exploration_move_cap=8,
            combat_move_divisor=2,
            ws_divisor=2,
            bs_divisor=2,
            strength_delta=-2,
        )
        log.append(
            f"  {hero.name}: nausea caps exploration movement at 8, halves combat move/WS/BS, "
            "and gives Strength -2 for the expedition."
        )
        return

    if gas_type == "Madness":
        hero.add_status_effect(
            "madness",
            turns=6,
            scope="expedition",
            madness_attack_allies=False,
            gm_control_policy="gm_selectable_movement",
            gm_orders=[],
        )
        log.append(f"  {hero.name}: madness puts the hero under GM control for 6 turns.")
        return

    if gas_type == "Strong Poison":
        damage, rolls = roll_damage(8, hero.toughness, False)
        log.append(f"  {hero.name}: strong poison {rolls} vs T{hero.toughness} = {damage} wounds.")
        if damage:
            apply_damage_to_hero(hero, damage, log, source="Strong Poison")
        return

    if gas_type == "Deadly Poison":
        if hero.has_usable_healing_potion():
            hero.consume_healing_potion()
            hero.current_wounds = hero.max_wounds
            log.append(f"  {hero.name}: deadly poison is neutralized by a Healing Potion.")
            return
        if hero.has_fate_available():
            hero.queue_fate_decision(hero.current_wounds, source="Deadly Poison")
            log.append(f"  {hero.name}: deadly poison requires a Fate decision without a Healing Potion.")
        else:
            hero.is_dead = True
            hero.is_ko = True
            hero.current_wounds = 0
            log.append(f"  {hero.name}: deadly poison kills them without a Healing Potion.")
        return


def _apply_gas_trap(hero, dungeon, log: List[str], trap_location: Tuple[int, int], affected_heroes: Optional[List[object]] = None):
    targets = _get_gas_area_targets(hero, trap_location, affected_heroes)
    if not targets:
        log.append("  Gas trap: no living heroes are inside the gas cloud.")
        return

    affected = []
    for target, ring in targets:
        resistance_roll = _roll_d12()
        modifier = 0 if ring == 0 else -ring
        adjusted_roll = resistance_roll + modifier
        starting_toughness = int(getattr(target, "toughness", 1))
        zone_label = "centre" if ring == 0 else ("adjacent ring" if ring == 1 else "outer ring")
        modifier_note = "" if modifier == 0 else f" {modifier:+d}"
        if adjusted_roll <= starting_toughness:
            log.append(
                f"  Gas resistance: {target.name} in the {zone_label} rolls {resistance_roll}{modifier_note} "
                f"= {adjusted_roll} <= starting T{starting_toughness}; no effect."
            )
            continue
        log.append(
            f"  Gas resistance: {target.name} in the {zone_label} rolls {resistance_roll}{modifier_note} "
            f"= {adjusted_roll} > starting T{starting_toughness}; affected."
        )
        affected.append(target)

    if not affected:
        log.append("  Gas trap: everyone in the cloud resists the gas.")
        return

    gas_roll = _roll_d12()
    gas_type = _lookup_table(gas_roll, GAS_EFFECTS)
    log.append(f"  Gas trap: effect roll {gas_roll} -> {gas_type}.")

    for target in affected:
        _apply_gas_effect(target, gas_type, log)


def _find_adjacent_clear_tile(hero, dungeon) -> Optional[Tuple[int, int]]:
    """Return a nearby walkable square a hero can climb into from a pit."""
    for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
        target = (hero.x + dx, hero.y + dy)
        if dungeon.is_walkable(*target):
            return target
    return None


def _resolve_pit_fall(hero, dungeon, log: List[str]):
    """Apply the wound/climb sequence for a pit trap."""
    fall_roll = _roll_d12()
    log.append(f"  Pit trap: fall roll {fall_roll}.")
    if fall_roll >= 9:
        apply_damage_to_hero(hero, 1, log)

    climb_roll = _roll_d12()
    effective_speed = hero.get_effective_speed("exploration")
    escape_tile = _find_adjacent_clear_tile(hero, dungeon)
    if climb_roll <= effective_speed:
        if escape_tile is not None:
            hero.x, hero.y = escape_tile
            log.append(
                f"  Climb-out roll {climb_roll} <= Speed {effective_speed}: {hero.name} scrambles clear to {escape_tile}."
            )
        else:
            log.append(
                f"  Climb-out roll {climb_roll} <= Speed {effective_speed}, but there is no clear square to climb into."
            )
    else:
        if escape_tile is not None and hero.has_fate_available():
            hero.queue_failed_roll_fate_decision(
                "pit_climb",
                roll=climb_roll,
                escape_tile=[escape_tile[0], escape_tile[1]],
            )
            log.append(
                f"  Climb-out roll {climb_roll} > Speed {effective_speed}: {hero.name} may spend Fate to scramble clear."
            )
            return
        log.append(
            f"  Climb-out roll {climb_roll} > Speed {effective_speed}: {hero.name} remains in the pit for now."
        )


def resolve_pit_fall(hero, dungeon, log: List[str]):
    """Public wrapper for pit-fall resolution used by later Fate outcomes."""
    _resolve_pit_fall(hero, dungeon, log)


def resolve_pit_leap(hero, dungeon, log: List[str], pit_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
    """Attempt to leap over a visible pit trap."""
    dx = pit_pos[0] - hero.x
    dy = pit_pos[1] - hero.y
    if abs(dx) + abs(dy) != 1:
        log.append("  You must stand next to the pit to leap it.")
        return None

    landing = (pit_pos[0] + dx, pit_pos[1] + dy)
    if not dungeon.is_walkable(*landing):
        log.append(f"  There is no safe landing square beyond the pit at {landing}.")
        return None

    leap_roll = _roll_d12()
    effective_speed = hero.get_effective_speed("exploration")
    if leap_roll <= effective_speed:
        hero.x, hero.y = landing
        log.append(
            f"  Pit leap roll {leap_roll} <= Speed {effective_speed}: {hero.name} clears the pit and lands at {landing}."
        )
        return landing

    if hero.has_fate_available():
        hero.queue_failed_roll_fate_decision(
            "pit_leap",
            pit=[pit_pos[0], pit_pos[1]],
            landing=[landing[0], landing[1]],
            roll=leap_roll,
        )
        log.append(
            f"  Pit leap roll {leap_roll} > Speed {effective_speed}: {hero.name} may spend Fate to turn the failed leap into a success."
        )
        return (hero.x, hero.y)

    hero.x, hero.y = pit_pos
    log.append(
        f"  Pit leap roll {leap_roll} > Speed {effective_speed}: {hero.name} falls into the pit at {pit_pos}."
    )
    _resolve_pit_fall(hero, dungeon, log)
    return (hero.x, hero.y)


__all__ = [
    "TrapDefinition",
    "TRAPS",
    "get_pit_leap_destination",
    "get_portcullis_placement_options",
    "get_trap_marker",
    "mark_trap",
    "resolve_failed_disarm_outcome",
    "resolve_pit_fall",
    "roll_random_trap",
    "resolve_pit_leap",
    "resolve_trap_event",
]

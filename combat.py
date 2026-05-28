"""
Combat resolution engine for Advanced HeroQuest.
"""

import random
from typing import Callable, Tuple, Optional, List
from hero import Hero
from monster import Monster


# Hit Roll Table: attacker WS vs defender WS
# Returns the minimum roll needed to hit on D12
HIT_ROLL_TABLE = [
    # Def WS:  1   2   3   4   5   6   7   8   9  10  11  12
    [7,   8,  9, 10, 10, 10, 10, 10, 10, 10, 10, 10],  # Att WS 1
    [6,   7,  8,  9, 10, 10, 10, 10, 10, 10, 10, 10],  # Att WS 2
    [5,   6,  7,  8,  9, 10, 10, 10, 10, 10, 10, 10],  # Att WS 3
    [4,   5,  6,  7,  8,  9, 10, 10, 10, 10, 10, 10],  # Att WS 4
    [3,   4,  5,  6,  7,  8,  9, 10, 10, 10, 10, 10],  # Att WS 5
    [2,   3,  4,  5,  6,  7,  8,  9, 10, 10, 10, 10],  # Att WS 6
    [2,   2,  3,  4,  5,  6,  7,  8,  9, 10, 10, 10],  # Att WS 7
    [2,   2,  2,  3,  4,  5,  6,  7,  8,  9, 10, 10],  # Att WS 8
    [2,   2,  2,  2,  3,  4,  5,  6,  7,  8,  9, 10],  # Att WS 9
    [2,   2,  2,  2,  2,  3,  4,  5,  6,  7,  8,  9],  # Att WS 10
    [2,   2,  2,  2,  2,  2,  3,  4,  5,  6,  7,  8],  # Att WS 11
    [2,   2,  2,  2,  2,  2,  2,  3,  4,  5,  6,  7],  # Att WS 12
]


def roll_d(sides: int = 12) -> int:
    """Roll a die with given sides."""
    return random.randint(1, sides)


def get_model_occupied_tiles(model) -> set[Tuple[int, int]]:
    """Return occupied board tiles for heroes and footprint-aware monsters."""
    if isinstance(model, Monster):
        return set(model.get_occupied_tiles())
    return {(model.x, model.y)}


def get_fireball_template_area(x: int, y: int) -> List[Tuple[int, int]]:
    """Return the grid squares covered by the AHQ fireball template."""
    return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def get_ranged_los_state_for_models(
    dungeon,
    attacker,
    target,
    friendly_models: List,
    hostile_models: List,
    attacker_tiles: Optional[List[Tuple[int, int]]] = None,
    target_tiles: Optional[List[Tuple[int, int]]] = None,
) -> Tuple[str, Tuple[int, int], Tuple[int, int]]:
    """Evaluate ranged LOS, including large-monster footprint exceptions."""
    origin_tiles = set(attacker_tiles or get_model_occupied_tiles(attacker))
    destination_tiles = set(target_tiles or get_model_occupied_tiles(target))
    large_endpoint = (
        isinstance(attacker, Monster) and attacker.is_large_monster()
    ) or (
        isinstance(target, Monster) and target.is_large_monster()
    )

    blocker_tiles: set[Tuple[int, int]] = set()
    friendly_blocker_tiles: set[Tuple[int, int]] = set()
    for models, friendly in ((friendly_models, True), (hostile_models, False)):
        for model in models:
            if model is attacker or model is target or getattr(model, "is_dead", False):
                continue
            if large_endpoint and not (isinstance(model, Monster) and model.is_large_monster()):
                continue
            tiles = get_model_occupied_tiles(model) - origin_tiles - destination_tiles
            blocker_tiles.update(tiles)
            if friendly:
                friendly_blocker_tiles.update(tiles)

    best: Optional[Tuple[str, Tuple[int, int], Tuple[int, int]]] = None
    rank = {"clear": 0, "partial": 1, "blocked": 2}
    for origin_x, origin_y in sorted(origin_tiles):
        adjacent_friendly = {
            pos for pos in friendly_blocker_tiles
            if abs(pos[0] - origin_x) + abs(pos[1] - origin_y) == 1
        }
        for target_x, target_y in sorted(destination_tiles):
            state = dungeon.get_los_state(
                origin_x,
                origin_y,
                target_x,
                target_y,
                model_blockers=blocker_tiles,
                adjacent_friendly_blockers=adjacent_friendly,
            )
            result = (state, (origin_x, origin_y), (target_x, target_y))
            if best is None or rank[state] < rank[best[0]]:
                best = result
            if state == "clear":
                return result
    return best or ("blocked", (attacker.x, attacker.y), (target.x, target.y))


def get_hit_roll_needed(att_ws: int, def_ws: int) -> int:
    """Get the minimum D12 roll needed to hit."""
    att_idx = max(0, min(11, att_ws - 1))
    def_idx = max(0, min(11, def_ws - 1))
    return HIT_ROLL_TABLE[att_idx][def_idx]


def resolve_melee_attack(
    attacker: Hero,
    defender: Monster,
    log: Optional[List[str]] = None,
    allow_free_attack: bool = True,
    is_free_attack: bool = False,
) -> Tuple[bool, int, str]:
    """
    Resolve a melee attack.
    
    Returns:
        (hit: bool, damage: int, message: str)
    """
    messages = []
    
    # Get hit roll needed
    hit_needed = get_hit_roll_needed(attacker.get_effective_ws(), defender.ws)
    
    # Roll to hit
    hit_roll = roll_d(12)
    critical_threshold = attacker.get_weapon_critical()
    fumble_threshold = attacker.get_weapon_fumble()
    
    # Check critical/fumble
    is_critical = hit_roll >= critical_threshold
    is_fumble = hit_roll <= fumble_threshold
    
    # Log attack immediately
    if log is not None:
        log.append(f"{attacker.name} attacks {defender.name}: rolled {hit_roll} (need {hit_needed}+)")
    
    if is_fumble:
        if log is not None:
            log.append(f"  FUMBLE! {defender.name} gets a free attack!")
        if allow_free_attack:
            resolve_monster_attack(defender, attacker, log, allow_free_attack=True, attack_name="free attack")
        return False, 0, "fumble"
    
    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append(f"  Miss!")
        return False, 0, "miss"
    
    # Hit! Roll for damage
    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")
    
    flaming_hand = attacker.get_status_effect("flaming_hand_of_destruction")
    if flaming_hand is not None:
        roll = roll_d(12)
        damage = roll
        rolls = [roll]
        if log is not None:
            log.append(f"  Flaming Hand of Destruction: automatic {damage} wounds from one D12 roll.")
    else:
        damage_dice = attacker.get_damage_dice() + attacker.get_bonus_melee_damage_dice()
        damage, rolls = roll_damage(damage_dice, defender.toughness, is_critical)
        weapon = attacker.get_equipped_melee_weapon() or {}
        weapon_name = str(weapon.get("name", "")).lower()
        magical_weapon = "magic" in weapon_name or "rune" in weapon_name or "chaos" in weapon_name
        if defender.has_special_rule("invulnerable") and 12 not in rolls and not magical_weapon and not is_free_attack:
            damage = 0

    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{defender.toughness} = {damage} wounds")
    
    # Apply damage
    died = defender.take_damage(damage)
    if died:
        if log is not None:
            log.append(f"  {defender.name} is killed! (+{defender.pv} PV)")
    
    return True, damage, "critical" if is_critical else "hit"


def resolve_hero_vs_hero_attack(
    attacker: Hero,
    defender: Hero,
    log: Optional[List[str]] = None,
    allow_free_attack: bool = True,
) -> Tuple[bool, int, str]:
    """Resolve a melee attack from one hero against another."""
    hit_needed = get_hit_roll_needed(attacker.get_effective_ws(), defender.get_effective_ws())
    hit_roll = roll_d(12)
    critical_threshold = attacker.get_weapon_critical()
    fumble_threshold = attacker.get_weapon_fumble()

    is_critical = hit_roll >= critical_threshold
    is_fumble = hit_roll <= fumble_threshold

    if log is not None:
        log.append(f"{attacker.name} attacks {defender.name}: rolled {hit_roll} (need {hit_needed}+)")

    if is_fumble:
        if log is not None:
            log.append(f"  FUMBLE! {defender.name} gets a free attack!")
        if allow_free_attack:
            resolve_hero_vs_hero_attack(defender, attacker, log, allow_free_attack=True)
        return False, 0, "fumble"

    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append("  Miss!")
        return False, 0, "miss"

    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")

    damage_dice = attacker.get_damage_dice() + attacker.get_bonus_melee_damage_dice()
    damage, rolls = roll_damage(damage_dice, defender.get_effective_toughness(), is_critical)
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{defender.get_effective_toughness()} = {damage} wounds")

    hero_ko = apply_damage_to_hero(defender, damage, log, allow_fate=False, source="Madness")
    if hero_ko and log is not None and defender.is_dead:
        log.append(f"  {defender.name} has DIED!")
    return True, damage, "critical" if is_critical else "hit"


def resolve_monster_attack(
    attacker: Monster,
    defender: Hero,
    log: Optional[List[str]] = None,
    damage_dice: Optional[int] = None,
    attack_name: str = "attacks",
    allow_free_attack: bool = True,
    attack_index: int = 0,
    monster_fate_roll: Optional[Callable[[Monster, str, int, int], bool]] = None,
) -> Tuple[bool, int, bool]:
    """
    Resolve a monster melee attack.
    
    Returns:
        (hit: bool, damage: int, hero_died_or_ko: bool)
    """
    # Get hit roll needed
    defender_ws = 1 if defender.is_ko else defender.get_effective_ws()
    hit_needed = get_hit_roll_needed(attacker.ws, defender_ws)
    
    # Roll to hit
    hit_roll = roll_d(12)
    critical_threshold = attacker.get_attack_critical_threshold(attack_index)
    fumble_threshold = attacker.get_attack_fumble_threshold(attack_index)
    
    is_critical = hit_roll >= critical_threshold
    is_fumble = hit_roll <= fumble_threshold
    
    # Log attack immediately
    if log is not None:
        log.append(f"{attacker.name} {attack_name} {defender.name}: rolled {hit_roll} (need {hit_needed}+)")

    failed_hit_roll = is_fumble or (hit_roll < hit_needed and not is_critical)
    if failed_hit_roll and monster_fate_roll is not None:
        if monster_fate_roll(attacker, f"{attack_name} hit roll", hit_roll, hit_needed):
            hit_roll = hit_needed
            is_fumble = False
            is_critical = False
    
    if is_fumble:
        if log is not None:
            log.append(f"  FUMBLE! {defender.name} gets a free attack!")
        if allow_free_attack:
            resolve_melee_attack(defender, attacker, log, allow_free_attack=True, is_free_attack=True)
        return False, 0, False
    
    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append(f"  Miss!")
        return False, 0, False
    
    # Hit!
    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")
    
    # Roll damage
    attack_damage_dice = damage_dice if damage_dice is not None else attacker.get_attack_damage_dice(attack_index)
    toughness = defender.get_effective_toughness()
    damage, rolls = roll_damage(attack_damage_dice, toughness, is_critical)
    
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{toughness} = {damage} wounds")
    
    hero_ko = apply_damage_to_hero(defender, damage, log)
    if hit_roll >= hit_needed and attacker.has_special_rule("cause_disease") and not defender.is_dead:
        disease_roll = roll_d(12)
        disease_succeeds = disease_roll >= defender.toughness
        if not disease_succeeds and monster_fate_roll is not None:
            disease_succeeds = monster_fate_roll(
                attacker,
                "disease roll",
                disease_roll,
                defender.toughness,
            )
        if disease_succeeds:
            defender.add_status_effect("diseased", scope="campaign")
            if log is not None:
                log.append(
                    f"  Disease takes root! {defender.name} is diseased ({disease_roll} vs starting T{defender.toughness})."
                )
        elif log is not None:
            log.append(f"  Disease roll {disease_roll} vs starting T{defender.toughness}: resisted.")
    return True, damage, hero_ko


def resolve_monster_ranged_attack(
    attacker: Monster,
    defender: Hero,
    log: Optional[List[str]] = None,
    partial_obscured: bool = False,
    fumble_target: Optional[Monster] = None,
    monster_fate_roll: Optional[Callable[[Monster, str, int, int], bool]] = None,
) -> Tuple[bool, int, bool]:
    """
    Resolve a monster ranged attack.

    Uses the monster's ranged profile for damage and BS for the attack roll.
    """
    ranged_profile = attacker.ranged or {}
    hit_needed = get_hit_roll_needed(max(attacker.bs, 1), max(defender.get_effective_bs(), 1))
    hit_roll = roll_d(12)
    critical_threshold = ranged_profile.get("critical", 12)
    fumble_threshold = ranged_profile.get("fumble", 1)

    is_critical = hit_roll >= critical_threshold
    is_fumble = hit_roll <= fumble_threshold

    attack_name = ranged_profile.get("name", "ranged attack")
    if log is not None:
        log.append(f"{attacker.name} uses {attack_name} on {defender.name}: rolled {hit_roll} (need {hit_needed}+)")
        if partial_obscured:
            log.append("  Target is partially obscured.")

    failed_hit_roll = is_fumble or (hit_roll < hit_needed and not is_critical)
    if failed_hit_roll and monster_fate_roll is not None:
        if monster_fate_roll(attacker, f"{attack_name} hit roll", hit_roll, hit_needed):
            hit_roll = hit_needed
            is_fumble = False
            is_critical = False

    if is_fumble:
        if fumble_target is not None:
            toughness = fumble_target.toughness
            damage, rolls = roll_damage(ranged_profile.get("damage_dice", 1), toughness, False)
            if log is not None:
                log.append(f"  FUMBLE! {attacker.name} hits {fumble_target.name} instead.")
                log.append(f"  Damage roll: {rolls} vs T{toughness} = {damage} wounds")
                if damage and fumble_target.take_damage(damage):
                    log.append(f"  {fumble_target.name} is killed! (+{fumble_target.pv} PV)")
            return False, damage, False
        if log is not None:
            log.append("  Miss!")
        return False, 0, False

    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append("  Miss!")
        return False, 0, False

    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")

    toughness = defender.get_effective_toughness()
    if is_critical:
        toughness = max(1, (toughness + 1) // 2)
    damage, rolls = roll_damage(ranged_profile.get("damage_dice", 1), toughness, is_critical)
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{toughness} = {damage} wounds")

    hero_ko = apply_damage_to_hero(defender, damage, log)
    return True, damage, hero_ko


def resolve_hero_ranged_attack(
    attacker: Hero,
    defender: Monster,
    log: Optional[List[str]] = None,
    partial_obscured: bool = False,
    fumble_target: Optional[Hero] = None,
    magic_ammo_effect: Optional[str] = None,
) -> Tuple[bool, int, str]:
    """
    Resolve a hero ranged attack.

    Uses the hero's BS against the monster's BS, mirroring the existing
    monster ranged resolution.
    """
    weapon = attacker.get_equipped_ranged_weapon() or {}
    weapon_name = weapon.get("name", "ranged weapon")
    hit_needed = get_hit_roll_needed(max(attacker.get_effective_bs(), 1), max(defender.bs, 1))
    hit_roll = roll_d(12)
    magic_ammo_effect = (magic_ammo_effect or "").strip().lower() or None
    critical_threshold = attacker.get_ranged_critical()
    fumble_threshold = attacker.get_ranged_fumble()

    always_hits = magic_ammo_effect == "true_flight"
    is_critical = (hit_roll >= critical_threshold) and not always_hits
    is_fumble = (hit_roll <= fumble_threshold) and not always_hits

    if log is not None:
        if always_hits:
            log.append(f"{attacker.name} shoots {weapon_name} at {defender.name} with true-flight ammunition.")
        else:
            log.append(
                f"{attacker.name} shoots {weapon_name} at {defender.name}: rolled {hit_roll} (need {hit_needed}+)"
            )
        if partial_obscured:
            log.append("  Target is partially obscured.")

    if is_fumble:
        if fumble_target is not None:
            toughness = fumble_target.get_effective_toughness()
            damage, rolls = roll_damage(attacker.get_ranged_damage_dice(), toughness, False)
            if log is not None:
                log.append(f"  FUMBLE! {attacker.name} hits {fumble_target.name} instead.")
                log.append(f"  Damage roll: {rolls} vs T{toughness} = {damage} wounds")
            if damage:
                apply_damage_to_hero(fumble_target, damage, log)
            return False, damage, "fumble_ally"
        if log is not None:
            log.append("  Miss!")
        return False, 0, "fumble"

    if hit_roll < hit_needed and not is_critical and not always_hits:
        if log is not None:
            log.append("  Miss!")
        return False, 0, "miss"

    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")

    toughness = defender.toughness
    if is_critical:
        toughness = max(1, (toughness + 1) // 2)
    damage_dice = attacker.get_ranged_damage_dice()
    if magic_ammo_effect == "death":
        damage_dice += 1
    if magic_ammo_effect == "assassin":
        damage, rolls = _roll_assassin_ammo_damage(damage_dice, toughness)
    else:
        damage, rolls = roll_damage(damage_dice, toughness, is_critical)
    weapon = attacker.get_equipped_ranged_weapon() or {}
    weapon_name = str(weapon.get("name", "")).lower()
    magical_weapon = bool(magic_ammo_effect) or "magic" in weapon_name or "rune" in weapon_name or "chaos" in weapon_name
    if defender.has_special_rule("invulnerable") and 12 not in rolls and not magical_weapon:
        damage = 0
    if log is not None:
        if magic_ammo_effect == "death":
            log.append("  Arrows/Bolts of Death add +1 damage die.")
        elif magic_ammo_effect == "assassin":
            log.append("  Assassin ammunition causes critical damage on damage rolls of 10+.")
        log.append(f"  Damage roll: {rolls} vs T{toughness} = {damage} wounds")

    died = defender.take_damage(damage)
    if died and log is not None:
        log.append(f"  {defender.name} is killed! (+{defender.pv} PV)")

    return True, damage, "critical" if is_critical else "hit"


def _roll_assassin_ammo_damage(dice: int, toughness: int) -> Tuple[int, List[int]]:
    """Roll damage where every 10+ damage roll generates critical follow-up dice."""
    wounds = 0
    rolls: List[int] = []
    dice_to_roll = dice
    while dice_to_roll > 0:
        extra_dice = 0
        for _ in range(dice_to_roll):
            roll = roll_d(12)
            rolls.append(roll)
            if roll >= toughness:
                wounds += 1
            if roll >= 10:
                extra_dice += 1
        dice_to_roll = extra_dice
    return wounds, rolls


def apply_damage_to_hero(
    defender: Hero,
    damage: int,
    log: Optional[List[str]] = None,
    *,
    allow_fate: bool = True,
    source: str = "attack",
) -> bool:
    """Apply damage to a hero, queueing Fate decisions for turn damage when allowed."""
    if damage <= 0:
        return False
    defender.record_turn_damage(damage)
    if allow_fate and defender.current_wounds - damage <= 0 and defender.has_fate_available():
        defender.queue_fate_decision(defender.damage_taken_this_turn, source=source)
        if log is not None:
            log.append(f"  {defender.name} would be slain and may spend a Fate Point to negate all damage suffered this turn.")
        return True

    hero_ko = defender.take_damage(damage)
    if hero_ko:
        if defender.is_dead:
            if log is not None:
                log.append(f"  {defender.name} has DIED!")
        else:
            if log is not None:
                log.append(f"  {defender.name} is knocked out!")
    return hero_ko


def roll_damage(dice: int, toughness: int, is_critical: bool = False) -> tuple:
    """
    Roll damage dice against toughness.
    Each die that rolls >= toughness = 1 wound.
    Critical hits: roll extra dice and add (reroll 12s).
    
    Returns:
        (wounds: int, rolls: List[int]) - total wounds and individual rolls
    """
    wounds = 0
    rolls = []
    dice_to_roll = dice
    
    while dice_to_roll > 0:
        extra_dice = 0
        for _ in range(dice_to_roll):
            roll = roll_d(12)
            rolls.append(roll)
            if roll >= toughness:
                wounds += 1
            if is_critical and roll == 12:
                extra_dice += 1
        
        if not is_critical:
            break
        dice_to_roll = extra_dice
    
    return wounds, rolls


def resolve_spell_damage(dice: int, toughness: int) -> tuple:
    """Resolve spell damage against a Toughness value."""
    return roll_damage(dice, toughness, False)


def do_surprise_roll(has_elf: bool = False, has_sentry: bool = False) -> Tuple[str, int, int]:
    """
    Do surprise roll at start of combat.
    
    Returns:
        (winner: str "heroes" or "gm", hero_roll: int, gm_roll: int)
    """
    hero_roll = roll_d(12)
    gm_roll = roll_d(12)
    
    if has_elf:
        hero_roll += 1
    if has_sentry:
        gm_roll += 1
    
    # Cap at 12
    hero_roll = min(12, hero_roll)
    gm_roll = min(12, gm_roll)
    
    if hero_roll >= gm_roll:
        return "heroes", hero_roll, gm_roll
    else:
        return "gm", hero_roll, gm_roll


def find_target_hero(heroes: List[Hero], monsters: List[Monster]) -> Optional[Hero]:
    """
    Find the target hero for monsters to attack.
    Priority: lowest WS, then lowest T, then random.
    Only target living, non-KO heroes.
    """
    valid_targets = [h for h in heroes if not h.is_dead and not h.is_ko and h.current_wounds > 0]
    
    if not valid_targets:
        return None
    
    # Sort by WS (ascending), then by T (ascending)
    valid_targets.sort(key=lambda h: (h.get_effective_ws(), h.toughness))
    
    return valid_targets[0]


class CombatResult:
    """Result of a combat action."""
    
    def __init__(self, hit: bool, damage: int, killed: bool = False, 
                 critical: bool = False, fumble: bool = False, fate_spent: bool = False):
        self.hit = hit
        self.damage = damage
        self.killed = killed
        self.critical = critical
        self.fumble = fumble
        self.fate_spent = fate_spent

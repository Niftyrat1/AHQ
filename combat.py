"""
Combat resolution engine for Advanced HeroQuest.
"""

import random
from typing import Tuple, Optional, List
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
            resolve_monster_attack(defender, attacker, log, allow_free_attack=False, attack_name="free attack")
        return False, 0, "fumble"
    
    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append(f"  Miss!")
        return False, 0, "miss"
    
    # Hit! Roll for damage
    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")
    
    damage_dice = attacker.get_damage_dice() + attacker.get_bonus_melee_damage_dice()
    damage, rolls = roll_damage(damage_dice, defender.toughness, is_critical)
    
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{defender.toughness} = {damage} wounds")
    
    # Apply damage
    died = defender.take_damage(damage)
    if died:
        if log is not None:
            log.append(f"  {defender.name} is killed! (+{defender.pv} PV)")
    
    return True, damage, "critical" if is_critical else "hit"


def resolve_monster_attack(
    attacker: Monster,
    defender: Hero,
    log: Optional[List[str]] = None,
    damage_dice: Optional[int] = None,
    attack_name: str = "attacks",
    allow_free_attack: bool = True,
) -> Tuple[bool, int, bool]:
    """
    Resolve a monster melee attack.
    
    Returns:
        (hit: bool, damage: int, hero_died_or_ko: bool)
    """
    # Get hit roll needed
    hit_needed = get_hit_roll_needed(attacker.ws, defender.get_effective_ws())
    
    # Roll to hit
    hit_roll = roll_d(12)
    critical_threshold = attacker.get_critical_threshold()
    fumble_threshold = attacker.get_fumble_threshold()
    
    is_critical = hit_roll >= critical_threshold
    is_fumble = hit_roll <= fumble_threshold
    
    # Log attack immediately
    if log is not None:
        log.append(f"{attacker.name} {attack_name} {defender.name}: rolled {hit_roll} (need {hit_needed}+)")
    
    if is_fumble:
        if log is not None:
            log.append(f"  FUMBLE! {defender.name} gets a free attack!")
        if allow_free_attack:
            resolve_melee_attack(defender, attacker, log, allow_free_attack=False)
        return False, 0, False
    
    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append(f"  Miss!")
        return False, 0, False
    
    # Hit!
    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")
    
    # Roll damage
    attack_damage_dice = damage_dice if damage_dice is not None else attacker.get_damage_dice()
    damage, rolls = roll_damage(attack_damage_dice, defender.toughness, is_critical)
    
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{defender.toughness} = {damage} wounds")
    
    hero_ko = apply_damage_to_hero(defender, damage, log)
    return True, damage, hero_ko


def resolve_monster_ranged_attack(
    attacker: Monster,
    defender: Hero,
    log: Optional[List[str]] = None
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

    if is_fumble:
        if log is not None:
            log.append("  Miss!")
        return False, 0, False

    if hit_roll < hit_needed and not is_critical:
        if log is not None:
            log.append("  Miss!")
        return False, 0, False

    if log is not None:
        log.append(f"  Hit!{(' CRITICAL!' if is_critical else '')}")

    damage, rolls = roll_damage(ranged_profile.get("damage_dice", 1), defender.toughness, is_critical)
    if log is not None:
        log.append(f"  Damage roll: {rolls} vs T{defender.toughness} = {damage} wounds")

    hero_ko = apply_damage_to_hero(defender, damage, log)
    return True, damage, hero_ko


def apply_damage_to_hero(defender: Hero, damage: int, log: Optional[List[str]] = None) -> bool:
    """Apply damage to a hero, including automatic fate use."""
    hero_ko = False
    if defender.current_wounds - damage <= 0 and defender.current_fate > 0:
        if log is not None:
            log.append(f"  {defender.name} spends a Fate Point to survive!")
        defender.spend_fate()
        return False

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

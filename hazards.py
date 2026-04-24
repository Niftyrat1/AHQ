"""AHQ hazard tables, room metadata helpers, and core room interactions."""

import random
from typing import Dict, List, Optional, Tuple


HAZARD_TABLE = (
    (1, 1, "wandering_monster"),
    (2, 2, "non_player_character"),
    (3, 3, "chasm"),
    (4, 4, "statue"),
    (5, 5, "rats_or_bats"),
    (6, 6, "mould"),
    (7, 7, "mushrooms"),
    (8, 8, "grate"),
    (9, 9, "pool"),
    (10, 10, "magic_circle"),
    (11, 11, "trapdoor"),
    (12, 12, "throne"),
)

NPC_TABLE = (
    (1, 3, "maiden"),
    (4, 6, "witch"),
    (7, 9, "man_at_arms"),
    (10, 12, "rogue"),
)

HAZARD_LABELS = {
    "wandering_monster": "Wandering Monsters",
    "non_player_character": "Non-Player Character",
    "chasm": "Chasm",
    "statue": "Statue",
    "rats": "Rats",
    "bats": "Bats",
    "mould": "Mould",
    "mushrooms": "Filz Mushrooms",
    "grate": "Grate",
    "pool": "Pool",
    "magic_circle": "Magic Circle",
    "trapdoor": "Trapdoor",
    "throne": "Throne",
}

HAZARD_SYMBOLS = {
    "wandering_monster": "WM",
    "non_player_character": "NPC",
    "chasm": "CH",
    "statue": "ST",
    "rats": "RT",
    "bats": "BT",
    "mould": "MO",
    "mushrooms": "MU",
    "grate": "GR",
    "pool": "PL",
    "magic_circle": "MC",
    "trapdoor": "TD",
    "throne": "TH",
}

HAZARD_COLORS = {
    "wandering_monster": "#6a4a4a",
    "non_player_character": "#5a4a6a",
    "chasm": "#3a2a2a",
    "statue": "#5a5a62",
    "rats": "#5a4a3a",
    "bats": "#4a3a5a",
    "mould": "#3f5a3f",
    "mushrooms": "#5a3f5a",
    "grate": "#4a4f5a",
    "pool": "#2f5664",
    "magic_circle": "#6a4f2f",
    "trapdoor": "#6b4a2b",
    "throne": "#6a5530",
}


def _roll_d12() -> int:
    return random.randint(1, 12)


def _lookup_table(roll: int, table) -> str:
    for low, high, result in table:
        if low <= roll <= high:
            return result
    raise ValueError(f"Roll {roll} did not match table")


def roll_hazard_room() -> Dict[str, object]:
    """Roll a hazard-room result from the AHQ hazard table."""
    hazard_roll = _roll_d12()
    hazard_type = _lookup_table(hazard_roll, HAZARD_TABLE)
    hazard_data: Dict[str, object] = {
        "roll": hazard_roll,
        "type": hazard_type,
        "revealed": False,
        "resolved": False,
    }

    if hazard_type == "rats_or_bats":
        beast_roll = _roll_d12()
        hazard_data["subroll"] = beast_roll
        hazard_data["type"] = "rats" if beast_roll % 2 == 0 else "bats"
        return hazard_data

    if hazard_type == "non_player_character":
        npc_roll = _roll_d12()
        hazard_data["subroll"] = npc_roll
        hazard_data["npc_type"] = _lookup_table(npc_roll, NPC_TABLE)
        return hazard_data

    return hazard_data


def describe_hazard(hazard: Optional[Dict[str, object]]) -> str:
    """Return a short player-facing description for a hazard room."""
    if not hazard:
        return "Unknown hazard"

    hazard_type = str(hazard.get("type", "unknown"))
    label = HAZARD_LABELS.get(hazard_type, hazard_type.replace("_", " ").title())

    if hazard_type == "non_player_character":
        npc_type = str(hazard.get("npc_type", "character")).replace("_", " ")
        return f"{label}: {npc_type.title()}"

    return label


def get_hazard_symbol(hazard: Optional[Dict[str, object]]) -> str:
    """Return a short map symbol for a hazard room."""
    if not hazard:
        return "HZ"
    hazard_type = str(hazard.get("type", "unknown"))
    return HAZARD_SYMBOLS.get(hazard_type, "HZ")


def get_hazard_color(hazard: Optional[Dict[str, object]]) -> str:
    """Return a representative floor tint for a hazard room."""
    if not hazard:
        return "#5a4a55"
    hazard_type = str(hazard.get("type", "unknown"))
    return HAZARD_COLORS.get(hazard_type, "#5a4a55")


def hazard_blocks_movement(hazard: Optional[Dict[str, object]]) -> bool:
    """Whether the hazard should occupy and block its anchor square."""
    if not hazard:
        return False
    return str(hazard.get("type")) in {"statue", "chasm"}


def get_room_for_hero(hero, dungeon) -> Optional[Dict[str, object]]:
    """Return the room containing the hero, if any."""
    return dungeon.find_room_for_tile(hero.x, hero.y)


def get_hazard_anchor(room: Optional[Dict[str, object]]) -> Optional[Tuple[int, int]]:
    """Return the anchor square for a hazard room."""
    if not room:
        return None
    anchor = room.get("hazard_anchor")
    if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
        return int(anchor[0]), int(anchor[1])
    return None


def is_adjacent_or_same(hero, pos: Optional[Tuple[int, int]], dungeon) -> bool:
    """Whether the hero is on or next to a target square."""
    if pos is None:
        return False
    return (hero.x, hero.y) == pos or dungeon.is_adjacent(hero.x, hero.y, pos[0], pos[1])


def resolve_hazard_reveal(room, game) -> Optional[str]:
    """Resolve any immediate effect when a hazard room is first revealed."""
    hazard = room.get("hazard") or {}
    if hazard.get("entry_resolved"):
        return None

    hazard_type = str(hazard.get("type"))
    hazard["entry_resolved"] = True

    if hazard_type == "wandering_monster":
        monster_ids = game.roll_wandering_monsters()
        game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: wandering monsters")
        hazard["resolved"] = True
        return "Wandering monster hazard: monsters are lurking in the room."

    if hazard_type == "non_player_character":
        npc_type = str(hazard.get("npc_type", "character"))
        if npc_type == "maiden":
            monster_ids = game.roll_wandering_monsters()
            game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: maiden and guards")
            return "Non-player character hazard: a Maiden is held captive by guards."
        if npc_type == "witch":
            witch = game.create_hazard_npc("witch")
            anchor = get_hazard_anchor(room)
            if anchor is not None:
                witch.x, witch.y = anchor
            setattr(witch, "witch_escape_pending", True)
            setattr(witch, "witch_room_id", room.get("id"))
            game._start_combat_with_monsters_configured(
                [witch],
                summary_prefix="Hazard room: witch",
            )
            return "Non-player character hazard: a Witch has 1 combat round before she teleports away."
        if npc_type == "man_at_arms":
            monster_ids = game.roll_wandering_monsters()
            game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: man-at-arms and guards")
            return "Non-player character hazard: a Man-at-Arms is imprisoned by guards."
        if npc_type == "rogue":
            hazard["recruit_available"] = True
            hazard["resolved"] = True
            return "Non-player character hazard: a Rogue offers to travel with the party."
        return f"Non-player character hazard: {npc_type.replace('_', ' ').title()}."

    if hazard_type == "chasm":
        if not hazard.get("entry_setup_done"):
            hazard["entry_setup_done"] = True
            monster_ids = game.roll_wandering_monsters()
            game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: chasm guardians")
            chest_pos = game.place_hazard_chest(room)
            if chest_pos is not None:
                hazard["chest_pos"] = list(chest_pos)
        return "Chasm hazard: monsters guard the far side and a chest can be seen beyond the drop."

    if hazard_type == "throne":
        monster_ids = game.roll_wandering_monsters()
        game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: throne guards", throne=True)
        hazard["resolved"] = True
        return "Throne hazard: one monster commands the room from the throne."

    return None


def _resolve_deadly_poison(hero, label: str) -> str:
    """Apply a deadly-poison style effect."""
    if hero.current_fate > 0:
        hero.spend_fate()
        return f"{label} {hero.name} spends a Fate Point to survive."
    hero.is_dead = True
    hero.is_ko = True
    hero.current_wounds = 0
    return f"{label} {hero.name} dies."


def _apply_uncancelable_wounds(hero, wounds: int) -> str:
    """Apply damage that cannot be prevented by Fate."""
    hero.current_wounds -= wounds
    if hero.current_wounds <= 0:
        hero.current_wounds = 0
        hero.is_ko = True
        if hero.current_fate <= 0:
            hero.is_dead = True
            return f"{hero.name} is slain."
        return f"{hero.name} is knocked out."
    return f"{hero.name} suffers {wounds} wound(s)."


def _resolve_mould_effect(hero, auto_fail_cover: bool = False) -> str:
    """Resolve the mould table."""
    roll = _roll_d12()
    if roll == 1:
        return f"Mould roll: {roll}. " + _resolve_deadly_poison(hero, "")
    if 2 <= roll <= 6:
        if hero.current_fate > 0:
            hero.spend_fate()
            return f"Mould roll: {roll}. Poison resisted with Fate."
        hero.current_wounds = max(0, hero.current_wounds - 1)
        if hero.current_wounds == 0:
            hero.is_ko = True
        return f"Mould roll: {roll}. Poison causes 1 wound."
    if 7 <= roll <= 10:
        hero.add_status_effect(
            "mould_irritant",
            scope="next_combat",
            ws_delta=-2,
        )
        return f"Mould roll: {roll}. Irritant: WS -2 for the next combat."
    return f"Mould roll: {roll}. No effect."


def resolve_pool_drink(hero, room, game) -> str:
    """Resolve drinking from a hazard pool."""
    hazard = room.get("hazard") or {}
    roll = _roll_d12()
    if roll == 1:
        return f"Pool roll: {roll}. " + _resolve_deadly_poison(hero, "Deadly poison.")
    if 2 <= roll <= 4:
        turns = _roll_d12()
        hero.is_ko = True
        hero.ko_turns = turns
        return f"Pool roll: {roll}. Sleeping potion. {hero.name} is KO'd for {turns} turns."
    if 5 <= roll <= 8:
        hero.current_fate += 1
        hero.temp_fate_bonus += 1
        return f"Pool roll: {roll}. Luck. {hero.name} gains 1 temporary Fate Point."
    hero.current_wounds = hero.max_wounds
    return f"Pool roll: {roll}. Healing. {hero.name} recovers all lost wounds."


def resolve_magic_circle_entry(hero, room, game) -> Optional[str]:
    """Resolve stepping onto a magic circle."""
    hazard = room.get("hazard") or {}
    if hazard.get("drained", False):
        return "The Magic Circle is drained."

    roll = _roll_d12()
    if roll == 1:
        hero.current_fate = max(0, hero.current_fate - 1)
        hero.max_fate = max(0, hero.max_fate - 1)
        return f"Magic Circle roll: {roll}. Cursed. {hero.name} permanently loses 1 Fate Point."
    if roll == 2:
        from monster import roll_lair_encounter
        game.combat_log.append("Magic Circle roll: 2. Summoning!")
        game._start_combat_random(roll_lair_encounter(), trigger_tile=(hero.x, hero.y))
        game.combat_log.append("  Magic Circle summoning: heroes should be surprised in the first combat round.")
        hazard["resolved"] = True
        return None
    if 3 <= roll <= 6:
        return f"Magic Circle roll: {roll}. Nothing happens."
    if 7 <= roll <= 9:
        if hero.is_wizard():
            hero.free_spell_cast += 1
            hazard["drained"] = True
            return f"Magic Circle roll: {roll}. Magical power. {hero.name}'s next spell is free."
        return f"Magic Circle roll: {roll}. The circle does not respond to a non-Wizard."
    if 10 <= roll <= 11:
        hero.heal(1)
        hazard["drained"] = True
        return f"Magic Circle roll: {roll}. Healing. {hero.name} heals 1 wound."
    hero.current_fate += 1
    hero.temp_fate_bonus += 1
    hazard["drained"] = True
    return f"Magic Circle roll: {roll}. Fate. {hero.name} gains 1 temporary Fate Point."


def resolve_statue_interaction(hero, room, game) -> str:
    """Attempt to take the ruby from the statue."""
    from monster import Monster

    hazard = room.get("hazard") or {}
    anchor = get_hazard_anchor(room)
    roll = _roll_d12()
    hazard["resolved"] = True

    if roll <= 2:
        hero.current_fate = 0
        return f"Statue roll: {roll}. Curse. {hero.name}'s Fate Points drop to 0."

    if 3 <= roll <= 6:
        statue = Monster(
            monster_id="animated_statue",
            name="Animated Statue",
            ws=9,
            bs=0,
            strength=5,
            toughness=8,
            speed=6,
            bravery=12,
            intelligence=1,
            wounds=8,
            pv=8,
            weapons=[{"damage_dice": 5, "critical": 12, "fumble": 1}],
        )
        statue.x, statue.y = anchor
        game.monsters.append(statue)
        game._start_combat_with_monsters([statue])
        return f"Statue roll: {roll}. The statue animates and attacks!"

    if 7 <= roll <= 11:
        warlord = game.monster_library.create_monster("skaven_warlord")
        if warlord:
            warlord.x, warlord.y = anchor
            game.monsters.append(warlord)
            game._start_combat_with_monsters([warlord])
        return f"Statue roll: {roll}. The statue transforms into a Skaven Warlord Sentry!"

    hero.gold += 400
    game.gold_found += 400
    hazard["jewel_taken"] = True
    return f"Statue roll: {roll}. {hero.name} removes the ruby without mishap and gains 400 gold crowns."


def resolve_trapdoor_open(hero, room, game) -> str:
    """Open a trapdoor hazard and resolve its outcome."""
    from traps import resolve_trap_event

    hazard = room.get("hazard") or {}
    anchor = get_hazard_anchor(room)
    if hazard.get("opened_result"):
        return f"Trapdoor already opened: {hazard['opened_result']}."

    roll = _roll_d12()
    if roll == 1:
        hazard["opened_result"] = "trap"
        resolve_trap_event(
            hero,
            game.dungeon,
            game.combat_log,
            lambda _: None,
            resolve_magic_spell=lambda trapped_hero, spell_name, trap_origin=None: game._resolve_magic_trap_spell(
                trapped_hero, spell_name, trap_origin
            ),
            source="chest",
            can_spot=False,
            can_disarm=False,
        )
        return "Trapdoor roll: 1. Trapped trapdoor!"
    if 2 <= roll <= 3:
        hazard["opened_result"] = "room"
        return "Trapdoor roll: 2-3. A room lies beneath the trapdoor."
    if 4 <= roll <= 6:
        hazard["opened_result"] = "crypt"
        hazard["crypt_searched"] = False
        return "Trapdoor roll: 4-6. A crypt lies beneath the trapdoor."
    if 7 <= roll <= 9:
        hazard["opened_result"] = "maze"
        return "Trapdoor roll: 7-9. The trapdoor leads to The Maze. No sub-level is implemented yet."

    hazard["opened_result"] = "stairs"
    if anchor is not None:
        game.dungeon.grid[anchor] = game.dungeon.TileType.STAIRS_DOWN
    return "Trapdoor roll: 10-12. Stairs lead down."


def resolve_crypt_search(hero, room, game) -> str:
    """Search a crypt beneath a trapdoor."""
    from monster import Monster

    hazard = room.get("hazard") or {}
    if hazard.get("opened_result") != "crypt":
        return "There is no crypt to search."
    if hazard.get("crypt_searched"):
        return "The crypt has already been searched."

    hazard["crypt_searched"] = True
    roll = _roll_d12()
    if roll <= 2:
        return "Crypt roll: 1-2. " + _resolve_mould_effect(hero, auto_fail_cover=True)
    if 3 <= roll <= 6:
        return "Crypt roll: 3-6. Empty."
    if 7 <= roll <= 11:
        hero.gold += 25
        game.gold_found += 25
        return "Crypt roll: 7-11. A gold ring worth 25 gold crowns is found."

    anchor = get_hazard_anchor(room)
    undead = Monster(
        monster_id="undead_skaven",
        name="Undead Skaven",
        ws=8,
        bs=0,
        strength=6,
        toughness=12,
        speed=6,
        bravery=12,
        intelligence=1,
        wounds=1,
        pv=4,
        weapons=[{"damage_dice": 6, "critical": 12, "fumble": 1}],
    )
    undead.x, undead.y = anchor
    game.monsters.append(undead)
    game._start_combat_with_monsters([undead])
    return "Crypt roll: 12. An Undead Skaven erupts from the crypt!"


def resolve_fight_rats(hero, room, game) -> str:
    """Fight through a rats hazard room."""
    hazard = room.get("hazard") or {}
    rats_remaining = int(hazard.get("rats_remaining", 60))
    kill_roll = _roll_d12()
    rats_remaining = max(0, rats_remaining - kill_roll)
    hazard["rats_remaining"] = rats_remaining

    messages: List[str] = [f"Rats: {hero.name} kills {kill_roll}. {rats_remaining} remain."]
    if kill_roll <= 4:
        messages.append(_apply_uncancelable_wounds(hero, 1))

    if rats_remaining == 0:
        hazard["resolved"] = True
        messages.append("The room is cleared of rats.")

    return " ".join(messages)


def resolve_fight_bats(hero, room, game) -> str:
    """Fight through a bats hazard room."""
    hazard = room.get("hazard") or {}
    damage = (_roll_d12() + 1) // 2
    outcome = _apply_uncancelable_wounds(hero, damage)
    hazard["resolved"] = True
    return f"Bats: {hero.name} fights through the swarm and suffers {damage} wound(s). {outcome} The room is cleared of bats."


def resolve_mould_crossing(hero, room, game) -> str:
    """Attempt to cross a mould room with wet cloths."""
    hazard = room.get("hazard") or {}
    crossed = set(hazard.get("crossed_heroes", []))
    crossed.add(hero.id)
    hazard["crossed_heroes"] = sorted(crossed)
    return _resolve_mould_effect(hero)


def resolve_eat_mushroom(hero, room, game) -> str:
    """Eat one mushroom from a mushroom hazard room."""
    hazard = room.get("hazard") or {}
    count = int(hazard.get("mushroom_count", 0))
    if count <= 0:
        count = _roll_d12()
        hazard["mushroom_count"] = count

    if count <= 0:
        return "There are no mushrooms left to eat."

    hazard["mushroom_count"] = count - 1
    roll = _roll_d12()

    if roll <= 2:
        return f"Mushroom roll: {roll}. " + _resolve_deadly_poison(hero, "Deadly poison.")
    if 3 <= roll <= 4:
        turns = _roll_d12()
        hero.is_ko = True
        hero.ko_turns = max(hero.ko_turns, turns)
        return f"Mushroom roll: {roll}. Sleeping mushroom. {hero.name} is KO'd for {turns} turns."
    if 5 <= roll <= 6:
        return f"Mushroom roll: {roll}. Polka dots. No game effect."
    if 7 <= roll <= 8:
        hero.add_status_effect(
            "mushroom_strength",
            scope="combat",
            bonus_melee_damage_dice=1,
        )
        return f"Mushroom roll: {roll}. Strength mushroom. {hero.name} gets +1 melee damage die for the next combat."
    if 9 <= roll <= 10:
        hero.add_status_effect(
            "mushroom_speed",
            scope="combat",
            combat_speed_multiplier=2,
        )
        return f"Mushroom roll: {roll}. Speed mushroom. {hero.name}'s Speed is doubled for the next combat."

    hero.current_wounds = hero.max_wounds
    return f"Mushroom roll: {roll}. Healing mushroom. {hero.name} recovers all lost wounds."


def resolve_chasm_leap(hero, room, game) -> str:
    """Attempt a heroic leap across a chasm."""
    anchor = get_hazard_anchor(room)
    if anchor is None:
        return "The chasm cannot be crossed here."
    dx = anchor[0] - hero.x
    dy = anchor[1] - hero.y
    if abs(dx) + abs(dy) != 1:
        return "You must stand next to the chasm to leap it."

    landing = (anchor[0] + dx, anchor[1] + dy)
    if not game.dungeon.is_walkable(*landing):
        return f"There is no safe landing square beyond the chasm at {landing}."

    occupied = {
        (other.x, other.y)
        for other in game.party
        if other != hero and not other.is_dead and not other.is_ko
    }
    occupied.update(
        (monster.x, monster.y)
        for monster in game.monsters
        if not monster.is_dead
    )
    if landing in occupied:
        return f"The landing square at {landing} is occupied."

    roll = _roll_d12()
    effective_speed = hero.get_effective_speed("exploration")
    if roll > effective_speed:
        if hero.current_fate > 0:
            hero.spend_fate()
            hero.x, hero.y = landing
            return (
                f"Chasm leap roll: {roll} vs Speed {effective_speed}. Failed, but {hero.name} spends Fate and lands safely at {landing}."
            )
        hero.current_wounds = 0
        hero.is_ko = True
        hero.is_dead = True
        return f"Chasm leap roll: {roll} vs Speed {effective_speed}. {hero.name} falls into the chasm and dies."

    hero.x, hero.y = landing
    game.dungeon._explore_from(*landing)
    return f"Chasm leap roll: {roll} vs Speed {effective_speed}. {hero.name} lands safely at {landing}."


def resolve_grate_room(room, game) -> str:
    """Inspect and resolve the room beneath a grate."""
    hazard = room.get("hazard") or {}
    if hazard.get("lower_room_opened"):
        result = hazard.get("lower_room_kind", "unknown")
        return f"The grate already reveals a lower {result} room."

    roll = _roll_d12()
    if roll <= 6:
        lower_kind = "normal"
    elif roll <= 8:
        lower_kind = "hazard"
    elif roll <= 10:
        lower_kind = "lair"
    else:
        lower_kind = "quest"

    hazard["lower_room_opened"] = True
    hazard["lower_room_kind"] = lower_kind

    if lower_kind in {"lair", "quest"}:
        monster_ids = game.roll_wandering_monsters()
        prisoner_ids = ["skaven_warrior" for _ in monster_ids] or ["skaven_warrior"]
        game._start_room_hazard_combat(
            room,
            prisoner_ids,
            reason=f"Lower room beneath grate ({lower_kind})",
            prisoners=True,
            hero_surprise_bonus=2,
            ignore_elf_surprise_bonus=True,
        )
        return f"Grate: a lower {lower_kind} room full of prisoner monsters is revealed."

    return f"Grate: a lower {lower_kind} room is revealed beneath the floor."


def resolve_rescue_maiden(room, game) -> str:
    """Rescue the maiden after her guards are defeated."""
    hazard = room.get("hazard") or {}
    if hazard.get("npc_type") != "maiden":
        return "There is no maiden here."
    if hazard.get("rescued"):
        return "The Maiden has already been rescued."
    hazard["rescued"] = True
    game.expedition_followers["maiden"] = True
    return "The Maiden is rescued. If she survives the expedition, her father will reward the party with 100 gold crowns."


def resolve_release_man_at_arms(room, game) -> str:
    """Release the man-at-arms after his guards are defeated."""
    hazard = room.get("hazard") or {}
    if hazard.get("npc_type") != "man_at_arms":
        return "There is no Man-at-Arms here."
    if hazard.get("rescued"):
        return "The Man-at-Arms has already been released."
    hazard["rescued"] = True
    game.expedition_followers["man_at_arms"] = True
    return "The Man-at-Arms is released. He should become a henchman after the expedition; henchmen are not implemented yet."


def resolve_recruit_rogue(room, game) -> str:
    """Recruit the rogue NPC for the rest of the expedition."""
    hazard = room.get("hazard") or {}
    if hazard.get("npc_type") != "rogue":
        return "There is no Rogue here."
    if hazard.get("joined"):
        return "The Rogue is already travelling with the party."
    hazard["joined"] = True
    game.expedition_followers["rogue"] = True
    for hero in game.party:
        hero.add_status_effect(
            "rogue_companion",
            scope="expedition",
            trap_spot_delta=-1,
            trap_disarm_delta=-1,
        )
    return "The Rogue joins the party. Trap spotting and disarming suffer -1 while he travels with you."


__all__ = [
    "describe_hazard",
    "hazard_blocks_movement",
    "get_hazard_color",
    "get_hazard_symbol",
    "get_hazard_anchor",
    "get_room_for_hero",
    "is_adjacent_or_same",
    "resolve_crypt_search",
    "resolve_magic_circle_entry",
    "resolve_grate_room",
    "resolve_hazard_reveal",
    "resolve_recruit_rogue",
    "resolve_release_man_at_arms",
    "resolve_rescue_maiden",
    "resolve_fight_bats",
    "resolve_fight_rats",
    "resolve_chasm_leap",
    "resolve_mould_crossing",
    "resolve_pool_drink",
    "resolve_eat_mushroom",
    "resolve_statue_interaction",
    "resolve_trapdoor_open",
    "roll_hazard_room",
]

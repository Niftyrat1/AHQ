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

    if hazard_type == "mushrooms":
        hazard_data["mushroom_count"] = _roll_d12()
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


def _coerce_pos(pos) -> Optional[Tuple[int, int]]:
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        return (int(pos[0]), int(pos[1]))
    return None


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _hazard_far_side_tiles(room, game) -> List[Tuple[int, int]]:
    """Return room tiles beyond the hazard anchor from the entrance side."""
    anchor = get_hazard_anchor(room)
    entrance = _coerce_pos(room.get("entrance"))
    if anchor is None or entrance is None:
        return []

    axis = 0 if abs(anchor[0] - entrance[0]) >= abs(anchor[1] - entrance[1]) else 1
    direction = _sign(anchor[axis] - entrance[axis])
    if direction == 0:
        return []

    far_side = []
    for pos in sorted(game.dungeon.get_room_interior_tiles(room)):
        if pos == anchor:
            continue
        if (pos[axis] - anchor[axis]) * direction <= 0:
            continue
        if game.dungeon.is_walkable(*pos):
            far_side.append(pos)
    return far_side


def _roll_lower_room_kind() -> str:
    roll = _roll_d12()
    if roll <= 6:
        return "normal"
    if roll <= 8:
        return "hazard"
    if roll <= 10:
        return "lair"
    return "quest"


def get_lower_room_tiles(room: Optional[Dict[str, object]]) -> set[Tuple[int, int]]:
    """Return physical tiles for a revealed lower room."""
    if not room:
        return set()
    hazard = room.get("hazard") or {}
    return {
        (int(pos[0]), int(pos[1]))
        for pos in hazard.get("lower_room_tiles", [])
        if isinstance(pos, (list, tuple)) and len(pos) == 2
    }


def find_lower_room_for_tile(dungeon, x: int, y: int) -> Optional[Dict[str, object]]:
    """Return the upper hazard room whose lower-room layout contains a tile."""
    pos = (int(x), int(y))
    for room in getattr(dungeon, "rooms", []):
        if pos in get_lower_room_tiles(room):
            return room
    return None


def hero_is_in_lower_room(hero, room: Optional[Dict[str, object]]) -> bool:
    """Whether a hero is currently tracked inside this lower room."""
    if not room:
        return False
    hazard = room.get("hazard") or {}
    if hero.id in hazard.get("lower_room_heroes", []):
        return True
    return (hero.x, hero.y) in get_lower_room_tiles(room)


def get_lower_room_for_hero(hero, dungeon) -> Optional[Dict[str, object]]:
    """Return the lower-room hazard containing or tracking the hero."""
    for room in getattr(dungeon, "rooms", []):
        if hero_is_in_lower_room(hero, room):
            return room
    return None


def _next_lower_room_origin(game) -> Tuple[int, int]:
    lower_room_count = 0
    for room in getattr(game.dungeon, "rooms", []):
        hazard = room.get("hazard") or {}
        if hazard.get("lower_room_origin"):
            lower_room_count += 1
    return (1000, 1000 + lower_room_count * 12)


def _ensure_lower_room_layout(room, game) -> List[Tuple[int, int]]:
    """Create a small no-exit physical room beneath a grate or trapdoor."""
    hazard = room.setdefault("hazard", {})
    tiles = sorted(get_lower_room_tiles(room))
    if tiles:
        return tiles

    origin_x, origin_y = _next_lower_room_origin(game)
    width = 6
    height = 6
    interior = []
    for dx in range(width):
        for dy in range(height):
            pos = (origin_x + dx, origin_y + dy)
            if dx in {0, width - 1} or dy in {0, height - 1}:
                game.dungeon.grid[pos] = game.dungeon.TileType.WALL
            else:
                game.dungeon.grid[pos] = game.dungeon.TileType.FLOOR
                game.dungeon.explored.add(pos)
                interior.append(pos)

    hazard["lower_room_origin"] = [origin_x, origin_y]
    hazard["lower_room_width"] = width
    hazard["lower_room_height"] = height
    hazard["lower_room_tiles"] = [[x, y] for x, y in interior]
    entry = interior[len(interior) // 2]
    hazard["lower_room_entry_tile"] = [entry[0], entry[1]]
    hazard.setdefault("lower_room_heroes", [])
    return interior


def _coerce_lower_room_entry(hazard: Dict[str, object]) -> Optional[Tuple[int, int]]:
    return _coerce_pos(hazard.get("lower_room_entry_tile"))


def lower_room_entry_available(hero, room, game) -> Tuple[bool, str]:
    """Check whether a hero may climb down into a revealed lower room."""
    hazard = room.get("hazard") or {}
    if not hazard.get("lower_room_opened"):
        return False, "The lower room has not been revealed."
    if hero_is_in_lower_room(hero, room):
        return False, f"{hero.name} is already in the lower room."
    anchor = get_hazard_anchor(room)
    if anchor is None or not is_adjacent_or_same(hero, anchor, game.dungeon):
        return False, "You must be on or next to the grate or trapdoor opening."
    allowed, message = _lower_room_transfer_available(hazard, game)
    if not allowed:
        return False, message
    return True, ""


def lower_room_exit_available(hero, room, game) -> Tuple[bool, str]:
    """Check whether a hero may climb out of a lower room."""
    hazard = room.get("hazard") or {}
    if not hero_is_in_lower_room(hero, room):
        return False, f"{hero.name} is not in the lower room."
    if hazard.get("lower_room_requires_rope_to_exit", False) and _party_inventory_count(game, "rope_10ft") < 1:
        return False, "The heroes need at least 10 feet of rope to climb out of the lower room."
    allowed, message = _lower_room_transfer_available(hazard, game)
    if not allowed:
        return False, message
    return True, ""


def _lower_room_transfer_available(hazard: Dict[str, object], game) -> Tuple[bool, str]:
    limit = int(hazard.get("lower_room_model_limit_per_combat_turn", 1) or 1)
    if limit <= 0:
        return True, ""
    current_turn = int(getattr(game, "turn_count", 0))
    used_turn = hazard.get("lower_room_transfer_turn")
    used_count = int(hazard.get("lower_room_transfer_count", 0) or 0)
    if used_turn == current_turn and used_count >= limit:
        return False, "Only one model may enter or leave the lower room this turn."
    return True, ""


def _record_lower_room_transfer(hazard: Dict[str, object], game):
    current_turn = int(getattr(game, "turn_count", 0))
    if hazard.get("lower_room_transfer_turn") != current_turn:
        hazard["lower_room_transfer_turn"] = current_turn
        hazard["lower_room_transfer_count"] = 0
    hazard["lower_room_transfer_count"] = int(hazard.get("lower_room_transfer_count", 0) or 0) + 1


def _occupied_model_tiles(game, hero=None) -> set[Tuple[int, int]]:
    occupied = {
        (other.x, other.y)
        for other in game.party
        if other != hero and not other.is_dead and not other.is_ko
    }
    for monster in game.monsters:
        if not monster.is_dead:
            occupied.update(monster.get_occupied_tiles())
    return occupied


def choose_lower_room_entry_tile(hero, room, game) -> Optional[Tuple[int, int]]:
    """Choose the nearest free lower-room tile to the shaft."""
    hazard = room.get("hazard") or {}
    tiles = sorted(get_lower_room_tiles(room))
    if not tiles:
        tiles = sorted(_ensure_lower_room_layout(room, game))
    occupied = _occupied_model_tiles(game, hero)
    entry = _coerce_lower_room_entry(hazard)
    if entry is None:
        entry = tiles[len(tiles) // 2] if tiles else None
    free_tiles = [pos for pos in tiles if pos not in occupied and game.dungeon.is_walkable(*pos)]
    if not free_tiles:
        return None
    if entry is None:
        return free_tiles[0]
    return min(free_tiles, key=lambda pos: (abs(pos[0] - entry[0]) + abs(pos[1] - entry[1]), pos[1], pos[0]))


def choose_lower_room_exit_tile(hero, room, game) -> Optional[Tuple[int, int]]:
    """Choose the upper-room tile where a model emerges from the lower room."""
    anchor = get_hazard_anchor(room)
    if anchor is None:
        return None
    occupied = _occupied_model_tiles(game, hero)
    candidates = [anchor]
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        pos = (anchor[0] + dx, anchor[1] + dy)
        if pos in game.dungeon.get_room_interior_tiles(room):
            candidates.append(pos)
    for pos in candidates:
        if pos not in occupied and game.dungeon.is_walkable(*pos):
            return pos
    return None


def resolve_enter_lower_room(hero, room, game, landing: Optional[Tuple[int, int]] = None) -> str:
    """Move a hero into a revealed lower room."""
    allowed, message = lower_room_entry_available(hero, room, game)
    if not allowed:
        return message
    hazard = room.setdefault("hazard", {})
    target = landing or choose_lower_room_entry_tile(hero, room, game)
    if target is None:
        return "There is no free space in the lower room."
    if target not in get_lower_room_tiles(room):
        return "That square is not in the lower room."
    if target in _occupied_model_tiles(game, hero):
        return "That lower-room square is occupied."
    hero.x, hero.y = target
    lower_heroes = list(hazard.get("lower_room_heroes", []))
    if hero.id not in lower_heroes:
        lower_heroes.append(hero.id)
    hazard["lower_room_heroes"] = lower_heroes
    _record_lower_room_transfer(hazard, game)
    game.dungeon._explore_from(*target)
    return f"{hero.name} climbs down into the lower room."


def resolve_leave_lower_room(hero, room, game, landing: Optional[Tuple[int, int]] = None) -> str:
    """Move a hero out of a lower room, enforcing the rope requirement."""
    allowed, message = lower_room_exit_available(hero, room, game)
    if not allowed:
        return message
    hazard = room.setdefault("hazard", {})
    target = landing or choose_lower_room_exit_tile(hero, room, game)
    if target is None:
        return "There is no free space by the grate or trapdoor opening."
    if target in _occupied_model_tiles(game, hero):
        return "The space by the opening is occupied."
    hero.x, hero.y = target
    hazard["lower_room_heroes"] = [
        hero_id for hero_id in hazard.get("lower_room_heroes", []) if hero_id != hero.id
    ]
    _record_lower_room_transfer(hazard, game)
    game.dungeon._explore_from(*target)
    return f"{hero.name} climbs out of the lower room using the rope."


def _resolve_lower_room_from_hazard(room, game, source_label: str) -> str:
    """Resolve the abstract lower room used by grates and trapdoors."""
    hazard = room.get("hazard") or {}
    if hazard.get("lower_room_opened"):
        result = hazard.get("lower_room_kind", "unknown")
        return f"{source_label}: the lower {result} room has already been revealed."

    lower_kind = _roll_lower_room_kind()
    lower_tiles = _ensure_lower_room_layout(room, game)
    hazard["lower_room_opened"] = True
    hazard["lower_room_kind"] = lower_kind
    hazard["lower_room_requires_rope_to_exit"] = True
    hazard["lower_room_model_limit_per_combat_turn"] = 1

    if lower_kind in {"lair", "quest"}:
        monster_ids = game.roll_wandering_monsters()
        prisoner_ids = ["skaven_warrior" for _ in monster_ids] or ["skaven_warrior"]
        hazard["lower_room_prisoners"] = True
        hazard["lower_room_prisoner_damage_dice"] = 1
        entry = _coerce_lower_room_entry(hazard)
        placement_tiles = [pos for pos in lower_tiles if pos != entry] or lower_tiles
        monsters = game._start_room_hazard_combat(
            room,
            prisoner_ids,
            reason=f"Lower room beneath {source_label.lower()} ({lower_kind})",
            prisoners=True,
            hero_surprise_bonus=2,
            ignore_elf_surprise_bonus=True,
            placement_tiles=placement_tiles,
            preserve_placed_monsters=True,
        )
        hazard["lower_room_monsters"] = [
            monster.instance_id for monster in monsters if getattr(monster, "instance_id", None)
        ]
        return (
            f"{source_label}: a lower {lower_kind} room full of prisoner monsters is revealed. "
            "They fight with 1 damage die; rope is required to climb out, and only one model may enter or leave per turn."
        )

    hazard["lower_room_prisoners"] = False
    return (
        f"{source_label}: a lower {lower_kind} room is revealed beneath the floor. "
        "Rope is required to climb out, and only one model may enter or leave per turn."
    )


def _quest_specific_stairs_down_override(game) -> bool:
    """Whether trapdoor stairs-down results must be treated as lower rooms."""
    if bool(getattr(game, "quest_specific_stairs_down", False)):
        return True
    quest_id = getattr(game, "quest_id", None)
    if not quest_id:
        return False
    normalized = str(quest_id).lower().replace(" ", "_").replace("-", "_")
    return normalized in {"shattered_amulet", "quest_for_the_shattered_amulet"}


def _register_trapdoor_maze_entry(room, game, anchor: Optional[Tuple[int, int]]) -> Dict[str, object]:
    """Attach a live Heroquest maze sub-level entry to a trapdoor hazard."""
    if hasattr(game, "register_heroquest_maze_entry"):
        entry = game.register_heroquest_maze_entry(room, anchor)
    else:
        entry = {
            "type": "heroquest_maze",
            "source": "trapdoor",
            "room_id": room.get("id"),
            "origin_level": getattr(getattr(game, "dungeon", None), "level", None),
            "origin_anchor": [anchor[0], anchor[1]] if anchor is not None else None,
        }
    hazard = room.setdefault("hazard", {})
    hazard["maze_sub_level_available"] = True
    hazard["maze_sub_level_entered"] = False
    hazard["maze_sub_level_entry"] = dict(entry)
    return entry


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
            far_side_tiles = _hazard_far_side_tiles(room, game)
            if far_side_tiles:
                hazard["far_side_tiles"] = [[x, y] for x, y in far_side_tiles]
            chest_pos = game.place_hazard_chest(room, candidate_tiles=far_side_tiles or None)
            if chest_pos is not None:
                hazard["chest_pos"] = list(chest_pos)
            game._start_room_hazard_combat(
                room,
                monster_ids,
                reason="Hazard room: chasm guardians",
                placement_tiles=far_side_tiles or None,
                preserve_placed_monsters=bool(far_side_tiles),
            )
        return "Chasm hazard: monsters guard the far side and a chest can be seen beyond the drop."

    if hazard_type == "throne":
        monster_ids = game.roll_wandering_monsters()
        game._start_room_hazard_combat(room, monster_ids, reason="Hazard room: throne guards", throne=True)
        hazard["resolved"] = True
        return "Throne hazard: one monster commands the room from the throne."

    return None


def _resolve_deadly_poison(hero, label: str) -> str:
    """Apply a deadly-poison style effect."""
    if hero.has_fate_available():
        hero.queue_fate_decision(hero.current_wounds, source="Deadly Poison")
        return f"{label} {hero.name} must decide whether to spend a Fate Point to survive."
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

    awarded, left = game.award_party_gold(400, "statue ruby", note_pos=anchor)
    hazard["jewel_taken"] = True
    if left > 0:
        return f"Statue roll: {roll}. The ruby is worth 400 gold crowns; the party carries {awarded} and leaves {left} behind."
    return f"Statue roll: {roll}. The party gains 400 gold crowns from the ruby."


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
        return "Trapdoor roll: 2-3. " + _resolve_lower_room_from_hazard(room, game, "Trapdoor")
    if 4 <= roll <= 6:
        hazard["opened_result"] = "crypt"
        hazard["crypt_searched"] = False
        return "Trapdoor roll: 4-6. A crypt lies beneath the trapdoor."
    if 7 <= roll <= 9:
        hazard["opened_result"] = "maze"
        if not bool(getattr(game, "heroquest_maze_available", True)):
            hazard["maze_sub_level_available"] = False
            hazard["resolved"] = True
            return "Trapdoor roll: 7-9. The trapdoor leads to The Maze, but no Heroquest maze board is available; the Heroes find nothing."
        _register_trapdoor_maze_entry(room, game, anchor)
        return "Trapdoor roll: 7-9. The trapdoor opens onto stairs to a Heroquest maze sub-level."

    if _quest_specific_stairs_down_override(game):
        hazard["opened_result"] = "room"
        hazard["stairs_result_overridden"] = True
        return (
            "Trapdoor roll: 10-12. Quest-specific stairs-down rules treat this result as a room. "
            + _resolve_lower_room_from_hazard(room, game, "Trapdoor")
        )

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
        awarded, left = game.award_party_gold(25, "crypt ring", note_pos=get_hazard_anchor(room))
        if left > 0:
            return f"Crypt roll: 7-11. A gold ring is found; the party carries {awarded} gold crowns worth and leaves {left} behind."
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
    game._start_combat_with_monsters_configured(
        [undead],
        force_gm_surprise=True,
        preserve_placed_monsters=True,
        summary_prefix="Crypt undead:",
    )
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


def resolve_use_rat_poison(hero, room, game) -> str:
    """Use Rat Poison to clear a rats hazard room."""
    if hero.get_inventory_count("rat_poison") <= 0:
        return f"{hero.name} has no Rat Poison."
    hero.remove_inventory_item("rat_poison", 1)
    room.setdefault("hazard", {})["resolved"] = True
    return f"{hero.name} uses Rat Poison and clears the rats in one exploration turn."


def resolve_use_greek_fire(hero, room, game) -> str:
    """Use Greek Fire to clear a rats, bats, or mould room."""
    hazard = room.get("hazard") or {}
    hazard_type = str(hazard.get("type"))
    needed = 2 if hazard_type in {"rats", "bats"} else 1
    if hero.get_inventory_count("greek_fire_flask") < needed:
        return f"{hero.name} needs {needed} flask(s) of Greek Fire."
    hero.remove_inventory_item("greek_fire_flask", needed)
    hazard["resolved"] = True
    if hazard_type == "mould":
        return f"{hero.name} burns away the mould with Greek Fire."
    return f"{hero.name} uses Greek Fire and clears the {hazard_type}."


def resolve_fight_bats(hero, room, game) -> str:
    """Fight through a bats hazard room."""
    hazard = room.get("hazard") or {}
    damage = (_roll_d12() + 1) // 2
    outcome = _apply_uncancelable_wounds(hero, damage)
    hazard["resolved"] = True
    return f"Bats: {hero.name} fights through the swarm and suffers {damage} wound(s). {outcome} The room is cleared of bats."


def resolve_use_screetch_bug(hero, room, game) -> str:
    """Use a Screetch Bug to clear a bats hazard room."""
    if hero.get_inventory_count("screetch_bug") <= 0:
        return f"{hero.name} has no Screetch Bug."
    hero.remove_inventory_item("screetch_bug", 1)
    room.setdefault("hazard", {})["resolved"] = True
    return f"{hero.name} releases a Screetch Bug and the bats scatter."


def resolve_flames_of_death_hazard(hero, room, game) -> str:
    """Use Flames of Death to clear a rats or bats hazard room."""
    hazard = room.get("hazard") or {}
    hazard_type = str(hazard.get("type"))
    if hazard_type not in {"rats", "bats"}:
        return "Flames of Death is not a special solution for this hazard."

    can_cast, message = game.can_hero_cast_spell(hero, "Flames of Death", source_kind="spellbook")
    if not can_cast:
        return message or f"{hero.name} cannot cast Flames of Death."

    game._consume_spell_source(hero, "Flames of Death", "spellbook", None, None)
    if hasattr(game, "hero_has_attacked"):
        game.hero_has_attacked.add(hero.id)
    hazard["resolved"] = True
    if hazard_type == "rats":
        hazard["rats_remaining"] = 0
    return f"{hero.name} casts Flames of Death and clears the {hazard_type}."


def resolve_mould_crossing(hero, room, game) -> str:
    """Cross a mould room using wet cloths to avoid the spores."""
    hazard = room.get("hazard") or {}
    crossed = set(hazard.get("crossed_heroes", []))
    crossed.add(hero.id)
    hazard["crossed_heroes"] = sorted(crossed)
    return f"{hero.name} crosses the mould safely using wet cloths."


def resolve_eat_mushroom(hero, room, game) -> str:
    """Eat one mushroom from a mushroom hazard room."""
    hazard = room.get("hazard") or {}
    if "mushroom_count" not in hazard:
        hazard["mushroom_count"] = _roll_d12()
    count = int(hazard.get("mushroom_count", 0))

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


def _chasm_landing_for_hero(hero, room, game) -> Tuple[Optional[Tuple[int, int]], str]:
    anchor = get_hazard_anchor(room)
    if anchor is None:
        return None, "The chasm cannot be crossed here."
    dx = anchor[0] - hero.x
    dy = anchor[1] - hero.y
    if abs(dx) + abs(dy) != 1:
        return None, "You must stand next to the chasm to cross it."

    landing = (anchor[0] + dx, anchor[1] + dy)
    if not game.dungeon.is_walkable(*landing):
        return None, f"There is no safe landing square beyond the chasm at {landing}."

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
        return None, f"The landing square at {landing} is occupied."
    return landing, ""


def _chasm_same_side_heroes(hero, room, game) -> List[object]:
    anchor = get_hazard_anchor(room)
    if anchor is None:
        return []
    side_x = hero.x - anchor[0]
    side_y = hero.y - anchor[1]
    holders = []
    for other in game.party:
        if other == hero or other.is_dead or other.is_ko:
            continue
        if game.dungeon.find_room_for_tile(other.x, other.y) != room:
            continue
        other_x = other.x - anchor[0]
        other_y = other.y - anchor[1]
        if (other_x * side_x) + (other_y * side_y) > 0:
            holders.append(other)
    return holders


def _party_inventory_count(game, item_key: str) -> int:
    return sum(hero.get_inventory_count(item_key) for hero in game.party if not hero.is_dead)


def _consume_party_inventory(game, item_key: str, count: int) -> bool:
    remaining = int(count)
    for carrier in game.party:
        if carrier.is_dead:
            continue
        carried = carrier.get_inventory_count(item_key)
        if carried <= 0:
            continue
        take = min(remaining, carried)
        carrier.remove_inventory_item(item_key, take)
        remaining -= take
        if remaining == 0:
            return True
    return False


def _room_has_live_monsters(room, game) -> bool:
    room_tiles = set(game.dungeon.get_room_interior_tiles(room))
    return any(
        not monster.is_dead and (monster.x, monster.y) in room_tiles
        for monster in game.monsters
    )


def resolve_chasm_leap(hero, room, game) -> str:
    """Attempt a heroic leap across a chasm."""
    landing, error = _chasm_landing_for_hero(hero, room, game)
    if error:
        return error

    roll = _roll_d12()
    effective_speed = hero.get_effective_speed("exploration")
    if roll > effective_speed:
        if hero.has_fate_available():
            hero.queue_failed_roll_fate_decision("chasm", landing=[landing[0], landing[1]], roll=roll)
            return f"Chasm leap roll: {roll} vs Speed {effective_speed}. {hero.name} may spend Fate to turn the failed leap into a success."
        hero.current_wounds = 0
        hero.is_ko = True
        hero.is_dead = True
        return f"Chasm leap roll: {roll} vs Speed {effective_speed}. {hero.name} falls into the chasm and dies."

    hero.x, hero.y = landing
    game.dungeon._explore_from(*landing)
    return f"Chasm leap roll: {roll} vs Speed {effective_speed}. {hero.name} lands safely at {landing}."


def resolve_chasm_sensible_leap(hero, room, game) -> str:
    """Attempt a rope-secured leap across a chasm."""
    hazard = room.get("hazard") or {}
    if _party_inventory_count(game, "rope_10ft") < 1:
        return "The party needs at least 10 feet of rope for a sensible leap."
    holders = _chasm_same_side_heroes(hero, room, game)
    if not holders:
        return "A sensible leap needs at least one other hero on the same side holding the rope."

    landing, error = _chasm_landing_for_hero(hero, room, game)
    if error:
        return error

    roll = _roll_d12()
    effective_speed = hero.get_effective_speed("exploration")
    if roll <= effective_speed:
        hero.x, hero.y = landing
        game.dungeon._explore_from(*landing)
        for holder in holders:
            if hasattr(game, "hero_movement_remaining"):
                game.hero_movement_remaining[holder.id] = 0
        hazard["sensible_leap_success"] = True
        return f"Sensible leap roll: {roll} vs Speed {effective_speed}. {hero.name} lands safely with the rope."

    holder_rolls = []
    for holder in holders:
        save_roll = _roll_d12()
        holder_rolls.append(f"{holder.name} {save_roll} vs Strength {holder.get_effective_strength()}")
        if save_roll <= holder.get_effective_strength():
            for rope_holder in holders:
                if hasattr(game, "hero_movement_remaining"):
                    game.hero_movement_remaining[rope_holder.id] = 0
            return (
                f"Sensible leap roll: {roll} vs Speed {effective_speed}. "
                f"{hero.name} falls, but {holder.name} holds the rope and hauls them back. "
                f"Holder rolls: {', '.join(holder_rolls)}."
            )

    for holder in holders:
        if hasattr(game, "hero_movement_remaining"):
            game.hero_movement_remaining[holder.id] = 0

    if hero.has_fate_available():
        hero.queue_failed_roll_fate_decision("chasm", landing=[landing[0], landing[1]], roll=roll)
        return (
            f"Sensible leap roll: {roll} vs Speed {effective_speed}. "
            f"All rope holders fail ({', '.join(holder_rolls)}). {hero.name} may spend Fate to survive."
        )
    hero.current_wounds = 0
    hero.is_ko = True
    hero.is_dead = True
    return (
        f"Sensible leap roll: {roll} vs Speed {effective_speed}. "
        f"All rope holders fail ({', '.join(holder_rolls)}), and {hero.name} falls into the chasm and dies."
    )


def resolve_build_chasm_rope_ladder(hero, room, game) -> str:
    """Build a rope ladder across a chasm after a successful sensible leap."""
    hazard = room.get("hazard") or {}
    if hazard.get("rope_ladder_built"):
        return "The chasm rope ladder is already built."
    if not hazard.get("sensible_leap_success"):
        return "A hero must first make a sensible leap across the chasm with the rope."
    if _room_has_live_monsters(room, game):
        return "The rope ladder cannot be built while monsters are in the room."
    if _party_inventory_count(game, "rope_10ft") < 2:
        return "The party needs 20 feet of rope to build a rope ladder."
    if _party_inventory_count(game, "iron_spikes_10") < 1:
        return "The party needs 10 iron spikes to build a rope ladder."

    _consume_party_inventory(game, "rope_10ft", 2)
    _consume_party_inventory(game, "iron_spikes_10", 1)
    hazard["rope_ladder_built"] = True
    return f"{hero.name} builds a rope ladder across the chasm using 20 feet of rope and 10 iron spikes."


def resolve_cross_chasm_rope_ladder(hero, room, game) -> str:
    """Cross a completed chasm rope ladder safely."""
    hazard = room.get("hazard") or {}
    if not hazard.get("rope_ladder_built"):
        return "There is no rope ladder across this chasm."
    landing, error = _chasm_landing_for_hero(hero, room, game)
    if error:
        return error
    hero.x, hero.y = landing
    game.dungeon._explore_from(*landing)
    return f"{hero.name} crosses the chasm safely on the rope ladder."


def resolve_grate_room(room, game) -> str:
    """Inspect and resolve the room beneath a grate."""
    return _resolve_lower_room_from_hazard(room, game, "Grate")


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
    return "The Man-at-Arms is released. If he survives the expedition he will join the party's leader as a henchman after the delve."


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
    "choose_lower_room_entry_tile",
    "choose_lower_room_exit_tile",
    "describe_hazard",
    "find_lower_room_for_tile",
    "hazard_blocks_movement",
    "get_hazard_color",
    "get_hazard_symbol",
    "get_hazard_anchor",
    "get_lower_room_for_hero",
    "get_lower_room_tiles",
    "get_room_for_hero",
    "is_adjacent_or_same",
    "lower_room_entry_available",
    "lower_room_exit_available",
    "resolve_crypt_search",
    "resolve_enter_lower_room",
    "resolve_leave_lower_room",
    "resolve_magic_circle_entry",
    "resolve_grate_room",
    "resolve_hazard_reveal",
    "resolve_recruit_rogue",
    "resolve_release_man_at_arms",
    "resolve_rescue_maiden",
    "resolve_fight_bats",
    "resolve_fight_rats",
    "resolve_flames_of_death_hazard",
    "resolve_build_chasm_rope_ladder",
    "resolve_cross_chasm_rope_ladder",
    "resolve_use_greek_fire",
    "resolve_use_rat_poison",
    "resolve_use_screetch_bug",
    "resolve_chasm_leap",
    "resolve_chasm_sensible_leap",
    "resolve_mould_crossing",
    "resolve_pool_drink",
    "resolve_eat_mushroom",
    "resolve_statue_interaction",
    "resolve_trapdoor_open",
    "roll_hazard_room",
]

"""AHQ hazard tables and room metadata helpers."""

import random
from typing import Dict, Optional


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
    return str(hazard.get("type")) in {"statue"}


__all__ = [
    "describe_hazard",
    "hazard_blocks_movement",
    "get_hazard_color",
    "get_hazard_symbol",
    "roll_hazard_room",
]

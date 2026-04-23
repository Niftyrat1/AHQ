"""Dungeon exploration actions."""

from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING
import random
from hazards import (
    get_hazard_anchor,
    get_room_for_hero,
    is_adjacent_or_same,
    resolve_chasm_leap,
    resolve_crypt_search,
    resolve_eat_mushroom,
    resolve_fight_bats,
    resolve_fight_rats,
    resolve_grate_room,
    resolve_mould_crossing,
    resolve_pool_drink,
    resolve_recruit_rogue,
    resolve_release_man_at_arms,
    resolve_rescue_maiden,
    resolve_statue_interaction,
    resolve_trapdoor_open,
)
from traps import get_pit_leap_destination, get_trap_marker

if TYPE_CHECKING:
    from dungeon import Dungeon
    from hero import Hero


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    message: str
    end_turn: bool = True
    trigger_combat: bool = False


class DungeonAction:
    """Base class for dungeon exploration actions."""
    
    name: str = "Action"
    icon: str = "?"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if this action is available for the hero."""
        return False
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Execute the action."""
        return ActionResult(False, "Not implemented")


class OpenDoorAction(DungeonAction):
    """Open an adjacent closed door."""
    
    name = "Open Door"
    icon = "🚪"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if adjacent to a closed door."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.DOOR_CLOSED:
                return True
        return False
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Open the door and generate what's beyond."""
        # Find adjacent closed door
        door_pos = None
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.DOOR_CLOSED:
                door_pos = (tx, ty)
                break
        
        if not door_pos:
            return ActionResult(False, "No closed door adjacent")
        
        # Check if combat was already active before opening
        was_in_combat = getattr(game, 'mode', 'DUNGEON') == 'COMBAT'
        
        # Open the door via game system (this may trigger combat)
        if game.open_door(door_pos[0], door_pos[1]):
            # Check if combat started as a result
            is_in_combat = getattr(game, 'mode', 'DUNGEON') == 'COMBAT'
            combat_started = is_in_combat and not was_in_combat
            
            return ActionResult(
                success=True,
                message=f"Opened door at {door_pos}",
                end_turn=True,
                trigger_combat=combat_started
            )
        return ActionResult(False, "Failed to open door")


class CloseDoorAction(DungeonAction):
    """Close an adjacent open door."""
    
    name = "Close Door"
    icon = "🔒"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if adjacent to an open door."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.DOOR_OPEN:
                return True
        return False
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Close the door."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.DOOR_OPEN:
                # Close the door
                dungeon.grid[(tx, ty)] = dungeon.TileType.DOOR_CLOSED
                if (tx, ty) in dungeon.doors:
                    dungeon.doors[(tx, ty)]["is_open"] = False
                return ActionResult(
                    success=True,
                    message=f"Closed door at ({tx}, {ty})",
                    end_turn=True
                )
        return ActionResult(False, "No open door to close")


class OpenChestAction(DungeonAction):
    """Open an adjacent closed treasure chest."""

    name = "Open Chest"
    icon = "C"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if adjacent to a closed chest."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.TREASURE_CLOSED:
                return True
        return False

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Open the chest and resolve trap/loot."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.TREASURE_CLOSED:
                message = game.open_treasure_chest(hero, tx, ty)
                return ActionResult(
                    success=True,
                    message=message,
                    end_turn=True,
                    trigger_combat=game.mode == "COMBAT",
                )
        return ActionResult(False, "No closed chest adjacent")


class LiftPortcullisAction(DungeonAction):
    """Lift a visible portcullis trap for the rest of the hero phase."""

    name = "Lift Portcullis"
    icon = "PC"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
            pos = (hero.x + dx, hero.y + dy)
            marker = get_trap_marker(dungeon, pos, "portcullis")
            if marker and marker.get("blocks_movement", False):
                return True
        return False

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
            pos = (hero.x + dx, hero.y + dy)
            marker = get_trap_marker(dungeon, pos, "portcullis")
            if marker and marker.get("blocks_movement", False):
                return ActionResult(
                    success=True,
                    message=game.lift_portcullis(hero, pos[0], pos[1]),
                    end_turn=True,
                )
        return ActionResult(False, "No portcullis nearby")


class LeapPitAction(DungeonAction):
    """Leap over an adjacent visible pit trap."""

    name = "Leap Pit"
    icon = "PT"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        return get_pit_leap_destination(hero, dungeon) is not None

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        leap = get_pit_leap_destination(hero, dungeon)
        if leap is None:
            return ActionResult(False, "No pit trap to leap")
        pit_pos, _landing = leap
        return ActionResult(
            success=True,
            message=game.leap_pit_trap(hero, pit_pos[0], pit_pos[1]),
            end_turn=True,
        )


class SearchSecretsAction(DungeonAction):
    """Search adjacent wall for secret doors."""
    
    name = "Search Secrets"
    icon = "🔍"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if adjacent to a wall that hasn't been searched."""
        # Get current room/section
        room_idx = getattr(hero, 'current_room_id', None)
        if room_idx is None:
            # Check if in a room
            for idx, room in enumerate(dungeon.rooms):
                if (hero.x, hero.y) in room.get('interior_tiles', set()):
                    room_idx = idx
                    break
        
        if room_idx is None:
            return False  # Not in a room or known section
        
        # Check if room has been searched for secrets
        room = dungeon.rooms[room_idx]
        if room and room.get('searched_secrets', False):
            return False  # Already searched this room
        
        # Check if adjacent to any wall
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.WALL:
                # Check if this specific wall was searched
                wall_key = (room_idx, tx, ty)
                searched_walls = room.get('searched_walls', set()) if room else set()
                if wall_key not in searched_walls:
                    return True
        return False
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Search for secret doors per WHQ rules (D12)."""
        # Find which room we're in
        room_idx = None
        for idx, room in enumerate(dungeon.rooms):
            if (hero.x, hero.y) in room.get('interior_tiles', set()):
                room_idx = idx
                break
        
        if room_idx is None:
            return ActionResult(False, "Must be in a room to search for secrets")
        
        room = dungeon.rooms[room_idx]
        
        # Find adjacent wall to search
        wall_pos = None
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.WALL:
                wall_key = (room_idx, tx, ty)
                searched_walls = room.get('searched_walls', set())
                if wall_key not in searched_walls:
                    wall_pos = (tx, ty)
                    break
        
        if not wall_pos:
            return ActionResult(False, "No unsearched walls adjacent")
        
        # Mark wall as searched
        if 'searched_walls' not in room:
            room['searched_walls'] = set()
        room['searched_walls'].add((room_idx, wall_pos[0], wall_pos[1]))
        
        # Roll D12 for secret door
        roll = random.randint(1, 12)
        
        if roll == 1:
            # GM may draw dungeon counter
            return ActionResult(
                success=True,
                message=f"Search roll: {roll}. GM may draw a dungeon counter.",
                end_turn=True
            )
        elif 2 <= roll <= 6:
            # No secret door
            return ActionResult(
                success=True,
                message=f"Search roll: {roll}. No secret door found.",
                end_turn=True
            )
        else:  # 7-12
            # Place secret door
            dungeon.grid[wall_pos] = dungeon.TileType.DOOR_CLOSED
            dungeon.doors[wall_pos] = {"is_open": False, "from_room": True}
            room['searched_secrets'] = True  # Mark room as searched
            return ActionResult(
                success=True,
                message=f"Search roll: {roll}. Secret door found at {wall_pos}!",
                end_turn=True
            )


class SearchTreasureAction(DungeonAction):
    """Search room for hidden treasure."""
    
    name = "Search Treasure"
    icon = "💰"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check if in a room that hasn't been searched for treasure."""
        for room in dungeon.rooms:
            if (hero.x, hero.y) in room.get('interior_tiles', set()):
                # Check if room has been searched for treasure
                if not room.get('searched_treasure', False):
                    return True
        return False
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Search for hidden treasure per WHQ rules (2D12)."""
        # Find which room we're in
        room_idx = None
        room_data = None
        for idx, room in enumerate(dungeon.rooms):
            if (hero.x, hero.y) in room.get('interior_tiles', set()):
                room_idx = idx
                room_data = room
                break
        
        if room_idx is None:
            return ActionResult(False, "Must be in a room to search for treasure")
        
        if room_data.get('searched_treasure', False):
            return ActionResult(False, "This room has already been searched")
        
        # Mark as searched
        room_data['searched_treasure'] = True
        
        # Roll 2D12
        roll1 = random.randint(1, 12)
        roll2 = random.randint(1, 12)
        total = roll1 + roll2
        
        if 2 <= total <= 6:
            # GM may draw dungeon counter
            return ActionResult(
                success=True,
                message=f"Treasure search roll: {total} ({roll1}+{roll2}). GM may draw a dungeon counter.",
                end_turn=True
            )
        elif 7 <= total <= 16:
            # No treasure
            return ActionResult(
                success=True,
                message=f"Treasure search roll: {total} ({roll1}+{roll2}). No hidden treasure.",
                end_turn=True
            )
        elif 17 <= total <= 23:
            # Gold cache: D6 × 5
            gold_roll = random.randint(1, 6)
            gold_amount = gold_roll * 5
            hero.gold += gold_amount
            game.gold_found += gold_amount
            return ActionResult(
                success=True,
                message=f"Treasure search roll: {total} ({roll1}+{roll2}). Found {gold_amount} gold coins!",
                end_turn=True
            )
        else:  # 24
            # Magical treasure - consult Magic Treasure Table
            return ActionResult(
                success=True,
                message=f"Treasure search roll: {total} ({roll1}+{roll2}). Found magical treasure! (Consult Magic Treasure Table)",
                end_turn=True
            )


class DrinkPoolAction(DungeonAction):
    """Drink from a hazard pool."""

    name = "Drink Pool"
    icon = "P"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "pool":
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to drink from the pool")
        return ActionResult(True, resolve_pool_drink(hero, room, game), end_turn=True)


class TakeRubyAction(DungeonAction):
    """Attempt to take the ruby from a statue hazard."""

    name = "Take Ruby"
    icon = "R"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "statue" or hazard.get("resolved"):
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to interact with the statue")
        return ActionResult(True, resolve_statue_interaction(hero, room, game), end_turn=True, trigger_combat=game.mode == "COMBAT")


class OpenTrapdoorAction(DungeonAction):
    """Open a trapdoor hazard."""

    name = "Open Trapdoor"
    icon = "T"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "trapdoor" or hazard.get("opened_result"):
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to open the trapdoor")
        return ActionResult(True, resolve_trapdoor_open(hero, room, game), end_turn=True, trigger_combat=game.mode == "COMBAT")


class SearchCryptAction(DungeonAction):
    """Search a crypt under an opened trapdoor."""

    name = "Search Crypt"
    icon = "C"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "trapdoor":
            return False
        if hazard.get("opened_result") != "crypt" or hazard.get("crypt_searched"):
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to search the crypt")
        return ActionResult(True, resolve_crypt_search(hero, room, game), end_turn=True, trigger_combat=game.mode == "COMBAT")


class FightRatsAction(DungeonAction):
    """Fight through a room full of rats."""

    name = "Fight Rats"
    icon = "RT"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "rats" and not hazard.get("resolved", False)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the rats room to fight them")
        return ActionResult(True, resolve_fight_rats(hero, room, game), end_turn=True)


class FightBatsAction(DungeonAction):
    """Fight through a room full of bats."""

    name = "Fight Bats"
    icon = "BT"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "bats" and not hazard.get("resolved", False)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the bats room to fight them")
        return ActionResult(True, resolve_fight_bats(hero, room, game), end_turn=True)


class CrossMouldAction(DungeonAction):
    """Cross a mould room with wet cloths."""

    name = "Cross Mould"
    icon = "MO"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "mould":
            return False
        crossed = set(hazard.get("crossed_heroes", []))
        return hero.id not in crossed

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the mould room to cross it")
        return ActionResult(True, resolve_mould_crossing(hero, room, game), end_turn=True)


class EatMushroomAction(DungeonAction):
    """Eat a mushroom from a mushroom hazard room."""

    name = "Eat Mushroom"
    icon = "MU"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "mushrooms"

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the mushroom room to eat one")
        return ActionResult(True, resolve_eat_mushroom(hero, room, game), end_turn=True)


class LeapChasmAction(DungeonAction):
    """Attempt a heroic leap across a chasm."""

    name = "Leap Chasm"
    icon = "CH"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "chasm":
            return False
        anchor = get_hazard_anchor(room)
        if anchor is None:
            return False
        dx = anchor[0] - hero.x
        dy = anchor[1] - hero.y
        if abs(dx) + abs(dy) != 1:
            return False
        landing = (anchor[0] + dx, anchor[1] + dy)
        return dungeon.is_walkable(*landing)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the chasm room to leap it")
        return ActionResult(True, resolve_chasm_leap(hero, room, game), end_turn=True)


class InspectGrateAction(DungeonAction):
    """Inspect and lift a grate hazard."""

    name = "Inspect Grate"
    icon = "GR"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "grate":
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the grate room to inspect it")
        return ActionResult(
            True,
            resolve_grate_room(room, game),
            end_turn=True,
            trigger_combat=game.mode == "COMBAT",
        )


class RescueMaidenAction(DungeonAction):
    """Rescue the maiden once her guards are defeated."""

    name = "Rescue Maiden"
    icon = "MD"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "non_player_character" and hazard.get("npc_type") == "maiden" and not hazard.get("rescued")

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the maiden's room")
        return ActionResult(True, resolve_rescue_maiden(room, game), end_turn=True)


class ReleaseManAtArmsAction(DungeonAction):
    """Release the man-at-arms once his guards are defeated."""

    name = "Release Man-at-Arms"
    icon = "MA"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "non_player_character" and hazard.get("npc_type") == "man_at_arms" and not hazard.get("rescued")

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the Man-at-Arms' room")
        return ActionResult(True, resolve_release_man_at_arms(room, game), end_turn=True)


class RecruitRogueAction(DungeonAction):
    """Accept the rogue's offer to travel with the party."""

    name = "Recruit Rogue"
    icon = "RG"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "non_player_character" and hazard.get("npc_type") == "rogue" and not hazard.get("joined")

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the Rogue's room")
        return ActionResult(True, resolve_recruit_rogue(room, game), end_turn=True)


def get_available_actions(hero: "Hero", dungeon: "Dungeon") -> List[type]:
    """Get list of available action classes for the hero."""
    if hero.is_under_gm_control():
        return []

    actions = []
    
    if OpenDoorAction.is_available(hero, dungeon):
        actions.append(OpenDoorAction)
    
    if CloseDoorAction.is_available(hero, dungeon):
        actions.append(CloseDoorAction)

    if OpenChestAction.is_available(hero, dungeon):
        actions.append(OpenChestAction)

    if LiftPortcullisAction.is_available(hero, dungeon):
        actions.append(LiftPortcullisAction)

    if LeapPitAction.is_available(hero, dungeon):
        actions.append(LeapPitAction)
    
    if SearchSecretsAction.is_available(hero, dungeon):
        actions.append(SearchSecretsAction)
    
    if SearchTreasureAction.is_available(hero, dungeon):
        actions.append(SearchTreasureAction)

    if DrinkPoolAction.is_available(hero, dungeon):
        actions.append(DrinkPoolAction)

    if TakeRubyAction.is_available(hero, dungeon):
        actions.append(TakeRubyAction)

    if OpenTrapdoorAction.is_available(hero, dungeon):
        actions.append(OpenTrapdoorAction)

    if SearchCryptAction.is_available(hero, dungeon):
        actions.append(SearchCryptAction)

    if FightRatsAction.is_available(hero, dungeon):
        actions.append(FightRatsAction)

    if FightBatsAction.is_available(hero, dungeon):
        actions.append(FightBatsAction)

    if CrossMouldAction.is_available(hero, dungeon):
        actions.append(CrossMouldAction)

    if EatMushroomAction.is_available(hero, dungeon):
        actions.append(EatMushroomAction)

    if LeapChasmAction.is_available(hero, dungeon):
        actions.append(LeapChasmAction)

    if InspectGrateAction.is_available(hero, dungeon):
        actions.append(InspectGrateAction)

    if RescueMaidenAction.is_available(hero, dungeon):
        actions.append(RescueMaidenAction)

    if ReleaseManAtArmsAction.is_available(hero, dungeon):
        actions.append(ReleaseManAtArmsAction)

    if RecruitRogueAction.is_available(hero, dungeon):
        actions.append(RecruitRogueAction)
    
    return actions

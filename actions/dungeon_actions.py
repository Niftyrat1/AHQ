"""Dungeon exploration actions."""

from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING
import random
from hazards import (
    choose_lower_room_entry_tile,
    choose_lower_room_exit_tile,
    get_hazard_anchor,
    get_lower_room_for_hero,
    get_room_for_hero,
    is_adjacent_or_same,
    lower_room_entry_available,
    lower_room_exit_available,
    resolve_chasm_leap,
    resolve_chasm_sensible_leap,
    resolve_build_chasm_rope_ladder,
    resolve_cross_chasm_rope_ladder,
    resolve_crypt_search,
    resolve_eat_mushroom,
    resolve_fight_bats,
    resolve_fight_rats,
    resolve_flames_of_death_hazard,
    resolve_grate_room,
    resolve_enter_lower_room,
    resolve_leave_lower_room,
    resolve_mould_crossing,
    resolve_pool_drink,
    resolve_use_greek_fire,
    resolve_use_rat_poison,
    resolve_use_screetch_bug,
    resolve_recruit_rogue,
    resolve_release_man_at_arms,
    resolve_rescue_maiden,
    resolve_statue_interaction,
    resolve_trapdoor_open,
)
from magic_treasure import generate_magic_treasure
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


ORTHOGONAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _normalize_pos_list(positions) -> set[Tuple[int, int]]:
    """Convert room position containers into a tuple set."""
    return {
        (int(pos[0]), int(pos[1]))
        for pos in positions or []
        if isinstance(pos, (list, tuple)) and len(pos) == 2
    }


def _get_room_interior(room: dict) -> set[Tuple[int, int]]:
    """Return a room's interior tiles as tuples."""
    interior = room.get("interior_tiles", set())
    if isinstance(interior, set):
        return set(interior)
    return _normalize_pos_list(interior)


def _get_room_entrance(room: dict) -> Optional[Tuple[int, int]]:
    """Return the recorded entrance door position for a room."""
    entrance = room.get("entrance")
    if isinstance(entrance, list) and len(entrance) == 2:
        return (int(entrance[0]), int(entrance[1]))
    if isinstance(entrance, tuple) and len(entrance) == 2:
        return (int(entrance[0]), int(entrance[1]))
    return None


def _find_room_containing(hero: "Hero", dungeon: "Dungeon") -> Optional[dict]:
    """Return the room currently containing the hero."""
    return dungeon.find_room_for_tile(hero.x, hero.y)


def _get_room_doors(dungeon: "Dungeon", room: dict) -> set[Tuple[int, int]]:
    """Return door positions bordering a room interior."""
    interior = _get_room_interior(room)
    room_doors = set()
    for door_pos in dungeon.doors:
        if any(
            (door_pos[0] + dx, door_pos[1] + dy) in interior
            for dx, dy in ORTHOGONAL_DIRECTIONS
        ):
            room_doors.add(door_pos)
    return room_doors


def _room_allows_secret_search(dungeon: "Dungeon", room: dict) -> bool:
    """Room is legal for secret-door searching only if it has the entrance door and no others."""
    entrance = _get_room_entrance(room)
    if entrance is None:
        return False
    extra_doors = _get_room_doors(dungeon, room) - {entrance}
    return not extra_doors


def _get_corridor_section_tiles(hero: "Hero", dungeon: "Dungeon") -> set[Tuple[int, int]]:
    """Return the connected explored corridor section containing the hero."""
    start = (hero.x, hero.y)
    corridor_tiles = {dungeon.TileType.FLOOR, dungeon.TileType.PASSAGE_END}
    if dungeon.get_tile(*start) not in corridor_tiles:
        return set()

    section = set()
    frontier = [start]
    while frontier:
        pos = frontier.pop()
        if pos in section:
            continue
        if dungeon.get_tile(*pos) not in corridor_tiles:
            continue
        if dungeon.find_room_for_tile(*pos) is not None:
            continue
        section.add(pos)
        for dx, dy in ORTHOGONAL_DIRECTIONS:
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt not in section:
                frontier.append(nxt)
    return section


def _get_dead_end_search_context(hero: "Hero", dungeon: "Dungeon") -> Optional[dict]:
    """Return dead-end search metadata if the hero is in a searchable dead end."""
    section = _get_corridor_section_tiles(hero, dungeon)
    if not section:
        return None
    if not any(dungeon.get_tile(*pos) == dungeon.TileType.PASSAGE_END for pos in section):
        return None
    xs = {pos[0] for pos in section}
    ys = {pos[1] for pos in section}
    orientation = None
    if len(xs) > len(ys):
        orientation = "horizontal"
    elif len(ys) > len(xs):
        orientation = "vertical"
    return {"section": section, "orientation": orientation}


def _hero_started_turn_in_search_area(hero: "Hero", dungeon: "Dungeon", game) -> bool:
    """Check the AHQ requirement that secret searches start the turn in the same area."""
    start = game.hero_turn_start_positions.get(hero.id)
    if start is None:
        return False

    room = _find_room_containing(hero, dungeon)
    if room is not None:
        return start in _get_room_interior(room)

    dead_end = _get_dead_end_search_context(hero, dungeon)
    if dead_end is None:
        return False
    return start in dead_end["section"]


def _is_searchable_dead_end_wall(hero: "Hero", wall_pos: Tuple[int, int], orientation: Optional[str]) -> bool:
    """Dead-end secret-door searches only work on the long side walls."""
    if orientation == "horizontal":
        return wall_pos[1] != hero.y
    if orientation == "vertical":
        return wall_pos[0] != hero.x
    return True


def _get_secret_searchable_walls(hero: "Hero", dungeon: "Dungeon") -> List[Tuple[int, int]]:
    """Return adjacent wall tiles that can legally be searched for secret doors."""
    room = _find_room_containing(hero, dungeon)
    if room is not None:
        if not _room_allows_secret_search(dungeon, room):
            return []
        candidate_starts = {(hero.x, hero.y)}
        allowed_wall = lambda pos: True
    else:
        dead_end = _get_dead_end_search_context(hero, dungeon)
        if dead_end is None:
            return []
        candidate_starts = set(dead_end["section"])
        allowed_wall = lambda pos: _is_searchable_dead_end_wall(hero, pos, dead_end["orientation"])

    searchable = set()
    for start_x, start_y in candidate_starts:
        for dx, dy in ORTHOGONAL_DIRECTIONS:
            wall_pos = (start_x + dx, start_y + dy)
            if dungeon.get_tile(*wall_pos) != dungeon.TileType.WALL:
                continue
            if wall_pos in getattr(dungeon, "secret_door_searches", set()):
                continue
            if not allowed_wall(wall_pos):
                continue
            searchable.add(wall_pos)
    return sorted(searchable)


def _resolve_secret_search_roll(hero: "Hero", dungeon: "Dungeon", game, wall_pos: Tuple[int, int]) -> ActionResult:
    """Resolve the actual AHQ secret-door search roll against a chosen wall section."""
    dungeon.secret_door_searches.add(wall_pos)

    roll = random.randint(1, 12)
    if roll == 1:
        game._draw_dungeon_counter("Searching for secret doors.")
        return ActionResult(
            success=True,
            message=f"Search roll: {roll}. The wall holds no secret door.",
            end_turn=True
        )
    if 2 <= roll <= 6:
        return ActionResult(
            success=True,
            message=f"Search roll: {roll}. No secret door found.",
            end_turn=True
        )

    dungeon.grid[wall_pos] = dungeon.TileType.DOOR_CLOSED
    dungeon.doors[wall_pos] = {"is_open": False, "from_room": True}
    return ActionResult(
        success=True,
        message=f"Search roll: {roll}. Secret door found at {wall_pos}!",
        end_turn=True
    )


def resolve_pending_secret_search(hero: "Hero", dungeon: "Dungeon", game, wall_pos: Tuple[int, int]) -> str:
    """Resolve a board-targeted secret-door search choice."""
    if not _hero_started_turn_in_search_area(hero, dungeon, game):
        game.pending_board_action = None
        return "A hero must start the exploration turn in the same room or dead end to search for secret doors."

    wall_options = set(_get_secret_searchable_walls(hero, dungeon))
    if wall_pos not in wall_options:
        return "Choose a searchable wall section."

    result = _resolve_secret_search_roll(hero, dungeon, game, wall_pos)
    game.pending_board_action = None
    if result.end_turn:
        game.hero_movement_remaining[hero.id] = 0
    if result.trigger_combat:
        game.current_phase = "COMBAT"
        game.mode = "COMBAT"
    game.save_game()
    return result.message


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


class CollectChestTreasureAction(DungeonAction):
    """Collect recorded left-behind treasure from an adjacent tile."""

    name = "Collect Treasure"
    icon = "$"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            tx, ty = hero.x + dx, hero.y + dy
            if dungeon.get_tile(tx, ty) == dungeon.TileType.TREASURE_OPEN:
                room = dungeon.find_room_for_tile(hero.x, hero.y)
                if room and int(room.get("left_behind_gold", 0)) > 0:
                    return True
                game_state = getattr(dungeon, "game_state", None)
                if game_state and game_state.get_left_behind_treasure_at((tx, ty)):
                    return True
        return False

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        for dx, dy in ORTHOGONAL_DIRECTIONS + [(0, 0)]:
            tx, ty = hero.x + dx, hero.y + dy
            if game.get_left_behind_treasure_at((tx, ty)):
                return ActionResult(
                    success=True,
                    message=game.collect_left_behind_treasure_at(hero, (tx, ty)),
                    end_turn=True,
                )
        return ActionResult(False, "No opened chest with treasure nearby")


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


class DisarmTrapAction(DungeonAction):
    """Disarm an adjacent visible trap."""

    name = "Disarm Trap"
    icon = "DT"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        for dx, dy in ORTHOGONAL_DIRECTIONS + [(0, 0)]:
            pos = (hero.x + dx, hero.y + dy)
            marker = dungeon.trap_markers.get(pos)
            if marker and marker.get("type") == "visible_trap_zone" and marker.get("disarm_chance") is not None:
                return True
        return False

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        for dx, dy in ORTHOGONAL_DIRECTIONS + [(0, 0)]:
            pos = (hero.x + dx, hero.y + dy)
            marker = dungeon.trap_markers.get(pos)
            if marker and marker.get("type") == "visible_trap_zone" and marker.get("disarm_chance") is not None:
                return ActionResult(
                    success=True,
                    message=game.disarm_visible_trap(hero, pos[0], pos[1]),
                    end_turn=True,
                    trigger_combat=game.mode == "COMBAT",
                )
        return ActionResult(False, "No visible trap nearby")


class SearchSecretsAction(DungeonAction):
    """Search adjacent wall for secret doors."""
    
    name = "Search Secrets"
    icon = "🔍"
    
    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        """Check whether the hero is in a legal search area with an unsearched wall."""
        return bool(_get_secret_searchable_walls(hero, dungeon))
    
    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        """Search for secret doors using the AHQ exploration rules."""
        if not _hero_started_turn_in_search_area(hero, dungeon, game):
            return ActionResult(False, "A hero must start the exploration turn in the same room or dead end to search for secret doors.")

        wall_options = _get_secret_searchable_walls(hero, dungeon)
        if not wall_options:
            return ActionResult(False, "Secret-door searches are only allowed in dead ends or rooms with only the entrance door.")
        if len(wall_options) > 1:
            game.pending_board_action = {
                "type": "secret_door_search",
                "hero_id": hero.id,
                "wall_positions": [[x, y] for x, y in wall_options],
            }
            return ActionResult(True, "Choose a wall section to search for a secret door.", end_turn=False)

        return _resolve_secret_search_roll(hero, dungeon, game, wall_options[0])


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
        """Search for hidden treasure using the AHQ table."""
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
            game._draw_dungeon_counter("Hidden treasure search.")
            return ActionResult(
                success=True,
                message=f"Treasure search roll: {total} ({roll1}+{roll2}). No hidden treasure.",
                end_turn=True
            )
        elif 7 <= total <= 16:
            # Gold cache: D6 × 5
            gold_roll = random.randint(1, 6)
            gold_amount = gold_roll * 5
            awarded, left = game.award_party_gold(gold_amount, "hidden treasure", note_pos=(hero.x, hero.y))
            return ActionResult(
                success=True,
                message=(
                    f"Treasure search roll: {total} ({roll1}+{roll2}). "
                    f"Found {awarded} gold coins!"
                    + (f" {left} must be left behind." if left > 0 else "")
                ),
                end_turn=True
            )
        else:  # 17-24
            treasure_log: List[str] = []
            item = generate_magic_treasure(
                hero,
                treasure_log,
                game=game,
                source="hidden treasure",
                note_pos=(hero.x, hero.y),
            )
            for entry in treasure_log:
                game.combat_log.append(entry)
            game.hero_manager.update_hero(hero)
            return ActionResult(
                success=True,
                message=(
                    f"Treasure search roll: {total} ({roll1}+{roll2}). "
                    f"Found magical treasure: {item.get('name', 'Unknown')}."
                ),
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


class EnterMazeSubLevelAction(DungeonAction):
    """Enter a Heroquest maze sub-level opened by a trapdoor."""

    name = "Enter Maze"
    icon = "MZ"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "trapdoor" or hazard.get("opened_result") != "maze":
            return False
        if not hazard.get("maze_sub_level_available") or hazard.get("maze_sub_level_entered"):
            return False
        return is_adjacent_or_same(hero, get_hazard_anchor(room), dungeon)

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to enter the maze")
        return ActionResult(True, game.enter_heroquest_maze_sub_level(hero, room), end_turn=True)


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


class RatPoisonAction(DungeonAction):
    """Use Rat Poison to clear a rats hazard room."""

    name = "Use Rat Poison"
    icon = "RP"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "rats" and not hazard.get("resolved", False) and hero.get_inventory_count("rat_poison") > 0

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the rats room to use Rat Poison")
        return ActionResult(True, resolve_use_rat_poison(hero, room, game), end_turn=True)


class GreekFireAction(DungeonAction):
    """Use Greek Fire to clear certain hazard rooms."""

    name = "Use Greek Fire"
    icon = "GF"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        hazard_type = hazard.get("type")
        if hazard_type not in {"rats", "bats", "mould"} or hazard.get("resolved", False):
            return False
        needed = 2 if hazard_type in {"rats", "bats"} else 1
        return hero.get_inventory_count("greek_fire_flask") >= needed

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to use Greek Fire")
        return ActionResult(True, resolve_use_greek_fire(hero, room, game), end_turn=True)


class FlamesOfDeathHazardAction(DungeonAction):
    """Use Flames of Death to clear rats or bats."""

    name = "Flames of Death"
    icon = "FD"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") not in {"rats", "bats"} or hazard.get("resolved", False):
            return False
        return hero.is_wizard() and hero.can_cast_spells() and hero.knows_spell("Flames of Death") and (
            hero.free_spell_cast > 0 or hero.has_spell_components("Flames of Death")
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the hazard room to cast Flames of Death")
        return ActionResult(True, resolve_flames_of_death_hazard(hero, room, game), end_turn=True)


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


class ScreetchBugAction(DungeonAction):
    """Use a Screetch Bug to clear a bats hazard room."""

    name = "Use Screetch Bug"
    icon = "SB"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return hazard.get("type") == "bats" and not hazard.get("resolved", False) and hero.get_inventory_count("screetch_bug") > 0

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the bats room to use a Screetch Bug")
        return ActionResult(True, resolve_use_screetch_bug(hero, room, game), end_turn=True)


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


class SensibleLeapChasmAction(DungeonAction):
    """Attempt a rope-secured leap across a chasm."""

    name = "Sensible Leap"
    icon = "RL"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "chasm" or hazard.get("rope_ladder_built"):
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
            return ActionResult(False, "Must be in the chasm room to make a sensible leap")
        return ActionResult(True, resolve_chasm_sensible_leap(hero, room, game), end_turn=True)


class BuildChasmRopeLadderAction(DungeonAction):
    """Build a rope ladder across a chasm."""

    name = "Build Rope Ladder"
    icon = "LD"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        return (
            hazard.get("type") == "chasm"
            and hazard.get("sensible_leap_success", False)
            and not hazard.get("rope_ladder_built", False)
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the chasm room to build a rope ladder")
        return ActionResult(True, resolve_build_chasm_rope_ladder(hero, room, game), end_turn=True)


class CrossChasmRopeLadderAction(DungeonAction):
    """Cross a completed rope ladder across a chasm."""

    name = "Cross Rope Ladder"
    icon = "LD"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        if not room or room.get("room_kind") != "hazard":
            return False
        hazard = room.get("hazard") or {}
        if hazard.get("type") != "chasm" or not hazard.get("rope_ladder_built", False):
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
            return ActionResult(False, "Must be in the chasm room to cross the rope ladder")
        return ActionResult(True, resolve_cross_chasm_rope_ladder(hero, room, game), end_turn=True)


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


class EnterLowerRoomAction(DungeonAction):
    """Climb down into a revealed lower room."""

    name = "Enter Lower Room"
    icon = "DN"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_room_for_hero(hero, dungeon)
        game_state = getattr(dungeon, "game_state", None)
        if not room or game_state is None:
            return False
        allowed, _ = lower_room_entry_available(hero, room, game_state)
        return allowed and choose_lower_room_entry_tile(hero, room, game_state) is not None

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be by the grate or trapdoor opening")
        landing = choose_lower_room_entry_tile(hero, room, game)
        return ActionResult(True, resolve_enter_lower_room(hero, room, game, landing=landing), end_turn=True)


class LeaveLowerRoomAction(DungeonAction):
    """Climb out of a lower room."""

    name = "Leave Lower Room"
    icon = "UP"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        room = get_lower_room_for_hero(hero, dungeon)
        game_state = getattr(dungeon, "game_state", None)
        if not room or game_state is None:
            return False
        allowed, _ = lower_room_exit_available(hero, room, game_state)
        return allowed and choose_lower_room_exit_tile(hero, room, game_state) is not None

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        room = get_lower_room_for_hero(hero, dungeon)
        if not room:
            return ActionResult(False, "Must be in the lower room")
        landing = choose_lower_room_exit_tile(hero, room, game)
        return ActionResult(True, resolve_leave_lower_room(hero, room, game, landing=landing), end_turn=True)


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


class RemoveArmourAction(DungeonAction):
    """Remove currently worn armour and shields."""

    name = "Remove Armour"
    icon = "AR-"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        return any(
            item.get("equipped") and item.get("type") in {"armour", "armor", "shield"}
            for item in hero.equipment
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        removed = []
        for item in hero.equipment:
            if item.get("equipped") and item.get("type") in {"armour", "armor", "shield"}:
                item["equipped"] = False
                removed.append(str(item.get("name", "gear")))
        if not removed:
            return ActionResult(False, "No armour is currently being worn.")
        return ActionResult(True, f"{hero.name} removes {', '.join(removed)}.", end_turn=True)


class PutOnArmourAction(DungeonAction):
    """Put on carried armour and shields."""

    name = "Put On Armour"
    icon = "AR+"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        if not hero.can_wear_armour():
            return False
        return any(
            (not item.get("equipped")) and item.get("type") in {"armour", "armor", "shield"}
            for item in hero.equipment
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        if not hero.can_wear_armour():
            return ActionResult(False, f"{hero.name} cannot wear armour.")
        equipped = []
        for item in hero.equipment:
            if (not item.get("equipped")) and item.get("type") in {"armour", "armor", "shield"}:
                item["equipped"] = True
                equipped.append(str(item.get("name", "gear")))
        if not equipped:
            return ActionResult(False, "No armour is available to put on.")
        return ActionResult(True, f"{hero.name} puts on {', '.join(equipped)}.", end_turn=True)


class DrinkHealingPotionAction(DungeonAction):
    """Drink a healing potion during exploration."""

    name = "Drink Healing Potion"
    icon = "HP"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        return (
            (not hero.is_ko)
            and hero.has_usable_healing_potion()
            and hero.current_wounds < hero.max_wounds
            and not hero.has_pending_healing_potion()
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        return ActionResult(True, game.drink_healing_potion(hero), end_turn=True)


class DrinkStrengthPotionAction(DungeonAction):
    """Drink a strength potion at the start of an exploration turn."""

    name = "Drink Strength Potion"
    icon = "SP"

    @classmethod
    def is_available(cls, hero: "Hero", dungeon: "Dungeon") -> bool:
        game_state = getattr(dungeon, "game_state", None)
        if game_state is not None:
            allowed, _ = game_state.can_drink_strength_potion(hero)
            return allowed
        return any(
            item.get("type") == "potion" and item.get("potion_effect") == "strength"
            for item in hero.equipment
        )

    @classmethod
    def execute(cls, hero: "Hero", dungeon: "Dungeon", game) -> ActionResult:
        allowed, message = game.can_drink_strength_potion(hero)
        if not allowed:
            return ActionResult(False, message)
        return ActionResult(True, game.drink_strength_potion(hero), end_turn=False)



def get_available_actions(hero: "Hero", dungeon: "Dungeon") -> List[type]:
    """Get list of available action classes for the hero."""
    if hero.is_under_gm_control() or hero.is_restrained_by_mindstealer():
        return []
    game_state = getattr(dungeon, "game_state", None)
    if game_state is not None:
        game_state.ensure_phase_consistency()
        if game_state.current_phase == "EXPLORATION":
            game_state._enter_combat_if_monsters_visible()
        if game_state.has_pending_fate_decision():
            return []
        if game_state.current_phase != "EXPLORATION":
            return []
        if game_state.hero_movement_remaining.get(hero.id, 0) <= 0:
            return []

    actions = []
    
    if OpenDoorAction.is_available(hero, dungeon):
        actions.append(OpenDoorAction)
    
    if CloseDoorAction.is_available(hero, dungeon):
        actions.append(CloseDoorAction)

    if OpenChestAction.is_available(hero, dungeon):
        actions.append(OpenChestAction)

    if CollectChestTreasureAction.is_available(hero, dungeon):
        actions.append(CollectChestTreasureAction)

    if LiftPortcullisAction.is_available(hero, dungeon):
        actions.append(LiftPortcullisAction)

    if LeapPitAction.is_available(hero, dungeon):
        actions.append(LeapPitAction)

    if DisarmTrapAction.is_available(hero, dungeon):
        actions.append(DisarmTrapAction)
    
    if SearchSecretsAction.is_available(hero, dungeon):
        actions.append(SearchSecretsAction)
    
    if SearchTreasureAction.is_available(hero, dungeon):
        actions.append(SearchTreasureAction)

    if RemoveArmourAction.is_available(hero, dungeon):
        actions.append(RemoveArmourAction)

    if PutOnArmourAction.is_available(hero, dungeon):
        actions.append(PutOnArmourAction)

    if DrinkHealingPotionAction.is_available(hero, dungeon):
        actions.append(DrinkHealingPotionAction)

    if DrinkStrengthPotionAction.is_available(hero, dungeon):
        actions.append(DrinkStrengthPotionAction)


    if DrinkPoolAction.is_available(hero, dungeon):
        actions.append(DrinkPoolAction)

    if TakeRubyAction.is_available(hero, dungeon):
        actions.append(TakeRubyAction)

    if OpenTrapdoorAction.is_available(hero, dungeon):
        actions.append(OpenTrapdoorAction)

    if SearchCryptAction.is_available(hero, dungeon):
        actions.append(SearchCryptAction)

    if EnterMazeSubLevelAction.is_available(hero, dungeon):
        actions.append(EnterMazeSubLevelAction)

    if FightRatsAction.is_available(hero, dungeon):
        actions.append(FightRatsAction)

    if RatPoisonAction.is_available(hero, dungeon):
        actions.append(RatPoisonAction)

    if GreekFireAction.is_available(hero, dungeon):
        actions.append(GreekFireAction)

    if FlamesOfDeathHazardAction.is_available(hero, dungeon):
        actions.append(FlamesOfDeathHazardAction)

    if FightBatsAction.is_available(hero, dungeon):
        actions.append(FightBatsAction)

    if ScreetchBugAction.is_available(hero, dungeon):
        actions.append(ScreetchBugAction)

    if CrossMouldAction.is_available(hero, dungeon):
        actions.append(CrossMouldAction)

    if EatMushroomAction.is_available(hero, dungeon):
        actions.append(EatMushroomAction)

    if LeapChasmAction.is_available(hero, dungeon):
        actions.append(LeapChasmAction)

    if SensibleLeapChasmAction.is_available(hero, dungeon):
        actions.append(SensibleLeapChasmAction)

    if BuildChasmRopeLadderAction.is_available(hero, dungeon):
        actions.append(BuildChasmRopeLadderAction)

    if CrossChasmRopeLadderAction.is_available(hero, dungeon):
        actions.append(CrossChasmRopeLadderAction)

    if InspectGrateAction.is_available(hero, dungeon):
        actions.append(InspectGrateAction)

    if EnterLowerRoomAction.is_available(hero, dungeon):
        actions.append(EnterLowerRoomAction)

    if LeaveLowerRoomAction.is_available(hero, dungeon):
        actions.append(LeaveLowerRoomAction)

    if RescueMaidenAction.is_available(hero, dungeon):
        actions.append(RescueMaidenAction)

    if ReleaseManAtArmsAction.is_available(hero, dungeon):
        actions.append(ReleaseManAtArmsAction)

    if RecruitRogueAction.is_available(hero, dungeon):
        actions.append(RecruitRogueAction)
    
    return actions

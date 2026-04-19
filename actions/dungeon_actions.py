"""Dungeon exploration actions."""

from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING
import random

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


def get_available_actions(hero: "Hero", dungeon: "Dungeon") -> List[type]:
    """Get list of available action classes for the hero."""
    actions = []
    
    if OpenDoorAction.is_available(hero, dungeon):
        actions.append(OpenDoorAction)
    
    if CloseDoorAction.is_available(hero, dungeon):
        actions.append(CloseDoorAction)
    
    if SearchSecretsAction.is_available(hero, dungeon):
        actions.append(SearchSecretsAction)
    
    if SearchTreasureAction.is_available(hero, dungeon):
        actions.append(SearchTreasureAction)
    
    return actions

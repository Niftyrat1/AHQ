"""
Tile types for Advanced HeroQuest dungeon.
"""
from enum import Enum, auto


class TileType(Enum):
    """Types of dungeon tiles."""
    UNEXPLORED = auto()
    FLOOR = auto()
    WALL = auto()
    DOOR_CLOSED = auto()
    DOOR_OPEN = auto()
    PASSAGE_END = auto()
    STAIRS_DOWN = auto()
    STAIRS_OUT = auto()
    TREASURE_CLOSED = auto()
    TREASURE_OPEN = auto()
    PIT_TRAP = auto()

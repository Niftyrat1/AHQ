"""
Dungeon generation logic for Advanced HeroQuest.

Refactored into separate modules:
- passages.py: generate_passage_from()
- passage_ends.py: resolve_passage_end() and passage end types
- rooms.py: generate_room() and room logic

This file maintains backward compatibility by re-exporting from submodules.
"""
from typing import List, Tuple

# Import and re-export for backward compatibility
from .passages import generate_passage_from
from .passage_ends import resolve_passage_end as _resolve_passage_end
from .rooms import generate_room as _generate_room

__all__ = ['generate_passage_from', '_resolve_passage_end', '_generate_room']

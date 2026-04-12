# AHQ Project Architecture

## Key facts Cascade must know before editing

- Dungeon grid uses (x, y) tuples as keys, NOT strings
- `pending_junctions` maps (x,y) -> list of direction tuples
- `explored` is a set of (x,y) tuples — tiles the player can SEE
- `rooms` is a list of sets — used for whole-room reveal on entry
- TILE_SIZE = 24px. Camera is in grid coords, not pixels.
- `check_and_generate_junction` must NOT be defined at module level
- `Set` must be imported from typing before use in type hints
- `wandering_monsters` is a set on Dungeon, serialised in to_dict/from_dict

## Project Structure

```
dungeon/
    __init__.py       # Re-exports Dungeon, TileType
    tiles.py          # TileType enum only (~20 lines)
    generator.py      # All generation logic (~300 lines)
    dungeon.py        # Core Dungeon class (~200 lines)
```

## Common bugs to avoid

- Never define a method both inside and outside the class
- Never set `door_info = self.doors[(x,y)] = True` — this sets to bool not dict
- `_is_room_wall` must exist before `check_and_generate_junction` calls it
- Path checking must use BFS not naive x-then-y stepping (diagonal gaps)
- Always check for existing passage floor when generating to prevent crossings

## Interface Contracts

### generator.py public functions:
- `generate_passage_from(dungeon, x, y, direction, auto_explore) -> List[Tuple[int, int]]`
- `_generate_room(dungeon, door_x, door_y, entrance_dir, from_passage) -> None`
- `_resolve_passage_end(dungeon, x, y, direction, roll) -> None`
- `_place_monsters_in_room(dungeon, room_tiles, encounter_type) -> None`

### dungeon.py key methods:
- `check_and_generate_junction(x, y) -> bool`
- `_explore_from(x, y) -> None`
- `open_door(x, y) -> bool`
- `to_dict() / from_dict(data)` for serialization

## Logging

The Dungeon class takes an optional `debug_log` list parameter. When provided:
- `dungeon._log(msg)` appends to the list and prints to console
- Game passes `self.dungeon_debug_log` to capture dungeon logs
- Logs are displayed in combat log with `[D]` prefix

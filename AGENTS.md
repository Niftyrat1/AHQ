# AHQ Project Architecture

## Key facts Cascade must know before editing

- Dungeon grid uses (x, y) tuples as keys, NOT strings
- `pending_junctions` maps (x,y) -> list of direction tuples
- `explored` is a set of (x,y) tuples — tiles the player can SEE
- `rooms` currently stores room metadata dicts, not plain sets
- Room dicts currently include `interior_tiles`, search flags, dimensions, origin data, `room_kind`, and optional hazard metadata
- Whole-room reveal and room-scoped logic must use the room tile fields, not `if pos in room`
- TILE_SIZE = 24px. Camera is in grid coords, not pixels.
- `check_and_generate_junction` must NOT be defined at module level
- `Set` must be imported from typing before use in type hints
- `wandering_monsters` is a set on Dungeon, serialised in to_dict/from_dict
- `rooms` must be serialised once room state becomes authoritative for reveal, search, and combat placement
- Trap rules live in `traps.py`; hazard tables and room hazard metadata live in `hazards.py`

## Project Structure

```
dungeon/
    __init__.py       # Re-exports Dungeon, TileType
    tiles.py          # TileType enum only (~20 lines)
    generator.py      # Backward-compatible re-exports
    passages.py       # Passage generation logic
    passage_ends.py   # Passage-end resolution
    rooms.py          # Room generation and room metadata
    dungeon.py        # Core Dungeon class
hazards.py           # Hazard-room tables and metadata helpers
traps.py             # Trap tables and trap resolution
```

## Common bugs to avoid

- Never define a method both inside and outside the class
- Never set `door_info = self.doors[(x,y)] = True` — this sets to bool not dict
- `_is_room_wall` must exist before `check_and_generate_junction` calls it
- Path checking must use BFS not naive x-then-y stepping (diagonal gaps)
- Always check for existing passage floor when generating to prevent crossings
- Keep room handling consistent across reveal, save/load, combat placement, and room actions
- If you change room storage shape, update `dungeon.py`, `rooms.py`, `game.py`, and `actions/dungeon_actions.py` together
- Keep the AHQ trap/hazard tables centralised in `traps.py` and `hazards.py`, not duplicated in UI/game code

## Interface Contracts

### passages.py public functions:
- `generate_passage_from(dungeon, x, y, direction, from_room=False) -> List[Tuple[int, int]]`

### rooms.py public functions:
- `generate_room(dungeon, door_x, door_y, entrance_dir, from_passage=False) -> bool | None`

### passage_ends.py public functions:
- `resolve_passage_end(dungeon, left_pos, right_pos, direction, roll) -> None`

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

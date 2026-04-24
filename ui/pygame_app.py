"""Primary pygame-ce frontend for AHQ."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pygame

from actions import get_available_actions
from game import GameState
from gm import find_path_bfs
from hero import Hero, roll_hero_race, roll_hero_stats, roll_starting_gold
from monster import Monster


LEFT_PANEL_WIDTH = 220
RIGHT_PANEL_WIDTH = 280
PANEL_GAP = 20
BOARD_TOP = 72
TILE_SIZE = 28
CAMERA_STEP = 3

BG = (16, 17, 23)
PANEL = (31, 34, 43)
PANEL_ALT = (41, 45, 56)
OVERLAY = (9, 10, 15, 210)
TEXT = (232, 232, 236)
MUTED = (166, 169, 180)
ACCENT = (210, 177, 83)
GREEN = (62, 137, 89)
BLUE = (78, 111, 168)
PURPLE = (126, 101, 170)
RED = (184, 72, 72)
GOLD = (195, 154, 67)
BLACK = (9, 10, 15)

RANDOM_FIRST_NAMES = [
    "Aldric", "Borin", "Cedric", "Doran", "Eldar", "Fenris", "Gareth", "Halric",
    "Ivan", "Jorah", "Kael", "Loric", "Magnus", "Norrin", "Orik", "Perrin",
    "Quint", "Ragnar", "Soren", "Thorin", "Ulric", "Varian", "Wulfric", "Xander",
    "Yorick", "Zane", "Aeliana", "Brianna", "Cassandra", "Diana", "Elara", "Fiona",
]
RANDOM_LAST_NAMES = [
    "Ironheart", "Stormbreaker", "Doomsayer", "Swiftblade", "Stonefist",
    "Shadowbane", "Fireborn", "Frostwind", "Thunderaxe", "Dragonbane",
    "Steelguard", "Ravenwood", "Blackwood", "Silverhand", "Goldmane",
    "Brightsword", "Darkhollow", "Wolfheart", "Eagleeye", "Bearclaw",
]


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    enabled: bool = True
    payload: Any = None


@dataclass
class CreationState:
    race: Optional[str] = None
    class_type: str = "Warrior"
    stats: Optional[Dict[str, int]] = None
    gold: int = 0
    name: str = ""
    equipment: Optional[List[Dict[str, Any]]] = None


class PygameApp:
    """pygame-ce application shell for the AHQ rules engine."""

    def __init__(self):
        pygame.init()
        display_info = pygame.display.Info()
        current_w = getattr(display_info, "current_w", 0) or 1600
        current_h = getattr(display_info, "current_h", 0) or 1000
        max_w = max(1280, current_w - 120)
        max_h = max(800, current_h - 120)
        self.window_width = min(1600, max_w)
        self.window_height = min(1000, max_h)
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("Advanced HeroQuest")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 15)
        self.title_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 30, bold=True)

        self.game = GameState()
        self.running = True
        self.current_screen = "tavern"
        self.roster: List[Hero] = []
        self.party_ids: List[str] = []
        self.selected_hero_id: Optional[str] = None
        self.message = "pygame-ce frontend active."
        self.last_log_index = 0
        self.log_scroll_lines = 0
        self.camera_x = 0
        self.camera_y = 0
        self.map_overlay_open = False
        self.buttons: List[Button] = []
        self.action_buttons: List[Button] = []
        self.modal_buttons: List[Button] = []
        self.creation_state: Optional[CreationState] = None
        self.typing_target: Optional[str] = None
        self.pending_spell: Optional[Dict[str, Any]] = None
        self.movement_preview_hero_id: Optional[str] = None
        self.tables = self._load_tables()

        self._refresh_roster()
        if self.game.has_save_game():
            self.message = "Save game found. Use Continue Save or press C."

    def _layout(self) -> Dict[str, pygame.Rect]:
        """Return the current window layout derived from the live window size."""
        width, height = self.screen.get_size()
        self.window_width, self.window_height = width, height
        left_panel = pygame.Rect(20, 72, LEFT_PANEL_WIDTH, max(400, height - 110))
        right_panel = pygame.Rect(width - RIGHT_PANEL_WIDTH - 20, 72, RIGHT_PANEL_WIDTH, max(400, height - 110))
        board_left = left_panel.right + PANEL_GAP
        board_right = right_panel.left - PANEL_GAP
        board_rect = pygame.Rect(board_left, BOARD_TOP, max(200, board_right - board_left), max(300, height - 132))
        top_bar = pygame.Rect(20, 18, width - 40, 40)
        footer = pygame.Rect(20, height - 44, width - 40, 28)
        return {
            "left_panel": left_panel,
            "right_panel": right_panel,
            "board": board_rect,
            "top_bar": top_bar,
            "footer": footer,
        }

    def _load_tables(self) -> Dict[str, Any]:
        tables_path = Path(__file__).resolve().parent.parent / "data" / "tables.json"
        if tables_path.exists():
            with open(tables_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        return {}

    def run(self):
        """Main loop."""
        while self.running:
            self._handle_events()
            self._draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()

    def _refresh_roster(self):
        self.roster = self.game.hero_manager.get_all_heroes()
        valid_ids = {hero.id for hero in self.roster}
        self.party_ids = [hero_id for hero_id in self.party_ids if hero_id in valid_ids]
        if self.selected_hero_id not in valid_ids:
            self.selected_hero_id = self.roster[0].id if self.roster else None

    def _get_selected_hero(self) -> Optional[Hero]:
        source = self.game.party if self.current_screen == "dungeon" else self.roster
        for hero in source:
            if hero.id == self.selected_hero_id:
                return hero
        return source[0] if source else None

    def _get_party_for_begin(self) -> List[Hero]:
        party_lookup = {hero.id: hero for hero in self.roster}
        return [party_lookup[hero_id] for hero_id in self.party_ids if hero_id in party_lookup][:4]

    def _sync_log(self):
        self.last_log_index = len(self.game.combat_log)
        self.log_scroll_lines = 0

    def _pull_new_logs(self):
        if self.last_log_index < len(self.game.combat_log):
            self.message = self.game.combat_log[-1]
            self.last_log_index = len(self.game.combat_log)
            self.log_scroll_lines = 0

    def _get_hero_status(self, hero_id: str) -> Tuple[int, bool]:
        remaining = self.game.hero_movement_remaining.get(hero_id, 0)
        attacked = hero_id in self.game.hero_has_attacked
        return remaining, attacked

    def _selected_hero_attack_mode(self) -> str:
        hero = self._get_selected_hero()
        if hero is None:
            return "-"
        weapon = hero.get_equipped_ranged_weapon()
        if weapon is None:
            return "Melee"
        suffix = " (unloaded)" if not hero.is_ranged_weapon_loaded() else ""
        return f"Ranged: {weapon.get('name', 'Bow')}{suffix}"

    def _get_available_actions_for_selected(self) -> List[type]:
        self.game.ensure_phase_consistency()
        hero = self._get_selected_hero()
        if hero is None or self.game.dungeon is None:
            return []
        if self.game.current_phase != "EXPLORATION":
            return []
        if self.game.hero_movement_remaining.get(hero.id, 0) <= 0:
            return []
        return get_available_actions(hero, self.game.dungeon)

    def _random_name(self) -> str:
        return f"{random.choice(RANDOM_FIRST_NAMES)} {random.choice(RANDOM_LAST_NAMES)}"

    def _open_creation_modal(self):
        dagger = self._build_creation_item("dagger") or {"name": "Dagger", "key": "dagger", "type": "weapon", "equipped": True}
        self.creation_state = CreationState(
            name=self._random_name(),
            equipment=[dagger],
        )
        self.typing_target = "creation_name"
        self.message = "Hero creation opened."

    def _cancel_creation_modal(self):
        self.creation_state = None
        self.typing_target = None
        self.message = "Hero creation cancelled."

    def _create_hero_from_modal(self):
        state = self.creation_state
        if state is None:
            return
        if not state.race:
            self.message = "Roll a race first."
            return
        if not state.stats:
            self.message = "Roll stats first."
            return
        if state.gold <= 0:
            self.message = "Roll starting gold first."
            return
        name = state.name.strip()
        if not name:
            self.message = "Enter a hero name."
            return

        equipment = list(state.equipment or [self._build_creation_item("dagger") or {"name": "Dagger", "key": "dagger", "type": "weapon", "equipped": True}])
        hero = self.game.hero_manager.create_hero(
            name=name,
            race=state.race,
            class_type=state.class_type,
            stats=state.stats,
            gold=state.gold,
            equipment=equipment,
        )
        self.creation_state = None
        self.typing_target = None
        self._refresh_roster()
        self.selected_hero_id = hero.id
        self.message = f"{hero.name} created."

    def _begin_quest(self):
        party = self._get_party_for_begin()
        if not party:
            self.message = "Choose at least one hero for the party."
            return
        self.game.start_quest(party)
        self.current_screen = "dungeon"
        self.selected_hero_id = party[0].id
        self.movement_preview_hero_id = None
        self._sync_log()
        self._center_camera()
        self.message = "The expedition enters the dungeon..."

    def _continue_save(self):
        if not self.game.load_game():
            self.message = "Could not load the save."
            return
        self.current_screen = "dungeon" if self.game.mode in ("DUNGEON", "COMBAT") else "tavern"
        self.selected_hero_id = self.game.party[0].id if self.game.party else self.selected_hero_id
        self.movement_preview_hero_id = None
        self._sync_log()
        self._center_camera()
        self.message = "Save loaded."

    def _return_to_tavern(self):
        self.game._exit_dungeon()
        self.current_screen = "tavern"
        self._refresh_roster()
        self.selected_hero_id = self.roster[0].id if self.roster else None
        self.movement_preview_hero_id = None
        self.message = "Returned to the tavern."

    def _delete_selected_hero(self):
        hero = self._get_selected_hero()
        if hero is None or self.current_screen != "tavern":
            return
        if hero.id in self.party_ids:
            self.party_ids.remove(hero.id)
        self.game.hero_manager.delete_hero(hero.id)
        self._refresh_roster()
        self.message = f"{hero.name} deleted."

    def _add_selected_to_party(self):
        hero = self._get_selected_hero()
        if hero is None:
            return
        if hero.id in self.party_ids:
            self.message = f"{hero.name} is already in the party."
            return
        if len(self.party_ids) >= 4:
            self.message = "Party is full."
            return
        self.party_ids.append(hero.id)
        self.message = f"{hero.name} added to the party."

    def _remove_selected_from_party(self):
        hero = self._get_selected_hero()
        if hero is None:
            return
        if hero.id not in self.party_ids:
            self.message = f"{hero.name} is not in the party."
            return
        self.party_ids.remove(hero.id)
        self.message = f"{hero.name} removed from the party."

    def _execute_action(self, action_class):
        hero = self._get_selected_hero()
        if hero is None or self.game.dungeon is None:
            return
        if self.game.current_phase != "EXPLORATION":
            self.message = "That action can only be used during exploration."
            return
        if self.game.hero_movement_remaining.get(hero.id, 0) <= 0:
            self.message = f"{hero.name} has already used their turn."
            return
        result = action_class.execute(hero, self.game.dungeon, self.game)
        self.message = result.message
        if result.end_turn:
            self.game.hero_movement_remaining[hero.id] = 0
        self.movement_preview_hero_id = None
        self._pull_new_logs()
        self._center_camera()

    def _activate_spell_cast(self, spell_option: Dict[str, Any]):
        hero = self._get_selected_hero()
        if hero is None:
            return
        if str(spell_option.get("target_mode", "none")) == "none":
            _, message = self.game.cast_spell(
                hero,
                str(spell_option["spell_name"]),
                target=None,
                source_kind=str(spell_option.get("source_kind", "spellbook")),
                item_index=spell_option.get("item_index"),
                scroll_spell_index=spell_option.get("scroll_spell_index"),
            )
            self.message = message
            self.pending_spell = None
            self.movement_preview_hero_id = None
            self._pull_new_logs()
            self._center_camera()
            return
        self.pending_spell = dict(spell_option)
        self.message = f"{spell_option['spell_name']}: click a board target. Esc cancels."

    def _end_phase(self):
        self.movement_preview_hero_id = None
        self.game.end_hero_phase()
        self._pull_new_logs()

    def _go_down_stairs(self):
        if self.game.dungeon is None:
            return
        from dungeon import Dungeon

        self.game.dungeon_debug_log.clear()
        self.game.monsters = []
        self.game.dungeon = Dungeon(
            level=self.game.dungeon.level + 1,
            debug_log=self.game.dungeon_debug_log,
            monster_library=self.game.monster_library,
        )
        self.game.dungeon._on_monster_placed = lambda m: self.game.monsters.append(m)
        start_x, start_y = self.game.dungeon.hero_start
        for index, hero in enumerate(self.game.party):
            hero.x = start_x + (index % 2)
            hero.y = start_y + (index // 2)
        self.game.current_phase = "EXPLORATION"
        self.game.mode = "DUNGEON"
        self.game.hero_phase_active = True
        self.game.hero_movement_remaining = {
            hero.id: self.game._get_movement_allowance_for_phase(hero, "EXPLORATION")
            for hero in self.game.party
        }
        self.game.hero_has_attacked.clear()
        self.game.combat_log.append(f"Descended to dungeon level {self.game.dungeon.level}.")
        self._sync_log()
        self._center_camera()
        self.message = f"Descended to dungeon level {self.game.dungeon.level}."

    def _center_camera(self):
        heroes = [hero for hero in self.game.party if not hero.is_dead]
        if not heroes:
            return
        avg_x = sum(hero.x for hero in heroes) / len(heroes)
        avg_y = sum(hero.y for hero in heroes) / len(heroes)
        board_rect = self._layout()["board"]
        board_width = board_rect.width // TILE_SIZE
        board_height = board_rect.height // TILE_SIZE
        self.camera_x = int(avg_x - board_width // 2)
        self.camera_y = int(avg_y - board_height // 2)

    def _grid_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        board_rect = self._layout()["board"]
        return board_rect.left + (x - self.camera_x) * TILE_SIZE, board_rect.top + (y - self.camera_y) * TILE_SIZE

    def _screen_to_grid(self, sx: int, sy: int) -> Optional[Tuple[int, int]]:
        board_rect = self._layout()["board"]
        if not board_rect.collidepoint(sx, sy):
            return None
        return (sx - board_rect.left) // TILE_SIZE + self.camera_x, (sy - board_rect.top) // TILE_SIZE + self.camera_y

    def _focus_camera_on(self, gx: int, gy: int):
        board_rect = self._layout()["board"]
        board_width = board_rect.width // TILE_SIZE
        board_height = board_rect.height // TILE_SIZE
        self.camera_x = int(gx - board_width // 2)
        self.camera_y = int(gy - board_height // 2)

    def _toggle_map_overlay(self):
        self.map_overlay_open = not self.map_overlay_open
        self.message = "Map opened." if self.map_overlay_open else "Map closed."

    def _get_map_bounds(self) -> Optional[Tuple[int, int, int, int]]:
        dungeon = self.game.dungeon
        if dungeon is None:
            return None
        points = set(dungeon.explored)
        for hero in self.game.party:
            if not hero.is_dead:
                points.add((hero.x, hero.y))
        for monster in self.game.monsters:
            if not monster.is_dead and dungeon.is_explored(monster.x, monster.y):
                points.add((monster.x, monster.y))
        if not points:
            return None
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        return min(xs), min(ys), max(xs), max(ys)

    def _get_minimap_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel_rect.x + 12, panel_rect.y + 46, panel_rect.width - 24, 212)

    def _get_log_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        minimap = self._get_minimap_rect(panel_rect)
        return pygame.Rect(panel_rect.x + 12, minimap.bottom + 44, panel_rect.width - 24, panel_rect.bottom - minimap.bottom - 56)

    def _get_left_section_rects(self) -> Dict[str, pygame.Rect]:
        left_panel = self._layout()["left_panel"]
        inner_x = left_panel.x + 8
        inner_width = left_panel.width - 16
        content_top = left_panel.y + 46
        content_bottom = left_panel.bottom - 12
        available_height = content_bottom - content_top

        party_height = min(418, max(180, 12 + len(self.game.party) * 98))
        monster_count = len([monster for monster in self.game.monsters if not monster.is_dead])
        monster_height = min(180, max(100, 72 + min(monster_count, 5) * 42))
        gap = 10
        min_action_height = 250
        overflow = party_height + monster_height + min_action_height + gap * 2 - available_height
        if overflow > 0:
            reducible_party = max(0, party_height - 180)
            reduce_party = min(reducible_party, overflow)
            party_height -= reduce_party
            overflow -= reduce_party
        if overflow > 0:
            reducible_monsters = max(0, monster_height - 100)
            reduce_monsters = min(reducible_monsters, overflow)
            monster_height -= reduce_monsters
            overflow -= reduce_monsters
        action_height = max(180, available_height - party_height - monster_height - gap * 2)

        party_rect = pygame.Rect(inner_x, content_top, inner_width, party_height)
        monster_rect = pygame.Rect(inner_x, party_rect.bottom + gap, inner_width, monster_height)
        action_rect = pygame.Rect(inner_x, monster_rect.bottom + gap, inner_width, max(120, content_bottom - (monster_rect.bottom + gap)))
        return {
            "party": party_rect,
            "monsters": monster_rect,
            "actions": action_rect,
        }

    def _get_wrapped_log_lines(self, max_width: int) -> List[str]:
        lines: List[str] = []
        for message in self.game.combat_log:
            lines.extend(self._wrap_text_px(message, self.small_font, max_width))
        return lines or [""]

    def _scroll_log(self, delta: int):
        if self.current_screen != "dungeon":
            return
        panel_rect = self._get_log_rect(self._layout()["right_panel"])
        visible_lines = max(1, (panel_rect.height - 20) // 18)
        wrapped_lines = self._get_wrapped_log_lines(panel_rect.width - 30)
        max_scroll = max(0, len(wrapped_lines) - visible_lines)
        self.log_scroll_lines = max(0, min(max_scroll, self.log_scroll_lines + delta))

    def _map_screen_to_grid(self, point: Tuple[int, int], rect: pygame.Rect) -> Optional[Tuple[int, int]]:
        bounds = self._get_map_bounds()
        if bounds is None or not rect.collidepoint(point):
            return None
        min_x, min_y, max_x, max_y = bounds
        span_x = max(1, max_x - min_x + 1)
        span_y = max(1, max_y - min_y + 1)
        scale = min(rect.width / span_x, rect.height / span_y)
        if scale <= 0:
            return None
        draw_width = span_x * scale
        draw_height = span_y * scale
        origin_x = rect.x + (rect.width - draw_width) / 2
        origin_y = rect.y + (rect.height - draw_height) / 2
        local_x = point[0] - origin_x
        local_y = point[1] - origin_y
        if local_x < 0 or local_y < 0 or local_x >= draw_width or local_y >= draw_height:
            return None
        gx = min_x + int(local_x // scale)
        gy = min_y + int(local_y // scale)
        return gx, gy

    def _handle_map_click(self, pos: Tuple[int, int]) -> bool:
        if self.current_screen != "dungeon":
            return False
        layout = self._layout()
        if self.map_overlay_open:
            overlay_rect = pygame.Rect(80, 80, self.window_width - 160, self.window_height - 160)
            grid = self._map_screen_to_grid(pos, overlay_rect.inflate(-32, -72))
            if grid is not None:
                self._focus_camera_on(*grid)
                self.message = f"Map focused on {grid}."
                return True
            self.map_overlay_open = False
            self.message = "Map closed."
            return True

        minimap_rect = self._get_minimap_rect(layout["right_panel"])
        if minimap_rect.collidepoint(pos):
            grid = self._map_screen_to_grid(pos, minimap_rect)
            if grid is not None:
                self._focus_camera_on(*grid)
                self.message = f"Map focused on {grid}."
            return True
        return False

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if self.game.mode in ("DUNGEON", "COMBAT"):
                    self.game.save_game()
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            if event.type == pygame.MOUSEWHEEL:
                self._handle_mouse_wheel(pygame.mouse.get_pos(), event.y)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._handle_button_click(event.pos):
                    continue
                if self.creation_state is not None:
                    continue
                if self._handle_map_click(event.pos):
                    continue
                if self.current_screen == "tavern":
                    self._handle_tavern_click(event.pos)
                else:
                    self._handle_dungeon_click(event.pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                delta = 3 if event.button == 4 else -3
                self._handle_mouse_wheel(event.pos, delta)

    def _handle_mouse_wheel(self, pos: Tuple[int, int], delta: int):
        if self.current_screen != "dungeon" or self.creation_state is not None or self.map_overlay_open:
            return
        log_rect = self._get_log_rect(self._layout()["right_panel"])
        if log_rect.collidepoint(pos):
            self._scroll_log(delta)

    def _handle_keydown(self, event: pygame.event.Event):
        if self.creation_state is not None:
            if event.key == pygame.K_ESCAPE:
                self._cancel_creation_modal()
                return
            if self.typing_target == "creation_name":
                if event.key == pygame.K_BACKSPACE:
                    self.creation_state.name = self.creation_state.name[:-1]
                elif event.key == pygame.K_RETURN:
                    self._create_hero_from_modal()
                elif event.unicode and event.unicode.isprintable() and len(self.creation_state.name) < 28:
                    self.creation_state.name += event.unicode
            return

        if self.current_screen == "tavern":
            if event.key == pygame.K_c:
                self._open_creation_modal()
            elif event.key == pygame.K_DELETE:
                self._delete_selected_hero()
            elif event.key == pygame.K_a:
                self._add_selected_to_party()
            elif event.key == pygame.K_r:
                self._remove_selected_from_party()
            elif event.key == pygame.K_RETURN:
                self._begin_quest()
            elif event.key == pygame.K_ESCAPE:
                self.running = False
            return

        if event.key == pygame.K_m:
            self._toggle_map_overlay()
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.camera_x -= CAMERA_STEP
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.camera_x += CAMERA_STEP
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.camera_y -= CAMERA_STEP
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.camera_y += CAMERA_STEP
        elif event.key == pygame.K_SPACE:
            self._end_phase()
        elif event.key == pygame.K_TAB:
            self._cycle_selected_hero()
        elif event.key == pygame.K_ESCAPE:
            if self.map_overlay_open:
                self.map_overlay_open = False
                self.message = "Map closed."
            elif self.pending_spell is not None:
                self.pending_spell = None
                self.message = "Spell targeting cancelled."
            else:
                self._return_to_tavern()

    def _cycle_selected_hero(self):
        heroes = [hero for hero in self.game.party if not hero.is_dead]
        if not heroes:
            return
        ids = [hero.id for hero in heroes]
        if self.selected_hero_id not in ids:
            self.selected_hero_id = ids[0]
            self.movement_preview_hero_id = self.selected_hero_id
            return
        index = ids.index(self.selected_hero_id)
        self.selected_hero_id = ids[(index + 1) % len(ids)]
        self.movement_preview_hero_id = self.selected_hero_id

    def _handle_button_click(self, pos: Tuple[int, int]) -> bool:
        active_buttons = self.modal_buttons if self.creation_state is not None else (self.buttons + self.action_buttons)
        for button in active_buttons:
            if not button.enabled or not button.rect.collidepoint(pos):
                continue
            if button.action == "begin_quest":
                self._begin_quest()
            elif button.action == "continue_save":
                self._continue_save()
            elif button.action == "quit":
                self.running = False
            elif button.action == "create_hero":
                self._open_creation_modal()
            elif button.action == "delete_hero":
                self._delete_selected_hero()
            elif button.action == "add_party":
                self._add_selected_to_party()
            elif button.action == "remove_party":
                self._remove_selected_from_party()
            elif button.action == "end_phase":
                self._end_phase()
            elif button.action == "return_tavern":
                self._return_to_tavern()
            elif button.action == "action":
                self._execute_action(button.payload)
            elif button.action == "cast_spell":
                self._activate_spell_cast(dict(button.payload))
            elif button.action == "toggle_map":
                self._toggle_map_overlay()
            elif button.action == "creation_roll_race":
                self.creation_state.race = roll_hero_race()
                self.message = f"Race rolled: {self.creation_state.race}."
            elif button.action == "creation_warrior":
                self.creation_state.class_type = "Warrior"
            elif button.action == "creation_wizard":
                self.creation_state.class_type = "Wizard"
            elif button.action == "creation_roll_stats":
                race = self.creation_state.race
                if not race:
                    self.message = "Roll race first."
                else:
                    self.creation_state.stats = roll_hero_stats(race)
                    self.message = "Stats rolled."
            elif button.action == "creation_roll_gold":
                self.creation_state.gold = roll_starting_gold()
                self.message = f"Starting gold: {self.creation_state.gold} gc."
            elif button.action == "creation_random_name":
                self.creation_state.name = self._random_name()
            elif button.action == "creation_cancel":
                self._cancel_creation_modal()
            elif button.action == "creation_finish":
                self._create_hero_from_modal()
            elif button.action == "creation_buy_item":
                self._buy_creation_item(str(button.payload))
            return True
        return False

    def _get_equipment_table(self) -> Dict[str, Dict[str, Any]]:
        return self.tables.get("equipment", {})

    def _creation_has_item(self, item_key: str) -> bool:
        state = self.creation_state
        if state is None:
            return False
        return any(item.get("key") == item_key for item in (state.equipment or []))

    def _build_creation_item(self, item_key: str) -> Optional[Dict[str, Any]]:
        equipment_table = self._get_equipment_table()
        data = equipment_table.get(item_key)
        if data is None:
            return None

        item: Dict[str, Any] = {
            "key": item_key,
            "name": data.get("display_name", item_key.replace("_", " ").title()),
            "type": data.get("type", "weapon"),
            "equipped": True,
        }
        for field in (
            "damage_dice",
            "strength_damage",
            "two_handed",
            "critical",
            "fumble",
            "long_reach",
            "max_range",
            "move_and_fire",
            "min_strength",
            "requires_reload",
            "starts_loaded",
            "armour_value",
            "bs_modifier",
            "speed_modifier",
            "notes",
        ):
            if field in data:
                item[field] = data[field]
        if item.get("requires_reload"):
            item["loaded"] = bool(data.get("starts_loaded", True))
        return item

    def _buy_creation_item(self, item_key: str):
        state = self.creation_state
        if state is None:
            return
        equipment_table = self._get_equipment_table()
        data = equipment_table.get(item_key)
        if data is None:
            self.message = "Unknown equipment item."
            return
        if state.gold <= 0:
            self.message = "Roll starting gold first."
            return
        if item_key in {"leather_armour", "chain_armour", "plate_armour", "mithril_armour", "light_armour", "heavy_armour", "shield"} and state.class_type == "Wizard":
            self.message = "Wizards cannot buy armour or shields."
            return

        item = self._build_creation_item(item_key)
        if item is None:
            self.message = "Could not build that item."
            return
        if self._creation_has_item(item_key):
            self.message = f"{item['name']} is already in the loadout."
            return

        cost = int(data.get("cost", 0))
        if cost > state.gold:
            self.message = f"Not enough gold for {item['name']}."
            return

        state.gold -= cost
        state.equipment = list(state.equipment or [])
        if item.get("type") == "weapon":
            for existing in state.equipment:
                if existing.get("type") == "weapon":
                    existing["equipped"] = False
        elif item.get("type") == "ranged_weapon":
            for existing in state.equipment:
                if existing.get("type") == "ranged_weapon":
                    existing["equipped"] = False
        elif item.get("type") in {"armour", "armor"}:
            for existing in state.equipment:
                if existing.get("type") in {"armour", "armor"}:
                    existing["equipped"] = False
        elif item.get("type") == "shield":
            for existing in state.equipment:
                if existing.get("type") == "shield":
                    existing["equipped"] = False
        state.equipment.append(item)
        self.message = f"Bought {item['name']} for {cost} gc."

    def _handle_tavern_click(self, pos: Tuple[int, int]):
        roster_x = 30
        roster_y = 136
        row_h = 32
        for idx, hero in enumerate(self.roster):
            rect = pygame.Rect(roster_x, roster_y + idx * row_h, 540, 29)
            if rect.collidepoint(pos):
                self.selected_hero_id = hero.id
                self.movement_preview_hero_id = None
                return

    def _handle_dungeon_click(self, pos: Tuple[int, int]):
        self.game.ensure_phase_consistency()
        grid_pos = self._screen_to_grid(*pos)
        if grid_pos is None or self.game.dungeon is None:
            return

        hero = self._get_selected_hero()
        if hero is None:
            return

        gx, gy = grid_pos

        if self.pending_spell is not None:
            success, message = self.game.cast_spell(
                hero,
                str(self.pending_spell["spell_name"]),
                target=(gx, gy),
                source_kind=str(self.pending_spell.get("source_kind", "spellbook")),
                item_index=self.pending_spell.get("item_index"),
                scroll_spell_index=self.pending_spell.get("scroll_spell_index"),
            )
            self.message = message
            if success:
                self.pending_spell = None
                self._pull_new_logs()
                self._center_camera()
            return

        for party_hero in self.game.party:
            if not party_hero.is_dead and (party_hero.x, party_hero.y) == (gx, gy):
                self.selected_hero_id = party_hero.id
                self.movement_preview_hero_id = party_hero.id
                self.message = f"{party_hero.name} selected."
                return

        monster = self._get_monster_at(gx, gy)
        if monster is not None:
            self.game.hero_attack(hero, monster)
            self._pull_new_logs()
            return

        tile = self.game.dungeon.get_tile(gx, gy)
        starting_stairs = {(0, 0), (1, 0), (0, 1), (1, 1)}
        if tile == self.game.dungeon.TileType.DOOR_CLOSED:
            if self.game.dungeon.is_adjacent(hero.x, hero.y, gx, gy):
                self.game.open_door(gx, gy)
                self._pull_new_logs()
            else:
                self.message = "Stand adjacent to the door."
            return
        if tile == self.game.dungeon.TileType.STAIRS_DOWN and (gx, gy) not in starting_stairs:
            if self.game.dungeon.is_adjacent(hero.x, hero.y, gx, gy) or (hero.x, hero.y) == (gx, gy):
                self._go_down_stairs()
            else:
                self.message = "Move next to the stairs first."
            return
        if tile == self.game.dungeon.TileType.STAIRS_OUT:
            if self.game.dungeon.is_adjacent(hero.x, hero.y, gx, gy) or (hero.x, hero.y) == (gx, gy):
                self._return_to_tavern()
            else:
                self.message = "Move next to the exit first."
            return

        moved = self.game.move_hero(hero, gx, gy)
        if moved:
            self.movement_preview_hero_id = None
            self._pull_new_logs()
            self._center_camera()
        else:
            self._pull_new_logs()

    def _get_monster_at(self, x: int, y: int) -> Optional[Monster]:
        for monster in self.game.monsters:
            if not monster.is_dead and (monster.x, monster.y) == (x, y):
                return monster
        return None

    def _draw(self):
        self.buttons = []
        self.action_buttons = []
        self.modal_buttons = []
        self.screen.fill(BG)
        self._draw_top_bar()
        if self.current_screen == "tavern":
            self._draw_tavern()
        else:
            self._draw_dungeon()
        if self.creation_state is not None:
            self._draw_creation_modal()
        self._draw_footer()

    def _draw_top_bar(self):
        rect = self._layout()["top_bar"]
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_ALT, rect, 1, border_radius=8)
        if self.current_screen == "tavern":
            title = "Advanced HeroQuest | Tavern | C Create | A Add | R Remove | Enter Begin"
        else:
            title = (
                f"Advanced HeroQuest | {self.game.current_phase} | "
                f"{'Hero' if self.game.hero_phase_active else 'GM'} Phase | "
                "Space End Phase | Tab Cycle Hero | Arrows/WASD Pan | M Map"
            )
        self.screen.blit(self.small_font.render(title, True, TEXT), (32, 30))
        if self.current_screen == "dungeon":
            map_label = "Close Map" if self.map_overlay_open else "Open Map"
            self._draw_button(
                pygame.Rect(rect.right - 136, rect.y + 5, 116, 30),
                map_label,
                "toggle_map",
                color=PURPLE,
                small=True,
            )

    def _draw_panel(self, rect: pygame.Rect, title: str):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_ALT, rect, 1, border_radius=8)
        self.screen.blit(self.title_font.render(title, True, TEXT), (rect.x + 12, rect.y + 10))

    def _draw_button(
        self,
        rect: pygame.Rect,
        label: str,
        action: str,
        enabled: bool = True,
        payload: Any = None,
        *,
        color: Tuple[int, int, int] = BLUE,
        modal: bool = False,
        small: bool = False,
    ):
        fill = color if enabled else (74, 74, 80)
        pygame.draw.rect(self.screen, fill, rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=6)
        font = self.small_font if small else self.font
        label = self._fit_text(label, font, rect.width - 12)
        surf = font.render(label, True, TEXT if enabled else MUTED)
        text_rect = surf.get_rect(center=rect.center)
        self.screen.blit(surf, text_rect)
        button = Button(rect=rect, label=label, action=action, enabled=enabled, payload=payload)
        if modal:
            self.modal_buttons.append(button)
        else:
            self.buttons.append(button)

    def _draw_action_button(self, rect: pygame.Rect, label: str, action_class):
        pygame.draw.rect(self.screen, GREEN, rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=6)
        surf = self.small_font.render(self._fit_text(label, self.small_font, rect.width - 12), True, TEXT)
        self.screen.blit(surf, surf.get_rect(center=rect.center))
        self.action_buttons.append(Button(rect=rect, label=label, action="action", enabled=True, payload=action_class))

    def _draw_spell_button(self, rect: pygame.Rect, label: str, spell_option: Dict[str, Any]):
        pygame.draw.rect(self.screen, PURPLE, rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=6)
        clipped = self._fit_text(label, self.small_font, rect.width - 12)
        surf = self.small_font.render(clipped, True, TEXT)
        self.screen.blit(surf, (rect.x + 6, rect.y + (rect.height - surf.get_height()) // 2))
        self.action_buttons.append(Button(rect=rect, label=label, action="cast_spell", enabled=True, payload=spell_option))

    def _fit_text(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        """Clip text with ellipsis so it fits the button width."""
        if font.size(text)[0] <= max_width:
            return text
        ellipsis = "..."
        clipped = text
        while clipped and font.size(clipped + ellipsis)[0] > max_width:
            clipped = clipped[:-1]
        return clipped + ellipsis if clipped else ellipsis

    def _draw_tavern(self):
        roster_rect = pygame.Rect(20, 72, 560, 810)
        detail_rect = pygame.Rect(600, 72, 860, 810)
        self._draw_panel(roster_rect, "Hero Roster")
        self._draw_panel(detail_rect, "Hero Details")

        self.screen.blit(
            self.small_font.render("Select a hero from the roster, then use the buttons below.", True, MUTED),
            (36, 108),
        )

        roster_y = 136
        for idx, hero in enumerate(self.roster):
            row_rect = pygame.Rect(30, roster_y + idx * 32, 540, 29)
            selected = hero.id == self.selected_hero_id
            in_party = hero.id in self.party_ids
            fill = (64, 95, 75) if in_party else PANEL_ALT
            if selected:
                pygame.draw.rect(self.screen, ACCENT, row_rect.inflate(4, 4), border_radius=6)
            pygame.draw.rect(self.screen, fill, row_rect, border_radius=6)
            label = (
                f"{hero.name:15} {hero.race:6} {hero.class_type:7} "
                f"WS {hero.ws:2} W {hero.current_wounds}/{hero.max_wounds} F {hero.current_fate}"
            )
            self.screen.blit(self.small_font.render(label, True, TEXT), (row_rect.x + 8, row_rect.y + 6))

        selected = self._get_selected_hero()
        if selected is not None:
            self._draw_hero_detail(selected, detail_rect.x + 20, detail_rect.y + 56)
        else:
            self.screen.blit(self.font.render("No hero selected.", True, TEXT), (detail_rect.x + 20, detail_rect.y + 64))

        party = self._get_party_for_begin()
        party_y = 676
        self.screen.blit(self.font.render(f"Party {len(party)}/4", True, ACCENT), (620, party_y))
        for idx, hero in enumerate(party):
            self.screen.blit(self.small_font.render(f"- {hero.name} ({hero.race} {hero.class_type})", True, TEXT), (620, party_y + 28 + idx * 22))

        button_y = 786
        self._draw_button(pygame.Rect(620, button_y, 150, 38), "Create Hero", "create_hero", color=GREEN)
        self._draw_button(pygame.Rect(784, button_y, 150, 38), "Delete Hero", "delete_hero", enabled=selected is not None, color=RED)
        self._draw_button(pygame.Rect(948, button_y, 150, 38), "Add To Party", "add_party", enabled=selected is not None, color=BLUE)
        self._draw_button(pygame.Rect(1112, button_y, 150, 38), "Remove", "remove_party", enabled=selected is not None, color=PURPLE)
        self._draw_button(pygame.Rect(1276, button_y, 170, 38), "Begin Quest", "begin_quest", enabled=bool(party), color=GOLD)
        self._draw_button(pygame.Rect(1112, 832, 160, 34), "Continue Save", "continue_save", enabled=self.game.has_save_game(), small=True)
        self._draw_button(pygame.Rect(1286, 832, 160, 34), "Quit", "quit", color=RED, small=True)

    def _draw_hero_detail(self, hero: Hero, x: int, y: int):
        lines = [
            f"Name:  {hero.name}",
            f"Race:  {hero.race}",
            f"Class: {hero.class_type}",
            "",
            "Statistics:",
            f"  Weapon Skill:    {hero.ws:2}",
            f"  Ballistic Skill: {hero.bs:2}",
            f"  Strength:        {hero.strength:2}",
            f"  Toughness:       {hero.toughness:2}",
            f"  Speed:           {hero.speed:2}",
            f"  Bravery:         {hero.bravery:2}",
            f"  Intelligence:    {hero.intelligence:2}",
            "",
            f"Wounds: {hero.current_wounds}/{hero.max_wounds}",
            f"Fate:   {hero.current_fate}/{hero.max_fate}",
            f"Gold:   {hero.gold}",
            "",
            "Equipment:",
        ]
        lines.extend(f"  - {item.get('name', 'Unknown')}" for item in hero.equipment)
        for index, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, TEXT), (x, y + index * 26))

    def _draw_dungeon(self):
        self.game.ensure_phase_consistency()
        layout = self._layout()
        left_panel = layout["left_panel"]
        right_panel = layout["right_panel"]
        board_rect = layout["board"]
        self._draw_panel(left_panel, "Party")
        self._draw_panel(right_panel, "Expedition Map")
        pygame.draw.rect(self.screen, PANEL, board_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_ALT, board_rect, 1, border_radius=8)
        self._draw_board()
        self._draw_left_panel()
        self._draw_right_panel(right_panel)
        if self.map_overlay_open:
            self._draw_map_overlay()

    def _draw_board(self):
        dungeon = self.game.dungeon
        if dungeon is None:
            return
        board_rect = self._layout()["board"]
        tiles_x = board_rect.width // TILE_SIZE
        tiles_y = board_rect.height // TILE_SIZE
        for sx in range(tiles_x):
            for sy in range(tiles_y):
                gx = self.camera_x + sx
                gy = self.camera_y + sy
                rect = pygame.Rect(board_rect.left + sx * TILE_SIZE, board_rect.top + sy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if not dungeon.is_explored(gx, gy):
                    pygame.draw.rect(self.screen, BLACK, rect)
                    continue
                tile = dungeon.get_tile(gx, gy)
                room = dungeon.find_room_for_tile(gx, gy)
                pygame.draw.rect(self.screen, self._get_tile_color(tile, room), rect)
                pygame.draw.rect(self.screen, (44, 46, 58), rect, 1)
                self._draw_tile_symbol(rect, tile, gx, gy)

                trap_marker = dungeon.trap_markers.get((gx, gy))
                if trap_marker:
                    inner = rect.inflate(-8, -8)
                    pygame.draw.rect(self.screen, (255, 159, 67), inner, 2)
                    self._draw_centered_text(trap_marker.get("symbol", "TR"), rect, self.small_font, (255, 221, 134))

        self._draw_movement_overlay()

        for monster in self.game.monsters:
            if monster.is_dead:
                continue
            sx, sy = self._grid_to_screen(monster.x, monster.y)
            outer = pygame.Rect(sx + 4, sy + 4, TILE_SIZE - 8, TILE_SIZE - 8)
            pygame.draw.ellipse(self.screen, RED, outer)
            self._draw_centered_text(monster.name[0], pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE), self.font, TEXT)

        selected_id = self.selected_hero_id
        for hero in self.game.party:
            if hero.is_dead:
                continue
            sx, sy = self._grid_to_screen(hero.x, hero.y)
            outer = pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE)
            if hero.id == selected_id:
                pygame.draw.rect(self.screen, ACCENT, outer, 2)
            fill = BLUE if hero.class_type == "Warrior" else PURPLE
            if hero.is_ko:
                fill = (105, 108, 118)
            pygame.draw.ellipse(self.screen, fill, outer.inflate(-8, -8))
            self._draw_centered_text(hero.name[0], outer, self.font, TEXT)

    def _draw_tile_symbol(self, rect: pygame.Rect, tile, x: int, y: int):
        dungeon = self.game.dungeon
        starting_stairs = {(0, 0), (1, 0), (0, 1), (1, 1)}
        if tile == dungeon.TileType.DOOR_CLOSED:
            pygame.draw.line(self.screen, (74, 44, 18), (rect.left + 4, rect.centery), (rect.right - 4, rect.centery), 2)
        elif tile == dungeon.TileType.STAIRS_DOWN:
            label = "S" if (x, y) in starting_stairs else "D"
            self._draw_centered_text(label, rect, self.small_font, BLACK)
        elif tile == dungeon.TileType.STAIRS_OUT:
            self._draw_centered_text("O", rect, self.small_font, BLACK)
        elif tile == dungeon.TileType.TREASURE_CLOSED:
            self._draw_centered_text("C", rect, self.small_font, TEXT)
        elif tile == dungeon.TileType.TREASURE_OPEN:
            self._draw_centered_text("OC", rect, self.small_font, TEXT)
        elif tile == dungeon.TileType.STATUE:
            self._draw_centered_text("ST", rect, self.small_font, TEXT)
        elif tile == dungeon.TileType.CHASM:
            self._draw_centered_text("CH", rect, self.small_font, ACCENT)
        elif tile == dungeon.TileType.GRATE:
            self._draw_centered_text("GR", rect, self.small_font, TEXT)
        elif tile == dungeon.TileType.THRONE:
            self._draw_centered_text("TH", rect, self.small_font, TEXT)

    def _draw_movement_overlay(self):
        hero = self._get_selected_hero()
        dungeon = self.game.dungeon
        if hero is None or dungeon is None or hero.is_dead or hero.is_ko:
            return
        if self.movement_preview_hero_id != hero.id:
            return
        remaining, _ = self._get_hero_status(hero.id)
        if remaining <= 0:
            return
        occupied = {
            (other.x, other.y)
            for other in self.game.party
            if other != hero and not other.is_dead and not other.is_ko
        }
        occupied.update((monster.x, monster.y) for monster in self.game.monsters if not monster.is_dead)
        for dx in range(-remaining, remaining + 1):
            for dy in range(-remaining, remaining + 1):
                tx, ty = hero.x + dx, hero.y + dy
                if (tx, ty) == (hero.x, hero.y):
                    continue
                if (tx, ty) in occupied or not dungeon.is_explored(tx, ty) or not dungeon.is_walkable(tx, ty):
                    continue
                path = find_path_bfs(hero.x, hero.y, tx, ty, dungeon, occupied)
                if path is None or self.game.get_path_movement_cost(path) > remaining:
                    continue
                sx, sy = self._grid_to_screen(tx, ty)
                center = (sx + TILE_SIZE // 2, sy + TILE_SIZE // 2)
                pygame.draw.circle(self.screen, (120, 180, 255), center, 7)
                pygame.draw.circle(self.screen, (50, 84, 150), center, 7, 2)

    def _get_tile_color(self, tile, room) -> Tuple[int, int, int]:
        dungeon = self.game.dungeon
        if tile == dungeon.TileType.FLOOR:
            return (86, 72, 86) if room is not None and room.get("room_kind") == "hazard" else (78, 79, 90)
        if tile == dungeon.TileType.WALL:
            return (28, 28, 42)
        if tile == dungeon.TileType.PASSAGE_END:
            return (78, 55, 40)
        if tile == dungeon.TileType.DOOR_CLOSED:
            return (139, 90, 43)
        if tile == dungeon.TileType.DOOR_OPEN:
            return (187, 138, 91)
        if tile == dungeon.TileType.STAIRS_DOWN:
            return (50, 205, 50)
        if tile == dungeon.TileType.STAIRS_OUT:
            return (200, 184, 150)
        if tile == dungeon.TileType.STATUE:
            return (122, 122, 132)
        if tile == dungeon.TileType.CHASM:
            return (5, 6, 11)
        if tile == dungeon.TileType.GRATE:
            return (81, 88, 98)
        if tile == dungeon.TileType.THRONE:
            return (123, 96, 48)
        if tile == dungeon.TileType.PIT_TRAP:
            return (36, 18, 16)
        if tile == dungeon.TileType.TREASURE_CLOSED:
            return (110, 80, 32)
        if tile == dungeon.TileType.TREASURE_OPEN:
            return (90, 72, 50)
        return (58, 58, 68)

    def _draw_centered_text(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color):
        surf = font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def _draw_left_panel(self):
        sections = self._get_left_section_rects()
        self._draw_party_panel(sections["party"])
        self._draw_monster_panel(sections["monsters"])
        self._draw_action_panel(sections["actions"])

    def _draw_right_panel(self, panel_rect: pygame.Rect):
        minimap_rect = self._get_minimap_rect(panel_rect)
        log_rect = self._get_log_rect(panel_rect)
        self.screen.blit(self.font.render("Mini Map", True, ACCENT), (panel_rect.x + 16, panel_rect.y + 14))
        self._draw_button(
            pygame.Rect(panel_rect.right - 116, panel_rect.y + 10, 92, 26),
            "Full Map",
            "toggle_map",
            color=BLUE,
            small=True,
        )
        pygame.draw.rect(self.screen, PANEL_ALT, minimap_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, minimap_rect, 1, border_radius=6)
        self._draw_map(minimap_rect, show_frame=True)
        self.screen.blit(self.font.render("Combat Log", True, ACCENT), (panel_rect.x + 16, log_rect.y - 28))
        pygame.draw.rect(self.screen, PANEL_ALT, log_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, log_rect, 1, border_radius=6)
        self._draw_log_panel(log_rect)

    def _draw_map(self, rect: pygame.Rect, *, show_frame: bool = False):
        dungeon = self.game.dungeon
        bounds = self._get_map_bounds()
        if dungeon is None or bounds is None:
            self._draw_centered_text("No map", rect, self.small_font, MUTED)
            return

        min_x, min_y, max_x, max_y = bounds
        span_x = max(1, max_x - min_x + 1)
        span_y = max(1, max_y - min_y + 1)
        scale = min(rect.width / span_x, rect.height / span_y)
        tile_px = max(2, int(scale))
        draw_width = span_x * tile_px
        draw_height = span_y * tile_px
        origin_x = rect.x + (rect.width - draw_width) // 2
        origin_y = rect.y + (rect.height - draw_height) // 2

        for gx, gy in sorted(dungeon.explored):
            tile = dungeon.get_tile(gx, gy)
            room = dungeon.find_room_for_tile(gx, gy)
            color = self._get_tile_color(tile, room)
            mini_rect = pygame.Rect(
                origin_x + (gx - min_x) * tile_px,
                origin_y + (gy - min_y) * tile_px,
                tile_px,
                tile_px,
            )
            pygame.draw.rect(self.screen, color, mini_rect)
            if tile_px >= 5:
                pygame.draw.rect(self.screen, BLACK, mini_rect, 1)

        for hero in self.game.party:
            if hero.is_dead or not dungeon.is_explored(hero.x, hero.y):
                continue
            hero_rect = pygame.Rect(
                origin_x + (hero.x - min_x) * tile_px,
                origin_y + (hero.y - min_y) * tile_px,
                tile_px,
                tile_px,
            )
            pygame.draw.rect(self.screen, BLUE if hero.class_type == "Warrior" else PURPLE, hero_rect)
            if hero.id == self.selected_hero_id:
                pygame.draw.rect(self.screen, ACCENT, hero_rect, 1)

        for monster in self.game.monsters:
            if monster.is_dead or not dungeon.is_explored(monster.x, monster.y):
                continue
            monster_rect = pygame.Rect(
                origin_x + (monster.x - min_x) * tile_px,
                origin_y + (monster.y - min_y) * tile_px,
                tile_px,
                tile_px,
            )
            pygame.draw.rect(self.screen, RED, monster_rect)

        if show_frame:
            board_rect = self._layout()["board"]
            visible_w = max(1, board_rect.width // TILE_SIZE)
            visible_h = max(1, board_rect.height // TILE_SIZE)
            camera_rect = pygame.Rect(
                origin_x + (self.camera_x - min_x) * tile_px,
                origin_y + (self.camera_y - min_y) * tile_px,
                visible_w * tile_px,
                visible_h * tile_px,
            )
            clipped = camera_rect.clip(rect)
            if clipped.width > 0 and clipped.height > 0:
                pygame.draw.rect(self.screen, ACCENT, clipped, 2)

    def _draw_map_overlay(self):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill(OVERLAY)
        self.screen.blit(overlay, (0, 0))
        rect = pygame.Rect(80, 80, self.window_width - 160, self.window_height - 160)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_ALT, rect, 1, border_radius=10)
        self.screen.blit(self.big_font.render("Expedition Map", True, TEXT), (rect.x + 20, rect.y + 16))
        self.screen.blit(
            self.small_font.render("Click anywhere on the map to center the camera. Esc or click outside closes.", True, MUTED),
            (rect.x + 22, rect.y + 52),
        )
        map_rect = rect.inflate(-32, -72)
        map_rect.y += 22
        map_rect.height -= 22
        pygame.draw.rect(self.screen, PANEL_ALT, map_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, map_rect, 1, border_radius=6)
        self._draw_map(map_rect, show_frame=True)

    def _draw_party_panel(self, panel_rect: pygame.Rect):
        pygame.draw.rect(self.screen, PANEL_ALT, panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 1, border_radius=6)
        self.screen.blit(self.font.render("Party", True, ACCENT), (panel_rect.x + 8, panel_rect.y + 8))
        content_rect = panel_rect.inflate(-8, -38)
        self.screen.set_clip(content_rect)
        y = content_rect.y + 4
        for hero in self.game.party:
            rect = pygame.Rect(content_rect.x, y, content_rect.width, 90)
            if rect.bottom > content_rect.bottom:
                break
            pygame.draw.rect(self.screen, PANEL_ALT, rect, border_radius=6)
            if hero.id == self.selected_hero_id:
                pygame.draw.rect(self.screen, ACCENT, rect, 2, border_radius=6)
            remaining, attacked = self._get_hero_status(hero.id)
            status = "DEAD" if hero.is_dead else "KO" if hero.is_ko else "OK"
            lines = [
                hero.name,
                f"{hero.race} {hero.class_type}",
                f"W {hero.current_wounds}/{hero.max_wounds} F {hero.current_fate}",
                f"M {remaining} {'A' if attacked else '-'} {status}",
            ]
            for idx, line in enumerate(lines):
                self.screen.blit(self.small_font.render(line, True, TEXT), (rect.x + 8, rect.y + 8 + idx * 20))
            if hero.status_effects:
                effects = ", ".join(effect.get("name", "?") for effect in hero.status_effects[:2])
                self.screen.blit(self.small_font.render(effects[:20], True, MUTED), (rect.x + 8, rect.y + 68))
            y += 98
        self.screen.set_clip(None)

    def _draw_action_panel(self, panel_rect: pygame.Rect):
        pygame.draw.rect(self.screen, PANEL_ALT, panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 1, border_radius=6)
        hero = self._get_selected_hero()
        x = panel_rect.x + 8
        y = panel_rect.y + 8
        self.screen.blit(self.font.render("Actions", True, ACCENT), (x, y))
        content_rect = panel_rect.inflate(-8, -38)
        y = content_rect.y + 4
        if hero is None:
            self.screen.blit(self.small_font.render("No hero selected.", True, TEXT), (x, y))
            return
        self.screen.set_clip(content_rect)
        remaining, attacked = self._get_hero_status(hero.id)
        info = [
            hero.name,
            f"{hero.race} {hero.class_type}",
            f"Phase: {self.game.current_phase}",
            f"Move {remaining}  Attack {'Yes' if attacked else 'No'}",
            self._selected_hero_attack_mode(),
            f"BS {hero.get_effective_bs()}  T {hero.get_effective_toughness()}  Sp {hero.get_effective_speed(self.game.current_phase.lower())}",
        ]
        for line in info:
            if y + 18 > content_rect.bottom:
                self.screen.set_clip(None)
                return
            self.screen.blit(self.small_font.render(line, True, TEXT), (x, y))
            y += 20
        y += 8
        for action_class in self._get_available_actions_for_selected()[:10]:
            if y + 28 > content_rect.bottom - 80:
                break
            label = f"{action_class.icon} {action_class.name}"
            self._draw_action_button(pygame.Rect(x, y, content_rect.width, 28), label, action_class)
            y += 34
        spell_options = self.game.get_available_spell_options(hero)
        if spell_options:
            if y + 22 <= content_rect.bottom - 80:
                self.screen.blit(self.small_font.render("Magic", True, ACCENT), (x, y))
                y += 24
            for spell_option in spell_options[:8]:
                if y + 32 > content_rect.bottom - 80:
                    break
                self._draw_spell_button(
                    pygame.Rect(x, y, content_rect.width, 32),
                    str(spell_option["label"]),
                    spell_option,
                )
                y += 38
        self.screen.set_clip(None)
        if self.pending_spell is not None:
            pending_y = max(panel_rect.bottom - 106, min(y, panel_rect.bottom - 106))
            self.screen.blit(
                self.small_font.render(f"Casting: {self.pending_spell['spell_name']}", True, GOLD),
                (x, pending_y),
            )
        button_bottom = panel_rect.bottom
        self._draw_button(pygame.Rect(x, button_bottom - 76, content_rect.width, 36), "End Hero Phase", "end_phase", enabled=self.game.hero_phase_active, color=GOLD)
        self._draw_button(pygame.Rect(x, button_bottom - 32, content_rect.width, 32), "Return To Tavern", "return_tavern", color=RED, small=True)

    def _draw_monster_panel(self, panel_rect: pygame.Rect):
        pygame.draw.rect(self.screen, PANEL_ALT, panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, panel_rect, 1, border_radius=6)
        x = panel_rect.x + 8
        y = panel_rect.y + 8
        self.screen.blit(self.font.render("Monsters", True, ACCENT), (x, y))
        content_rect = panel_rect.inflate(-8, -38)
        y = content_rect.y + 4
        monsters = [monster for monster in self.game.monsters if not monster.is_dead]
        if not monsters:
            self.screen.blit(self.small_font.render("None visible", True, MUTED), (x, y))
            return
        self.screen.set_clip(content_rect)
        for monster in monsters[:5]:
            if y + 36 > content_rect.bottom:
                break
            line = f"{monster.name[:14]:14} {monster.current_wounds}/{monster.max_wounds}"
            self.screen.blit(self.small_font.render(line, True, TEXT), (x, y))
            y += 18
            pos_line = f"@({monster.x},{monster.y}) WS {monster.ws}"
            self.screen.blit(self.small_font.render(pos_line, True, MUTED), (x, y))
            y += 22
        self.screen.set_clip(None)

    def _draw_log_panel(self, panel_rect: pygame.Rect):
        x = panel_rect.x + 10
        y = panel_rect.y + 10
        max_width = panel_rect.width - 30
        visible_lines = max(1, (panel_rect.height - 20) // 18)
        wrapped_lines = self._get_wrapped_log_lines(max_width)
        max_scroll = max(0, len(wrapped_lines) - visible_lines)
        self.log_scroll_lines = max(0, min(max_scroll, self.log_scroll_lines))
        end_index = len(wrapped_lines) - self.log_scroll_lines
        start_index = max(0, end_index - visible_lines)
        visible = wrapped_lines[start_index:end_index]
        for line in visible:
            self.screen.blit(self.small_font.render(line, True, TEXT), (x, y))
            y += 18
        if max_scroll > 0:
            track = pygame.Rect(panel_rect.right - 10, panel_rect.y + 8, 4, panel_rect.height - 16)
            pygame.draw.rect(self.screen, (58, 61, 74), track, border_radius=2)
            thumb_height = max(18, int(track.height * (visible_lines / len(wrapped_lines))))
            thumb_range = max(1, track.height - thumb_height)
            thumb_offset = int((self.log_scroll_lines / max_scroll) * thumb_range)
            thumb = pygame.Rect(track.x, track.bottom - thumb_height - thumb_offset, track.width, thumb_height)
            pygame.draw.rect(self.screen, ACCENT, thumb, border_radius=2)

    def _wrap_text(self, text: str, width: int) -> List[str]:
        words = text.split()
        if not words:
            return [""]
        lines = [words[0]]
        for word in words[1:]:
            trial = f"{lines[-1]} {word}"
            if len(trial) <= width:
                lines[-1] = trial
            else:
                lines.append(word)
        return lines

    def _wrap_text_px(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        words = text.split()
        if not words:
            return [""]
        lines = [words[0]]
        for word in words[1:]:
            trial = f"{lines[-1]} {word}"
            if font.size(trial)[0] <= max_width:
                lines[-1] = trial
            else:
                lines.append(word)
        return lines

    def _draw_creation_modal(self):
        state = self.creation_state
        if state is None:
            return
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill(OVERLAY)
        self.screen.blit(overlay, (0, 0))

        modal_width = min(980, self.window_width - 120)
        modal_height = min(760, self.window_height - 120)
        rect = pygame.Rect(
            (self.window_width - modal_width) // 2,
            (self.window_height - modal_height) // 2,
            modal_width,
            modal_height,
        )
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_ALT, rect, 1, border_radius=10)
        self.screen.blit(self.big_font.render("Create Hero", True, TEXT), (rect.x + 20, rect.y + 18))
        self.screen.blit(self.small_font.render("Type the name directly. Enter creates the hero, Esc cancels.", True, MUTED), (rect.x + 22, rect.y + 58))

        self.screen.blit(self.font.render(f"Race: {state.race or 'Not rolled'}", True, TEXT), (rect.x + 30, rect.y + 110))
        self._draw_button(pygame.Rect(rect.x + 260, rect.y + 104, 160, 32), "Roll Race", "creation_roll_race", modal=True, color=GREEN, small=True)

        self.screen.blit(self.font.render("Class:", True, TEXT), (rect.x + 30, rect.y + 158))
        self._draw_button(pygame.Rect(rect.x + 130, rect.y + 152, 140, 32), "Warrior", "creation_warrior", modal=True, color=BLUE if state.class_type == "Warrior" else PANEL_ALT, small=True)
        self._draw_button(pygame.Rect(rect.x + 284, rect.y + 152, 140, 32), "Wizard", "creation_wizard", modal=True, color=PURPLE if state.class_type == "Wizard" else PANEL_ALT, small=True)

        self.screen.blit(self.font.render("Stats:", True, TEXT), (rect.x + 30, rect.y + 208))
        self._draw_button(pygame.Rect(rect.x + 130, rect.y + 202, 160, 32), "Roll Stats", "creation_roll_stats", modal=True, enabled=state.race is not None, color=GREEN, small=True)
        if state.stats:
            stats_lines = [
                f"WS {state.stats['WS']}  BS {state.stats['BS']}  S {state.stats['S']}  T {state.stats['T']}",
                f"Sp {state.stats['Sp']}  Br {state.stats['Br']}  Int {state.stats['Int']}",
                f"W {state.stats['W']}  Fate {state.stats['Fate']}",
            ]
            for idx, line in enumerate(stats_lines):
                self.screen.blit(self.small_font.render(line, True, TEXT), (rect.x + 320, rect.y + 208 + idx * 20))

        self.screen.blit(self.font.render(f"Gold: {state.gold} gc", True, TEXT), (rect.x + 30, rect.y + 292))
        self._draw_button(pygame.Rect(rect.x + 130, rect.y + 286, 160, 32), "Roll Gold", "creation_roll_gold", modal=True, color=GREEN, small=True)

        self.screen.blit(self.font.render("Name:", True, TEXT), (rect.x + 30, rect.y + 350))
        input_rect = pygame.Rect(rect.x + 130, rect.y + 342, 390, 38)
        pygame.draw.rect(self.screen, PANEL_ALT, input_rect, border_radius=6)
        pygame.draw.rect(self.screen, ACCENT, input_rect, 2, border_radius=6)
        name_text = state.name if state.name else ""
        self.screen.blit(self.font.render(name_text + ("_" if self.typing_target == "creation_name" else ""), True, TEXT), (input_rect.x + 10, input_rect.y + 8))
        self._draw_button(pygame.Rect(rect.x + 540, rect.y + 344, 160, 32), "Random Name", "creation_random_name", modal=True, color=BLUE, small=True)

        self.screen.blit(self.font.render("Starting equipment:", True, TEXT), (rect.x + 30, rect.y + 412))
        equipment = state.equipment or []
        for idx, item in enumerate(equipment[:5]):
            equipped_note = " [E]" if item.get("equipped") else ""
            self.screen.blit(
                self.small_font.render(f"- {item.get('name', 'Unknown')}{equipped_note}", True, MUTED),
                (rect.x + 48, rect.y + 442 + idx * 20),
            )

        shop_x = rect.x + 360
        shop_y = rect.y + 412
        shop_width = rect.right - shop_x - 24
        shop_cols = 4
        shop_gap = 8
        button_width = max(86, (shop_width - shop_gap * (shop_cols - 1)) // shop_cols)
        self.screen.blit(self.font.render("Buy equipment:", True, TEXT), (shop_x, shop_y))
        shop_items = [
            ("Dagger", "dagger"),
            ("Sword", "sword"),
            ("Axe", "axe"),
            ("Warhammer", "warhammer"),
            ("Spear", "spear"),
            ("Halberd", "halberd"),
            ("2H Sword", "double_handed_sword"),
            ("2H Axe", "double_handed_axe"),
            ("Thrown Dagger", "thrown_dagger"),
            ("Thrown Axe", "thrown_axe"),
            ("Thrown Spear", "thrown_spear"),
            ("Short Bow", "short_bow"),
            ("Bow", "bow"),
            ("Long Bow", "long_bow"),
            ("Crossbow", "crossbow"),
            ("Shield", "shield"),
            ("Leather", "leather_armour"),
            ("Chain", "chain_armour"),
            ("Plate", "plate_armour"),
            ("Mithril", "mithril_armour"),
        ]
        equipment_table = self._get_equipment_table()
        for idx, (label, key) in enumerate(shop_items):
            row = idx // shop_cols
            col = idx % shop_cols
            item_data = equipment_table.get(key, {})
            cost = int(item_data.get("cost", 0))
            btn_label = f"{label} {cost}gc"
            enabled = state.gold >= cost and not self._creation_has_item(key)
            if key in {"shield", "leather_armour", "chain_armour", "plate_armour", "mithril_armour"} and state.class_type == "Wizard":
                enabled = False
            self._draw_button(
                pygame.Rect(shop_x + col * (button_width + shop_gap), rect.y + 442 + row * 32, button_width, 28),
                btn_label,
                "creation_buy_item",
                modal=True,
                enabled=enabled,
                payload=key,
                color=BLUE,
                small=True,
            )

        footer_y = rect.bottom - 54
        self._draw_button(pygame.Rect(rect.x + 360, footer_y, 150, 38), "Create Hero", "creation_finish", modal=True, color=GOLD)
        self._draw_button(pygame.Rect(rect.x + 528, footer_y, 120, 38), "Cancel", "creation_cancel", modal=True, color=RED)

    def _draw_footer(self):
        rect = self._layout()["footer"]
        pygame.draw.rect(self.screen, PANEL_ALT, rect, border_radius=6)
        pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=6)
        self.screen.blit(self.small_font.render(self.message[:190], True, TEXT), (rect.x + 10, rect.y + 6))

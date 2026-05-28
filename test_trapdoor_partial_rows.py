import unittest
from unittest.mock import patch

from actions.dungeon_actions import EnterMazeSubLevelAction
from dungeon import Dungeon
from game import GameState
from hazards import resolve_trapdoor_open
from hero import Hero


def make_hero(name="Hero"):
    hero = Hero(
        name,
        "Human",
        "Warrior",
        ws=6,
        bs=6,
        strength=3,
        toughness=3,
        speed=6,
        bravery=7,
        intelligence=7,
        wounds=4,
        fate=2,
        equipment=[],
    )
    hero.x = 20
    hero.y = 20
    return hero


def make_trapdoor_game():
    game = GameState()
    game.save_game = lambda: None
    game.dungeon = Dungeon(level=2, debug_log=[], monster_library=game.monster_library)
    game.dungeon.game_state = game
    game.dungeon._on_monster_placed = lambda monster: game.monsters.append(monster)
    hero = make_hero()
    game.party = [hero]
    game.current_phase = "EXPLORATION"
    game.mode = "DUNGEON"
    game.hero_phase_active = True
    game.hero_movement_remaining = {hero.id: hero.get_movement_allowance("exploration")}

    room_tiles = {(20, 20), (21, 20), (20, 21), (21, 21)}
    for pos in room_tiles:
        game.dungeon.grid[pos] = game.dungeon.TileType.FLOOR
        game.dungeon.explored.add(pos)
    room = {
        "id": 99,
        "room_kind": "hazard",
        "interior_tiles": room_tiles,
        "hazard": {"type": "trapdoor", "revealed": True, "resolved": False},
        "hazard_anchor": [21, 20],
        "entrance": [19, 20],
    }
    game.dungeon.rooms.append(room)
    return game, hero, room


class TrapdoorPartialRowsTests(unittest.TestCase):
    def test_trapdoor_maze_result_creates_enterable_sub_level(self):
        game, hero, room = make_trapdoor_game()

        with patch("hazards.random.randint", return_value=7):
            message = resolve_trapdoor_open(hero, room, game)

        hazard = room["hazard"]
        self.assertIn("Heroquest maze sub-level", message)
        self.assertEqual(hazard["opened_result"], "maze")
        self.assertTrue(hazard["maze_sub_level_available"])
        self.assertEqual(hazard["maze_sub_level_entry"]["type"], "heroquest_maze")
        self.assertEqual(game.pending_sub_level_entry["room_id"], room["id"])
        self.assertTrue(EnterMazeSubLevelAction.is_available(hero, game.dungeon))

        result = EnterMazeSubLevelAction.execute(hero, game.dungeon, game)

        self.assertTrue(result.success)
        self.assertIn("Entered Heroquest maze sub-level", result.message)
        self.assertEqual(game.active_sub_level["type"], "heroquest_maze")
        self.assertEqual(game.active_sub_level["origin_level"], 2)
        self.assertEqual(game.dungeon.level, 3)
        self.assertIsNone(game.pending_sub_level_entry)
        self.assertIn((hero.x, hero.y), game.entered_tiles)

    def test_trapdoor_maze_result_without_heroquest_board_finds_nothing(self):
        game, hero, room = make_trapdoor_game()
        game.heroquest_maze_available = False

        with patch("hazards.random.randint", return_value=8):
            message = resolve_trapdoor_open(hero, room, game)

        self.assertIn("find nothing", message)
        self.assertEqual(room["hazard"]["opened_result"], "maze")
        self.assertFalse(room["hazard"]["maze_sub_level_available"])
        self.assertIsNone(game.pending_sub_level_entry)
        self.assertFalse(EnterMazeSubLevelAction.is_available(hero, game.dungeon))

    def test_quest_specific_trapdoor_stairs_are_treated_as_lower_room(self):
        game, hero, room = make_trapdoor_game()
        game.quest_specific_stairs_down = True

        with patch("hazards.random.randint", side_effect=[12, 6]):
            message = resolve_trapdoor_open(hero, room, game)

        hazard = room["hazard"]
        self.assertIn("treat this result as a room", message)
        self.assertEqual(hazard["opened_result"], "room")
        self.assertTrue(hazard["stairs_result_overridden"])
        self.assertTrue(hazard["lower_room_opened"])
        self.assertEqual(hazard["lower_room_kind"], "normal")
        self.assertNotEqual(game.dungeon.grid[(21, 20)], game.dungeon.TileType.STAIRS_DOWN)

    def test_normal_trapdoor_stairs_create_stairs_down(self):
        game, hero, room = make_trapdoor_game()

        with patch("hazards.random.randint", return_value=12):
            message = resolve_trapdoor_open(hero, room, game)

        self.assertIn("Stairs lead down", message)
        self.assertEqual(room["hazard"]["opened_result"], "stairs")
        self.assertEqual(game.dungeon.grid[(21, 20)], game.dungeon.TileType.STAIRS_DOWN)


if __name__ == "__main__":
    unittest.main()

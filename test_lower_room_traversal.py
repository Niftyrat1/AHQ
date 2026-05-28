import unittest
from unittest.mock import patch

from dungeon import Dungeon
from game import GameState
from hazards import get_lower_room_tiles, resolve_grate_room
from hero import Hero


def make_hero(name="Hero", x=20, y=20):
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
    )
    hero.x = x
    hero.y = y
    return hero


def make_game_with_grate_room():
    game = GameState()
    game.save_game = lambda: None
    game.dungeon = Dungeon()
    game.dungeon.game_state = game
    game.dungeon._on_monster_placed = lambda monster: game.monsters.append(monster)
    game.mode = "DUNGEON"
    game.current_phase = "EXPLORATION"

    interior = {(20, 20), (21, 20), (20, 21), (21, 21)}
    for pos in interior:
        game.dungeon.grid[pos] = game.dungeon.TileType.FLOOR
        game.dungeon.explored.add(pos)
    game.dungeon.grid[(20, 20)] = game.dungeon.TileType.GRATE
    room = {
        "interior_tiles": interior,
        "walls": set(),
        "room_kind": "hazard",
        "hazard_anchor": [20, 20],
        "hazard": {"type": "grate", "revealed": True, "resolved": False},
    }
    game.dungeon.rooms.append(room)
    return game, room


class LowerRoomTraversalTests(unittest.TestCase):
    def test_grate_reveals_physical_lower_room_and_tracks_entry(self):
        game, room = make_game_with_grate_room()
        hero = make_hero()
        game.party = [hero]
        game.hero_movement_remaining = {hero.id: hero.get_movement_allowance("exploration")}

        with patch("hazards._roll_lower_room_kind", return_value="normal"):
            message = resolve_grate_room(room, game)

        lower_tiles = sorted(get_lower_room_tiles(room))
        self.assertIn("lower normal room", message)
        self.assertTrue(lower_tiles)
        self.assertTrue(all(game.dungeon.is_walkable(*pos) for pos in lower_tiles))

        landing = lower_tiles[0]
        allowed, reason, distance = game.can_move_hero_to(hero, *landing)
        self.assertTrue(allowed, reason)
        self.assertEqual(distance, 1)
        self.assertTrue(game.move_hero(hero, *landing))
        self.assertEqual((hero.x, hero.y), landing)
        self.assertIn(hero.id, room["hazard"]["lower_room_heroes"])

    def test_lower_room_exit_requires_rope(self):
        game, room = make_game_with_grate_room()
        hero = make_hero()
        game.party = [hero]
        game.hero_movement_remaining = {hero.id: hero.get_movement_allowance("exploration")}

        with patch("hazards._roll_lower_room_kind", return_value="normal"):
            resolve_grate_room(room, game)
        landing = sorted(get_lower_room_tiles(room))[0]
        self.assertTrue(game.move_hero(hero, *landing))
        game.turn_count += 1
        game.hero_movement_remaining[hero.id] = hero.get_movement_allowance("exploration")

        allowed, reason, _ = game.can_move_hero_to(hero, 20, 20)
        self.assertFalse(allowed)
        self.assertIn("rope", reason.lower())

        hero.add_inventory_item("rope_10ft", 1)
        allowed, reason, _ = game.can_move_hero_to(hero, 20, 20)
        self.assertTrue(allowed, reason)
        self.assertTrue(game.move_hero(hero, 20, 20))
        self.assertEqual((hero.x, hero.y), (20, 20))
        self.assertNotIn(hero.id, room["hazard"]["lower_room_heroes"])

    def test_only_one_model_may_transfer_per_turn(self):
        game, room = make_game_with_grate_room()
        hero = make_hero("First", 20, 20)
        second = make_hero("Second", 21, 20)
        game.party = [hero, second]
        game.hero_movement_remaining = {
            hero.id: hero.get_movement_allowance("exploration"),
            second.id: second.get_movement_allowance("exploration"),
        }

        with patch("hazards._roll_lower_room_kind", return_value="normal"):
            resolve_grate_room(room, game)

        lower_tiles = sorted(get_lower_room_tiles(room))
        self.assertTrue(game.move_hero(hero, *lower_tiles[0]))
        allowed, reason, _ = game.can_move_hero_to(second, *lower_tiles[1])
        self.assertFalse(allowed)
        self.assertIn("Only one model", reason)


if __name__ == "__main__":
    unittest.main()

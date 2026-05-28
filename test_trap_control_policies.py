import unittest
from unittest.mock import patch

from dungeon import Dungeon
from game import GameState
from hero import Hero
from traps import resolve_trap_event


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
        fate=1,
        equipment=[],
    )
    return hero


def make_game_with_open_board(width=8, height=8):
    game = GameState()
    game.save_game = lambda: None
    game.dungeon = Dungeon()
    game.dungeon.game_state = game
    game.dungeon.grid = {}
    game.dungeon.rooms = []
    for x in range(width):
        for y in range(height):
            game.dungeon.grid[(x, y)] = game.dungeon.TileType.FLOOR
    return game


class TrapControlPolicyTests(unittest.TestCase):
    def test_portcullis_uses_queued_gm_room_line(self):
        game = make_game_with_open_board(4, 3)
        interior = {(x, y) for x in range(4) for y in range(3)}
        game.dungeon.rooms.append({"interior_tiles": interior, "width": 4, "height": 3})
        hero = make_hero()
        hero.x, hero.y = 1, 1
        game.party = [hero]
        chosen_line = [(2, 0), (2, 1), (2, 2)]
        game.set_next_portcullis_placement(chosen_line)

        resolve_trap_event(
            hero,
            game.dungeon,
            game.combat_log,
            lambda *_: None,
            trap_name="Portcullis",
            can_spot=False,
            trap_pos=(hero.x, hero.y),
        )

        marked = {pos for pos, marker in game.dungeon.trap_markers.items() if marker.get("type") == "portcullis"}
        self.assertEqual(marked, set(chosen_line))
        self.assertIn("GM places the portcullis", " ".join(game.combat_log))

    def test_fireball_trap_uses_queued_gm_direction(self):
        game = make_game_with_open_board()
        hero = make_hero()
        hero.x, hero.y = 7, 7
        game.party = [hero]
        self.assertEqual(game.queue_fireball_trap_directions([(1, 0)]), "Fireball trap directions queued.")
        game._queue_fireball_trap((0, 0))
        game.active_fireball_traps[0]["delay_phases"] = 0

        game._advance_fireball_traps()

        self.assertEqual((game.active_fireball_traps[0]["x"], game.active_fireball_traps[0]["y"]), (8, 0))
        self.assertIn((8, 0), game.dungeon.trap_markers)

    def test_gas_madness_uses_queued_gm_destination_without_attacking(self):
        game = make_game_with_open_board()
        hero = make_hero("Mad Hero")
        ally = make_hero("Ally")
        hero.x, hero.y = 0, 0
        ally.x, ally.y = 1, 0
        hero.add_status_effect(
            "madness",
            turns=6,
            scope="expedition",
            madness_attack_allies=False,
            gm_orders=[],
        )
        game.party = [hero, ally]
        game.current_phase = "EXPLORATION"

        self.assertEqual(game.queue_madness_move(hero, 0, 2), "GM movement queued for Mad Hero.")
        with patch("game.resolve_hero_vs_hero_attack") as attack:
            game._run_mad_hero_phase()

        self.assertEqual((hero.x, hero.y), (0, 2))
        attack.assert_not_called()

    def test_mindstealer_uses_queued_gm_destination_and_attack(self):
        game = make_game_with_open_board()
        hero = make_hero("Mindstolen")
        target = make_hero("Target")
        hero.x, hero.y = 0, 0
        target.x, target.y = 1, 1
        hero.add_status_effect(
            "madness",
            turns=6,
            scope="expedition",
            madness_attack_allies=True,
            gm_orders=[],
        )
        game.party = [hero, target]
        game.current_phase = "COMBAT"

        self.assertEqual(
            game.queue_mindstealer_action(hero, 0, 1, target),
            "GM Mindstealer action queued for Mindstolen.",
        )
        with patch("game.resolve_hero_vs_hero_attack") as attack:
            game._run_mad_hero_phase()

        self.assertEqual((hero.x, hero.y), (0, 1))
        attack.assert_called_once_with(hero, target, game.combat_log)


if __name__ == "__main__":
    unittest.main()

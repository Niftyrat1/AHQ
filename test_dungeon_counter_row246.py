import unittest
from unittest.mock import patch

from dungeon import Dungeon
from game import GameState
from hero import Hero
from monster import Monster


def make_hero() -> Hero:
    hero = Hero(
        "Hero",
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
    hero.x = 0
    hero.y = 0
    return hero


def make_game() -> GameState:
    game = GameState()
    game.save_game = lambda: None
    game.dungeon = Dungeon()
    game.dungeon.game_state = game
    hero = make_hero()
    game.party = [hero]
    game.hero_movement_remaining = {hero.id: hero.get_movement_allowance("exploration")}
    return game


class DungeonCounterRow246Tests(unittest.TestCase):
    def test_held_fate_counter_turns_failed_monster_hit_roll_into_success(self):
        game = make_game()
        hero = game.party[0]
        monster = Monster(
            "weak_monster",
            "Weak Monster",
            ws=1,
            bs=1,
            strength=1,
            toughness=3,
            speed=6,
            bravery=5,
            intelligence=5,
            wounds=1,
            pv=1,
            weapons=[{"name": "Club", "damage_dice": 1, "critical": 12, "fumble": 1}],
        )
        monster.x = 1
        monster.y = 0
        game.monsters = [monster]
        game.current_phase = "COMBAT"
        game.held_dungeon_counters = ["fate"]

        with patch("gm.get_tactics", return_value="MOVE_ATTACK"), patch("combat.roll_d", side_effect=[2, 1]):
            game._run_combat_gm_phase()

        self.assertNotIn("fate", game.held_dungeon_counters)
        joined_log = "\n".join(game.combat_log)
        self.assertIn("GM spends a Fate counter for Weak Monster", joined_log)
        self.assertIn("becomes a success", joined_log)
        self.assertIn("Hit!", joined_log)

    def test_wandering_counter_drawn_outside_end_exploration_is_held_then_played_far_los(self):
        game = make_game()
        game.current_phase = "EXPLORATION"
        game.held_dungeon_counters = []
        calls = []

        def fake_start(monster_ids, trigger_tile=None, placement_mode="section"):
            calls.append((monster_ids, trigger_tile, placement_mode))
            game.current_phase = "COMBAT"

        game._start_combat_random = fake_start

        game._resolve_dungeon_counter("wandering")
        self.assertEqual(game.held_dungeon_counters, ["wandering"])
        self.assertEqual(calls, [])

        with patch("game.check_dungeon_counter", return_value=None), patch("game.roll_lair_encounter", return_value=["skaven_warrior"]):
            game._run_exploration_gm_phase()

        self.assertEqual(game.held_dungeon_counters, [])
        self.assertEqual(calls, [(["skaven_warrior"], (0, 0), "far_los")])

    def test_character_counter_waits_for_monster_placement(self):
        game = make_game()
        game.current_phase = "EXPLORATION"
        game._resolve_dungeon_counter("character")
        self.assertEqual(game.held_dungeon_counters, ["character"])
        self.assertEqual(game.monsters, [])

        spawned = []

        def fake_spawn(monster_ids, **kwargs):
            spawned.append((monster_ids, kwargs))
            return []

        game.current_phase = "COMBAT"
        game._spawn_reinforcements = fake_spawn
        game._play_held_character_counters((0, 0), "section")

        self.assertEqual(game.held_dungeon_counters, [])
        self.assertTrue(spawned)
        self.assertIn("skaven_warlord", spawned[0][0])
        self.assertFalse(spawned[0][1]["play_character_counters"])

    def test_only_one_ambush_counter_plays_per_combat_turn(self):
        game = make_game()
        game.current_phase = "COMBAT"
        game.held_dungeon_counters = ["ambush", "ambush"]
        calls = []

        def fake_spawn(monster_ids, **kwargs):
            calls.append((monster_ids, kwargs))
            return []

        game._spawn_reinforcements = fake_spawn

        with patch("game.roll_lair_encounter", return_value=["skaven_warrior"]):
            game._play_held_combat_counters()

        self.assertEqual(len(calls), 1)
        self.assertEqual(game.held_dungeon_counters, ["ambush"])

        game._reset_combat_turn_flags()
        with patch("game.roll_lair_encounter", return_value=["skaven_warrior"]):
            game._play_held_combat_counters()

        self.assertEqual(len(calls), 2)
        self.assertEqual(game.held_dungeon_counters, [])


if __name__ == "__main__":
    unittest.main()

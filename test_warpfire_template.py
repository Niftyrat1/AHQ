import unittest
from unittest.mock import patch

from combat import get_fireball_template_area
from gm import _resolve_warpfire_attack
from monster import Monster


class DummyDungeon:
    def is_walkable(self, x, y):
        return True

    def get_los_state(self, x1, y1, x2, y2, model_blockers=None, adjacent_friendly_blockers=None):
        return "clear"


class DummyHero:
    def __init__(self, name, x, y):
        self.name = name
        self.x = x
        self.y = y
        self.is_dead = False
        self.is_ko = False

    def get_effective_bs(self):
        return 3

    def get_effective_toughness(self):
        return 4


class WarpfireTemplateTests(unittest.TestCase):
    def test_fireball_template_is_center_plus_eight_adjacent_squares(self):
        self.assertEqual(
            set(get_fireball_template_area(10, 20)),
            {
                (9, 19), (9, 20), (9, 21),
                (10, 19), (10, 20), (10, 21),
                (11, 19), (11, 20), (11, 21),
            },
        )

    def test_successful_warpfire_only_damages_models_under_template(self):
        thrower = Monster(
            "skaven_warpfire_thrower_team",
            "Warpfire Team",
            ws=6,
            bs=6,
            strength=4,
            toughness=4,
            speed=10,
            bravery=6,
            intelligence=6,
            wounds=3,
            pv=10,
            weapons=[],
            special_rules=["special_ranged_attack"],
        )
        thrower.x = 0
        thrower.y = 0
        thrower.set_support_offset(0, 1)

        target = DummyHero("Target", 4, 0)
        under_template = DummyHero("Template Ally", 4, 1)
        adjacent_to_team = DummyHero("Near Team", 0, -1)
        damaged = []

        def record_damage(hero, damage, log):
            damaged.append(hero.name)
            return False

        with (
            patch("gm.roll_d", return_value=6),
            patch("gm.roll_damage", return_value=(1, [12])),
            patch("gm.apply_damage_to_hero", side_effect=record_damage),
        ):
            resolved = _resolve_warpfire_attack(
                thrower,
                target,
                [target, under_template, adjacent_to_team],
                [thrower],
                DummyDungeon(),
                [],
            )

        self.assertTrue(resolved)
        self.assertEqual(damaged, ["Target", "Template Ally"])


if __name__ == "__main__":
    unittest.main()

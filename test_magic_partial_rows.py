import unittest
from unittest.mock import patch

from game import GameState
from hero import Hero
from monster import Monster
from combat import resolve_hero_ranged_attack


def make_hero(name="Hero", class_type="Warrior", equipment=None):
    hero = Hero(
        name,
        "Human",
        class_type,
        ws=6,
        bs=6,
        strength=3,
        toughness=3,
        speed=6,
        bravery=7,
        intelligence=7,
        wounds=4,
        fate=2,
        equipment=equipment,
    )
    hero.x = 0
    hero.y = 0
    return hero


def make_game():
    game = GameState()
    game.save_game = lambda: None
    game.hero_manager.update_hero = lambda hero: None
    return game


class MagicPartialRowsTests(unittest.TestCase):
    def test_strength_potion_applies_three_turn_melee_bonus(self):
        game = make_game()
        hero = make_hero(
            equipment=[
                {
                    "name": "Strength Potion",
                    "type": "potion",
                    "potion_effect": "strength",
                    "equipped": True,
                }
            ]
        )
        game.party = [hero]
        game.current_phase = "EXPLORATION"
        game.hero_movement_remaining = {hero.id: hero.get_movement_allowance("exploration")}

        allowed, message = game.can_drink_strength_potion(hero)
        self.assertTrue(allowed, message)
        result = game.drink_strength_potion(hero)

        self.assertIn("Strength Potion", result)
        self.assertEqual(hero.get_effective_strength(), 5)
        self.assertEqual(hero.get_bonus_melee_damage_dice(), 2)
        self.assertFalse(any(item.get("potion_effect") == "strength" for item in hero.equipment))

    def test_flames_of_the_phoenix_is_blocked_in_enemy_death_zone(self):
        game = make_game()
        wizard = make_hero(
            "Magnus",
            "Wizard",
            equipment=[{"name": "Dagger", "type": "weapon", "equipped": True}],
        )
        monster = Monster(
            "skaven",
            "Skaven",
            ws=5,
            bs=0,
            strength=3,
            toughness=3,
            speed=6,
            bravery=5,
            intelligence=5,
            wounds=1,
            pv=5,
            weapons=[{"name": "Sword"}],
        )
        monster.x = 1
        monster.y = 0
        game.party = [wizard]
        game.monsters = [monster]
        game.current_phase = "COMBAT"
        game.hero_movement_remaining = {wizard.id: wizard.get_movement_allowance("combat")}

        allowed, message = game.can_hero_cast_spell(wizard, "Flames of the Phoenix")

        self.assertFalse(allowed)
        self.assertIn("enemy death zone", message)

    def test_warpscroll_cannot_start_in_long_reach_death_zone(self):
        game = make_game()
        spearman = make_hero(
            equipment=[
                {
                    "name": "Magic Spear",
                    "type": "weapon",
                    "equipped": True,
                    "long_reach": True,
                }
            ]
        )
        monk = Monster(
            "plague_monk",
            "Plague Monk",
            ws=5,
            bs=0,
            strength=3,
            toughness=3,
            speed=6,
            bravery=7,
            intelligence=7,
            wounds=1,
            pv=10,
            weapons=[{"name": "Sword"}],
            spellcasting={"mode": "warpscroll", "charges": {"Warpscroll": 1}},
        )
        monk.x = 1
        monk.y = 1
        game.party = [spearman]
        game.monsters = [monk]

        self.assertTrue(game._monster_is_in_any_enemy_death_zone(monk))
        self.assertFalse(game._monster_cast_spell(monk))
        self.assertIsNone(monk.spellcasting.get("charging_spell"))

    def test_magic_ammunition_is_consumed_before_normal_ammo(self):
        hero = make_hero(
            equipment=[
                {
                    "name": "Bow",
                    "type": "ranged_weapon",
                    "equipped": True,
                    "damage_dice": 3,
                    "max_range": 36,
                },
                {
                    "name": "Arrows of Death",
                    "type": "ammo",
                    "ammo_type": "arrow",
                    "quantity": 1,
                    "ammo_effect": "death",
                },
            ]
        )
        hero.ammo["arrows"] = 6

        self.assertTrue(hero.has_ammo_for_ranged_weapon())
        self.assertTrue(hero.consume_ranged_ammo())
        self.assertEqual(hero.last_ranged_ammo_effect, "death")
        self.assertEqual(hero.ammo["arrows"], 6)
        self.assertFalse(any(item.get("name") == "Arrows of Death" for item in hero.equipment))

    def test_arrows_of_death_add_one_damage_die(self):
        hero = make_hero(
            equipment=[
                {
                    "name": "Bow",
                    "type": "ranged_weapon",
                    "equipped": True,
                    "damage_dice": 3,
                    "max_range": 36,
                }
            ]
        )
        monster = Monster(
            "target",
            "Target",
            ws=5,
            bs=1,
            strength=3,
            toughness=4,
            speed=6,
            bravery=5,
            intelligence=5,
            wounds=10,
            pv=1,
            weapons=[],
        )
        log = []
        with patch("combat.roll_d", side_effect=[9, 4, 4, 4, 4]):
            hit, damage, result = resolve_hero_ranged_attack(
                hero,
                monster,
                log,
                magic_ammo_effect="death",
            )

        self.assertTrue(hit)
        self.assertEqual(result, "hit")
        self.assertEqual(damage, 4)
        self.assertIn("add +1 damage die", " ".join(log))

    def test_true_flight_hits_without_attack_roll(self):
        hero = make_hero(
            equipment=[
                {
                    "name": "Bow",
                    "type": "ranged_weapon",
                    "equipped": True,
                    "damage_dice": 1,
                    "max_range": 36,
                }
            ]
        )
        monster = Monster(
            "target",
            "Target",
            ws=5,
            bs=12,
            strength=3,
            toughness=4,
            speed=6,
            bravery=5,
            intelligence=5,
            wounds=10,
            pv=1,
            weapons=[],
        )
        with patch("combat.roll_d", return_value=4):
            hit, _, _ = resolve_hero_ranged_attack(hero, monster, [], magic_ammo_effect="true_flight")

        self.assertTrue(hit)

    def test_assassin_ammunition_critical_damage_on_ten_plus(self):
        hero = make_hero(
            equipment=[
                {
                    "name": "Bow",
                    "type": "ranged_weapon",
                    "equipped": True,
                    "damage_dice": 1,
                    "max_range": 36,
                }
            ]
        )
        monster = Monster(
            "target",
            "Target",
            ws=5,
            bs=1,
            strength=3,
            toughness=11,
            speed=6,
            bravery=5,
            intelligence=5,
            wounds=10,
            pv=1,
            weapons=[],
        )
        with patch("combat.roll_d", side_effect=[9, 10, 11, 3]):
            hit, damage, _ = resolve_hero_ranged_attack(hero, monster, [], magic_ammo_effect="assassin")

        self.assertTrue(hit)
        self.assertEqual(damage, 1)


if __name__ == "__main__":
    unittest.main()

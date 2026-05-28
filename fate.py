"""Fate decision handling and failed-roll recovery rules."""

from __future__ import annotations

from typing import Iterable, Optional, TYPE_CHECKING

from hero import Hero

if TYPE_CHECKING:
    from game import GameState


def get_pending_fate_hero(party: Iterable[Hero]) -> Optional[Hero]:
    """Return the first hero currently awaiting a Fate decision, if any."""
    for hero in party:
        if hero.has_pending_fate_decision():
            return hero
    return None


def has_pending_fate_decision(party: Iterable[Hero]) -> bool:
    """Whether any hero in the party is awaiting a Fate decision."""
    return get_pending_fate_hero(party) is not None


def resolve_pending_fate(game_state: "GameState", use_fate: bool) -> str:
    """Resolve the current pending Fate decision for the active game state."""
    hero = get_pending_fate_hero(game_state.party)
    if hero is None:
        return "No Fate decision is pending."

    pending = dict(hero.pending_fate_decision or {})
    pending_type = str(pending.get("type", "damage"))
    damage = int(pending.get("damage", 0))

    if use_fate:
        if not hero.spend_fate():
            return f"{hero.name} has no Fate Points to spend."
        if pending_type == "failed_roll":
            _resolve_spent_failed_roll(game_state, hero, pending)
        else:
            _resolve_spent_damage(game_state, hero, pending)
        game_state.save_game()
        return f"{hero.name} spends a Fate Point."

    hero.pending_fate_decision = None
    if pending_type == "failed_roll":
        return _resolve_refused_failed_roll(game_state, hero, pending)

    hero_ko = hero.take_damage(damage)
    if hero_ko:
        if hero.is_dead:
            if hero.death_turn is None:
                hero.death_turn = game_state.turn_count
            game_state.combat_log.append(f"{hero.name} refuses to spend Fate and dies.")
        else:
            game_state.combat_log.append(f"{hero.name} refuses to spend Fate and is knocked out.")
    if game_state._all_true_heroes_dead():
        game_state._game_over()
        return f"{hero.name} refuses to spend Fate and dies."
    game_state.ensure_phase_consistency()
    game_state.save_game()
    return f"{hero.name} refuses to spend Fate."


def _resolve_spent_failed_roll(game_state: "GameState", hero: Hero, pending: dict) -> None:
    """Apply the successful Fate branch for a failed roll."""
    source = str(pending.get("source", "failed roll"))
    if source == "chasm":
        landing = pending.get("landing")
        if isinstance(landing, list) and len(landing) == 2:
            hero.x, hero.y = int(landing[0]), int(landing[1])
            game_state.dungeon._explore_from(hero.x, hero.y)
    elif source == "disarm_trap":
        center = pending.get("trap_center")
        if isinstance(center, list) and len(center) == 2:
            from traps import clear_visible_trap

            clear_visible_trap(game_state.dungeon, (int(center[0]), int(center[1])))
        game_state.combat_log.append(f"{hero.name} spends Fate and turns the failed disarm into a success.")
    elif source == "portcullis_lift":
        for zone_pos in pending.get("zone_positions", []):
            if not (isinstance(zone_pos, list) and len(zone_pos) == 2):
                continue
            current_marker = game_state.dungeon.trap_markers.get((int(zone_pos[0]), int(zone_pos[1])))
            if current_marker is None:
                continue
            current_marker["blocks_movement"] = False
            current_marker["temporary_open"] = True
            current_marker["opened_on_turn"] = game_state.turn_count
        game_state.combat_log.append(f"{hero.name} spends Fate and forces the portcullis open.")
    elif source == "poisoned_wind_breath":
        game_state.combat_log.append(f"{hero.name} spends Fate and holds their breath through the poisoned wind.")
    elif source == "warpscroll":
        game_state.combat_log.append(f"{hero.name} spends Fate and resists the Warpscroll.")
    elif source == "choke":
        game_state.combat_log.append(f"{hero.name} spends Fate and survives the choking spell.")
    elif source == "pit_leap":
        landing = pending.get("landing")
        if isinstance(landing, list) and len(landing) == 2:
            hero.x, hero.y = int(landing[0]), int(landing[1])
            game_state.dungeon._explore_from(hero.x, hero.y)
    elif source == "pit_climb":
        escape_tile = pending.get("escape_tile")
        if isinstance(escape_tile, list) and len(escape_tile) == 2:
            hero.x, hero.y = int(escape_tile[0]), int(escape_tile[1])
            game_state.combat_log.append(f"{hero.name} spends Fate and scrambles out of the pit.")
    elif source == "fearsome_bravery":
        hero.remove_status_effect("cowering")
        game_state.combat_log.append(f"{hero.name} spends Fate and stands firm against fear.")
    elif source == "power_of_the_phoenix":
        target_id = pending.get("target_hero_id")
        target_hero = next((current for current in game_state.party if current.id == target_id), None)
        if target_hero is not None:
            target_hero.restore_to_full()
            game_state.combat_log.append(
                f"{hero.name} spends Fate and turns the failed Power of the Phoenix test into a success."
            )
    elif source == "inferno_of_doom":
        area = []
        for pos in pending.get("area", []):
            if isinstance(pos, list) and len(pos) == 2:
                area.append((int(pos[0]), int(pos[1])))
        damage_dice = int(pending.get("success_damage_dice", pending.get("failed_damage_dice", 5)))
        spell_name = str(pending.get("spell_name", "Inferno of Doom"))
        if area:
            game_state._apply_spell_damage(area, damage_dice, spell_name)
    game_state.combat_log.append(f"{hero.name} spends a Fate Point and turns a failed roll into a success.")


def _resolve_spent_damage(game_state: "GameState", hero: Hero, pending: dict) -> None:
    """Apply the successful Fate branch for turn-wide damage negation."""
    landing = pending.get("landing")
    if isinstance(landing, list) and len(landing) == 2:
        hero.x, hero.y = int(landing[0]), int(landing[1])
    game_state.combat_log.append(f"{hero.name} spends a Fate Point and negates all damage suffered this turn.")


def _resolve_refused_failed_roll(game_state: "GameState", hero: Hero, pending: dict) -> str:
    """Apply the normal failed-roll outcome after Fate is refused."""
    source = str(pending.get("source", "failed roll"))
    if source == "chasm":
        hero.current_wounds = 0
        hero.is_ko = True
        hero.is_dead = True
        if hero.death_turn is None:
            hero.death_turn = game_state.turn_count
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and falls into the chasm.")
        if game_state._all_true_heroes_dead():
            game_state._game_over()
        else:
            game_state.ensure_phase_consistency()
            game_state.save_game()
        return f"{hero.name} refuses to spend Fate and dies."

    if source == "disarm_trap":
        center = pending.get("trap_center")
        if isinstance(center, list) and len(center) == 2:
            from traps import resolve_failed_disarm_outcome

            resolve_failed_disarm_outcome(
                hero,
                game_state.dungeon,
                game_state.combat_log,
                (int(center[0]), int(center[1])),
                raw_disarm_roll=pending.get("raw_disarm_roll"),
            )
        game_state.ensure_phase_consistency()
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate and the trap goes off."

    if source == "portcullis_lift":
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and the portcullis stays shut.")
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate and the portcullis stays shut."

    if source == "poisoned_wind_breath":
        from combat import apply_damage_to_hero

        apply_damage_to_hero(hero, hero.current_wounds, game_state.combat_log, allow_fate=False, source="Poisoned Wind")
        game_state.ensure_phase_consistency()
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate and chokes in the poisoned wind."

    if source == "warpscroll":
        _kill_hero(game_state, hero, f"{hero.name} refuses to spend Fate and dies to the Warpscroll.")
        return f"{hero.name} refuses to spend Fate and dies."

    if source == "choke":
        _kill_hero(game_state, hero, f"{hero.name} refuses to spend Fate and suffocates.")
        return f"{hero.name} refuses to spend Fate and dies."

    if source == "pit_leap":
        pit = pending.get("pit")
        if isinstance(pit, list) and len(pit) == 2:
            hero.x, hero.y = int(pit[0]), int(pit[1])
        from traps import resolve_pit_fall

        resolve_pit_fall(hero, game_state.dungeon, game_state.combat_log)
        game_state.ensure_phase_consistency()
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate and falls into the pit."

    if source == "pit_climb":
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and remains trapped in the pit.")
        game_state.ensure_phase_consistency()
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate."

    if source == "fearsome_bravery":
        hero.add_status_effect("cowering", scope="phase")
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and cowers before the fearsome foe.")
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate."

    if source == "power_of_the_phoenix":
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and the failed resurrection stands.")
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate."

    if source == "inferno_of_doom":
        area = []
        for pos in pending.get("area", []):
            if isinstance(pos, list) and len(pos) == 2:
                area.append((int(pos[0]), int(pos[1])))
        damage_dice = int(pending.get("failed_damage_dice", 5))
        spell_name = str(pending.get("spell_name", "Inferno of Doom"))
        if area:
            game_state._apply_spell_damage(area, damage_dice, spell_name)
        game_state.combat_log.append(f"{hero.name} refuses to spend Fate and the failed spell roll stands.")
        game_state.save_game()
        return f"{hero.name} refuses to spend Fate."

    game_state.combat_log.append(f"{hero.name} refuses to spend Fate and the failed roll stands.")
    game_state.save_game()
    return f"{hero.name} refuses to spend Fate."


def _kill_hero(game_state: "GameState", hero: Hero, log_message: str) -> None:
    """Kill a hero from a refused Fate branch and update state consistently."""
    hero.is_dead = True
    hero.is_ko = True
    hero.current_wounds = 0
    hero.death_turn = game_state.turn_count
    game_state.combat_log.append(log_message)
    if game_state._all_true_heroes_dead():
        game_state._game_over()
    else:
        game_state.ensure_phase_consistency()
        game_state.save_game()

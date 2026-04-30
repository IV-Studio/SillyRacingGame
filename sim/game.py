from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import random
from typing import Dict, List, Optional

from sim.abilities import Ability, MysteryCard, load_abilities, load_mystery_cards
from sim.actions import ActionBoard, ActionSlot, parse_action_value
from sim.dice import DiceLibrary, DieFace
from sim.player import Player
from sim.track import Track


@dataclass
class GameConfig:
    player_count: int = 3
    laps_to_win: int = 5
    seed: int = 1
    max_rounds: int = 60


class RacerGame:
    def __init__(self, root: Path, config: GameConfig) -> None:
        self.root = root
        self.config = config
        data_root = root / "data"
        self.dice = DiceLibrary.from_csv(data_root / "dice_faces.csv")
        self.abilities = load_abilities(data_root / "abilities.csv")
        self.mystery_cards = load_mystery_cards(data_root / "mystery_cards.csv")
        self.board = ActionBoard.from_csv(data_root / "action_rows.csv")
        self.track = Track.from_csv(data_root / "track_spaces.csv")
        self.rng = random.Random(config.seed)
        self.players = [Player(index=i, name=f"P{i + 1}") for i in range(config.player_count)]
        self.first_player_index = 0
        self.round_number = 0
        self.winner: Optional[Player] = None
        self.market: List[Ability] = []
        self.ability_deck = self.abilities[:]
        self.mystery_deck = self.mystery_cards[:]
        self.rng.shuffle(self.ability_deck)
        self.rng.shuffle(self.mystery_deck)
        self.metrics: Dict[str, object] = {
            "rounds_played": 0,
            "movement_per_round": [],
            "lap_snapshots": [],
            "ability_wins": Counter(),
        }
        self.placed_traps: Dict[int, str] = {}
        self.active_reaction_moves: Optional[Counter[int]] = None

    def refresh_ability_market(self) -> None:
        target_size = min(len(self.players) + 1, len(self.ability_deck))
        while len(self.market) < target_size and self.ability_deck:
            self.market.append(self.ability_deck.pop())

    def draw_mystery_card(self) -> MysteryCard:
        if not self.mystery_deck:
            self.mystery_deck = self.mystery_cards[:]
            self.rng.shuffle(self.mystery_deck)
        return self.mystery_deck.pop()

    def run(self) -> Dict[str, object]:
        while self.winner is None and self.round_number < self.config.max_rounds:
            self.play_round()
        if self.winner is None:
            leader = max(self.players, key=lambda player: (player.laps, player.position, player.coins))
            self.winner = leader
        self.metrics["rounds_played"] = self.round_number
        for ability in self.winner.abilities:
            self.metrics["ability_wins"][ability.name] += 1
        return {
            "winner": self.winner.name,
            "rounds": self.round_number,
            "players": self.players,
            "metrics": self.metrics,
        }

    def play_round(self) -> None:
        self.round_number += 1
        self.board.reset()
        self.refresh_ability_market()
        for player in self.players:
            player.reset_round_effects()
        self.drafting_phase()
        round_movement_before = sum(player.stats["movement"] for player in self.players)
        self.resolution_phase()
        round_movement_after = sum(player.stats["movement"] for player in self.players)
        self.metrics["movement_per_round"].append(round_movement_after - round_movement_before)
        self.metrics["lap_snapshots"].append([player.laps for player in self.players])

    def drafting_phase(self) -> None:
        turn_order = self.turn_order_from_first_player()
        for _ in range(5):
            for player_index in turn_order:
                row = self.choose_draft_row(self.players[player_index])
                placed = row.place(player_index)
                if not placed:
                    fallback = self.best_available_row(self.players[player_index])
                    fallback.place(player_index)

    def choose_draft_row(self, player: Player):
        candidates = []
        for row in self.board.rows:
            open_slot = row.next_open_slot()
            if open_slot is None:
                continue
            slot = row.slots[open_slot]
            candidates.append((self.evaluate_row(player, row.row_id, slot.value), row))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def best_available_row(self, player: Player):
        open_rows = [row for row in self.board.rows if row.next_open_slot() is not None]
        open_rows.sort(
            key=lambda row: self.evaluate_row(player, row.row_id, row.slots[row.next_open_slot()].value),
            reverse=True,
        )
        return open_rows[0]

    def evaluate_row(self, player: Player, row_id: str, raw_value: str) -> float:
        value = parse_action_value(raw_value)
        lead = max(self.player_progress(other) for other in self.players)
        my_progress = self.player_progress(player)
        behind = max(0, lead - my_progress)
        if row_id == "first_player":
            return 2.0 if behind < 8 else 0.5
        if row_id == "gain_coins":
            return int(raw_value) + (2.5 if player.coins < 4 else 0.0)
        if row_id == "gain_fuel":
            return int(raw_value) + (3.0 if player.fuel < 3 else 0.0)
        if row_id == "fixed_move":
            return float(raw_value) + behind * 0.05
        if row_id == "ability_draft":
            cost = int(raw_value)
            if not self.market:
                return 0.5
            return (5.5 - cost * 0.3) + (2.0 if player.coins >= cost else -2.0)
        if row_id == "dice_yellow_orange_burst":
            return 2.0 + behind * 0.02
        if row_id == "dice_orange_red_push":
            risk_bonus = 1.0 if player.fuel >= 2 else -0.5
            return 3.2 + risk_bonus + behind * 0.04
        if row_id == "dice_yellow_red_gamble":
            risk_bonus = 2.0 if player.fuel >= 3 else -1.0
            return 3.8 + risk_bonus + behind * 0.06
        return float(value.get("keep", "0"))

    def resolution_phase(self) -> None:
        for row in self.board.rows:
            if self.winner is not None:
                return
            if row.row_id == "ability_draft":
                pairs = list(row.occupied_pairs())
                pairs.sort(key=lambda pair: int(pair[0].value), reverse=True)
            else:
                pairs = row.occupied_pairs()
            for slot, player_index in pairs:
                self.resolve_slot(slot, self.players[player_index])
                if self.winner is not None:
                    return

    def resolve_slot(self, slot: ActionSlot, player: Player) -> None:
        slot_start = int(self.player_progress(player))
        followers = self.followers_for_player(player)
        self.active_reaction_moves = Counter()
        self.consume_proactive_cards(player)
        if slot.row_id == "first_player":
            if slot.slot_index == 0:
                self.first_player_index = player.index
        elif slot.row_id == "gain_coins":
            player.gain_coins(int(slot.value))
        elif slot.row_id == "gain_fuel":
            bonus = int(slot.value) + self.bonus_resource_gain(player, "fuel", "gain_fuel")
            player.gain_fuel(bonus)
        elif slot.row_id == "fixed_move":
            move_bonus = self.total_move_bonus(player, "fixed_move")
            self.move_player(player, int(slot.value) + move_bonus)
        elif slot.row_id == "ability_draft":
            self.resolve_ability_draft(player, int(slot.value))
        elif slot.row_type == "dice_move":
            self.resolve_dice_move(player, slot)
        self.flush_reactive_moves()
        slot_end = int(self.player_progress(player))
        net_delta = slot_end - slot_start
        if net_delta != 0:
            for follower in followers:
                self.move_player(follower, net_delta)
        self.active_reaction_moves = None

    def resolve_ability_draft(self, player: Player, cost: int) -> None:
        if not self.market or player.coins < cost:
            return
        scored_market = sorted(self.market, key=lambda ability: self.evaluate_ability(player, ability), reverse=True)
        chosen = scored_market[0]
        if player.spend_coins(cost):
            player.add_ability(chosen)
            self.market.remove(chosen)

    def evaluate_ability(self, player: Player, ability: Ability) -> float:
        effect_scores = {
            "reroll_once": 5.0,
            "extra_roll": 5.5,
            "extra_keep": 6.0,
            "fuel_discount": 4.5,
            "color_upgrade": 4.0 if player.fuel >= 2 else 2.0,
            "ignore_trap": 3.5,
            "collect_passed_coins": 4.0,
            "collect_passed_boxes": 3.5,
            "bonus_on_color": 3.0,
            "move_bonus": 4.0,
            "gain_bonus": 3.0,
            "reroll_color_once": 3.5,
            "adjust_color_roll": 4.0,
            "fixed_die_value": 4.5,
            "round_up_even": 3.5,
            "parity_transform": 4.0,
            "position_roll_modifier": 3.0,
            "predict_red_roll": 2.5,
            "match_orange_roll": 2.5,
            "matching_bonus": 3.5,
            "mismatch_bonus": 3.0,
            "avoid_trap_once_per_round": 4.0,
            "place_trap_on_negative": 2.5,
            "limit_trap_setback": 3.0,
            "trap_rerolls": 3.0,
            "trap_extra_choice": 3.0,
            "collect_backward_rewards": 2.5,
            "space_is_trap": 2.0,
            "follow_movement": 2.5,
            "move_bonus_on_pass": 3.0,
            "move_when_passed": 2.0,
            "move_when_landed_on": 2.0,
            "move_on_roll_value": 2.0,
        }
        return effect_scores.get(ability.effect_type, 1.0)

    def resolve_dice_move(self, player: Player, slot: ActionSlot) -> None:
        params = parse_action_value(slot.value)
        colors = params["colors"].split("|")
        keep = int(params["keep"])
        roll_count = int(params["roll"]) + self.extra_roll_count(player)
        keep_count = keep + self.extra_keep_count(player)
        colors = self.upgraded_colors(player, colors)
        pool = [self.roll_selected_color(player, colors) for _ in range(roll_count)]
        if self.should_reroll_pool(player, pool):
            pool = [self.roll_selected_color(player, colors) for _ in range(roll_count)]
        keepers = self.choose_kept_faces(player, pool, keep_count)
        self.apply_overclock(player, keepers)
        move_total = 0
        fuel_total = 0
        for face in keepers:
            move_total += face.value
            fuel_total += max(0, face.fuel_cost - self.fuel_discount(player))
            bonus_coins = self.bonus_on_color(player, face.color)
            if bonus_coins:
                player.gain_coins(bonus_coins)
        move_total += self.dice_pool_bonus(player, keepers)
        if fuel_total > 0:
            paid = player.spend_fuel(fuel_total)
            if not paid:
                move_total = 0
        move_total += self.consume_move_bonus_card(player)
        self.move_player(player, move_total)

    def consume_proactive_cards(self, player: Player) -> None:
        for card in list(player.mystery_cards):
            if card.effect_type == "gain_fuel" and player.fuel <= 2:
                player.gain_fuel(int(card.parameters.get("amount", "0")))
                player.remove_mystery(card)
            elif card.effect_type == "gain_coins" and player.coins <= 2:
                player.gain_coins(int(card.parameters.get("amount", "0")))
                player.remove_mystery(card)
            elif card.effect_type == "sabotage_blast":
                if self.should_use_sabotage(player, card):
                    self.resolve_sabotage(player, card)
                    player.remove_mystery(card)

    def should_use_sabotage(self, player: Player, card: MysteryCard) -> bool:
        blast_range = int(card.parameters.get("range", "3"))
        targets = [other for other in self.players if other is not player and self.distance_between(player, other) <= blast_range]
        return bool(targets)

    def resolve_sabotage(self, player: Player, card: MysteryCard) -> None:
        blast_range = int(card.parameters.get("range", "3"))
        die_color = card.parameters.get("die_color", "yellow")
        for other in self.players:
            if other is player or self.distance_between(player, other) > blast_range:
                continue
            face = self.roll_selected_color(other, [die_color], context="trap")
            setback = max(0, face.value)
            if setback > 0:
                self.resolve_trap_like_setback(other, setback)

    def apply_overclock(self, player: Player, keepers: List[DieFace]) -> None:
        if not keepers:
            return
        for card in list(player.mystery_cards):
            if card.effect_type == "overclock":
                boost = int(card.parameters.get("amount", "2"))
                best = max(keepers, key=lambda face: face.value)
                keepers[keepers.index(best)] = DieFace(
                    id=f"{best.id}_overclock",
                    color=best.color,
                    description=f"{best.description} Add {boost} movement.",
                    value=best.value + boost,
                    fuel_cost=best.fuel_cost,
                )
                player.remove_mystery(card)
                return

    def roll_selected_color(self, player: Player, allowed_colors: List[str], *, context: str = "movement", trigger_reactions: bool = True) -> DieFace:
        chosen_color = self.choose_roll_color(player, allowed_colors)
        face = self.dice.roll(self.rng, chosen_color)
        face = self.maybe_reroll_color_face(player, face, context=context)
        face = self.apply_roll_modifiers(player, face, context=context)
        if trigger_reactions:
            self.handle_reactive_roll_effects(player, face, context=context)
        return face

    def choose_roll_color(self, player: Player, allowed_colors: List[str]) -> str:
        if len(allowed_colors) == 1:
            return allowed_colors[0]
        lead = max(self.player_progress(other) for other in self.players)
        my_progress = self.player_progress(player)
        behind = max(0, lead - my_progress)
        best_color = allowed_colors[0]
        best_score = float("-inf")
        for color in allowed_colors:
            faces = self.dice.faces_by_color[color]
            average_value = sum(face.value for face in faces) / len(faces)
            average_fuel = sum(face.fuel_cost for face in faces) / len(faces)
            aggression = 0.35 if behind > 12 else 0.0
            caution = 0.75 if player.fuel < 2 else 0.45
            score = average_value + aggression - average_fuel * caution
            if score > best_score:
                best_score = score
                best_color = color
        return best_color

    def maybe_reroll_color_face(self, player: Player, face: DieFace, *, context: str) -> DieFace:
        for ability in player.has_ability("reroll_color_once"):
            if ability.parameters.get("color") != face.color:
                continue
            threshold = int(ability.parameters.get("threshold", "0"))
            if face.value > threshold:
                continue
            rerolled = self.dice.roll(self.rng, face.color)
            rerolled = self.apply_roll_modifiers(player, rerolled, context=context)
            if self.score_face(rerolled, context=context) >= self.score_face(face, context=context):
                face = rerolled
        return face

    def apply_roll_modifiers(self, player: Player, face: DieFace, *, context: str) -> DieFace:
        if context != "trap":
            for ability in player.has_ability("fixed_die_value"):
                fixed_value = int(ability.parameters.get("amount", "2"))
                fixed_face = self.replace_face_value(face, fixed_value, "fixed", f"{face.description} Use fixed {fixed_value} move.")
                if self.score_face(fixed_face, context=context) >= self.score_face(face, context=context):
                    face = fixed_face
        for ability in player.has_ability("adjust_color_roll"):
            if ability.parameters.get("color") != face.color:
                continue
            delta = int(ability.parameters.get("amount", "1"))
            plus_face = self.replace_face_value(face, face.value + delta, "plus", f"{face.description} Add {delta}.")
            minus_face = self.replace_face_value(face, face.value - delta, "minus", f"{face.description} Subtract {delta}.")
            face = max((face, plus_face, minus_face), key=lambda candidate: self.score_face(candidate, context=context))
        for _ in player.has_ability("round_up_even"):
            rounded = face.value if face.value % 2 == 0 else face.value + 1
            face = self.replace_face_value(face, rounded, "even", f"{face.description} Rounded up to even.")
        for ability in player.has_ability("parity_transform"):
            mode = ability.parameters.get("mode")
            if mode == "zero_even_double_odd":
                adjusted = 0 if face.value % 2 == 0 else face.value * 2
            elif mode == "minus2_even_plus2_odd":
                adjusted = face.value - 2 if face.value % 2 == 0 else face.value + 2
            else:
                continue
            face = self.replace_face_value(face, adjusted, "parity", f"{face.description} Parity modified.")
        for ability in player.has_ability("position_roll_modifier"):
            if self.is_last_place(player):
                bonus = int(ability.parameters.get("last_bonus", "0"))
                face = self.replace_face_value(face, face.value + bonus, "last", f"{face.description} Last-place boost.")
            elif self.is_first_place(player):
                penalty = int(ability.parameters.get("first_penalty", "0"))
                face = self.replace_face_value(face, face.value - penalty, "first", f"{face.description} First-place penalty.")
        return face

    def replace_face_value(self, face: DieFace, value: int, suffix: str, description: str) -> DieFace:
        return DieFace(
            id=f"{face.id}_{suffix}",
            color=face.color,
            description=description,
            value=value,
            fuel_cost=face.fuel_cost,
        )

    def score_face(self, face: DieFace, *, context: str) -> float:
        if context == "trap":
            return -max(0, face.value)
        return face.value - max(0, face.fuel_cost - 1) * 0.45

    def handle_reactive_roll_effects(self, roller: Player, face: DieFace, *, context: str) -> None:
        if face.value < 0:
            for ability in roller.has_ability("place_trap_on_negative"):
                self.place_trap_anywhere(roller, ability.parameters.get("color", "yellow"))
        for watcher in self.players:
            if face.color == "red":
                for ability in watcher.has_ability("predict_red_roll"):
                    prediction = self.rng.choice([candidate.value for candidate in self.dice.faces_by_color["red"]])
                    if prediction == face.value:
                        self.queue_reactive_move(watcher, int(ability.parameters.get("bonus", "2")))
            if face.color == "orange":
                for ability in watcher.has_ability("match_orange_roll"):
                    echo = self.roll_selected_color(watcher, ["orange"], context=context, trigger_reactions=False)
                    if echo.value == face.value:
                        self.queue_reactive_move(watcher, int(ability.parameters.get("bonus", "1")))
            if watcher is not roller:
                for ability in watcher.has_ability("move_on_roll_value"):
                    if face.value == int(ability.parameters.get("value", "0")):
                        self.queue_reactive_move(watcher, int(ability.parameters.get("amount", "0")))

    def should_reroll_pool(self, player: Player, pool: List[DieFace]) -> bool:
        for card in list(player.mystery_cards):
            if card.effect_type == "reroll_pool":
                threshold = int(card.parameters.get("threshold", "2"))
                if max(face.value for face in pool) <= threshold:
                    player.remove_mystery(card)
                    return True
        abilities = player.has_ability("reroll_once")
        if not abilities:
            return False
        threshold = int(abilities[0].parameters.get("threshold", "2"))
        return max(face.value for face in pool) <= threshold

    def choose_kept_faces(self, player: Player, pool: List[DieFace], keep_count: int) -> List[DieFace]:
        affordable = [face for face in pool if max(0, face.fuel_cost - self.fuel_discount(player)) <= player.fuel]
        chosen_pool = affordable if affordable else []
        chosen_pool.sort(key=lambda face: (face.value, -face.fuel_cost), reverse=True)
        return chosen_pool[:keep_count]

    def dice_pool_bonus(self, player: Player, keepers: List[DieFace]) -> int:
        bonus = 0
        if len(keepers) >= 2 and player.has_ability("matching_bonus"):
            counts = Counter(face.value for face in keepers)
            matching_values = [value for value, count in counts.items() if count >= 2]
            if matching_values:
                best_value = max(matching_values)
                multiplier = int(player.has_ability("matching_bonus")[0].parameters.get("multiplier", "2"))
                bonus += best_value * multiplier
        if len(keepers) >= 3 and player.has_ability("mismatch_bonus"):
            unique_values = {face.value for face in keepers}
            minimum_dice = int(player.has_ability("mismatch_bonus")[0].parameters.get("minimum_dice", "3"))
            if len(keepers) >= minimum_dice and len(unique_values) > 1:
                bonus += int(player.has_ability("mismatch_bonus")[0].parameters.get("amount", "0"))
        return bonus

    def upgraded_colors(self, player: Player, base_colors: List[str]) -> List[str]:
        upgraded = list(base_colors)
        for ability in player.has_ability("color_upgrade"):
            source = ability.parameters.get("from")
            target = ability.parameters.get("to")
            if source in upgraded and target:
                upgraded.append(target)
        unique_colors = []
        for color in upgraded:
            if color not in unique_colors:
                unique_colors.append(color)
        return unique_colors

    def extra_roll_count(self, player: Player) -> int:
        return sum(int(ability.parameters.get("count", "0")) for ability in player.has_ability("extra_roll"))

    def extra_keep_count(self, player: Player) -> int:
        return sum(int(ability.parameters.get("count", "0")) for ability in player.has_ability("extra_keep"))

    def fuel_discount(self, player: Player) -> int:
        return sum(int(ability.parameters.get("amount", "0")) for ability in player.has_ability("fuel_discount"))

    def bonus_resource_gain(self, player: Player, resource: str, row: str) -> int:
        total = 0
        for ability in player.has_ability("gain_bonus"):
            if ability.parameters.get("resource") == resource and ability.parameters.get("row") == row:
                total += int(ability.parameters.get("amount", "0"))
        return total

    def total_move_bonus(self, player: Player, trigger: str) -> int:
        total = 0
        for ability in player.has_ability("move_bonus"):
            if ability.trigger == trigger:
                total += int(ability.parameters.get("amount", "0"))
        return total

    def bonus_on_color(self, player: Player, color: str) -> int:
        total = 0
        for ability in player.has_ability("bonus_on_color"):
            if ability.parameters.get("color") == color:
                total += int(ability.parameters.get("coins", "1"))
        return total

    def consume_move_bonus_card(self, player: Player) -> int:
        for card in list(player.mystery_cards):
            if card.effect_type == "move_bonus":
                if player.laps < self.config.laps_to_win - 1 or player.position > self.track.length * 0.75:
                    player.remove_mystery(card)
                    return int(card.parameters.get("amount", "0"))
        return 0

    def move_player(self, player: Player, amount: int) -> None:
        if amount == 0:
            return
        steps = abs(amount)
        for step_index in range(steps):
            if amount > 0:
                landed_on_main = self.advance_one_step(player)
                if landed_on_main:
                    passed_space = self.track.get_space(player.position)
                    if self.collect_passed_coins(player) and step_index < steps - 1 and passed_space.space_type == "coin":
                        player.gain_coins(int(passed_space.metadata.get("coins", "1")))
                    if self.collect_passed_boxes(player) and step_index < steps - 1 and passed_space.space_type == "box":
                        self.resolve_passed_box(player)
                    self.handle_pass_triggers(player, is_final_step=step_index == steps - 1)
            else:
                self.retreat_one_step(player)
                if self.collect_backward_rewards(player):
                    self.resolve_backward_rewards(player)
        player.stats["movement"] += amount
        if player.laps >= self.config.laps_to_win:
            self.winner = player
            return
        self.resolve_post_move_cards(player)
        self.resolve_landing(player)

    def collect_passed_coins(self, player: Player) -> bool:
        return bool(player.has_ability("collect_passed_coins"))

    def collect_passed_boxes(self, player: Player) -> bool:
        return bool(player.has_ability("collect_passed_boxes"))

    def collect_backward_rewards(self, player: Player) -> bool:
        return bool(player.has_ability("collect_backward_rewards"))

    def player_progress(self, player: Player) -> float:
        return self.track.progress_value(position=player.position, laps=player.laps)

    def advance_one_step(self, player: Player) -> bool:
        next_position = (player.position + 1) % self.track.length
        if next_position == 0:
            player.laps += 1
        player.position = next_position
        return True

    def retreat_one_step(self, player: Player) -> None:
        if player.position == 0 and player.laps > 0:
            player.laps -= 1
        player.position = (player.position - 1) % self.track.length

    def resolve_landing(self, player: Player) -> None:
        if self.winner is not None:
            return
        trap_color = self.trap_color_on_space(player)
        self.queue_landed_on_moves(player)
        if trap_color is not None:
            self.resolve_trap(player, trap_color)
            return
        space = self.track.get_space(player.position)
        if space.space_type == "coin":
            player.gain_coins(int(space.metadata.get("coins", "1")))
        elif space.space_type == "box":
            self.apply_drawn_card(player, self.draw_mystery_card())
        elif space.space_type == "trap":
            self.resolve_trap(player, space.metadata.get("color", "yellow"))

    def resolve_trap(self, player: Player, color: str) -> None:
        if player.pending.ignore_next_trap:
            player.pending.ignore_next_trap = False
            player.stats["traps_ignored"] += 1
            return
        if player.has_ability("avoid_trap_once_per_round") and player.pending.traps_avoided_this_round == 0:
            player.pending.traps_avoided_this_round += 1
            player.stats["traps_ignored"] += 1
            return
        for card in list(player.mystery_cards):
            if card.effect_type == "ignore_trap":
                player.remove_mystery(card)
                player.stats["traps_ignored"] += 1
                return
        for ability in player.has_ability("ignore_trap"):
            if ability.parameters.get("color") == color:
                player.stats["traps_ignored"] += 1
                return
        face = self.best_trap_face(player, color)
        setback = max(0, face.value)
        for ability in player.has_ability("limit_trap_setback"):
            setback = min(setback, int(ability.parameters.get("amount", "2")))
        if setback > 0:
            self.resolve_trap_like_setback(player, setback)

    def resolve_trap_like_setback(self, player: Player, setback: int) -> None:
        for card in list(player.mystery_cards):
            if card.effect_type == "ignore_trap":
                player.remove_mystery(card)
                player.stats["traps_ignored"] += 1
                return
        self.move_player(player, -setback)

    def resolve_post_move_cards(self, player: Player) -> None:
        for card in list(player.mystery_cards):
            if card.effect_type == "drafting_line":
                bonus = self.drafting_line_bonus(player, int(card.parameters.get("range", "5")))
                if bonus > 0:
                    player.remove_mystery(card)
                    self.move_player(player, bonus)
                    return

    def drafting_line_bonus(self, player: Player, max_range: int) -> int:
        count = 0
        for other in self.players:
            if other is player:
                continue
            distance = self.forward_distance(player, other)
            if 1 <= distance <= max_range:
                count += 1
        return count

    def distance_between(self, player: Player, other: Player) -> int:
        my_progress = int(self.player_progress(player))
        other_progress = int(self.player_progress(other))
        return abs(other_progress - my_progress)

    def forward_distance(self, player: Player, other: Player) -> int:
        my_progress = int(self.player_progress(player))
        other_progress = int(self.player_progress(other))
        diff = other_progress - my_progress
        if diff <= 0:
            return 9999
        return diff

    def turn_order_from_first_player(self) -> List[int]:
        indices = list(range(len(self.players)))
        return indices[self.first_player_index :] + indices[: self.first_player_index]

    def is_first_place(self, player: Player) -> bool:
        my_progress = self.player_progress(player)
        return all(my_progress >= self.player_progress(other) for other in self.players)

    def is_last_place(self, player: Player) -> bool:
        my_progress = self.player_progress(player)
        return all(my_progress <= self.player_progress(other) for other in self.players)

    def queue_reactive_move(self, player: Player, amount: int) -> None:
        if amount == 0:
            return
        if self.active_reaction_moves is None:
            self.move_player(player, amount)
            return
        self.active_reaction_moves[player.index] += amount

    def flush_reactive_moves(self) -> None:
        if self.active_reaction_moves is None:
            return
        while self.active_reaction_moves:
            queued = dict(self.active_reaction_moves)
            self.active_reaction_moves.clear()
            for player_index, amount in queued.items():
                self.move_player(self.players[player_index], amount)

    def followers_for_player(self, player: Player) -> List[Player]:
        followers: List[Player] = []
        for other in self.players:
            if other is player:
                continue
            if other.position == player.position and other.laps == player.laps and other.has_ability("follow_movement"):
                followers.append(other)
        return followers

    def apply_drawn_card(self, player: Player, card: MysteryCard) -> None:
        if card.effect_type == "gain_fuel" and player.fuel <= 2:
            player.gain_fuel(int(card.parameters.get("amount", "0")))
        elif card.effect_type == "gain_coins" and player.coins <= 2:
            player.gain_coins(int(card.parameters.get("amount", "0")))
        else:
            player.draw_mystery(card)

    def resolve_passed_box(self, player: Player) -> None:
        self.apply_drawn_card(player, self.draw_mystery_card())

    def handle_pass_triggers(self, player: Player, *, is_final_step: bool) -> None:
        for other in self.players:
            if other is player:
                continue
            if other.position != player.position or other.laps != player.laps:
                continue
            if is_final_step:
                continue
            for ability in player.has_ability("move_bonus_on_pass"):
                self.queue_reactive_move(player, int(ability.parameters.get("amount", "0")))
            for ability in other.has_ability("move_when_passed"):
                self.queue_reactive_move(other, int(ability.parameters.get("amount", "0")))

    def queue_landed_on_moves(self, player: Player) -> None:
        for other in self.players:
            if other is player:
                continue
            if other.position == player.position and other.laps == player.laps:
                for ability in other.has_ability("move_when_landed_on"):
                    self.queue_reactive_move(other, int(ability.parameters.get("amount", "0")))

    def resolve_backward_rewards(self, player: Player) -> None:
        space = self.track.get_space(player.position)
        if space.space_type == "coin":
            player.gain_coins(int(space.metadata.get("coins", "1")))
        elif space.space_type == "box":
            self.resolve_passed_box(player)

    def trap_color_on_space(self, player: Player) -> Optional[str]:
        placed = self.placed_traps.get(player.position)
        if placed is not None:
            return placed
        for other in self.players:
            if other is player:
                continue
            if other.position == player.position and other.laps == player.laps and other.has_ability("space_is_trap"):
                return other.has_ability("space_is_trap")[0].parameters.get("color", "yellow")
        return None

    def best_trap_face(self, player: Player, color: str) -> DieFace:
        candidates = [self.roll_selected_color(player, [color], context="trap", trigger_reactions=False)]
        for ability in player.has_ability("trap_extra_choice"):
            extra_rolls = int(ability.parameters.get("count", "0"))
            for _ in range(extra_rolls):
                candidates.append(self.roll_selected_color(player, [color], context="trap", trigger_reactions=False))
        best = min(candidates, key=lambda face: max(0, face.value))
        rerolls = sum(int(ability.parameters.get("count", "0")) for ability in player.has_ability("trap_rerolls"))
        for _ in range(rerolls):
            retry = self.roll_selected_color(player, [color], context="trap", trigger_reactions=False)
            if max(0, retry.value) < max(0, best.value):
                best = retry
        self.handle_reactive_roll_effects(player, best, context="trap")
        return best

    def place_trap_anywhere(self, player: Player, color: str) -> None:
        rivals = [other for other in self.players if other is not player]
        if not rivals:
            target_index = (player.position + 3) % self.track.length
        else:
            target = max(rivals, key=self.player_progress)
            target_index = (target.position + 2) % self.track.length
        self.placed_traps[target_index] = color


def run_batch(root: Path, games: int, player_count: int, seed: int) -> Dict[str, object]:
    wins = Counter()
    rounds: List[int] = []
    aggregate = defaultdict(float)
    ability_wins = Counter()
    movement_per_round: List[float] = []
    lap_snapshots: List[List[int]] = []
    for offset in range(games):
        game = RacerGame(root=root, config=GameConfig(player_count=player_count, seed=seed + offset))
        result = game.run()
        wins[result["winner"]] += 1
        rounds.append(result["rounds"])
        movement_per_round.extend(result["metrics"]["movement_per_round"])
        lap_snapshots.extend(result["metrics"]["lap_snapshots"])
        for player in result["players"]:
            for key, value in player.stats.items():
                aggregate[key] += value
        for ability_name, count in result["metrics"]["ability_wins"].items():
            ability_wins[ability_name] += count
    average_rounds = sum(rounds) / len(rounds)
    average_stats = {key: value / (games * player_count) for key, value in aggregate.items()}
    average_lap_progression = 0.0
    if lap_snapshots:
        average_lap_progression = sum(sum(snapshot) / len(snapshot) for snapshot in lap_snapshots) / len(lap_snapshots)
    return {
        "games": games,
        "average_rounds": average_rounds,
        "win_rates": {player: count / games for player, count in wins.items()},
        "average_stats": average_stats,
        "average_movement_per_round": sum(movement_per_round) / len(movement_per_round) if movement_per_round else 0.0,
        "average_lap_progression": average_lap_progression,
        "ability_win_rates": {name: count / games for name, count in ability_wins.items()},
    }

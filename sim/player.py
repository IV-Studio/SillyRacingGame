from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from sim.abilities import Ability, MysteryCard


@dataclass
class PendingEffects:
    ignore_next_trap: bool = False
    traps_avoided_this_round: int = 0


@dataclass
class Player:
    index: int
    name: str
    position: int = 0
    laps: int = 0
    coins: int = 3
    fuel: int = 3
    abilities: List[Ability] = field(default_factory=list)
    mystery_cards: List[MysteryCard] = field(default_factory=list)
    pending: PendingEffects = field(default_factory=PendingEffects)
    stats: Dict[str, float] = field(
        default_factory=lambda: {
            "movement": 0.0,
            "fuel_spent": 0.0,
            "coins_gained": 0.0,
            "coins_spent": 0.0,
            "traps_ignored": 0.0,
            "boxes_drawn": 0.0,
        }
    )

    def gain_coins(self, amount: int) -> None:
        self.coins += amount
        self.stats["coins_gained"] += amount

    def spend_coins(self, amount: int) -> bool:
        if amount > self.coins:
            return False
        self.coins -= amount
        self.stats["coins_spent"] += amount
        return True

    def gain_fuel(self, amount: int) -> None:
        self.fuel = min(7, self.fuel + amount)

    def spend_fuel(self, amount: int) -> bool:
        if amount > self.fuel:
            return False
        self.fuel -= amount
        self.stats["fuel_spent"] += amount
        return True

    def add_ability(self, ability: Ability) -> None:
        self.abilities.append(ability)

    def draw_mystery(self, card: MysteryCard) -> None:
        self.mystery_cards.append(card)
        self.stats["boxes_drawn"] += 1

    def remove_mystery(self, card: MysteryCard) -> None:
        self.mystery_cards.remove(card)

    def has_ability(self, effect_type: str) -> List[Ability]:
        return [ability for ability in self.abilities if ability.effect_type == effect_type]

    def reset_round_effects(self) -> None:
        self.pending = PendingEffects()

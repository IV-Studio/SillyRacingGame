from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
from typing import Dict, List


def parse_parameters(raw: str) -> Dict[str, str]:
    parameters: Dict[str, str] = {}
    if not raw:
        return parameters
    for chunk in raw.split(";"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        parameters[key] = value
    return parameters


@dataclass(frozen=True)
class Ability:
    id: str
    name: str
    description: str
    trigger: str
    effect_type: str
    parameters: Dict[str, str]


@dataclass(frozen=True)
class MysteryCard:
    id: str
    name: str
    description: str
    effect_type: str
    parameters: Dict[str, str]


def load_abilities(path: Path) -> List[Ability]:
    abilities: List[Ability] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            abilities.append(
                Ability(
                    id=row["id"],
                    name=row["name"],
                    description=row.get("description", ""),
                    trigger=row["trigger"],
                    effect_type=row["effect_type"],
                    parameters=parse_parameters(row["parameters"]),
                )
            )
    return abilities


def load_mystery_cards(path: Path) -> List[MysteryCard]:
    cards: List[MysteryCard] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cards.append(
                MysteryCard(
                    id=row["id"],
                    name=row["name"],
                    description=row.get("description", ""),
                    effect_type=row["effect_type"],
                    parameters=parse_parameters(row["parameters"]),
                )
            )
    return cards

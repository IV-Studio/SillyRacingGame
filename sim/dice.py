from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import random
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class DieFace:
    id: str
    color: str
    description: str
    value: int
    fuel_cost: int


class DiceLibrary:
    def __init__(self, faces_by_color: Dict[str, List[DieFace]]) -> None:
        self.faces_by_color = faces_by_color

    @classmethod
    def from_csv(cls, path: Path) -> "DiceLibrary":
        faces_by_color: Dict[str, List[DieFace]] = {}
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                face = DieFace(
                    id=row["id"],
                    color=row["color"],
                    description=row.get("description", ""),
                    value=int(row["value"]),
                    fuel_cost=int(row["fuel_cost"]),
                )
                faces_by_color.setdefault(face.color, []).append(face)
        return cls(faces_by_color)

    def roll(self, rng: random.Random, color: str) -> DieFace:
        return rng.choice(self.faces_by_color[color])

    def available_colors(self) -> Iterable[str]:
        return self.faces_by_color.keys()

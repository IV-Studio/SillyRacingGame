from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
from typing import Dict, List

from sim.abilities import parse_parameters


@dataclass(frozen=True)
class TrackSpace:
    index: int
    space_type: str
    description: str
    metadata: Dict[str, str]


class Track:
    def __init__(self, spaces: List[TrackSpace]) -> None:
        self.spaces = spaces
        self.length = len(spaces)

    @classmethod
    def from_csv(cls, path: Path) -> "Track":
        spaces: List[TrackSpace] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                spaces.append(
                    TrackSpace(
                        index=int(row["index"]),
                        space_type=row["type"],
                        description=row.get("description", ""),
                        metadata=parse_parameters(row["metadata"]),
                    )
                )
        spaces.sort(key=lambda space: space.index)
        return cls(spaces)

    def get_space(self, index: int) -> TrackSpace:
        return self.spaces[index % self.length]

    def progress_value(self, position: int, laps: int) -> float:
        return laps * self.length + position

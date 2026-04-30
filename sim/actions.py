from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
from typing import Dict, List, Optional

from sim.abilities import parse_parameters


@dataclass(frozen=True)
class ActionSlot:
    row_id: str
    row_type: str
    slot_index: int
    description: str
    value: str


@dataclass
class RowState:
    row_id: str
    row_type: str
    slots: List[ActionSlot]
    placements: List[Optional[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.placements:
            self.placements = [None for _ in self.slots]

    def next_open_slot(self) -> Optional[int]:
        for index, occupant in enumerate(self.placements):
            if occupant is None:
                return index
        return None

    def place(self, player_index: int) -> bool:
        slot_index = self.next_open_slot()
        if slot_index is None:
            return False
        self.placements[slot_index] = player_index
        return True

    def occupied_pairs(self) -> List[tuple[ActionSlot, int]]:
        pairs: List[tuple[ActionSlot, int]] = []
        for slot, occupant in zip(self.slots, self.placements):
            if occupant is not None:
                pairs.append((slot, occupant))
        return pairs


class ActionBoard:
    def __init__(self, rows: List[RowState]) -> None:
        self.rows = rows
        self.rows_by_id = {row.row_id: row for row in rows}

    @classmethod
    def from_csv(cls, path: Path) -> "ActionBoard":
        grouped: Dict[str, List[ActionSlot]] = {}
        row_types: Dict[str, str] = {}
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                slot = ActionSlot(
                    row_id=row["id"],
                    row_type=row["type"],
                    slot_index=int(row["slot_index"]),
                    description=row.get("description", ""),
                    value=row["value"],
                )
                grouped.setdefault(slot.row_id, []).append(slot)
                row_types[slot.row_id] = slot.row_type
        ordered_rows: List[RowState] = []
        for row_id, slots in grouped.items():
            ordered_rows.append(
                RowState(
                    row_id=row_id,
                    row_type=row_types[row_id],
                    slots=sorted(slots, key=lambda item: item.slot_index),
                )
            )
        order = {
            "first_player": 0,
            "gain_coins": 1,
            "dice_yellow_orange_burst": 2,
            "gain_fuel": 3,
            "fixed_move": 4,
            "dice_orange_red_push": 5,
            "ability_draft": 6,
            "dice_yellow_red_gamble": 7,
        }
        ordered_rows.sort(key=lambda row: order.get(row.row_id, 99))
        return cls(ordered_rows)

    def reset(self) -> None:
        for row in self.rows:
            row.placements = [None for _ in row.slots]


def parse_action_value(raw: str) -> Dict[str, str]:
    return parse_parameters(raw)

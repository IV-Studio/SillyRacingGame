from __future__ import annotations

import csv
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "dice_faces.csv"
EXPORT_DIR = ROOT / "exports" / "tts"

SHEET_SIZE = 720
GRID_SIZE = 3
CELL = SHEET_SIZE // GRID_SIZE
FACE_POSITIONS = [
    (0, 1),
    (1, 1),
    (2, 1),
    (0, 2),
    (1, 2),
    (2, 2),
]

FONT_STACK = "Trebuchet MS, Verdana, sans-serif"


@dataclass(frozen=True)
class DieFace:
    id: str
    color: str
    description: str
    value: int
    fuel_cost: int


def load_faces() -> Dict[str, List[DieFace]]:
    faces_by_color: Dict[str, List[DieFace]] = {}
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            face = DieFace(
                id=row["id"],
                color=row["color"],
                description=row["description"],
                value=int(row["value"]),
                fuel_cost=int(row["fuel_cost"]),
            )
            faces_by_color.setdefault(face.color, []).append(face)
    return faces_by_color


def color_palette(color: str) -> tuple[str, str, str, str]:
    palettes = {
        "yellow": ("#F6C453", "#FFF7D7", "#8A6A12", "#3A3100"),
        "orange": ("#F08B37", "#FFE0C2", "#8A3E22", "#351A0A"),
        "red": ("#D94B4B", "#FFD6D6", "#7D2337", "#2D0A14"),
    }
    return palettes.get(color, ("#6B7A90", "#E4EBF2", "#2F3B4A", "#101720"))


def format_value(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def svg_header() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_SIZE}" height="{SHEET_SIZE}" '
        f'viewBox="0 0 {SHEET_SIZE} {SHEET_SIZE}">\n'
    )


def droplet_path(cx: float, cy: float, size: float) -> str:
    top_y = cy - size * 1.2
    bottom_y = cy + size * 1.15
    left_x = cx - size * 0.78
    right_x = cx + size * 0.78
    upper_y = cy - size * 0.2
    lower_y = cy + size * 0.35
    return (
        f"M {cx:.1f} {top_y:.1f} "
        f"C {cx + size * 0.85:.1f} {upper_y:.1f}, {right_x:.1f} {lower_y:.1f}, {cx:.1f} {bottom_y:.1f} "
        f"C {left_x:.1f} {lower_y:.1f}, {cx - size * 0.85:.1f} {upper_y:.1f}, {cx:.1f} {top_y:.1f} Z"
    )


def render_die_sheet(color: str, faces: List[DieFace]) -> str:
    if len(faces) != 6:
        raise ValueError(f"Expected 6 faces for {color}, found {len(faces)}.")

    fill, accent, border, text = color_palette(color)
    parts = [svg_header()]
    parts.append(f'<rect width="{SHEET_SIZE}" height="{SHEET_SIZE}" fill="{fill}"/>')

    for x in range(1, GRID_SIZE):
        position = x * CELL
        parts.append(f'<line x1="{position}" y1="0" x2="{position}" y2="{SHEET_SIZE}" stroke="{accent}" stroke-width="2" opacity="0.65"/>')
    for y in range(1, GRID_SIZE):
        position = y * CELL
        parts.append(f'<line x1="0" y1="{position}" x2="{SHEET_SIZE}" y2="{position}" stroke="{accent}" stroke-width="2" opacity="0.65"/>')

    for face, (col, row) in zip(faces, FACE_POSITIONS):
        x = col * CELL
        y = row * CELL
        value_y = y + 108
        fuel_y = y + 178
        parts.append(
            f'<text x="{x + CELL / 2:.1f}" y="{value_y}" text-anchor="middle" '
            f'font-family="{FONT_STACK}" font-size="84" font-weight="700" fill="{text}">{escape(format_value(face.value))}</text>'
        )
        for fuel_index in range(face.fuel_cost):
            spacing = 28
            start_x = x + CELL / 2 - (face.fuel_cost - 1) * spacing / 2
            cx = start_x + fuel_index * spacing
            parts.append(f'<path d="{droplet_path(cx, fuel_y, 20)}" fill="{border}" opacity="0.95"/>')

    parts.append("</svg>\n")
    return "\n".join(parts)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    faces_by_color = load_faces()
    for color, faces in faces_by_color.items():
        output_path = EXPORT_DIR / f"{color}_die_tts.svg"
        output_path.write_text(render_die_sheet(color, faces), encoding="utf-8")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

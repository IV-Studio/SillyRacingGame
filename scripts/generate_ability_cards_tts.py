from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import List


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "abilities.csv"
EXPORT_DIR = ROOT / "exports" / "tts"
FRONT_PATH = EXPORT_DIR / "ability_cards_front.svg"
BACK_PATH = EXPORT_DIR / "ability_cards_back.svg"

CARD_W = 750
CARD_H = 1050
GAP = 0

FONT_STACK = "Trebuchet MS, Verdana, sans-serif"
TITLE_SIZE = 52
BODY_SIZE = 32
SMALL_SIZE = 28


@dataclass(frozen=True)
class AbilityCard:
    id: str
    name: str
    description: str
    trigger: str


def load_cards() -> List[AbilityCard]:
    cards: List[AbilityCard] = []
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cards.append(
                AbilityCard(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    trigger=row["trigger"],
                )
            )
    return cards


def palette(trigger: str) -> tuple[str, str, str]:
    palettes = {
        "dice_row": ("#A14F10", "#FFD7AE", "#FFF6ED"),
        "movement": ("#12737E", "#BEEFF2", "#F0FDFF"),
        "trap": ("#5A2E88", "#E1D0FF", "#FBF7FF"),
        "reaction": ("#7D2337", "#FFD0DA", "#FFF2F5"),
        "fixed_move": ("#345C9C", "#CFE0FF", "#F4F8FF"),
        "resource": ("#2D6A4F", "#CCF1DE", "#F2FFF8"),
    }
    return palettes.get(trigger, ("#3A495E", "#D6E2EF", "#F7FAFD"))


def classify(trigger: str) -> str:
    labels = {
        "dice_row": "Dice",
        "movement": "Movement",
        "trap": "Trap",
        "reaction": "Reactive",
        "fixed_move": "Pace",
        "resource": "Resource",
    }
    return labels.get(trigger, "Ability")


def svg_header(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
    )


def choose_grid(card_count: int) -> tuple[int, int]:
    best_cols = 1
    best_rows = card_count
    best_score = float("inf")

    for cols in range(1, card_count + 1):
        rows = math.ceil(card_count / cols)
        sheet_w = cols * CARD_W + (cols - 1) * GAP
        sheet_h = rows * CARD_H + (rows - 1) * GAP
        score = abs(math.log(sheet_w / sheet_h))
        if score < best_score:
            best_score = score
            best_cols = cols
            best_rows = rows

    return best_cols, best_rows


def card_origin(index: int, cols: int) -> tuple[int, int]:
    col = index % cols
    row = index // cols
    return col * (CARD_W + GAP), row * (CARD_H + GAP)


def add_wrapped_text(parts: List[str], text: str, x: int, y: int, width_chars: int, line_height: int) -> None:
    for line_index, line in enumerate(wrap(text, width=width_chars)):
        parts.append(
            f'<text x="{x}" y="{y + line_index * line_height}" '
            f'font-family="{FONT_STACK}" font-size="{BODY_SIZE}" fill="#1D2836">{escape(line)}</text>'
        )


def render_front(cards: List[AbilityCard]) -> str:
    cols, rows = choose_grid(len(cards))
    sheet_w = cols * CARD_W + (cols - 1) * GAP
    sheet_h = rows * CARD_H + (rows - 1) * GAP
    parts = [svg_header(sheet_w, sheet_h)]
    parts.append(f'<rect width="{sheet_w}" height="{sheet_h}" fill="#101720"/>')
    for index, card in enumerate(cards):
        x, y = card_origin(index, cols)
        accent, accent_soft, panel = palette(card.trigger)
        parts.append(f'<g transform="translate({x},{y})">')
        parts.append(f'<rect width="{CARD_W}" height="{CARD_H}" fill="{panel}"/>')
        parts.append(f'<rect x="20" y="20" width="{CARD_W - 40}" height="{CARD_H - 40}" rx="28" fill="none" stroke="{accent}" stroke-width="8"/>')
        parts.append(f'<rect width="{CARD_W}" height="170" rx="36" fill="{accent}"/>')
        parts.append(f'<rect y="130" width="{CARD_W}" height="90" fill="{accent}"/>')
        parts.append(
            f'<text x="56" y="86" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'font-weight="700" fill="{accent_soft}" letter-spacing="3">{escape(classify(card.trigger).upper())}</text>'
        )
        parts.append(
            f'<text x="56" y="162" font-family="{FONT_STACK}" font-size="{TITLE_SIZE}" '
            f'font-weight="700" fill="#FFFFFF">{escape(card.name)}</text>'
        )
        parts.append(f'<circle cx="{CARD_W - 96}" cy="120" r="52" fill="{accent_soft}" fill-opacity="0.35"/>')
        parts.append(f'<circle cx="{CARD_W - 96}" cy="120" r="26" fill="#FFFFFF" fill-opacity="0.92"/>')
        parts.append(
            f'<text x="56" y="286" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'font-weight="700" fill="{accent}">Always on:</text>'
        )
        add_wrapped_text(parts, card.description, 56, 352, 30, 46)
        parts.append(
            f'<text x="56" y="{CARD_H - 92}" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'fill="#415166">Unique Ability</text>'
        )
        parts.append(
            f'<text x="{CARD_W - 56}" y="{CARD_H - 92}" text-anchor="end" '
            f'font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" fill="#415166">{escape(card.id)}</text>'
        )
        parts.append("</g>")
    parts.append("</svg>\n")
    return "\n".join(parts)


def render_back() -> str:
    parts = [svg_header(CARD_W, CARD_H)]
    parts.append(f'<rect width="{CARD_W}" height="{CARD_H}" fill="#182231"/>')
    parts.append(f'<rect x="20" y="20" width="{CARD_W - 40}" height="{CARD_H - 40}" rx="28" fill="none" stroke="#7AD9E1" stroke-width="8"/>')
    parts.append(f'<rect x="56" y="56" width="{CARD_W - 112}" height="{CARD_H - 112}" rx="24" fill="#223247"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="170" fill="#7AD9E1" fill-opacity="0.18"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="118" fill="#7AD9E1" fill-opacity="0.28"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="70" fill="#7AD9E1"/>')
    parts.append(
        f'<text x="{CARD_W / 2:.1f}" y="{CARD_H / 2 + 150:.1f}" text-anchor="middle" '
        f'font-family="{FONT_STACK}" font-size="64" font-weight="700" fill="#F4FDFF">Unique Ability</text>'
    )
    parts.append(
        f'<text x="{CARD_W / 2:.1f}" y="{CARD_H / 2 + 214:.1f}" text-anchor="middle" '
        f'font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" letter-spacing="4" fill="#D7E3F0">SILLY RACING GAME</text>'
    )
    parts.append("</svg>\n")
    return "\n".join(parts)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cards = load_cards()
    FRONT_PATH.write_text(render_front(cards), encoding="utf-8")
    BACK_PATH.write_text(render_back(), encoding="utf-8")
    print(f"Wrote {FRONT_PATH}")
    print(f"Wrote {BACK_PATH}")


if __name__ == "__main__":
    main()

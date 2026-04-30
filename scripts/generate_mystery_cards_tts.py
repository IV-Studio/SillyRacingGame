from __future__ import annotations

import csv
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import List


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "mystery_cards.csv"
EXPORT_DIR = ROOT / "exports" / "tts"
FRONT_PATH = EXPORT_DIR / "mystery_cards_front.svg"
BACK_PATH = EXPORT_DIR / "mystery_cards_back.svg"

COLS = 4
ROWS = 2
CARD_W = 750
CARD_H = 1050
GAP = 24
SHEET_W = COLS * CARD_W + (COLS - 1) * GAP
SHEET_H = ROWS * CARD_H + (ROWS - 1) * GAP

FONT_STACK = "Trebuchet MS, Verdana, sans-serif"
TITLE_SIZE = 54
BODY_SIZE = 34
SMALL_SIZE = 28


@dataclass(frozen=True)
class MysteryCard:
    id: str
    name: str
    description: str
    effect_type: str


def load_cards() -> List[MysteryCard]:
    cards: List[MysteryCard] = []
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cards.append(
                MysteryCard(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    effect_type=row["effect_type"],
                )
            )
    expected = COLS * ROWS
    if len(cards) != expected:
        raise ValueError(f"Expected exactly {expected} mystery cards for a {COLS}x{ROWS} TTS sheet, found {len(cards)}.")
    return cards


def palette(effect_type: str) -> tuple[str, str, str]:
    palettes = {
        "reroll_pool": ("#345C9C", "#CFE0FF", "#F4F8FF"),
        "move_bonus": ("#8A3E22", "#FFD8C2", "#FFF4EE"),
        "gain_fuel": ("#2D6A4F", "#CCF1DE", "#F2FFF8"),
        "gain_coins": ("#8A6A12", "#F7E8B3", "#FFFBEA"),
        "ignore_trap": ("#5A2E88", "#E1D0FF", "#FBF7FF"),
        "sabotage_blast": ("#7D2337", "#FFD0DA", "#FFF2F5"),
        "drafting_line": ("#12737E", "#BEEFF2", "#F0FDFF"),
        "overclock": ("#A14F10", "#FFD7AE", "#FFF6ED"),
    }
    return palettes.get(effect_type, ("#3A495E", "#D6E2EF", "#F7FAFD"))


def classify(effect_type: str) -> str:
    labels = {
        "reroll_pool": "Tuning",
        "move_bonus": "Burst",
        "gain_fuel": "Resource",
        "gain_coins": "Resource",
        "ignore_trap": "Defense",
        "sabotage_blast": "Attack",
        "drafting_line": "Positioning",
        "overclock": "Boost",
    }
    return labels.get(effect_type, "Mystery")


def svg_header(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
    )


def card_origin(index: int) -> tuple[int, int]:
    col = index % COLS
    row = index // COLS
    x = col * (CARD_W + GAP)
    y = row * (CARD_H + GAP)
    return x, y


def add_wrapped_text(parts: List[str], text: str, x: int, y: int, width_chars: int, line_height: int) -> None:
    for line_index, line in enumerate(wrap(text, width=width_chars)):
        parts.append(
            f'<text x="{x}" y="{y + line_index * line_height}" '
            f'font-family="{FONT_STACK}" font-size="{BODY_SIZE}" fill="#1D2836">{escape(line)}</text>'
        )


def render_front(cards: List[MysteryCard]) -> str:
    parts = [svg_header(SHEET_W, SHEET_H)]
    parts.append(f'<rect width="{SHEET_W}" height="{SHEET_H}" fill="#101720"/>')
    for index, card in enumerate(cards):
        x, y = card_origin(index)
        accent, accent_soft, panel = palette(card.effect_type)
        parts.append(f'<g transform="translate({x},{y})">')
        parts.append(f'<rect width="{CARD_W}" height="{CARD_H}" rx="36" fill="{panel}"/>')
        parts.append(f'<rect x="20" y="20" width="{CARD_W - 40}" height="{CARD_H - 40}" rx="28" fill="none" stroke="{accent}" stroke-width="8"/>')
        parts.append(f'<rect width="{CARD_W}" height="170" rx="36" fill="{accent}"/>')
        parts.append(f'<rect y="130" width="{CARD_W}" height="90" fill="{accent}"/>')
        parts.append(
            f'<text x="56" y="86" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'font-weight="700" fill="{accent_soft}" letter-spacing="3">{escape(classify(card.effect_type).upper())}</text>'
        )
        parts.append(
            f'<text x="56" y="166" font-family="{FONT_STACK}" font-size="{TITLE_SIZE}" '
            f'font-weight="700" fill="#FFFFFF">{escape(card.name)}</text>'
        )
        parts.append(f'<circle cx="{CARD_W - 96}" cy="120" r="52" fill="{accent_soft}" fill-opacity="0.35"/>')
        parts.append(f'<circle cx="{CARD_W - 96}" cy="120" r="26" fill="#FFFFFF" fill-opacity="0.92"/>')
        parts.append(
            f'<text x="56" y="286" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'font-weight="700" fill="{accent}">Play and discard:</text>'
        )
        add_wrapped_text(parts, card.description, 56, 352, 30, 48)
        parts.append(
            f'<text x="56" y="{CARD_H - 92}" font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" '
            f'fill="#415166">Mystery Box</text>'
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
    parts.append(f'<rect width="{CARD_W}" height="{CARD_H}" rx="36" fill="#182231"/>')
    parts.append(f'<rect x="20" y="20" width="{CARD_W - 40}" height="{CARD_H - 40}" rx="28" fill="none" stroke="#F6C453" stroke-width="8"/>')
    parts.append(f'<rect x="56" y="56" width="{CARD_W - 112}" height="{CARD_H - 112}" rx="24" fill="#223247"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="170" fill="#F6C453" fill-opacity="0.18"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="118" fill="#F6C453" fill-opacity="0.28"/>')
    parts.append(f'<circle cx="{CARD_W / 2:.1f}" cy="{CARD_H / 2 - 80:.1f}" r="70" fill="#F6C453"/>')
    parts.append(
        f'<text x="{CARD_W / 2:.1f}" y="{CARD_H / 2 + 150:.1f}" text-anchor="middle" '
        f'font-family="{FONT_STACK}" font-size="66" font-weight="700" fill="#FFF7E2">Mystery Box</text>'
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

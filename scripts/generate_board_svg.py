from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import Dict, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSET_PATH = ROOT / "assets" / "board.svg"
TTS_PATH = ROOT / "exports" / "tts" / "board.svg"

WIDTH = 1600
HEIGHT = 1600
GRID = 8
BORDER = 2
RADIUS = 8

PANEL_COLUMN_WIDTH = 400
PANEL_X = 24
PANEL_Y = 24
PANEL_W = 352
PANEL_H = HEIGHT - 48

TRACK_AREA_X = 416
TRACK_AREA_Y = 24
TRACK_AREA_WIDTH = WIDTH - TRACK_AREA_X - 24
TRACK_AREA_HEIGHT = HEIGHT - 48

TOTAL_SPACES = 60
ROAD_WIDTH = 112
CELL_LENGTH = 68
CELL_WIDTH = 92

FONT_STACK = "Trebuchet MS, Verdana, sans-serif"
H1_SIZE = 32
H1_LINE = 40
H2_SIZE = 24
H2_LINE = 32
H3_SIZE = 18
H3_LINE = 24
BODY_SIZE = 14
BODY_LINE = 24


@dataclass(frozen=True)
class TrackSpace:
    index: int
    space_type: str
    metadata: Dict[str, str]


@dataclass(frozen=True)
class ActionRow:
    row_id: str
    row_type: str
    slot_index: int
    value: str


Point = Tuple[float, float]

REFERENCE_PATH = (
    "M919.056 485.371"
    "C859.556 250.872 1389.02 -105.125 524.54 30.3735"
    "C192.396 82.4336 -144.944 413.872 66.0567 702.872"
    "C403.057 1089.37 327.185 334.535 509.04 301.874"
    "C734.54 261.374 891.056 702.872 563.056 952.872"
    "C274.646 1172.7 843.825 1303.58 1131.56 1070.87"
    "C1255.1 970.954 1428.04 710.373 1384.54 609.373"
    "C1256.27 311.543 965.218 667.304 919.056 485.371Z"
)


def parse_metadata(raw: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    if not raw:
        return parsed
    for chunk in raw.split(";"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        parsed[key] = value
    return parsed


def load_track_spaces() -> List[TrackSpace]:
    spaces: List[TrackSpace] = []
    with (DATA_DIR / "track_spaces.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            spaces.append(
                TrackSpace(
                    index=int(row["index"]),
                    space_type=row["type"],
                    metadata=parse_metadata(row["metadata"]),
                )
            )
    spaces.sort(key=lambda space: space.index)
    if len(spaces) != TOTAL_SPACES:
        raise ValueError(f"Board generator expects {TOTAL_SPACES} track spaces, found {len(spaces)}.")
    return spaces


def load_action_rows() -> Dict[str, List[ActionRow]]:
    grouped: Dict[str, List[ActionRow]] = {}
    with (DATA_DIR / "action_rows.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            action_row = ActionRow(
                row_id=row["id"],
                row_type=row["type"],
                slot_index=int(row["slot_index"]),
                value=row["value"],
            )
            grouped.setdefault(action_row.row_id, []).append(action_row)
    for rows in grouped.values():
        rows.sort(key=lambda row: row.slot_index)
    return grouped


def snap(value: float) -> float:
    return round(value / GRID) * GRID


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def interpolate(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def polar_point(center: Point, radius_x: float, radius_y: float, degrees: float, scale: float) -> Point:
    angle = math.radians(degrees)
    x = center[0] + math.cos(angle) * radius_x * scale
    y = center[1] + math.sin(angle) * radius_y * scale
    return (snap(x), snap(y))


def cubic_point(start: Point, control_a: Point, control_b: Point, end: Point, t: float) -> Point:
    inv = 1.0 - t
    x = (
        (inv ** 3) * start[0]
        + 3 * (inv ** 2) * t * control_a[0]
        + 3 * inv * (t ** 2) * control_b[0]
        + (t ** 3) * end[0]
    )
    y = (
        (inv ** 3) * start[1]
        + 3 * (inv ** 2) * t * control_a[1]
        + 3 * inv * (t ** 2) * control_b[1]
        + (t ** 3) * end[1]
    )
    return (x, y)


def parse_reference_segments(path_data: str) -> List[Tuple[Point, Point, Point, Point]]:
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", path_data)
    index = 0
    command = ""
    cursor = (0.0, 0.0)
    start_point = (0.0, 0.0)
    segments: List[Tuple[Point, Point, Point, Point]] = []

    def read_point() -> Point:
        nonlocal index
        point = (float(tokens[index]), float(tokens[index + 1]))
        index += 2
        return point

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in {"Z", "z"}:
                cursor = start_point
            continue
        if command == "M":
            cursor = read_point()
            start_point = cursor
            command = "C"
            continue
        if command == "C":
            control_a = read_point()
            control_b = read_point()
            end = read_point()
            segments.append((cursor, control_a, control_b, end))
            cursor = end
            continue
        raise ValueError(f"Unsupported SVG path command in reference path: {command}")
    return segments


def transform_points_to_track_area(points: Sequence[Point]) -> List[Point]:
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    source_w = max_x - min_x
    source_h = max_y - min_y

    target_x = TRACK_AREA_X + 72
    target_y = TRACK_AREA_Y + 136
    target_w = TRACK_AREA_WIDTH - 120
    target_h = TRACK_AREA_HEIGHT - 240
    scale = min(target_w / source_w, target_h / source_h)

    fitted_w = source_w * scale
    fitted_h = source_h * scale
    offset_x = target_x + (target_w - fitted_w) / 2
    offset_y = target_y + (target_h - fitted_h) / 2

    transformed: List[Point] = []
    for x, y in points:
        tx = offset_x + (x - min_x) * scale
        ty = offset_y + (y - min_y) * scale
        transformed.append((snap(tx), snap(ty)))
    return transformed


def reference_loop_points(samples_per_segment: int = 30) -> List[Point]:
    raw_points: List[Point] = []
    for start, control_a, control_b, end in parse_reference_segments(REFERENCE_PATH):
        for sample in range(samples_per_segment):
            t = sample / samples_per_segment
            raw_points.append(cubic_point(start, control_a, control_b, end, t))
    raw_points.append(parse_reference_segments(REFERENCE_PATH)[-1][-1])
    transformed = transform_points_to_track_area(raw_points)
    if transformed[0] != transformed[-1]:
        transformed.append(transformed[0])
    return transformed


def sample_loop(points: Sequence[Point], count: int) -> List[Tuple[float, float, float]]:
    segments = [dist(points[index], points[index + 1]) for index in range(len(points) - 1)]
    total = sum(segments)
    samples: List[Tuple[float, float, float]] = []
    for step in range(count):
        target = total * step / count
        walked = 0.0
        for index, segment_length in enumerate(segments):
            if walked + segment_length >= target:
                local_t = 0.0 if segment_length == 0 else (target - walked) / segment_length
                point = interpolate(points[index], points[index + 1], local_t)
                ahead_t = min(target + 4.0, total)
                ahead = point_on_loop(points, segments, ahead_t)
                angle = math.degrees(math.atan2(ahead[1] - point[1], ahead[0] - point[0]))
                samples.append((point[0], point[1], angle))
                break
            walked += segment_length
    return samples


def point_on_loop(points: Sequence[Point], segments: Sequence[float], target: float) -> Point:
    walked = 0.0
    for index, segment_length in enumerate(segments):
        if walked + segment_length >= target:
            local_t = 0.0 if segment_length == 0 else (target - walked) / segment_length
            return interpolate(points[index], points[index + 1], local_t)
        walked += segment_length
    return points[-1]


def path_d(points: Sequence[Point]) -> str:
    start = points[0]
    rest = " ".join(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return f"M {start[0]:.2f} {start[1]:.2f} {rest}"


def wrap_lines(text: str, width: float, font_size: int) -> List[str]:
    max_chars = max(1, int(width / max(font_size * 0.58, 1)))
    lines: List[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        lines.extend(wrap(paragraph, width=max_chars, break_long_words=False, break_on_hyphens=False))
    return lines or [text]


def text_block(
    x: float,
    y: float,
    width: float,
    text: str,
    *,
    size: int,
    line_height: int,
    weight: str,
    fill: str,
    anchor: str = "start",
) -> str:
    lines = wrap_lines(text, width, size)
    start_x = x if anchor == "start" else x + width / 2
    text_anchor = "start" if anchor == "start" else "middle"
    parts = [
        f'<text x="{start_x:.2f}" y="{y:.2f}" text-anchor="{text_anchor}" font-family="{FONT_STACK}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
    ]
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        parts.append(f'<tspan x="{start_x:.2f}" dy="{dy}">{escape(line)}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def section_box(x: float, y: float, width: float, height: float, fill: str, stroke: str, title: str | None = None) -> str:
    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="{BORDER}"/>'
    ]
    if title:
        parts.append(text_block(x + 16, y + 24, width - 32, title, size=H3_SIZE, line_height=H3_LINE, weight="600", fill="#F6F3EA"))
    return "".join(parts)


def render_background() -> str:
    return f"""
<defs>
  <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#F4E8CB"/>
    <stop offset="60%" stop-color="#E1C18A"/>
    <stop offset="100%" stop-color="#C98C57"/>
  </linearGradient>
  <linearGradient id="panelShell" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#22496F"/>
    <stop offset="100%" stop-color="#17334F"/>
  </linearGradient>
  <linearGradient id="road" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#736B64"/>
    <stop offset="100%" stop-color="#4D4642"/>
  </linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#5C3821" flood-opacity="0.18"/>
  </filter>
</defs>
<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
<rect x="{TRACK_AREA_X:.2f}" y="{TRACK_AREA_Y:.2f}" width="{TRACK_AREA_WIDTH:.2f}" height="{TRACK_AREA_HEIGHT:.2f}" rx="{RADIUS}" fill="#F6E4BE" opacity="0.32"/>
<circle cx="{TRACK_AREA_X + 944:.2f}" cy="280" r="176" fill="#5ECAD0" opacity="0.10"/>
<circle cx="{TRACK_AREA_X + 680:.2f}" cy="1320" r="216" fill="#E56D4B" opacity="0.08"/>
<circle cx="{TRACK_AREA_X + 272:.2f}" cy="1184" r="144" fill="#FFF6D8" opacity="0.16"/>
"""


def slot_style(slot: ActionRow) -> Tuple[str, str, str]:
    if slot.row_type == "dice_move":
        params = parse_metadata(slot.value)
        display_color = params.get("display_color", "yellow")
        if display_color == "yellow":
            return "#F7DB73", "#8C6700", params.get("display_value", "1")
        if display_color == "orange":
            return "#F4B08C", "#8A3E21", params.get("display_value", "1")
        return "#E88AA0", "#7A1733", params.get("display_value", "1")
    if slot.row_id == "ability_draft":
        return "#FCE8BD", "#A66E08", slot.value
    if slot.row_id == "first_player":
        return "#D6E1EE", "#426792", "1ST"
    if slot.row_id == "gain_coins":
        return "#F7DB73", "#8C6700", f"+{int(slot.value)}"
    if slot.row_id == "gain_fuel":
        return "#D5EDCA", "#496F34", f"+{int(slot.value)}"
    return "#F4C2B1", "#87442E", f"+{int(slot.value)}"


def render_action_slot(slot: ActionRow, x: float, y: float, width: float = 40, height: float = 40) -> str:
    fill, stroke, label = slot_style(slot)
    font_size = BODY_SIZE if len(label) > 2 else H3_SIZE
    font_weight = "700" if font_size == BODY_SIZE else "600"
    baseline = y + (26 if font_size == BODY_SIZE else 28)
    return (
        f'<g>'
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="{BORDER}"/>'
        f'<text x="{x + width / 2:.2f}" y="{baseline:.2f}" text-anchor="middle" font-family="{FONT_STACK}" '
        f'font-size="{font_size}" font-weight="{font_weight}" fill="{stroke}">{escape(label)}</text>'
        f"</g>"
    )


def render_row_card(
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    row_id: str,
    slots: Sequence[ActionRow],
) -> str:
    slot_start_x = x + 16
    slot_y = y + 56
    subtitle_map = {
        "first_player": "Claim next draft order.",
        "gain_coins": "Immediate coin gain.",
        "dice_yellow_orange_burst": "Yellow / orange dice row.",
        "gain_fuel": "Immediate fuel gain.",
        "fixed_move": "Deterministic movement.",
        "dice_orange_red_push": "Orange / red dice row.",
        "ability_draft": "Pay the slot value to bid.",
        "dice_yellow_red_gamble": "Yellow / red dice row.",
    }
    parts = [
        section_box(x, y, width, height, "#234562", "#F0E4C7"),
        text_block(x + 16, y + 24, width - 32, title, size=H3_SIZE, line_height=H3_LINE, weight="600", fill="#FFF6E0"),
        text_block(x + 16, y + 48, width - 32, subtitle_map[row_id], size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#D2DEE8"),
    ]
    for index, slot in enumerate(slots):
        parts.append(render_action_slot(slot, slot_start_x + index * 48, slot_y))
    return "\n".join(parts)


def render_legend_card(x: float, y: float, width: float, height: float) -> str:
    entries = [
        ("Coin", "#F6C64B", "#8A5800"),
        ("Box", "#4BC8D4", "#0E5968"),
        ("Trap", "#EF6A41", "#7C2816"),
        ("Safe", "#F7F1E3", "#776E62"),
    ]
    parts = [
        section_box(x, y, width, height, "#234562", "#F0E4C7"),
        text_block(x + 16, y + 24, width - 32, "Space Types", size=H3_SIZE, line_height=H3_LINE, weight="600", fill="#FFF6E0"),
    ]
    start_x = x + 16
    start_y = y + 56
    for index, (label, fill, stroke) in enumerate(entries):
        col = index % 2
        row = index // 2
        item_x = start_x + col * 144
        item_y = start_y + row * 32
        parts.append(
            f'<rect x="{item_x:.2f}" y="{item_y - 12:.2f}" width="16" height="16" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{BORDER}"/>'
        )
        parts.append(text_block(item_x + 24, item_y, 104, label, size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#DDE8F0"))
    return "\n".join(parts)


def render_summary_card(x: float, y: float, width: float, height: float) -> str:
    summary = [
        "First to 5 laps wins.",
        "Resolve rows from top to bottom.",
        "Only your landed space triggers.",
    ]
    parts = [
        section_box(x, y, width, height, "#234562", "#F0E4C7"),
        text_block(x + 16, y + 24, width - 32, "Play Reminder", size=H3_SIZE, line_height=H3_LINE, weight="600", fill="#FFF6E0"),
    ]
    cursor_y = y + 56
    for item in summary:
        parts.append(text_block(x + 16, cursor_y, width - 32, item, size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#DDE8F0"))
        cursor_y += 24
    return "\n".join(parts)


def render_main_panel(action_rows: Dict[str, List[ActionRow]]) -> str:
    title_x = PANEL_X + 16
    title_y = PANEL_Y + 16
    title_w = PANEL_W - 32
    title_h = 120
    row_x = title_x
    row_y = title_y + title_h + 16
    row_w = title_w
    row_h = 104
    row_gap = 16
    display_rows = [
        ("First Player", "first_player"),
        ("Gain Coins", "gain_coins"),
        ("Dice A", "dice_yellow_orange_burst"),
        ("Gain Fuel", "gain_fuel"),
        ("Fixed Move", "fixed_move"),
        ("Dice B", "dice_orange_red_push"),
        ("Ability Bid", "ability_draft"),
        ("Dice C", "dice_yellow_red_gamble"),
    ]
    legend_y = row_y + len(display_rows) * row_h + (len(display_rows) - 1) * row_gap + 16
    summary_y = legend_y + 120 + 16
    parts = [
        '<g filter="url(#shadow)">',
        f'<rect x="{PANEL_X:.2f}" y="{PANEL_Y:.2f}" width="{PANEL_W:.2f}" height="{PANEL_H:.2f}" rx="{RADIUS}" fill="url(#panelShell)" stroke="#F0E4C7" stroke-width="{BORDER}"/>',
        section_box(title_x, title_y, title_w, title_h, "#234562", "#F0E4C7"),
        text_block(title_x + 16, title_y + 32, title_w - 32, "Racer Prototype", size=H1_SIZE, line_height=H1_LINE, weight="700", fill="#FFF6E0"),
        text_block(title_x + 16, title_y + 72, title_w - 32, "Draft actions. Race hard. Finish 5 laps.", size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#D5E1EA"),
    ]
    for index, (label, row_id) in enumerate(display_rows):
        parts.append(render_row_card(row_x, row_y + index * (row_h + row_gap), row_w, row_h, label, row_id, action_rows[row_id]))
    parts.append(render_legend_card(row_x, legend_y, row_w, 120))
    parts.append(render_summary_card(row_x, summary_y, row_w, 112))
    parts.append("</g>")
    return "\n".join(parts)


def space_colors(space: TrackSpace) -> Tuple[str, str, str]:
    if space.space_type == "coin":
        return "#F6C64B", "#8A5800", "#FFF1B6"
    if space.space_type == "box":
        return "#4BC8D4", "#0E5968", "#DCF9FF"
    if space.space_type == "trap":
        trap_color = space.metadata.get("color", "yellow")
        if trap_color == "yellow":
            return "#F8A513", "#7A4B00", "#FFE0A1"
        if trap_color == "orange":
            return "#EF6A41", "#7C2816", "#FFD3C4"
        return "#DE4764", "#701226", "#FFC5D1"
    return "#F7F1E3", "#776E62", "#FFF8EF"


def render_track_network() -> str:
    main_points = reference_loop_points()
    main_path = path_d(main_points)
    return "\n".join(
        [
        '<g filter="url(#shadow)">',
        f'<path d="{main_path}" fill="none" stroke="#EED8B0" stroke-width="{ROAD_WIDTH + 24}" stroke-linecap="round" stroke-linejoin="round" opacity="0.70"/>',
        f'<path d="{main_path}" fill="none" stroke="url(#road)" stroke-width="{ROAD_WIDTH}" stroke-linecap="round" stroke-linejoin="round"/>',
        f'<path d="{main_path}" fill="none" stroke="#FFF7E1" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="24 16" opacity="0.92"/>',
        "</g>",
        ]
    )


def space_marker(space: TrackSpace, accent: str, stroke: str) -> str:
    parts = [
        f'<text x="-12" y="-18" font-family="{FONT_STACK}" font-size="{BODY_SIZE}" font-weight="600" fill="{stroke}">{space.index}</text>'
    ]
    if space.metadata.get("start") == "true":
        parts.append(f'<rect x="-14" y="-10" width="28" height="28" rx="{RADIUS}" fill="#15324D" opacity="0.96"/>')
        parts.append(f'<text x="0" y="9" text-anchor="middle" font-family="{FONT_STACK}" font-size="{BODY_SIZE}" font-weight="700" fill="#FFF6E2">GO</text>')
    elif space.metadata.get("finish_band") == "true":
        x = -14
        for index in range(4):
            fill = "#171717" if index % 2 == 0 else "#FBF2D9"
            parts.append(f'<rect x="{x + index * 7:.2f}" y="-12" width="7" height="24" fill="{fill}"/>')
    elif space.space_type == "coin":
        parts.append(f'<circle cx="0" cy="5" r="11" fill="{accent}" stroke="{stroke}" stroke-width="{BORDER}"/>')
        parts.append(f'<text x="0" y="10" text-anchor="middle" font-family="{FONT_STACK}" font-size="{BODY_SIZE}" font-weight="700" fill="{stroke}">{space.metadata.get("coins", "1")}</text>')
    elif space.space_type == "box":
        parts.append(f'<rect x="-12" y="-6" width="24" height="24" rx="{RADIUS}" fill="{accent}" stroke="{stroke}" stroke-width="{BORDER}"/>')
        parts.append(f'<text x="0" y="11" text-anchor="middle" font-family="{FONT_STACK}" font-size="{H3_SIZE}" font-weight="600" fill="{stroke}">?</text>')
    elif space.space_type == "trap":
        color_code = space.metadata.get("color", "yellow")[0].upper()
        parts.append(f'<polygon points="0,-14 14,12 -14,12" fill="{accent}" stroke="{stroke}" stroke-width="{BORDER}"/>')
        parts.append(f'<text x="0" y="8" text-anchor="middle" font-family="{FONT_STACK}" font-size="{BODY_SIZE}" font-weight="700" fill="{stroke}">{color_code}</text>')
    return "".join(parts)


def render_track_spaces(spaces: List[TrackSpace], positions: Sequence[Tuple[float, float, float]]) -> str:
    parts: List[str] = []
    for space, (cx, cy, angle) in zip(spaces, positions):
        fill, stroke, accent = space_colors(space)
        parts.append(
            f'<g transform="translate({cx:.2f} {cy:.2f}) rotate({angle:.2f})">'
            f'<rect x="{-CELL_LENGTH / 2:.2f}" y="{-CELL_WIDTH / 2:.2f}" width="{CELL_LENGTH:.2f}" height="{CELL_WIDTH:.2f}" rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="{BORDER}"/>'
            f'{space_marker(space, accent, stroke)}'
            f'</g>'
        )
    return "\n".join(parts)


def render_track_info() -> str:
    title_box_x = 440
    title_box_y = 40
    title_box_w = 336
    title_box_h = 112
    stats_box_x = 1240
    stats_box_y = 1256
    stats_box_w = 304
    stats_box_h = 168
    return "\n".join(
        [
            '<g filter="url(#shadow)">',
            section_box(title_box_x, title_box_y, title_box_w, title_box_h, "#FFF6E0", "#C89A58"),
            text_block(title_box_x + 16, title_box_y + 32, title_box_w - 32, "Winding Track", size=H2_SIZE, line_height=H2_LINE, weight="700", fill="#18324D"),
            text_block(title_box_x + 16, title_box_y + 64, title_box_w - 32, "One long winding route around the circuit.", size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#5D5348"),
            section_box(stats_box_x, stats_box_y, stats_box_w, stats_box_h, "#173552", "#F0E4C7"),
            text_block(stats_box_x + 16, stats_box_y + 24, stats_box_w - 32, "Race Goal", size=H3_SIZE, line_height=H3_LINE, weight="600", fill="#FFF6E0"),
            text_block(stats_box_x + 16, stats_box_y + 56, stats_box_w - 32, "Complete 5 laps", size=H2_SIZE, line_height=H2_LINE, weight="700", fill="#F6C64B"),
            text_block(stats_box_x + 16, stats_box_y + 96, stats_box_w - 32, "Coins, boxes, and traps trigger only when landed on.", size=BODY_SIZE, line_height=BODY_LINE, weight="400", fill="#D8E4EC"),
            "</g>",
        ]
    )


def build_svg() -> str:
    spaces = load_track_spaces()
    action_rows = load_action_rows()
    track_points = reference_loop_points()
    positions = sample_loop(track_points, len(spaces))
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
            render_background(),
            render_track_network(),
            render_track_spaces(spaces, positions),
            render_main_panel(action_rows),
            render_track_info(),
            "</svg>",
        ]
    )


def main() -> None:
    svg = build_svg()
    ASSET_PATH.write_text(svg, encoding="utf-8")
    TTS_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {ASSET_PATH}")
    print(f"Wrote {TTS_PATH}")


if __name__ == "__main__":
    main()

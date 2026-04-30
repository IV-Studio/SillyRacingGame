"""Deterministic board.svg generator — v2 take.

Reads the rules-of-record CSVs under data/ and emits a clean circuit-style
board: a rounded-rectangle track with 60 oriented tiles, the 8-row action
board nested inside the infield, and a player-facing legend and win
condition. (Shortcuts are parked for now — shortcuts.csv can repopulate
and a future revision can restore the chord arcs.)

Given the same CSV inputs, this script always produces byte-identical SVG
output (no time, no randomness, no floating-point accumulation beyond a
fixed grid snap).

Run:
    python scripts/generate_board_svg_v2.py
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSET_PATH = ROOT / "assets" / "board_v2.svg"
TTS_PATH = ROOT / "exports" / "tts" / "board_v2.svg"

# ---- Canvas & track geometry (all in SVG user units) ------------------

WIDTH = 1600
HEIGHT = 1600
CENTER = (800.0, 800.0)

# Rounded-rectangle centerline of the road.
TRACK_W = 1360.0          # full width of centerline rectangle
TRACK_H = 1180.0          # full height of centerline rectangle
TRACK_R = 250.0           # corner radius of centerline (generous, so tiles don't bunch on arcs)

ROAD_WIDTH = 120.0        # width of the painted asphalt
SHOULDER_WIDTH = 24.0     # dirt shoulder on each side of the asphalt

TILE_LONG = 62.0          # tile length along the track direction
TILE_WIDE = 94.0          # tile width across the track
RADIUS = 10               # generic corner radius for panels / tiles

TOTAL_SPACES = 60

FONT_STACK = "Trebuchet MS, Verdana, sans-serif"
H1_SIZE = 40
H2_SIZE = 24
H3_SIZE = 18
BODY_SIZE = 14
SMALL_SIZE = 13


# ---- Data loading -----------------------------------------------------


@dataclass(frozen=True)
class TrackSpace:
    index: int
    space_type: str
    metadata: Dict[str, str]


@dataclass(frozen=True)
class ActionSlot:
    row_id: str
    row_type: str
    slot_index: int
    value: str


@dataclass(frozen=True)
class Shortcut:
    label: str
    start_index: int
    reconnect_index: int


def _parse_metadata(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not raw:
        return out
    for chunk in raw.split(";"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        out[key] = value
    return out


def load_track_spaces() -> List[TrackSpace]:
    spaces: List[TrackSpace] = []
    with (DATA_DIR / "track_spaces.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            spaces.append(
                TrackSpace(
                    index=int(row["index"]),
                    space_type=row["type"],
                    metadata=_parse_metadata(row["metadata"]),
                )
            )
    spaces.sort(key=lambda s: s.index)
    if len(spaces) != TOTAL_SPACES:
        raise ValueError(
            f"Expected {TOTAL_SPACES} track spaces, found {len(spaces)}."
        )
    return spaces


def load_action_rows() -> Dict[str, List[ActionSlot]]:
    grouped: Dict[str, List[ActionSlot]] = {}
    with (DATA_DIR / "action_rows.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            slot = ActionSlot(
                row_id=row["id"],
                row_type=row["type"],
                slot_index=int(row["slot_index"]),
                value=row["value"],
            )
            grouped.setdefault(slot.row_id, []).append(slot)
    for slots in grouped.values():
        slots.sort(key=lambda s: s.slot_index)
    return grouped


def load_shortcuts() -> List[Shortcut]:
    out: List[Shortcut] = []
    with (DATA_DIR / "shortcuts.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                Shortcut(
                    label=row["label"],
                    start_index=int(row["start_index"]),
                    reconnect_index=int(row["reconnect_index"]),
                )
            )
    return out


# ---- Perimeter parameterization --------------------------------------
#
# The track centerline is a rounded rectangle. We walk it counter-
# clockwise (the racing direction) starting at the bottom-center, which
# is the position of the START/GO space (index 0 on the board).
#
# Parameterization layout, by arc length segments:
#   0: half bottom-left straight         length = (W - 2R) / 2
#   1: bottom-left corner (quarter arc)  length = pi R / 2
#   2: left straight                     length = H - 2R
#   3: top-left corner                   length = pi R / 2
#   4: top straight                      length = W - 2R
#   5: top-right corner                  length = pi R / 2
#   6: right straight                    length = H - 2R
#   7: bottom-right corner               length = pi R / 2
#   8: half bottom-right straight        length = (W - 2R) / 2
# -----------------------------------------------------------------------


def _segment_lengths() -> List[float]:
    half_h = (TRACK_W - 2 * TRACK_R) / 2.0
    full_v = TRACK_H - 2 * TRACK_R
    full_h = TRACK_W - 2 * TRACK_R
    corner = math.pi * TRACK_R / 2.0
    return [
        half_h,   # 0
        corner,   # 1
        full_v,   # 2
        corner,   # 3
        full_h,   # 4
        corner,   # 5
        full_v,   # 6
        corner,   # 7
        half_h,   # 8
    ]


def perimeter_length() -> float:
    return sum(_segment_lengths())


def point_at_arc(t: float) -> Tuple[float, float, float]:
    """Return (x, y, tangent_angle_degrees) at arc length t along the
    centerline, measured counter-clockwise from the bottom-center.
    """
    cx, cy = CENTER
    half_w = TRACK_W / 2.0
    half_h = TRACK_H / 2.0
    r = TRACK_R

    segments = _segment_lengths()
    total = sum(segments)
    # Wrap defensively.
    t = t % total

    # Segment 0: bottom strip, moving left from (cx, cy+half_h)
    #           to (cx - half_w + r, cy + half_h). Tangent = 180 deg.
    seg = segments[0]
    if t <= seg:
        x = cx - t
        y = cy + half_h
        return (x, y, 180.0)
    t -= seg

    # Segment 1: bottom-left corner. Center of arc (cx - half_w + r, cy + half_h - r).
    # Arc goes from angle 90deg (pointing +y from center) sweeping CCW to 180deg (pointing -x).
    seg = segments[1]
    if t <= seg:
        center_cx = cx - half_w + r
        center_cy = cy + half_h - r
        theta = math.pi / 2.0 + (t / seg) * (math.pi / 2.0)  # 90 -> 180 deg
        x = center_cx + r * math.cos(theta)
        y = center_cy + r * math.sin(theta)
        # Tangent = perpendicular to radius, advancing CCW around corner center
        # means tangent angle = theta + 90deg.
        tangent = math.degrees(theta + math.pi / 2.0)
        return (x, y, tangent)
    t -= seg

    # Segment 2: left straight, moving up from (cx - half_w, cy + half_h - r)
    #           to (cx - half_w, cy - half_h + r). Tangent = 270 deg (-y).
    seg = segments[2]
    if t <= seg:
        x = cx - half_w
        y = cy + half_h - r - t
        return (x, y, 270.0)
    t -= seg

    # Segment 3: top-left corner. Center (cx - half_w + r, cy - half_h + r).
    # Arc from 180deg to 270deg CCW (from -x through -y).
    seg = segments[3]
    if t <= seg:
        center_cx = cx - half_w + r
        center_cy = cy - half_h + r
        theta = math.pi + (t / seg) * (math.pi / 2.0)  # 180 -> 270 deg
        x = center_cx + r * math.cos(theta)
        y = center_cy + r * math.sin(theta)
        tangent = math.degrees(theta + math.pi / 2.0)
        return (x, y, tangent)
    t -= seg

    # Segment 4: top straight, moving right from (cx - half_w + r, cy - half_h)
    #           to (cx + half_w - r, cy - half_h). Tangent = 0 deg (+x).
    seg = segments[4]
    if t <= seg:
        x = cx - half_w + r + t
        y = cy - half_h
        return (x, y, 0.0)
    t -= seg

    # Segment 5: top-right corner. Center (cx + half_w - r, cy - half_h + r).
    # Arc from 270deg to 360deg CCW (from -y through +x).
    seg = segments[5]
    if t <= seg:
        center_cx = cx + half_w - r
        center_cy = cy - half_h + r
        theta = 3 * math.pi / 2.0 + (t / seg) * (math.pi / 2.0)
        x = center_cx + r * math.cos(theta)
        y = center_cy + r * math.sin(theta)
        tangent = math.degrees(theta + math.pi / 2.0)
        return (x, y, tangent)
    t -= seg

    # Segment 6: right straight, moving down from (cx + half_w, cy - half_h + r)
    #           to (cx + half_w, cy + half_h - r). Tangent = 90 deg (+y).
    seg = segments[6]
    if t <= seg:
        x = cx + half_w
        y = cy - half_h + r + t
        return (x, y, 90.0)
    t -= seg

    # Segment 7: bottom-right corner. Center (cx + half_w - r, cy + half_h - r).
    # Arc from 0deg to 90deg CCW (from +x through +y).
    seg = segments[7]
    if t <= seg:
        center_cx = cx + half_w - r
        center_cy = cy + half_h - r
        theta = 0.0 + (t / seg) * (math.pi / 2.0)
        x = center_cx + r * math.cos(theta)
        y = center_cy + r * math.sin(theta)
        tangent = math.degrees(theta + math.pi / 2.0)
        return (x, y, tangent)
    t -= seg

    # Segment 8: bottom-right half, moving left from (cx + half_w - r, cy + half_h)
    #           to (cx, cy + half_h). Tangent = 180 deg.
    x = cx + half_w - r - t
    y = cy + half_h
    return (x, y, 180.0)


def space_positions() -> List[Tuple[float, float, float]]:
    total = perimeter_length()
    positions: List[Tuple[float, float, float]] = []
    for i in range(TOTAL_SPACES):
        # Place each space at the center of its arc-length bucket
        # (arc-length = perimeter * (i + 0.5) / N), then shift so that
        # the GO tile (index 0) is exactly at the bottom-center marker.
        # Arc length 0 lives at bottom-center, so we offset by -0.5 tile
        # and wrap, placing half-tile-before and half-tile-after across
        # the GO line visually.
        t = total * (i / TOTAL_SPACES)
        positions.append(point_at_arc(t))
    return positions


# ---- Styling helpers --------------------------------------------------


def _space_palette(space: TrackSpace) -> Tuple[str, str, str]:
    if space.space_type == "coin":
        return "#F6C64B", "#8A5800", "#FFF1B6"
    if space.space_type == "box":
        return "#4BC8D4", "#0E5968", "#DCF9FF"
    if space.space_type == "trap":
        color = space.metadata.get("color", "yellow")
        if color == "yellow":
            return "#F8A513", "#7A4B00", "#FFE0A1"
        if color == "orange":
            return "#EF6A41", "#7C2816", "#FFD3C4"
        return "#DE4764", "#701226", "#FFC5D1"
    # plain space
    return "#F7F1E3", "#776E62", "#FFF8EF"


def _dice_slot_style(value: str) -> Tuple[str, str, str]:
    meta = _parse_metadata(value)
    color = meta.get("display_color", "yellow")
    count = meta.get("display_value", "1")
    if color == "yellow":
        return "#F7DB73", "#8C6700", count
    if color == "orange":
        return "#F4B08C", "#8A3E21", count
    return "#E88AA0", "#7A1733", count


def _slot_style(slot: ActionSlot) -> Tuple[str, str, str]:
    if slot.row_type == "dice_move":
        return _dice_slot_style(slot.value)
    if slot.row_id == "first_player":
        return "#D6E1EE", "#233E5B", "1ST"
    if slot.row_id == "gain_coins":
        return "#F7DB73", "#8C6700", f"+{int(slot.value)}"
    if slot.row_id == "gain_fuel":
        return "#D5EDCA", "#3C5D2A", f"+{int(slot.value)}"
    if slot.row_id == "ability_draft":
        return "#FCE8BD", "#8A5800", slot.value  # coin cost
    if slot.row_id == "fixed_move":
        return "#F4C2B1", "#87442E", f"+{int(slot.value)}"
    return "#EEE", "#333", slot.value


# ---- Rendering building blocks ---------------------------------------


def _text(
    x: float,
    y: float,
    content: str,
    *,
    size: int = BODY_SIZE,
    weight: str = "400",
    fill: str = "#18324D",
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="{FONT_STACK}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}">{escape(content)}</text>'
    )


def render_background() -> str:
    return f"""
<defs>
  <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#F4E8CB"/>
    <stop offset="55%" stop-color="#E3C089"/>
    <stop offset="100%" stop-color="#C98C57"/>
  </linearGradient>
  <radialGradient id="infield" cx="50%" cy="50%" r="60%">
    <stop offset="0%" stop-color="#DCEAD1"/>
    <stop offset="100%" stop-color="#9CB889"/>
  </radialGradient>
  <linearGradient id="asphalt" x1="0%" y1="0%" x2="0%" y2="100%">
    <stop offset="0%" stop-color="#5A534D"/>
    <stop offset="100%" stop-color="#3E3833"/>
  </linearGradient>
  <filter id="drop" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#5C3821" flood-opacity="0.22"/>
  </filter>
</defs>
<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
"""


def _rounded_rect_path(cx: float, cy: float, w: float, h: float, r: float) -> str:
    """SVG path string for a rounded rectangle centered at (cx, cy)."""
    x = cx - w / 2.0
    y = cy - h / 2.0
    return (
        f"M {x + r:.2f} {y:.2f} "
        f"H {x + w - r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x + w:.2f} {y + r:.2f} "
        f"V {y + h - r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x + w - r:.2f} {y + h:.2f} "
        f"H {x + r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x:.2f} {y + h - r:.2f} "
        f"V {y + r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x + r:.2f} {y:.2f} Z"
    )


def render_track() -> str:
    cx, cy = CENTER
    centerline = _rounded_rect_path(cx, cy, TRACK_W, TRACK_H, TRACK_R)
    infield_w = TRACK_W - ROAD_WIDTH - 12.0
    infield_h = TRACK_H - ROAD_WIDTH - 12.0
    infield_r = max(TRACK_R - ROAD_WIDTH / 2.0 - 6.0, 40.0)
    infield = _rounded_rect_path(cx, cy, infield_w, infield_h, infield_r)

    return "\n".join(
        [
            '<g filter="url(#drop)">',
            # Dirt shoulders (outer glow around the asphalt)
            f'<path d="{centerline}" fill="none" stroke="#EED8B0" '
            f'stroke-width="{ROAD_WIDTH + SHOULDER_WIDTH * 2:.2f}" '
            f'stroke-linejoin="round"/>',
            # Asphalt
            f'<path d="{centerline}" fill="none" stroke="url(#asphalt)" '
            f'stroke-width="{ROAD_WIDTH:.2f}" stroke-linejoin="round"/>',
            # Outer lane line
            f'<path d="{centerline}" fill="none" stroke="#F8EED0" '
            f'stroke-width="3" stroke-dasharray="22 14" opacity="0.85" '
            f'stroke-linejoin="round"/>',
            "</g>",
            # Infield grass
            f'<path d="{infield}" fill="url(#infield)" stroke="#6F8C5E" '
            f'stroke-width="3" opacity="0.95"/>',
        ]
    )


def render_shortcuts(shortcuts: List[Shortcut], positions: Sequence[Tuple[float, float, float]]) -> str:
    # Draw each shortcut as an inward-curving chord between its endpoints,
    # with a soft label in the middle. Purely visual — mechanics live in
    # the rules text when shortcuts are wired up.
    if not shortcuts:
        return ""
    parts: List[str] = ['<g opacity="0.85">']
    for sc in shortcuts:
        sx, sy, _ = positions[sc.start_index]
        ex, ey, _ = positions[sc.reconnect_index]
        mx = (sx + ex) / 2.0
        my = (sy + ey) / 2.0
        # Pull midpoint toward the infield center for a nice arc.
        cx, cy = CENTER
        pull = 0.38
        qx = mx + (cx - mx) * pull
        qy = my + (cy - my) * pull
        parts.append(
            f'<path d="M {sx:.2f} {sy:.2f} Q {qx:.2f} {qy:.2f} {ex:.2f} {ey:.2f}" '
            f'fill="none" stroke="#C98C57" stroke-width="10" '
            f'stroke-linecap="round" stroke-dasharray="4 10" opacity="0.85"/>'
        )
        # Label pill
        label = sc.label
        pill_w = 12 + 7.2 * len(label)
        parts.append(
            f'<g transform="translate({qx:.2f} {qy:.2f})">'
            f'<rect x="{-pill_w / 2:.2f}" y="-14" width="{pill_w:.2f}" height="26" '
            f'rx="13" fill="#FFF6E0" stroke="#87442E" stroke-width="2"/>'
            f'<text x="0" y="4" text-anchor="middle" font-family="{FONT_STACK}" '
            f'font-size="{BODY_SIZE}" font-weight="700" fill="#87442E">{escape(label)}</text>'
            f'</g>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def render_spaces(spaces: List[TrackSpace], positions: Sequence[Tuple[float, float, float]]) -> str:
    parts: List[str] = []
    for space, (px, py, angle) in zip(spaces, positions):
        fill, stroke, accent = _space_palette(space)
        half_l = TILE_LONG / 2.0
        half_w = TILE_WIDE / 2.0
        group = [
            f'<g transform="translate({px:.2f} {py:.2f}) rotate({angle:.2f})">'
        ]
        # Tile body
        group.append(
            f'<rect x="{-half_l:.2f}" y="{-half_w:.2f}" width="{TILE_LONG:.2f}" '
            f'height="{TILE_WIDE:.2f}" rx="{RADIUS}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"/>'
        )
        # Small index label (outside edge of tile so it sits on the shoulder)
        label_y = -half_w - 6
        group.append(
            f'<text x="0" y="{label_y:.2f}" text-anchor="middle" '
            f'font-family="{FONT_STACK}" font-size="{SMALL_SIZE}" font-weight="700" '
            f'fill="#2B2320">{space.index}</text>'
        )
        # Icon by type
        if space.metadata.get("start") == "true":
            group.append(
                f'<rect x="{-half_l + 3:.2f}" y="{-half_w + 3:.2f}" '
                f'width="{TILE_LONG - 6:.2f}" height="{TILE_WIDE - 6:.2f}" '
                f'rx="{RADIUS}" fill="#15324D"/>'
                f'<text x="0" y="10" text-anchor="middle" font-family="{FONT_STACK}" '
                f'font-size="{H2_SIZE + 4}" font-weight="800" fill="#FFF6E2">GO</text>'
            )
        elif space.metadata.get("finish_band") == "true":
            squares = 5
            sq_w = (TILE_LONG - 6) / squares
            for i in range(squares):
                color = "#18181A" if i % 2 == 0 else "#FBF2D9"
                xs = -half_l + 3 + i * sq_w
                group.append(
                    f'<rect x="{xs:.2f}" y="{-half_w + 3:.2f}" '
                    f'width="{sq_w:.2f}" height="{TILE_WIDE - 6:.2f}" fill="{color}"/>'
                )
        elif space.space_type == "coin":
            group.append(
                f'<circle cx="0" cy="0" r="22" fill="{accent}" '
                f'stroke="{stroke}" stroke-width="3"/>'
                f'<text x="0" y="9" text-anchor="middle" font-family="{FONT_STACK}" '
                f'font-size="{H2_SIZE}" font-weight="800" fill="{stroke}">'
                f'{escape(space.metadata.get("coins", "1"))}</text>'
            )
        elif space.space_type == "box":
            group.append(
                f'<rect x="-22" y="-22" width="44" height="44" rx="8" '
                f'fill="{accent}" stroke="{stroke}" stroke-width="3"/>'
                f'<text x="0" y="12" text-anchor="middle" font-family="{FONT_STACK}" '
                f'font-size="{H2_SIZE + 6}" font-weight="800" fill="{stroke}">?</text>'
            )
        elif space.space_type == "trap":
            code = space.metadata.get("color", "yellow")[0].upper()
            group.append(
                f'<polygon points="0,-24 22,18 -22,18" fill="{accent}" '
                f'stroke="{stroke}" stroke-width="3"/>'
                f'<text x="0" y="12" text-anchor="middle" font-family="{FONT_STACK}" '
                f'font-size="{H3_SIZE + 2}" font-weight="800" fill="{stroke}">{code}</text>'
            )
        group.append("</g>")
        parts.append("".join(group))
    return "\n".join(parts)


# ---- Infield action board --------------------------------------------


def render_header() -> str:
    # Centered over the top straight of the infield.
    cx = CENTER[0]
    return "\n".join(
        [
            _text(cx, 104, "RACER PROTOTYPE", size=H1_SIZE, weight="800",
                  fill="#18324D", anchor="middle"),
            _text(cx, 138, "Draft actions. Race hard. First to 5 laps wins.",
                  size=BODY_SIZE + 2, weight="400", fill="#3C5A78", anchor="middle"),
        ]
    )


def render_action_board(action_rows: Dict[str, List[ActionSlot]]) -> str:
    display_rows = [
        ("First Player", "first_player", "Claim next draft order"),
        ("Gain Coins", "gain_coins", "Immediate coin gain"),
        ("Dice Movement A", "dice_yellow_orange_burst", "Yellow / orange row"),
        ("Gain Fuel", "gain_fuel", "Immediate fuel gain (max 7)"),
        ("Fixed Movement", "fixed_move", "Move the printed amount"),
        ("Dice Movement B", "dice_orange_red_push", "Orange / red row"),
        ("Ability Draft", "ability_draft", "Pay slot cost to draft"),
        ("Dice Movement C", "dice_yellow_red_gamble", "Mostly red row"),
    ]

    # Infield action panel geometry — tucked safely inside the grass area.
    panel_w = 760.0
    panel_h = 720.0
    panel_x = CENTER[0] - panel_w / 2.0
    panel_y = CENTER[1] - panel_h / 2.0 + 20.0  # nudge down to leave room for header/legend

    row_h = 68.0
    row_gap = 8.0
    row_x = panel_x + 16.0
    row_y = panel_y + 80.0
    row_w = panel_w - 32.0
    slot_w = 52.0
    slot_h = 40.0
    slot_gap = 8.0

    parts: List[str] = [
        f'<g filter="url(#drop)">',
        f'<rect x="{panel_x:.2f}" y="{panel_y:.2f}" width="{panel_w:.2f}" '
        f'height="{panel_h:.2f}" rx="18" fill="#FFF7E1" stroke="#18324D" '
        f'stroke-width="3"/>',
        _text(panel_x + panel_w / 2.0, panel_y + 36, "Action Board", size=H2_SIZE,
              weight="800", fill="#18324D", anchor="middle"),
        _text(panel_x + panel_w / 2.0, panel_y + 62, "Resolve rows top to bottom",
              size=BODY_SIZE, weight="400", fill="#4C6A86", anchor="middle"),
    ]

    for i, (title, row_id, subtitle) in enumerate(display_rows):
        ry = row_y + i * (row_h + row_gap)
        parts.append(
            f'<rect x="{row_x:.2f}" y="{ry:.2f}" width="{row_w:.2f}" '
            f'height="{row_h:.2f}" rx="10" fill="#F4E6C4" stroke="#B58E4E" '
            f'stroke-width="2"/>'
        )
        # Row number
        parts.append(
            f'<circle cx="{row_x + 24:.2f}" cy="{ry + row_h / 2:.2f}" r="16" '
            f'fill="#18324D"/>'
            + _text(row_x + 24, ry + row_h / 2 + 5, str(i + 1),
                    size=BODY_SIZE + 1, weight="800", fill="#FFF6E2", anchor="middle")
        )
        parts.append(_text(row_x + 52, ry + 24, title, size=H3_SIZE,
                           weight="700", fill="#18324D"))
        parts.append(_text(row_x + 52, ry + 44, subtitle, size=BODY_SIZE - 1,
                           weight="400", fill="#6A7A8A"))

        # Slots, right-aligned
        slots = action_rows.get(row_id, [])
        total_slots_w = len(slots) * slot_w + max(len(slots) - 1, 0) * slot_gap
        sx = row_x + row_w - 16 - total_slots_w
        sy = ry + (row_h - slot_h) / 2
        for j, slot in enumerate(slots):
            fill, stroke, label = _slot_style(slot)
            x = sx + j * (slot_w + slot_gap)
            font_size = BODY_SIZE if len(label) > 2 else H3_SIZE
            parts.append(
                f'<rect x="{x:.2f}" y="{sy:.2f}" width="{slot_w:.2f}" '
                f'height="{slot_h:.2f}" rx="8" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="2"/>'
                + _text(x + slot_w / 2, sy + slot_h / 2 + 5, label,
                        size=font_size, weight="800", fill=stroke, anchor="middle")
            )

    parts.append("</g>")
    return "\n".join(parts)


def render_legend() -> str:
    # Legend strip just below the action board inside the infield.
    cx, cy = CENTER
    legend_y = cy + 380  # below action board
    entries = [
        ("Coin", "#F6C64B", "#8A5800", "coin"),
        ("Box", "#4BC8D4", "#0E5968", "box"),
        ("Yellow trap", "#F8A513", "#7A4B00", "trap"),
        ("Orange trap", "#EF6A41", "#7C2816", "trap"),
        ("Red trap", "#DE4764", "#701226", "trap"),
    ]
    total_w = 860.0
    item_w = total_w / len(entries)
    left_x = cx - total_w / 2.0

    parts: List[str] = [
        f'<rect x="{left_x:.2f}" y="{legend_y - 34:.2f}" width="{total_w:.2f}" '
        f'height="64" rx="12" fill="#FFF6E0" stroke="#18324D" stroke-width="2"/>',
    ]
    for i, (label, fill, stroke, kind) in enumerate(entries):
        x = left_x + i * item_w + item_w / 2.0
        # Mini icon
        if kind == "coin":
            parts.append(
                f'<circle cx="{x - 58:.2f}" cy="{legend_y:.2f}" r="11" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            )
        elif kind == "box":
            parts.append(
                f'<rect x="{x - 69:.2f}" y="{legend_y - 11:.2f}" width="22" '
                f'height="22" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            )
        else:
            parts.append(
                f'<polygon points="{x - 58},{legend_y - 12} {x - 46},{legend_y + 10} '
                f'{x - 70},{legend_y + 10}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            )
        parts.append(
            _text(x - 38, legend_y + 5, label, size=BODY_SIZE,
                  weight="700", fill="#18324D")
        )
    return "\n".join(parts)


def render_goal_badge() -> str:
    # Race goal tucked near the top of the infield.
    cx = CENTER[0]
    y = CENTER[1] - 380
    w = 340.0
    h = 62.0
    x = cx - w / 2.0
    return (
        f'<g>'
        f'<rect x="{x:.2f}" y="{y - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="14" fill="#18324D" stroke="#F6C64B" stroke-width="3"/>'
        + _text(cx, y + 6, "RACE GOAL: 5 LAPS",
                size=H2_SIZE, weight="800", fill="#F6C64B", anchor="middle")
        + '</g>'
    )


# ---- Top-level build --------------------------------------------------


def build_svg() -> str:
    spaces = load_track_spaces()
    action_rows = load_action_rows()
    positions = space_positions()

    chunks = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        render_background(),
        render_header(),
        render_track(),
        render_spaces(spaces, positions),
        render_goal_badge(),
        render_action_board(action_rows),
        render_legend(),
        "</svg>",
    ]
    return "\n".join(chunks)


def main() -> None:
    svg = build_svg()
    ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    TTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSET_PATH.write_text(svg, encoding="utf-8")
    TTS_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {ASSET_PATH}")
    print(f"Wrote {TTS_PATH}")


if __name__ == "__main__":
    main()

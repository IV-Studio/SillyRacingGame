from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports" / "tts"

CARD_SHEET_NAMES = {
    "ability_cards_front.svg",
    "ability_cards_back.svg",
    "mystery_cards_front.svg",
    "mystery_cards_back.svg",
}


def svg_dimensions(svg_path: Path) -> tuple[int, int]:
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))

    def parse_length(value: str) -> int:
        match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
        if not match:
            raise ValueError(f"Could not parse SVG length '{value}' in {svg_path}")
        return round(float(match.group(1)))

    width = root.attrib.get("width")
    height = root.attrib.get("height")
    if width and height:
        return parse_length(width), parse_length(height)

    view_box = root.attrib.get("viewBox")
    if view_box:
        _, _, view_w, view_h = view_box.split()
        return round(float(view_w)), round(float(view_h))

    raise ValueError(f"Could not determine dimensions for {svg_path}")


def export_with_qlmanage(qlmanage: str, svg_path: Path, png_path: Path) -> None:
    width, height = svg_dimensions(svg_path)
    size = max(width, height)
    magick = shutil.which("magick")
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(
            [
                qlmanage,
                "-t",
                "-s",
                str(size),
                "-o",
                temp_dir,
                str(svg_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        rendered_path = Path(temp_dir) / f"{svg_path.name}.png"
        if not rendered_path.exists():
            raise FileNotFoundError(f"Quick Look did not produce {rendered_path}")
        if magick:
            subprocess.run(
                [
                    magick,
                    str(rendered_path),
                    "-gravity",
                    "center",
                    "-crop",
                    f"{width}x{height}+0+0",
                    "+repage",
                    str(png_path),
                ],
                check=True,
            )
        else:
            shutil.copyfile(rendered_path, png_path)


def export_with_magick(magick: str, svg_path: Path, png_path: Path) -> None:
    subprocess.run(
        [
            magick,
            str(svg_path),
            "-background",
            "none",
            str(png_path),
        ],
        check=True,
    )


def main() -> None:
    magick = shutil.which("magick")
    qlmanage = shutil.which("qlmanage")
    if not qlmanage and not magick:
        raise SystemExit("Neither 'qlmanage' nor 'magick' was found.")

    svg_paths = sorted(EXPORT_DIR.glob("*.svg"))
    if not svg_paths:
        raise SystemExit(f"No SVG files found in {EXPORT_DIR}")

    for svg_path in svg_paths:
        png_path = svg_path.with_suffix(".png")
        if svg_path.name in CARD_SHEET_NAMES and magick:
            export_with_magick(magick, svg_path, png_path)
        elif qlmanage:
            export_with_qlmanage(qlmanage, svg_path, png_path)
        elif magick:
            export_with_magick(magick, svg_path, png_path)
        print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()
